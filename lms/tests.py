from decimal import Decimal
from unittest.mock import Mock

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import RequestFactory, TestCase
from django.utils import timezone
from wagtail.models import Page
from wagtail_lms.models import CourseEnrollment

from lms.models import (
    CourseCategory,
    CourseInstructor,
    CourseProduct,
    CourseReview,
    CoursesIndexPage,
    CourseTag,
    EnrollmentRecord,
    ExtendedCoursePage,
    LearnerDashboardPage,
)

# BUSINESS LOGIC TESTS ONLY
# Tests focus on custom methods, business validation, and LMS-specific functionality


class CourseCategoryTest(TestCase):
    """Test CourseCategory snippet model"""

    def test_category_str_representation(self):
        """Test string representation"""
        category = CourseCategory.objects.create(
            name="Web Development", slug="web-dev", icon="fa-code"
        )
        self.assertEqual(str(category), "Web Development")

    def test_category_ordering(self):
        """Test categories are ordered by name"""
        CourseCategory.objects.create(name="Zulu", slug="zulu")
        CourseCategory.objects.create(name="Alpha", slug="alpha")
        CourseCategory.objects.create(name="Mike", slug="mike")

        categories = list(CourseCategory.objects.all())
        self.assertEqual(categories[0].name, "Alpha")
        self.assertEqual(categories[1].name, "Mike")
        self.assertEqual(categories[2].name, "Zulu")


class CourseTagTest(TestCase):
    """Test CourseTag snippet model"""

    def test_tag_str_representation(self):
        """Test string representation"""
        tag = CourseTag.objects.create(name="Python", slug="python")
        self.assertEqual(str(tag), "Python")

    def test_tag_ordering(self):
        """Test tags are ordered by name"""
        CourseTag.objects.create(name="React", slug="react")
        CourseTag.objects.create(name="Django", slug="django")
        CourseTag.objects.create(name="Python", slug="python")

        tags = list(CourseTag.objects.all())
        self.assertEqual(tags[0].name, "Django")
        self.assertEqual(tags[1].name, "Python")
        self.assertEqual(tags[2].name, "React")


class CoursesIndexPageTest(TestCase):
    """Test CoursesIndexPage functionality"""

    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(
            title="Courses", slug="courses", intro="<p>Browse our courses</p>"
        )
        self.root_page.add_child(instance=self.courses_index)
        self.courses_index.save_revision().publish()

        # Create test categories and tags
        self.category1 = CourseCategory.objects.create(
            name="Programming", slug="programming"
        )
        self.category2 = CourseCategory.objects.create(name="Design", slug="design")
        self.tag1 = CourseTag.objects.create(name="Python", slug="python")
        self.tag2 = CourseTag.objects.create(name="JavaScript", slug="javascript")

        # Create test courses
        self.course1 = ExtendedCoursePage(
            title="Python Basics",
            slug="python-basics",
            difficulty="beginner",
            is_published=True,
        )
        self.courses_index.add_child(instance=self.course1)
        self.course1.categories.add(self.category1)
        self.course1.tags.add(self.tag1)
        self.course1.save_revision().publish()

        self.course2 = ExtendedCoursePage(
            title="JavaScript Advanced",
            slug="javascript-advanced",
            difficulty="advanced",
            is_published=True,
        )
        self.courses_index.add_child(instance=self.course2)
        self.course2.categories.add(self.category1)
        self.course2.tags.add(self.tag2)
        self.course2.save_revision().publish()

        self.factory = RequestFactory()

    def test_get_context_all_courses(self):
        """Test context returns all courses when no filters applied"""
        request = self.factory.get("/courses/")
        context = self.courses_index.get_context(request)

        self.assertEqual(context["courses"].count(), 2)
        self.assertIn("categories", context)
        self.assertIn("tags", context)

    def test_get_context_filter_by_category(self):
        """Test filtering courses by category"""
        request = self.factory.get("/courses/?category=programming")
        context = self.courses_index.get_context(request)

        # Both courses are in programming category
        courses_list = list(context["courses"])
        self.assertGreater(len(courses_list), 0)
        self.assertEqual(context["selected_category"], "programming")

    def test_get_context_filter_by_tag(self):
        """Test filtering courses by tag"""
        request = self.factory.get("/courses/?tag=python")
        context = self.courses_index.get_context(request)

        # At least one course has python tag
        courses_list = list(context["courses"])
        self.assertGreater(len(courses_list), 0)
        self.assertEqual(context["selected_tag"], "python")

    def test_get_context_search(self):
        """Test search functionality"""
        request = self.factory.get("/courses/?q=Python")
        context = self.courses_index.get_context(request)

        self.assertEqual(context["search_query"], "Python")


