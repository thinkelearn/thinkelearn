from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import stripe
from django.contrib.auth.models import User
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
from payments.models import Payment, PaymentLedgerEntry, WebhookEvent


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
                headers={"stripe-signature": "test-signature"},
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
                headers={"stripe-signature": "invalid"},
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
            EnrollmentRecord.objects.filter(course_enrollment__isnull=False).count(),
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

    @patch("payments.webhooks.send_refund_confirmation_email")
    def test_charge_refunded_revokes_access(self, mock_send_email):
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
        self.assertEqual(payment.amount_refunded, Decimal("49.00"))
        self.assertEqual(payment.amount_net, Decimal("0"))
        mock_send_email.assert_called_once()
        _, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["enrollment_id"], enrollment.id)
        self.assertEqual(kwargs["refund_amount"], Decimal("49.00"))
        self.assertEqual(kwargs["original_amount"], Decimal("49.00"))
        self.assertFalse(kwargs["is_partial"])

    @patch("payments.webhooks.send_refund_confirmation_email")
    def test_partial_refund_keeps_enrollment_active(self, mock_send_email):
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
        self.assertEqual(payment.failure_reason, "")
        mock_send_email.assert_called_once()
        _, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["enrollment_id"], enrollment.id)
        self.assertEqual(kwargs["refund_amount"], Decimal("20.00"))
        self.assertEqual(kwargs["original_amount"], Decimal("49.00"))
        self.assertTrue(kwargs["is_partial"])
        self.assertEqual(payment.amount_refunded, Decimal("20.00"))
        self.assertEqual(payment.amount_net, Decimal("29.00"))
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.REFUND
            ).count(),
            1,
        )

    @patch("payments.webhooks.send_refund_confirmation_email")
    def test_refund_outside_window_logs_warning(self, mock_send_email):
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
        mock_send_email.assert_called_once()

    def test_checkout_completed_enrollment_not_found(self):
        """Test checkout completed webhook when enrollment doesn't exist."""
        event_data = {
            "id": "evt_no_enrollment",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_nonexistent",
                    "amount_total": 4900,
                    "payment_intent": "pi_nonexistent",
                    "metadata": {"enrollment_record_id": "99999"},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("enrollment not found" in log.lower() for log in logs.output)
        )

    def test_checkout_completed_payment_not_found(self):
        """Test checkout completed webhook when payment doesn't exist."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )

        event_data = {
            "id": "evt_no_payment",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_no_payment",
                    "amount_total": 4900,
                    "payment_intent": "pi_no_payment",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()

        # Enrollment should still be activated even without payment record
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertTrue(any("payment not found" in log.lower() for log in logs.output))

    def test_checkout_completed_already_active_enrollment(self):
        """Test checkout completed webhook for already active enrollment."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()  # Already active

        Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
        )

        event_data = {
            "id": "evt_already_active",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_duplicate",
                    "amount_total": 4900,
                    "payment_intent": "pi_duplicate",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()

        # Should log warning and not process duplicate
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertTrue(
            any("not in pending/failed status" in log.lower() for log in logs.output)
        )

    def test_async_payment_failed_enrollment_not_found(self):
        """Test async payment failed webhook when enrollment doesn't exist."""
        event_data = {
            "id": "evt_failed_no_enrollment",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed_nonexistent",
                    "payment_status": "unpaid",
                    "metadata": {"enrollment_record_id": "99999"},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("enrollment not found" in log.lower() for log in logs.output)
        )

    def test_async_payment_failed_already_active(self):
        """Test async payment failed for already active enrollment."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()  # Already active

        event_data = {
            "id": "evt_failed_active",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed_active",
                    "payment_status": "unpaid",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()

        # Should not change status from ACTIVE to PAYMENT_FAILED
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertTrue(
            any("not in pending status" in log.lower() for log in logs.output)
        )

    def test_refund_payment_not_found(self):
        """Test refund webhook when payment doesn't exist."""
        event_data = {
            "id": "evt_refund_no_payment",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_nonexistent",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("payment not found" in log.lower() for log in logs.output))

    def test_refund_missing_payment_intent(self):
        """Test refund webhook missing payment_intent field."""
        event_data = {
            "id": "evt_refund_no_intent",
            "type": "charge.refunded",
            "data": {
                "object": {
                    # Missing payment_intent
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("missing payment_intent" in log.lower() for log in logs.output)
        )

    @patch("payments.webhooks.send_refund_confirmation_email")
    def test_refund_user_without_email(self, mock_send_email):
        """Test refund email handling when user has no email address."""
        user_no_email = User.objects.create_user(
            username="noemail", email="", password="pass"
        )
        enrollment = EnrollmentRecord.create_for_user(
            user_no_email, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()

        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_no_email",
        )

        event_data = {
            "id": "evt_refund_no_email",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_no_email",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        # Refund should still process successfully
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.REFUNDED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

        mock_send_email.assert_called_once()

    @patch("payments.webhooks.send_refund_confirmation_email")
    def test_refund_invalid_enrollment_status(self, mock_send_email):
        """Test refund for enrollment in invalid status (not ACTIVE/REFUNDED)."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        # Keep enrollment in PENDING_PAYMENT status

        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_invalid_status",
        )

        event_data = {
            "id": "evt_refund_invalid_status",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_invalid_status",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        # Payment should be updated, but enrollment status should not change
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT
        )  # Unchanged
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertTrue(
            any("not in active/refunded status" in log.lower() for log in logs.output)
        )
        mock_send_email.assert_not_called()

    @patch("payments.webhooks.send_refund_confirmation_email")
    def test_refund_ledger_idempotent(self, mock_send_email):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_refund_dupe",
        )
        event_data = {
            "id": "evt_refund_dupe",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_dupe",
                    "payment_intent": "pi_refund_dupe",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                    "refunds": {
                        "data": [
                            {
                                "id": "re_dupe",
                                "amount": 2000,
                                "currency": "cad",
                                "created": int(timezone.now().timestamp()),
                            }
                        ]
                    },
                }
            },
        }
        event_data_retry = {
            **event_data,
            "id": "evt_refund_dupe_retry",
        }

        self._post_webhook(event_data)
        response = self._post_webhook(event_data_retry)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.REFUND
            ).count(),
            1,
        )
        mock_send_email.assert_called()

    def test_charge_succeeded_creates_ledger_entry(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
            stripe_payment_intent_id="pi_charge",
        )
        event_data = {
            "id": "evt_charge",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_123",
                    "payment_intent": "pi_charge",
                    "amount": 4900,
                    "currency": "cad",
                    "created": int(timezone.now().timestamp()),
                }
            },
        }

        response = self._post_webhook(event_data)

        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.amount_gross, Decimal("49.00"))
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.CHARGE
            ).count(),
            1,
        )
