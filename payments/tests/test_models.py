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
            stripe_charge_id="ch_test_1",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.REFUND,
            amount=Decimal("20.00"),
            currency="CAD",
            stripe_refund_id="re_test_1",
        )

        payment.recalculate_totals()
        payment.refresh_from_db()

        self.assertEqual(payment.amount_gross, Decimal("99.99"))
        self.assertEqual(payment.amount_refunded, Decimal("20.00"))
        self.assertEqual(payment.amount_net, Decimal("79.99"))

    def test_payment_totals_with_fees(self):
        """Test that FEE entries correctly reduce amount_net."""
        payment = Payment.objects.create(
            enrollment_record=self.enrollment,
            amount=Decimal("100.00"),
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.CHARGE,
            amount=Decimal("100.00"),
            currency="CAD",
            stripe_charge_id="ch_test_2",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.FEE,
            amount=Decimal("2.90"),  # Stripe fee
            currency="CAD",
        )

        payment.recalculate_totals()
        payment.refresh_from_db()

        self.assertEqual(payment.amount_gross, Decimal("100.00"))
        self.assertEqual(payment.amount_refunded, Decimal("0"))
        # Net should be gross - fees
        self.assertEqual(payment.amount_net, Decimal("97.10"))

    def test_payment_totals_with_adjustments(self):
        """Test that ADJUSTMENT entries correctly modify amount_net."""
        payment = Payment.objects.create(
            enrollment_record=self.enrollment,
            amount=Decimal("100.00"),
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.CHARGE,
            amount=Decimal("100.00"),
            currency="CAD",
            stripe_charge_id="ch_test_3",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.ADJUSTMENT,
            amount=Decimal("5.00"),  # Credit adjustment
            currency="CAD",
        )

        payment.recalculate_totals()
        payment.refresh_from_db()

        self.assertEqual(payment.amount_gross, Decimal("100.00"))
        # Net should be gross + adjustment
        self.assertEqual(payment.amount_net, Decimal("105.00"))

    def test_payment_totals_with_all_entry_types(self):
        """Test comprehensive calculation with all entry types."""
        payment = Payment.objects.create(
            enrollment_record=self.enrollment,
            amount=Decimal("100.00"),
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.CHARGE,
            amount=Decimal("100.00"),
            currency="CAD",
            stripe_charge_id="ch_test_4",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.FEE,
            amount=Decimal("2.90"),
            currency="CAD",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.REFUND,
            amount=Decimal("20.00"),
            currency="CAD",
            stripe_refund_id="re_test_2",
        )
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.ADJUSTMENT,
            amount=Decimal("5.00"),
            currency="CAD",
        )

        payment.recalculate_totals()
        payment.refresh_from_db()

        self.assertEqual(payment.amount_gross, Decimal("100.00"))
        self.assertEqual(payment.amount_refunded, Decimal("20.00"))
        # Net = 100 (gross) - 20 (refund) - 2.90 (fee) + 5 (adjustment) = 82.10
        self.assertEqual(payment.amount_net, Decimal("82.10"))


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