class ExtendedCoursePageTest(TestCase):
    """Test ExtendedCoursePage business logic"""

    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)

        self.course = ExtendedCoursePage(
            title="Test Course",
            slug="test-course",
            difficulty="beginner",
            duration_hours=10,
            is_published=True,
        )
        self.courses_index.add_child(instance=self.course)
        self.course.save_revision().publish()

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.factory = RequestFactory()

    def test_get_average_rating_with_no_reviews(self):
        """Test average rating calculation when no reviews exist"""
        avg_rating = self.course.get_average_rating()
        self.assertIsNone(avg_rating)

    def test_get_average_rating_with_reviews(self):
        """Test average rating calculation with multiple reviews"""
        user1 = User.objects.create_user(username="user1", password="pass")
        user2 = User.objects.create_user(username="user2", password="pass")
        user3 = User.objects.create_user(username="user3", password="pass")

        CourseReview.objects.create(course=self.course, user=user1, rating=5)
        CourseReview.objects.create(course=self.course, user=user2, rating=4)
        CourseReview.objects.create(course=self.course, user=user3, rating=3)

        avg_rating = self.course.get_average_rating()
        self.assertEqual(avg_rating, 4.0)

    def test_get_enrollment_count(self):
        """Test enrollment count calculation"""
        # Initially zero
        self.assertEqual(self.course.get_enrollment_count(), 0)

        # Create enrollments
        user1 = User.objects.create_user(username="user1", password="pass")
        user2 = User.objects.create_user(username="user2", password="pass")

        CourseEnrollment.objects.create(user=user1, course=self.course)
        CourseEnrollment.objects.create(user=user2, course=self.course)

        self.assertEqual(self.course.get_enrollment_count(), 2)

    def test_can_user_enroll_already_enrolled(self):
        """Test cannot enroll if already enrolled"""
        CourseEnrollment.objects.create(user=self.user, course=self.course)

        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

    def test_can_user_enroll_enrollment_limit_reached(self):
        """Test cannot enroll when enrollment limit is reached"""
        self.course.enrollment_limit = 2
        self.course.save()

        user1 = User.objects.create_user(username="user1", password="pass")
        user2 = User.objects.create_user(username="user2", password="pass")

        CourseEnrollment.objects.create(user=user1, course=self.course)
        CourseEnrollment.objects.create(user=user2, course=self.course)

        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

    def test_can_user_enroll_with_unlimited_enrollment(self):
        """Test can enroll when no enrollment limit is set"""
        # Create many enrollments
        for i in range(10):
            user = User.objects.create_user(username=f"user{i}", password="pass")
            CourseEnrollment.objects.create(user=user, course=self.course)

        # Should still be able to enroll
        can_enroll = self.course.can_user_enroll(self.user)
        self.assertTrue(can_enroll)

    def test_can_user_enroll_prerequisites_not_met(self):
        """Test cannot enroll when prerequisites are not completed"""
        prereq_course = ExtendedCoursePage(
            title="Prerequisite Course", slug="prereq-course"
        )
        self.courses_index.add_child(instance=prereq_course)

        self.course.prerequisite_courses.add(prereq_course)

        # User not enrolled in prerequisite
        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

    def test_can_user_enroll_prerequisites_incomplete(self):
        """Test cannot enroll when prerequisites are enrolled but not completed"""
        prereq_course = ExtendedCoursePage(
            title="Prerequisite Course", slug="prereq-course"
        )
        self.courses_index.add_child(instance=prereq_course)

        self.course.prerequisite_courses.add(prereq_course)

        # User enrolled but not completed prerequisite
        CourseEnrollment.objects.create(
            user=self.user, course=prereq_course, completed_at=None
        )

        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

    def test_can_user_enroll_prerequisites_completed(self):
        """Test can enroll when prerequisites are completed"""

        prereq_course = ExtendedCoursePage(
            title="Prerequisite Course", slug="prereq-course"
        )
        self.courses_index.add_child(instance=prereq_course)

        self.course.prerequisite_courses.add(prereq_course)

        # User completed prerequisite
        CourseEnrollment.objects.create(
            user=self.user, course=prereq_course, completed_at=timezone.now()
        )

        can_enroll = self.course.can_user_enroll(self.user)
        self.assertTrue(can_enroll)

    def test_can_user_enroll_multiple_prerequisites(self):
        """Test prerequisites validation with multiple required courses"""

        prereq1 = ExtendedCoursePage(title="Prereq 1", slug="prereq-1")
        prereq2 = ExtendedCoursePage(title="Prereq 2", slug="prereq-2")
        self.courses_index.add_child(instance=prereq1)
        self.courses_index.add_child(instance=prereq2)

        self.course.prerequisite_courses.add(prereq1, prereq2)

        # Only completed first prerequisite
        CourseEnrollment.objects.create(
            user=self.user, course=prereq1, completed_at=timezone.now()
        )

        # Should not be able to enroll
        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

        # Complete second prerequisite
        CourseEnrollment.objects.create(
            user=self.user, course=prereq2, completed_at=timezone.now()
        )

        # Now should be able to enroll
        can_enroll = self.course.can_user_enroll(self.user)
        self.assertTrue(can_enroll)

    def test_get_completion_rate_no_enrollments(self):
        """Test completion rate when no enrollments exist"""
        completion_rate = self.course.get_completion_rate()
        self.assertEqual(completion_rate, 0)

    def test_get_completion_rate_with_enrollments(self):
        """Test completion rate calculation"""

        user1 = User.objects.create_user(username="user1", password="pass")
        user2 = User.objects.create_user(username="user2", password="pass")
        user3 = User.objects.create_user(username="user3", password="pass")
        user4 = User.objects.create_user(username="user4", password="pass")

        # 2 completed, 2 in progress
        CourseEnrollment.objects.create(
            user=user1, course=self.course, completed_at=timezone.now()
        )
        CourseEnrollment.objects.create(
            user=user2, course=self.course, completed_at=timezone.now()
        )
        CourseEnrollment.objects.create(user=user3, course=self.course)
        CourseEnrollment.objects.create(user=user4, course=self.course)

        completion_rate = self.course.get_completion_rate()
        self.assertEqual(completion_rate, 50.0)

    def test_get_context_authenticated_user(self):
        """Test context for authenticated user"""
        request = self.factory.get(f"/courses/{self.course.slug}/")
        request.user = self.user

        context = self.course.get_context(request)

        self.assertIn("can_enroll", context)
        self.assertIn("user_review", context)
        self.assertIn("average_rating", context)
        self.assertIn("total_reviews", context)
        self.assertIn("enrollment_count", context)

    def test_get_context_anonymous_user(self):
        """Test context for anonymous user"""
        request = self.factory.get(f"/courses/{self.course.slug}/")
        request.user = Mock(is_authenticated=False)

        context = self.course.get_context(request)

        self.assertFalse(context["can_enroll"])
        self.assertIsNone(context["user_review"])

    def test_get_context_related_courses(self):
        """Test related courses in context"""
        related1 = ExtendedCoursePage(title="Related 1", slug="related-1")
        related2 = ExtendedCoursePage(title="Related 2", slug="related-2")
        self.courses_index.add_child(instance=related1)
        self.courses_index.add_child(instance=related2)
        related1.save_revision().publish()
        related2.save_revision().publish()

        self.course.related_courses.add(related1, related2)

        request = self.factory.get(f"/courses/{self.course.slug}/")
        request.user = self.user

        context = self.course.get_context(request)

        self.assertEqual(len(context["related_courses"]), 2)


