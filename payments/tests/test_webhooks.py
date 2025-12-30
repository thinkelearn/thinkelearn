from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import stripe
from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page

from lms.models import (
    CourseProduct,
    CoursesIndexPage,
    EnrollmentRecord,
    ExtendedCoursePage,
)
from payments.models import Payment, WebhookEvent


class StripeWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="stripehook", email="stripehook@example.com", password="pass"
        )
        root_page = Page.add_root(title="Root")
        courses_index = CoursesIndexPage(title="Courses", slug="courses")
        root_page.add_child(instance=courses_index)

        self.course = ExtendedCoursePage(
            title="Webhook Course",
            slug="webhook-course",
            difficulty="beginner",
            is_published=True,
        )
        courses_index.add_child(instance=self.course)
        self.course.save_revision().publish()

        self.product = CourseProduct.objects.create(
            course=self.course,
            pricing_type=CourseProduct.PricingType.FIXED,
            fixed_price=Decimal("49.00"),
        )
        self.url = reverse("payments:stripe_webhook")

    def _post_webhook(self, event_data):
        mock_event = Mock()
        mock_event.to_dict.return_value = event_data
        with patch(
            "payments.views.stripe.Webhook.construct_event", return_value=mock_event
        ):
            return self.client.post(
                self.url,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="test-signature",
            )

    def test_webhook_requires_signature(self):
        response = self.client.post(
            self.url, data=b"{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_invalid_signature(self):
        with patch(
            "payments.views.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("Invalid", "sig"),
        ):
            response = self.client.post(
                self.url,
                data=b"{}",
                content_type="application/json",
                HTTP_STRIPE_SIGNATURE="invalid",
            )

        self.assertEqual(response.status_code, 400)

    def test_checkout_session_completed_activates_enrollment(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
        )
        event_data = {
            "id": "evt_success",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "amount_total": 4900,
                    "payment_intent": "pi_123",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertIsNotNone(enrollment.course_enrollment)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.stripe_event_id, "evt_success")
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_webhook_idempotency(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
        )
        event_data = {
            "id": "evt_idempotent",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_456",
                    "amount_total": 4900,
                    "payment_intent": "pi_456",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        self._post_webhook(event_data)
        response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(
            EnrollmentRecord.objects.filter(
                course_enrollment__isnull=False
            ).count(),
            1,
        )

    def test_async_payment_failed_marks_enrollment_failed(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
        )
        event_data = {
            "id": "evt_failed",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed",
                    "payment_status": "unpaid",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PAYMENT_FAILED)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failure_reason, "unpaid")

    def test_charge_refunded_revokes_access(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_refund",
        )

        event_data = {
            "id": "evt_refund",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_refund",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.REFUNDED)
        self.assertIsNone(enrollment.course_enrollment)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(len(mail.outbox), 1)

    def test_partial_refund_keeps_enrollment_active(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_partial",
        )

        event_data = {
            "id": "evt_partial",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_partial",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(payment.failure_reason, "Partial refund")

    def test_refund_outside_window_logs_warning(self):
        self.product.refund_window_days = 0
        self.product.save(update_fields=["refund_window_days"])

        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        EnrollmentRecord.objects.filter(pk=enrollment.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_old_refund",
        )

        event_data = {
            "id": "evt_old_refund",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_old_refund",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING"):
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.REFUNDED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
