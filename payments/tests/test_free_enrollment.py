import json
from decimal import Decimal

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


class FreeEnrollmentFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="freeuser",
            email="freeuser@example.com",
            password="password123",
        )
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)

        self.course = ExtendedCoursePage(
            title="Free Course",
            slug="free-course",
            difficulty="beginner",
            is_published=True,
        )
        self.courses_index.add_child(instance=self.course)
        self.course.save_revision().publish()

        self.product = CourseProduct.objects.create(
            course=self.course,
            pricing_type=CourseProduct.PricingType.FREE,
            fixed_price=Decimal("0"),
        )
        self.url = reverse("payments:checkout_session")

    def test_free_enrollment_creates_course_enrollment(self):
        self.client.force_login(self.user)
        payload = {
            "product_id": self.product.id,
            "amount": "0",
            "success_url": "https://example.com/success",
            "cancel_url": "https://example.com/cancel",
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(EnrollmentRecord.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 0)

        enrollment = EnrollmentRecord.objects.first()
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)

        # Verify CourseEnrollment was created for the correct course
        course_enrollment = CourseEnrollment.objects.filter(
            user=self.user, course=self.course
        ).first()
        self.assertIsNotNone(
            course_enrollment,
            "CourseEnrollment should be created for the specific free course",
        )
        # Compare page IDs since course_enrollment.course returns base CoursePage
        self.assertEqual(course_enrollment.course.id, self.course.id)