class CourseInstructorTest(TestCase):
    """Test CourseInstructor model"""

    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)

        self.course = ExtendedCoursePage(title="Test Course", slug="test-course")
        self.courses_index.add_child(instance=self.course)

    def test_instructor_str_representation(self):
        """Test string representation"""
        instructor = CourseInstructor.objects.create(
            course=self.course,
            name="Dr. Jane Smith",
            title="Professor of Computer Science",
        )
        self.assertEqual(str(instructor), "Dr. Jane Smith")


class CourseReviewTest(TestCase):
    """Test CourseReview model and validation"""

    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)

        self.course = ExtendedCoursePage(title="Test Course", slug="test-course")
        self.courses_index.add_child(instance=self.course)

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_review_str_representation(self):
        """Test string representation"""
        review = CourseReview.objects.create(
            course=self.course, user=self.user, rating=5
        )
        expected = f"{self.user.username} - {self.course.title} (5/5)"
        self.assertEqual(str(review), expected)

    def test_review_default_approval(self):
        """Test reviews require manual approval by default"""
        review = CourseReview.objects.create(
            course=self.course, user=self.user, rating=4
        )
        self.assertFalse(review.is_approved)  # Changed: now requires manual approval

    def test_review_unique_per_user_course(self):
        """Test user can only review a course once"""
        from django.db import IntegrityError

        CourseReview.objects.create(course=self.course, user=self.user, rating=5)

        with self.assertRaises(IntegrityError):
            CourseReview.objects.create(course=self.course, user=self.user, rating=3)

    def test_review_ordering(self):
        """Test reviews are ordered by creation date (newest first)"""
        user1 = User.objects.create_user(username="user1", password="pass")
        user2 = User.objects.create_user(username="user2", password="pass")

        review1 = CourseReview.objects.create(course=self.course, user=user1, rating=5)
        review2 = CourseReview.objects.create(course=self.course, user=user2, rating=4)

        reviews = list(CourseReview.objects.all())
        # Newest first
        self.assertEqual(reviews[0].id, review2.id)
        self.assertEqual(reviews[1].id, review1.id)


