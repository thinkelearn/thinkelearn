from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from wagtail.models import Page

from lms.models import (
    CourseProduct,
    CoursesIndexPage,
    EnrollmentRecord,
    ExtendedCoursePage,
)
from payments.tasks import (
    cleanup_abandoned_enrollments,
    send_refund_confirmation_email,
)


class PaymentTaskTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="taskuser", email="task@example.com", password="pass"
        )
        root_page = Page.add_root(title="Root")
        courses_index = CoursesIndexPage(title="Courses", slug="courses")
        root_page.add_child(instance=courses_index)

        self.course = ExtendedCoursePage(
            title="Task Course",
            slug="task-course",
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

    def test_cleanup_abandoned_enrollments(self):
        old_enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        recent_enrollment = EnrollmentRecord.create_for_user(
            User.objects.create_user(username="newuser", password="pass"),
            self.product,
            amount=Decimal("49.00"),
        )

        EnrollmentRecord.objects.filter(pk=old_enrollment.pk).update(
            created_at=timezone.now() - timedelta(hours=30)
        )

        count = cleanup_abandoned_enrollments(
            cutoff=timezone.now() - timedelta(hours=24)
        )

        old_enrollment.refresh_from_db()
        recent_enrollment.refresh_from_db()

        self.assertEqual(count, 1)
        self.assertEqual(old_enrollment.status, EnrollmentRecord.Status.CANCELLED)
        self.assertEqual(
            recent_enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT
        )

    def test_cleanup_command(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        EnrollmentRecord.objects.filter(pk=enrollment.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )

        call_command("cleanup_abandoned_enrollments", hours=1)

        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.CANCELLED)

    def test_send_refund_confirmation_email(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()

        refund_date = timezone.now()
        with patch("payments.tasks.send_refund_confirmation") as mock_send:
            send_refund_confirmation_email(
                enrollment_id=enrollment.id,
                refund_amount="10.00",
                original_amount="49.00",
                refund_date=refund_date.isoformat(),
                is_partial=True,
            )

        mock_send.assert_called_once()
