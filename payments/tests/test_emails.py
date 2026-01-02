from decimal import Decimal

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase
from django.utils import timezone
from wagtail.models import Page

from lms.models import (
    CourseProduct,
    CoursesIndexPage,
    EnrollmentRecord,
    ExtendedCoursePage,
)
from payments.emails import send_refund_confirmation


class RefundEmailTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="refunduser", email="refund@example.com", password="pass"
        )
        root_page = Page.add_root(title="Root")
        courses_index = CoursesIndexPage(title="Courses", slug="courses")
        root_page.add_child(instance=courses_index)

        self.course = ExtendedCoursePage(
            title="Refund Course",
            slug="refund-course",
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

    def test_send_refund_confirmation(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()

        send_refund_confirmation(
            enrollment,
            refund_amount=Decimal("10.00"),
            original_amount=Decimal("49.00"),
            refund_date=timezone.now(),
            is_partial=True,
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Refund processed", mail.outbox[0].subject)
        self.assertIn("Refund Course", mail.outbox[0].subject)
        self.assertIn("partial refund", mail.outbox[0].body)