class LearnerDashboardPageTest(TestCase):
    """Test LearnerDashboardPage functionality"""

    def setUp(self):
        self.root_page = Page.add_root(title="Root")
        self.dashboard = LearnerDashboardPage(
            title="Dashboard", slug="dashboard", intro="<p>Your learning dashboard</p>"
        )
        self.root_page.add_child(instance=self.dashboard)

        self.courses_index = CoursesIndexPage(title="Courses", slug="courses")
        self.root_page.add_child(instance=self.courses_index)

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

        self.factory = RequestFactory()

    def test_get_context_unauthenticated_user(self):
        """Test dashboard context for unauthenticated user"""
        request = self.factory.get("/dashboard/")
        request.user = Mock(is_authenticated=False)

        context = self.dashboard.get_context(request)

        # Should not have enrollment data
        self.assertNotIn("active_enrollments", context)
        self.assertNotIn("completed_enrollments", context)

    def test_get_context_no_enrollments(self):
        """Test dashboard context with no enrollments"""
        request = self.factory.get("/dashboard/")
        request.user = self.user

        context = self.dashboard.get_context(request)

        self.assertEqual(context["total_courses"], 0)
        self.assertEqual(context["completed_courses"], 0)
        self.assertEqual(context["completion_percentage"], 0)

    def test_get_context_with_enrollments(self):
        """Test dashboard context with active and completed enrollments"""

        course1 = ExtendedCoursePage(title="Course 1", slug="course-1")
        course2 = ExtendedCoursePage(title="Course 2", slug="course-2")
        course3 = ExtendedCoursePage(title="Course 3", slug="course-3")
        self.courses_index.add_child(instance=course1)
        self.courses_index.add_child(instance=course2)
        self.courses_index.add_child(instance=course3)

        # 2 active, 1 completed
        CourseEnrollment.objects.create(user=self.user, course=course1)
        CourseEnrollment.objects.create(user=self.user, course=course2)
        CourseEnrollment.objects.create(
            user=self.user, course=course3, completed_at=timezone.now()
        )

        request = self.factory.get("/dashboard/")
        request.user = self.user

        context = self.dashboard.get_context(request)

        self.assertEqual(context["total_courses"], 3)
        self.assertEqual(context["completed_courses"], 1)
        self.assertEqual(context["active_enrollments"].count(), 2)
        self.assertEqual(context["completed_enrollments"].count(), 1)
        self.assertAlmostEqual(context["completion_percentage"], 33.3, places=1)

    def test_get_context_completion_percentage_calculation(self):
        """Test completion percentage is calculated correctly"""

        # Create 5 courses
        for i in range(5):
            course = ExtendedCoursePage(title=f"Course {i}", slug=f"course-{i}")
            self.courses_index.add_child(instance=course)

            # Complete 3 out of 5
            if i < 3:
                CourseEnrollment.objects.create(
                    user=self.user, course=course, completed_at=timezone.now()
                )
            else:
                CourseEnrollment.objects.create(user=self.user, course=course)

        request = self.factory.get("/dashboard/")
        request.user = self.user

        context = self.dashboard.get_context(request)

        self.assertEqual(context["total_courses"], 5)
        self.assertEqual(context["completed_courses"], 3)
        self.assertEqual(context["completion_percentage"], 60.0)


