from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from wagtail.models import Page

from lms.models import (
    CourseProduct,
    CoursesIndexPage,
    EnrollmentRecord,
    ExtendedCoursePage,
)
from payments.models import Payment, PaymentLedgerEntry, WebhookEvent


class PaymentModelTest(TestCase):
    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)
        self.course = ExtendedCoursePage(
            title="Test Course",
            slug="test-course",
            difficulty="beginner",
            is_published=True,
        )
        self.courses_index.add_child(instance=self.course)
        self.course.save_revision().publish()

        self.product = CourseProduct.objects.create(
            course=self.course,
            pricing_type="fixed",
            fixed_price=Decimal("99.99"),
        )
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )
        self.enrollment = EnrollmentRecord.create_for_user(
            user=self.user,
            product=self.product,
            amount=Decimal("99.99"),
        )

    def test_payment_defaults(self):
        payment = Payment.objects.create(
            enrollment_record=self.enrollment,
            amount=Decimal("99.99"),
        )

        self.assertEqual(payment.status, Payment.Status.INITIATED)
        self.assertEqual(payment.currency, "CAD")
        self.assertEqual(payment.amount_gross, Decimal("0"))
        self.assertEqual(payment.amount_refunded, Decimal("0"))
        self.assertEqual(payment.amount_net, Decimal("0"))

    def test_payment_status_updates(self):
        payment = Payment.objects.create(
            enrollment_record=self.enrollment,
            amount=Decimal("99.99"),
        )

        payment.status = Payment.Status.SUCCEEDED
        payment.save(update_fields=["status"])

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)

        payment.status = Payment.Status.FAILED
        payment.failure_reason = "Card declined"
        payment.save(update_fields=["status", "failure_reason"])

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failure_reason, "Card declined")

    def test_payment_totals_from_ledger(self):
        payment = Payment.objects.create(
            enrollment_record=self.enrollment,
            amount=Decimal("99.99"),
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.CHARGE,
            amount=Decimal("99.99"),
            currency="CAD",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.REFUND,
            amount=Decimal("20.00"),
            currency="CAD",
        )

        payment.recalculate_totals()
        payment.refresh_from_db()

        self.assertEqual(payment.amount_gross, Decimal("99.99"))
        self.assertEqual(payment.amount_refunded, Decimal("20.00"))
        self.assertEqual(payment.amount_net, Decimal("79.99"))


class WebhookEventModelTest(TestCase):
    def test_webhook_event_creation(self):
        event = WebhookEvent.objects.create(
            stripe_event_id="evt_test_123",
            event_type="checkout.session.completed",
            raw_event_data={"id": "evt_test_123"},
            success=True,
        )

        self.assertEqual(event.stripe_event_id, "evt_test_123")
        self.assertTrue(event.success)
