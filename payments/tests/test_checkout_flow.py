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
        self.client.force_login(self.user)
        mock_client = MockStripeClient()

        with patch("payments.views.get_stripe_client", return_value=mock_client):
            self.client.post(
                self.url,
                data=json.dumps(self.payload),
                content_type="application/json",
            )

        response = self.client.post(
            self.url,
            data=json.dumps(self.payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