class CourseProductTest(TestCase):
    """Test CourseProduct model and business logic"""

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

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_product_str_representation(self):
        """Test string representation"""
        product = CourseProduct.objects.create(
            course=self.course, base_price=Decimal("99.99")
        )
        self.assertEqual(str(product), "Test Course Product")

    def test_product_repr_representation(self):
        """Test __repr__ for debugging"""
        product = CourseProduct.objects.create(
            course=self.course, base_price=Decimal("49.99"), is_active=True
        )
        repr_str = repr(product)
        self.assertIn("CourseProduct", repr_str)
        self.assertIn(f"id={product.id!r}", repr_str)
        self.assertIn("base_price=Decimal('49.99')", repr_str)
        self.assertIn("is_active=True", repr_str)

    def test_product_default_values(self):
        """Test default values for product"""
        product = CourseProduct.objects.create(course=self.course)
        self.assertEqual(product.base_price, Decimal("0"))
        self.assertTrue(product.is_active)

    def test_enroll_user_free_course(self):
        """Test enrolling user in free course"""
        product = CourseProduct.objects.create(
            course=self.course, base_price=Decimal("0"), is_active=True
        )

        enrollment = product.enroll_user(self.user)

        self.assertEqual(enrollment.user, self.user)
        self.assertEqual(enrollment.product, product)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertIsNotNone(enrollment.course_enrollment)

    def test_enroll_user_paid_course(self):
        """Test enrolling user in paid course"""
        product = CourseProduct.objects.create(
            course=self.course, base_price=Decimal("99.99"), is_active=True
        )

        enrollment = product.enroll_user(self.user)

        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT)
        self.assertIsNone(enrollment.course_enrollment)

    def test_enroll_user_inactive_product(self):
        """Test cannot enroll in inactive product"""
        product = CourseProduct.objects.create(
            course=self.course, base_price=Decimal("0"), is_active=False
        )

        with self.assertRaises(ValidationError) as cm:
            product.enroll_user(self.user)

        self.assertIn("not currently available", str(cm.exception))

    def test_enroll_user_custom_amount(self):
        """Test enrolling with custom pay-what-you-can amount"""
        product = CourseProduct.objects.create(
            course=self.course, base_price=Decimal("99.99"), is_active=True
        )

        enrollment = product.enroll_user(self.user, amount=Decimal("25.00"))

        self.assertEqual(enrollment.pay_what_you_can_amount, Decimal("25.00"))
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT)


