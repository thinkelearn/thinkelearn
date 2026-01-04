import json
from decimal import Decimal
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from wagtail.models import Page
from wagtail_lms.models import CourseEnrollment

from lms.models import (
    CourseProduct,
    CoursesIndexPage,
    EnrollmentRecord,
    ExtendedCoursePage,
)
from payments.models import Payment
from payments.stripe_client import MockStripeClient, StripeClientError


class CheckoutSessionFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="stripeuser",
            email="stripeuser@example.com",
            password="password123",
        )
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)

        self.course = ExtendedCoursePage(
            title="Stripe Course",
            slug="stripe-course",
            difficulty="beginner",
            is_published=True,
        )
        self.courses_index.add_child(instance=self.course)
        self.course.save_revision().publish()

        self.product = CourseProduct.objects.create(
            course=self.course,
            pricing_type=CourseProduct.PricingType.FIXED,
            fixed_price=Decimal("49.00"),
        )
        self.url = reverse("payments:checkout_session")
        self.payload = {
            "product_id": self.product.id,
            "amount": "49.00",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }

    def test_create_checkout_session_success(self):
        self.client.force_login(self.user)
        mock_client = MockStripeClient(
            session_id="cs_test_123",
            session_url="https://stripe.test/session",
        )

        with patch("payments.views.get_stripe_client", return_value=mock_client):
            response = self.client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(EnrollmentRecord.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        enrollment = EnrollmentRecord.objects.first()
        payment = Payment.objects.first()

        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT)
        self.assertEqual(enrollment.stripe_checkout_session_id, "cs_test_123")
        self.assertEqual(payment.status, Payment.Status.PROCESSING)
        self.assertEqual(payment.stripe_checkout_session_id, "cs_test_123")

    def test_checkout_session_requires_authentication(self):
        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 401)

    def test_checkout_session_invalid_amount(self):
        self.client.force_login(self.user)
        self.product.pricing_type = CourseProduct.PricingType.PWYC
        self.product.min_price = Decimal("10.00")
        self.product.max_price = Decimal("100.00")
        self.product.suggested_price = Decimal("25.00")
        self.product.save()

        payload = {
            **self.payload,
            "amount": "5.00",
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(EnrollmentRecord.objects.count(), 0)

    def test_checkout_session_ineligible_user(self):
        self.client.force_login(self.user)
        self.course.enrollment_limit = 1
        self.course.save()

        other_user = User.objects.create_user(
            username="alreadyenrolled", password="password123"
        )
        CourseEnrollment.objects.create(user=other_user, course=self.course)

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(EnrollmentRecord.objects.count(), 0)

    def test_checkout_session_stripe_failure_rolls_back(self):
        self.client.force_login(self.user)
        mock_client = Mock()
        mock_client.create_checkout_session.side_effect = StripeClientError(
            "Stripe API error"
        )

        with patch("payments.views.get_stripe_client", return_value=mock_client):
            response = self.client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(EnrollmentRecord.objects.count(), 0)
        self.assertEqual(Payment.objects.count(), 0)

    def test_checkout_session_duplicate_enrollment(self):
        """Test that duplicate enrollment attempts for ACTIVE enrollments return 409"""
        self.client.force_login(self.user)
        # Create an ACTIVE enrollment (free course)
        self.product.pricing_type = CourseProduct.PricingType.FREE
        self.product.save()

        # Free courses don't need amount in payload
        free_payload = {
            "product_id": self.product.id,
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }

        # First request creates ACTIVE enrollment
        self.client.post(
            self.url,
            data=json.dumps(free_payload),
            content_type="application/json",
        )

        # Second request should fail with 409 for ACTIVE enrollment
        response = self.client.post(
            self.url,
            data=json.dumps(free_payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 409)

    def test_checkout_session_resume_pending_enrollment(self):
        """Test that users can resume PENDING_PAYMENT enrollments with a new checkout session"""
        self.client.force_login(self.user)
        mock_client = MockStripeClient(
            session_id="cs_test_first",
            session_url="https://stripe.test/session/first",
        )

        # First request creates PENDING_PAYMENT enrollment
        with patch("payments.views.get_stripe_client", return_value=mock_client):
            response1 = self.client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
            )

        self.assertEqual(response1.status_code, 201)
        self.assertEqual(EnrollmentRecord.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        first_enrollment = EnrollmentRecord.objects.first()
        self.assertEqual(first_enrollment.stripe_checkout_session_id, "cs_test_first")

        # User clicks back button and tries again - should create NEW session for SAME enrollment
        mock_client2 = MockStripeClient(
            session_id="cs_test_second",
            session_url="https://stripe.test/session/second",
        )

        with patch("payments.views.get_stripe_client", return_value=mock_client2):
            response2 = self.client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
            )

        # Should succeed with 201, not fail with 409
        self.assertEqual(response2.status_code, 201)
        # Still only one enrollment record
        self.assertEqual(EnrollmentRecord.objects.count(), 1)
        # But now two Payment records (one for each attempt)
        self.assertEqual(Payment.objects.count(), 2)

        # Enrollment should have the NEW session ID
        first_enrollment.refresh_from_db()
        self.assertEqual(first_enrollment.stripe_checkout_session_id, "cs_test_second")

        # Response should contain the new session URL
        response_data = response2.json()
        self.assertEqual(response_data["session_id"], "cs_test_second")
        self.assertEqual(
            response_data["session_url"], "https://stripe.test/session/second"
        )

    def test_checkout_session_change_amount_cancels_old_enrollment(self):
        """Test that changing the amount cancels old enrollment and creates new one"""
        self.client.force_login(self.user)
        # Use PWYC pricing to allow amount changes
        self.product.pricing_type = CourseProduct.PricingType.PWYC
        self.product.min_price = Decimal("10.00")
        self.product.max_price = Decimal("100.00")
        self.product.suggested_price = Decimal("25.00")
        self.product.save()

        # First request with $20
        mock_client1 = MockStripeClient(
            session_id="cs_test_20",
            session_url="https://stripe.test/session/20",
        )

        payload_20 = {
            **self.payload,
            "amount": "20.00",
        }

        with patch("payments.views.get_stripe_client", return_value=mock_client1):
            response1 = self.client.post(
                self.url,
                data=json.dumps(payload_20),
                content_type="application/json",
            )

        self.assertEqual(response1.status_code, 201)
        self.assertEqual(EnrollmentRecord.objects.count(), 1)

        first_enrollment = EnrollmentRecord.objects.first()
        self.assertEqual(first_enrollment.amount_paid, Decimal("20.00"))
        self.assertEqual(
            first_enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT
        )

        # User changes mind and wants to pay $30 instead
        mock_client2 = MockStripeClient(
            session_id="cs_test_30",
            session_url="https://stripe.test/session/30",
        )

        payload_30 = {
            **self.payload,
            "amount": "30.00",
        }

        with patch("payments.views.get_stripe_client", return_value=mock_client2):
            response2 = self.client.post(
                self.url,
                data=json.dumps(payload_30),
                content_type="application/json",
            )

        # Should succeed with 201
        self.assertEqual(response2.status_code, 201)
        # Now should have 2 enrollment records (old cancelled, new pending)
        self.assertEqual(EnrollmentRecord.objects.count(), 2)

        # Old enrollment should be cancelled
        first_enrollment.refresh_from_db()
        self.assertEqual(first_enrollment.status, EnrollmentRecord.Status.CANCELLED)
        self.assertEqual(first_enrollment.amount_paid, Decimal("20.00"))
        self.assertTrue(first_enrollment.idempotency_key.startswith("cancelled_"))
        self.assertLessEqual(len(first_enrollment.idempotency_key), 255)

        # New enrollment should be pending with new amount
        new_enrollment = EnrollmentRecord.objects.filter(
            status=EnrollmentRecord.Status.PENDING_PAYMENT
        ).first()
        self.assertIsNotNone(new_enrollment)
        self.assertNotEqual(new_enrollment.id, first_enrollment.id)
        self.assertEqual(new_enrollment.amount_paid, Decimal("30.00"))
        self.assertEqual(new_enrollment.stripe_checkout_session_id, "cs_test_30")

        # Response should contain the new session details
        response_data = response2.json()
        self.assertEqual(response_data["session_id"], "cs_test_30")
        self.assertEqual(response_data["enrollment_id"], new_enrollment.id)