class EnrollmentRecordTest(TestCase):
    """Test EnrollmentRecord model and business logic"""

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
            course=self.course, base_price=Decimal("99.99"), is_active=True
        )

        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_enrollment_str_representation(self):
        """Test string representation"""
        enrollment = EnrollmentRecord.objects.create(
            user=self.user,
            product=self.product,
            status=EnrollmentRecord.Status.ACTIVE,
            pay_what_you_can_amount=Decimal("99.99"),
        )
        expected = f"{self.user.username} - {self.course.title} (active)"
        self.assertEqual(str(enrollment), expected)

    def test_enrollment_repr_representation(self):
        """Test __repr__ for debugging"""
        enrollment = EnrollmentRecord.objects.create(
            user=self.user,
            product=self.product,
            status=EnrollmentRecord.Status.PENDING_PAYMENT,
            pay_what_you_can_amount=Decimal("50.00"),
        )
        repr_str = repr(enrollment)
        self.assertIn("EnrollmentRecord", repr_str)
        self.assertIn(f"id={enrollment.id!r}", repr_str)
        self.assertIn(f"user_id={self.user.id!r}", repr_str)
        self.assertIn(f"product_id={self.product.id!r}", repr_str)

    def test_course_property(self):
        """Test course property convenience accessor"""
        enrollment = EnrollmentRecord.objects.create(
            user=self.user, product=self.product
        )
        self.assertEqual(enrollment.course, self.course)

    def test_create_for_user_free_enrollment(self):
        """Test creating free enrollment (amount=0)"""
        enrollment = EnrollmentRecord.create_for_user(
            user=self.user, product=self.product, pay_what_you_can_amount=Decimal("0")
        )

        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertEqual(enrollment.pay_what_you_can_amount, Decimal("0"))
        self.assertIsNotNone(enrollment.course_enrollment)
        self.assertEqual(enrollment.course_enrollment.user, self.user)
        self.assertEqual(enrollment.course_enrollment.course, self.course)

    def test_create_for_user_paid_enrollment(self):
        """Test creating paid enrollment (amount>0)"""
        enrollment = EnrollmentRecord.create_for_user(
            user=self.user,
            product=self.product,
            pay_what_you_can_amount=Decimal("49.99"),
        )

        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT)
        self.assertEqual(enrollment.pay_what_you_can_amount, Decimal("49.99"))
        self.assertIsNone(enrollment.course_enrollment)

    def test_create_for_user_default_amount(self):
        """Test enrollment uses base_price when amount not specified"""
        enrollment = EnrollmentRecord.create_for_user(
            user=self.user, product=self.product
        )

        self.assertEqual(enrollment.pay_what_you_can_amount, self.product.base_price)

    def test_create_for_user_negative_amount(self):
        """Test cannot create enrollment with negative amount"""
        with self.assertRaises(ValidationError) as cm:
            EnrollmentRecord.create_for_user(
                user=self.user,
                product=self.product,
                pay_what_you_can_amount=Decimal("-10.00"),
            )

        self.assertIn("cannot be negative", str(cm.exception))

    def test_create_for_user_duplicate_prevention(self):
        """Test cannot create duplicate enrollment for same user/product"""
        # Create first enrollment
        EnrollmentRecord.create_for_user(
            user=self.user, product=self.product, pay_what_you_can_amount=Decimal("0")
        )

        # Try to create second enrollment
        with self.assertRaises(ValidationError) as cm:
            EnrollmentRecord.create_for_user(
                user=self.user,
                product=self.product,
                pay_what_you_can_amount=Decimal("0"),
            )

        self.assertIn("already have an enrollment", str(cm.exception))

    def test_create_for_user_cancelled_refunded_prevention(self):
        """Test cannot re-enroll if cancelled/refunded enrollment exists"""
        # Create cancelled enrollment
        EnrollmentRecord.objects.create(
            user=self.user,
            product=self.product,
            status=EnrollmentRecord.Status.CANCELLED_REFUNDED,
        )

        # Try to create new enrollment
        with self.assertRaises(ValidationError) as cm:
            EnrollmentRecord.create_for_user(
                user=self.user,
                product=self.product,
                pay_what_you_can_amount=Decimal("0"),
            )

        self.assertIn("cancelled/refunded enrollment", str(cm.exception))

    def test_create_for_user_validates_prerequisites(self):
        """Test enrollment validates prerequisites"""
        # Create prerequisite course
        prereq = ExtendedCoursePage(title="Prereq", slug="prereq")
        self.courses_index.add_child(instance=prereq)
        prereq.save_revision().publish()

        self.course.prerequisite_courses.add(prereq)

        # Try to enroll without completing prerequisite
        with self.assertRaises(ValidationError) as cm:
            EnrollmentRecord.create_for_user(
                user=self.user,
                product=self.product,
                pay_what_you_can_amount=Decimal("0"),
            )

        self.assertIn("do not meet the requirements", str(cm.exception))

    def test_create_for_user_validates_enrollment_limit(self):
        """Test enrollment validates enrollment limit"""
        self.course.enrollment_limit = 1
        self.course.save()

        # Create one enrollment
        other_user = User.objects.create_user(username="other", password="pass")
        CourseEnrollment.objects.create(user=other_user, course=self.course)

        # Try to enroll when limit reached
        with self.assertRaises(ValidationError) as cm:
            EnrollmentRecord.create_for_user(
                user=self.user,
                product=self.product,
                pay_what_you_can_amount=Decimal("0"),
            )

        self.assertIn("do not meet the requirements", str(cm.exception))

    def test_mark_paid_activates_enrollment(self):
        """Test mark_paid transitions pending to active"""
        enrollment = EnrollmentRecord.create_for_user(
            user=self.user,
            product=self.product,
            pay_what_you_can_amount=Decimal("99.99"),
        )

        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT)
        self.assertIsNone(enrollment.course_enrollment)

        enrollment.mark_paid()

        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertIsNotNone(enrollment.course_enrollment)

    def test_mark_paid_idempotent(self):
        """Test mark_paid is idempotent (safe to call multiple times)"""
        enrollment = EnrollmentRecord.create_for_user(
            user=self.user, product=self.product, pay_what_you_can_amount=Decimal("0")
        )

        # Already active
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        course_enroll_id = enrollment.course_enrollment.id

        # Call mark_paid again
        enrollment.mark_paid()

        # Should still be active with same enrollment
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertEqual(enrollment.course_enrollment.id, course_enroll_id)

    def test_mark_paid_cancelled_refunded_error(self):
        """Test cannot mark cancelled/refunded enrollment as paid"""
        enrollment = EnrollmentRecord.objects.create(
            user=self.user,
            product=self.product,
            status=EnrollmentRecord.Status.CANCELLED_REFUNDED,
        )

        with self.assertRaises(ValidationError) as cm:
            enrollment.mark_paid()

        self.assertIn("cancelled/refunded", str(cm.exception))

    def test_unique_together_constraint(self):
        """Test database enforces unique user/product constraint"""
        EnrollmentRecord.objects.create(user=self.user, product=self.product)

        with self.assertRaises(IntegrityError):
            EnrollmentRecord.objects.create(user=self.user, product=self.product)

    def test_can_user_enroll_blocks_cancelled_refunded(self):
        """Test can_user_enroll blocks users with cancelled/refunded enrollment"""
        # Create cancelled/refunded enrollment
        EnrollmentRecord.objects.create(
            user=self.user,
            product=self.product,
            status=EnrollmentRecord.Status.CANCELLED_REFUNDED,
        )

        # Users with cancelled/refunded enrollments cannot re-enroll automatically
        # They must contact support for manual re-enrollment
        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

    def test_can_user_enroll_blocks_active_enrollment(self):
        """Test can_user_enroll blocks users with active enrollment"""
        EnrollmentRecord.create_for_user(
            user=self.user, product=self.product, pay_what_you_can_amount=Decimal("0")
        )

        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)

    def test_can_user_enroll_blocks_pending_enrollment(self):
        """Test can_user_enroll blocks users with pending payment"""
        EnrollmentRecord.create_for_user(
            user=self.user,
            product=self.product,
            pay_what_you_can_amount=Decimal("50.00"),
        )

        can_enroll = self.course.can_user_enroll(self.user)
        self.assertFalse(can_enroll)
