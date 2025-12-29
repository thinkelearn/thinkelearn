"""
Extended LMS models for THINK eLearn.

These models extend the base wagtail-lms functionality with additional features:
- Course catalog pages
- Course prerequisites
- Course reviews and ratings
- Related courses
- Enhanced metadata (duration, difficulty, etc.)
"""

import logging

from django import forms
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Avg
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet
from wagtail_lms.models import CourseEnrollment, CoursePage

logger = logging.getLogger(__name__)


class CourseProduct(models.Model):
    """Sellable course product linked to a course page."""

    course = models.OneToOneField(
        "lms.ExtendedCoursePage",
        on_delete=models.CASCADE,
        related_name="product",
    )
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Base price for the course (0 for free)",
        validators=[MinValueValidator(0)],
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this product can be purchased or enrolled",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Course Product"
        verbose_name_plural = "Course Products"

    def __str__(self):
        return f"{self.course.title} Product"

    def __repr__(self):
        return (
            f"{self.__class__.__name__}("
            f"id={self.id!r}, "
            f"course_id={getattr(self.course, 'id', None)!r}, "
            f"base_price={self.base_price!r}, "
            f"is_active={self.is_active!r})"
        )

    def enroll_user(self, user, amount=None):
        """
        Create an enrollment record, handling free vs paid enrollments.

        Args:
            user: The user to enroll
            amount: Payment amount (defaults to base_price if None)

        Returns:
            EnrollmentRecord instance

        Raises:
            ValidationError: If product is inactive or user cannot enroll
        """
        # Check if product is active
        if not self.is_active:
            raise ValidationError("This course product is not currently available.")

        if amount is None:
            amount = self.base_price

        enrollment = EnrollmentRecord.create_for_user(
            user=user,
            product=self,
            pay_what_you_can_amount=amount,
        )

        return enrollment


class EnrollmentRecord(models.Model):
    """Enrollment record with payment status and optional pay-what-you-can amount."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        CANCELLED_REFUNDED = "cancelled_refunded", "Cancelled/Refunded"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(
        CourseProduct,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course_enrollment = models.OneToOneField(
        CourseEnrollment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enrollment_record",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    pay_what_you_can_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Optional pay-what-you-can amount (0 for free enrollments)",
        validators=[MinValueValidator(0)],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enrollment Record"
        verbose_name_plural = "Enrollment Records"
        unique_together = ("user", "product")

    def __str__(self):
        return f"{self.user.username} - {self.product.course.title} ({self.status})"

    def __repr__(self):
        return (
            f"<EnrollmentRecord id={self.id!r} "
            f"user_id={self.user_id!r} "
            f"product_id={self.product_id!r} "
            f"status={self.status!r} "
            f"course_enrollment_id={self.course_enrollment_id!r} "
            f"pay_what_you_can_amount={self.pay_what_you_can_amount!r}>"
        )

    @property
    def course(self):
        """
        Convenient access to the related course for this enrollment.

        This is a shortcut for accessing ``self.product.course``.
        """
        return self.product.course

    @classmethod
    @transaction.atomic
    def create_for_user(cls, user, product, pay_what_you_can_amount=None):
        """
        Create a new enrollment for a user.

        This method creates a new enrollment record and will NOT update existing
        enrollments. If an enrollment already exists (active, pending, or cancelled),
        this method will raise a ValidationError to prevent unintended state changes.

        For free enrollments (amount=0), this automatically creates the corresponding
        CourseEnrollment and sets status to ACTIVE. For paid enrollments (amount>0),
        the status is set to PENDING_PAYMENT and CourseEnrollment is created only
        after calling mark_paid().

        Args:
            user: The user to enroll
            product: The CourseProduct to enroll in
            pay_what_you_can_amount: Optional payment amount (defaults to product.base_price)

        Returns:
            EnrollmentRecord instance

        Raises:
            ValidationError: If amount is negative, user already has enrollment,
                           or user doesn't meet course prerequisites/limits
        """
        # Validate amount is non-negative
        amount = pay_what_you_can_amount
        if amount is None:
            amount = product.base_price

        if amount < 0:
            raise ValidationError("Payment amount cannot be negative.")

        # Check if enrollment already exists (any status)
        existing = cls.objects.filter(user=user, product=product).first()
        if existing:
            if existing.status == cls.Status.CANCELLED_REFUNDED:
                raise ValidationError(
                    "You have a cancelled/refunded enrollment for this course. "
                    "Please contact support to re-enroll."
                )
            else:
                raise ValidationError(
                    f"You already have an enrollment for this course (status: {existing.status})."
                )

        # Validate user can enroll (prerequisites, limits, etc.)
        if not product.course.can_user_enroll(user):
            raise ValidationError(
                "You do not meet the requirements to enroll in this course. "
                "Please check prerequisites and enrollment availability."
            )

        # Determine status based on amount
        status = cls.Status.ACTIVE if amount == 0 else cls.Status.PENDING_PAYMENT

        # Create enrollment record
        enrollment = cls.objects.create(
            user=user,
            product=product,
            status=status,
            pay_what_you_can_amount=amount,
        )

        # For free enrollments, create CourseEnrollment immediately
        if status == cls.Status.ACTIVE:
            enrollment._create_course_enrollment()

        return enrollment

    @transaction.atomic
    def _create_course_enrollment(self):
        """
        Internal method to create CourseEnrollment with race condition protection.

        Uses database transaction and get_or_create to prevent duplicate
        CourseEnrollment records in concurrent scenarios.
        """
        if self.course_enrollment is not None:
            return  # Already has enrollment

        try:
            # Use get_or_create to handle race conditions
            course_enroll, created = CourseEnrollment.objects.get_or_create(
                user=self.user,
                course=self.product.course,
            )

            self.course_enrollment = course_enroll
            self.save(update_fields=["course_enrollment"])

            if not created:
                logger.warning(
                    f"CourseEnrollment already existed for user={self.user.pk} "
                    f"course={self.product.course.pk} when creating enrollment record"
                )

        except IntegrityError as e:
            logger.error(
                f"IntegrityError creating CourseEnrollment for enrollment {self.pk}: {e}"
            )
            raise

    @transaction.atomic
    def mark_paid(self):
        """
        Mark a pending enrollment as paid and activate it.

        This method transitions a PENDING_PAYMENT enrollment to ACTIVE and creates
        the corresponding CourseEnrollment. If the enrollment is already ACTIVE,
        this is a no-op.

        Raises:
            ValidationError: If enrollment is CANCELLED_REFUNDED
        """
        if self.status == self.Status.ACTIVE:
            return  # Already active

        if self.status == self.Status.CANCELLED_REFUNDED:
            raise ValidationError(
                "Cannot mark a cancelled/refunded enrollment as paid. "
                "Create a new enrollment instead."
            )

        # Create course enrollment if needed
        self._create_course_enrollment()

        # Update status
        self.status = self.Status.ACTIVE
        self.save(update_fields=["status"])


@register_snippet
class CourseCategory(models.Model):
    """Course categories for organizing courses"""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(
        max_length=50,
        blank=True,
        help_text="Font Awesome icon class (e.g., 'fa-book', 'fa-code')",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
        FieldPanel("description"),
        FieldPanel("icon"),
    ]

    class Meta:
        verbose_name = "Course Category"
        verbose_name_plural = "Course Categories"
        ordering = ["name"]

    def __str__(self):
        return self.name


@register_snippet
class CourseTag(models.Model):
    """Tags for courses (technologies, topics, etc.)"""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("slug"),
    ]

    class Meta:
        verbose_name = "Course Tag"
        verbose_name_plural = "Course Tags"
        ordering = ["name"]

    def __str__(self):
        return self.name


class CoursesIndexPage(Page):
    """Landing page for course catalog"""

    intro = RichTextField(blank=True)
    hero_image = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Hero image for the courses page",
    )

    content_panels = [
        *Page.content_panels,
        FieldPanel("intro"),
        FieldPanel("hero_image"),
    ]

    # Only allow CoursePage children
    subpage_types = ["lms.ExtendedCoursePage"]

    class Meta:
        verbose_name = "Courses Index Page"

    def get_context(self, request):
        context = super().get_context(request)

        # Get filter/search parameters
        category = request.GET.get("category")
        tag = request.GET.get("tag")
        search_query = request.GET.get("q")

        # Get all live courses with optimized queries
        courses = (
            ExtendedCoursePage.objects.live()
            .descendant_of(self)
            .prefetch_related("categories", "tags", "reviews")
            .order_by("-first_published_at")
        )

        # Apply search first if specified (search returns SearchResults object)
        if search_query:
            courses = courses.search(search_query)

        # Then apply filters (these work on both QuerySet and SearchResults)
        if category:
            courses = courses.filter(categories__slug=category)
        if tag:
            courses = courses.filter(tags__slug=tag)

        context["courses"] = courses
        # Categories and tags are small datasets, no need for special optimization
        context["categories"] = CourseCategory.objects.all()
        context["tags"] = CourseTag.objects.all()
        context["selected_category"] = category
        context["selected_tag"] = tag
        context["search_query"] = search_query

        return context


class ExtendedCoursePage(CoursePage):
    """
    Extended course page with additional features.

    Inherits from wagtail_lms.models.CoursePage and adds:
    - Categories and tags
    - Prerequisites
    - Duration and difficulty
    - Reviews and ratings
    - Related courses
    """

    # Additional metadata
    categories = ParentalManyToManyField(CourseCategory, blank=True)
    tags = ParentalManyToManyField(CourseTag, blank=True)

    duration_hours = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Estimated duration in hours",
    )

    DIFFICULTY_CHOICES = [
        ("beginner", "Beginner"),
        ("intermediate", "Intermediate"),
        ("advanced", "Advanced"),
    ]

    difficulty = models.CharField(
        max_length=20,
        choices=DIFFICULTY_CHOICES,
        default="beginner",
    )

    prerequisites_description = RichTextField(
        blank=True,
        help_text="Description of course prerequisites",
    )

    learning_objectives = RichTextField(
        blank=True,
        help_text="What students will learn",
    )

    thumbnail = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="Course thumbnail image",
    )

    # Prerequisites (other courses)
    prerequisite_courses = ParentalManyToManyField(
        "self",
        symmetrical=False,
        blank=True,
        related_name="unlocked_courses",
        help_text="Courses that must be completed before this one",
    )

    # Related courses
    related_courses = ParentalManyToManyField(
        "self",
        symmetrical=True,
        blank=True,
        help_text="Related or similar courses",
    )

    # Enrollment settings
    is_published = models.BooleanField(
        default=True,
        help_text="Make this course available for enrollment",
    )

    enrollment_limit = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of enrollments (leave blank for unlimited)",
    )

    content_panels = [
        *CoursePage.content_panels,
        MultiFieldPanel(
            [
                FieldPanel("categories", widget=forms.CheckboxSelectMultiple),
                FieldPanel("tags", widget=forms.CheckboxSelectMultiple),
                FieldPanel("difficulty"),
                FieldPanel("duration_hours"),
            ],
            heading="Course Metadata",
        ),
        FieldPanel("thumbnail"),
        FieldPanel("learning_objectives"),
        FieldPanel("prerequisites_description"),
        FieldPanel("prerequisite_courses", widget=forms.CheckboxSelectMultiple),
        FieldPanel("related_courses", widget=forms.CheckboxSelectMultiple),
        MultiFieldPanel(
            [
                FieldPanel("is_published"),
                FieldPanel("enrollment_limit"),
            ],
            heading="Enrollment Settings",
        ),
        InlinePanel("course_instructors", label="Instructors"),
    ]

    search_fields = Page.search_fields + [
        index.SearchField("learning_objectives"),
        index.SearchField("prerequisites_description"),
        index.FilterField("difficulty"),
        index.FilterField("duration_hours"),
    ]

    # Parent page / subpage type rules
    parent_page_types = ["lms.CoursesIndexPage"]
    subpage_types = []

    class Meta:
        verbose_name = "Course"
        verbose_name_plural = "Courses"

    def get_context(self, request):
        context = super().get_context(request)

        # Add rating information
        context["average_rating"] = self.get_average_rating()
        context["total_reviews"] = self.reviews.count()
        context["enrollment_count"] = self.get_enrollment_count()

        # Prefetch recent reviews with user data for performance
        context["recent_reviews"] = (
            self.reviews.filter(is_approved=True)
            .select_related("user")
            .order_by("-created_at")[:5]
        )

        # Check if user can enroll
        if request.user.is_authenticated:
            context["can_enroll"] = self.can_user_enroll(request.user)
            context["user_review"] = self.reviews.filter(user=request.user).first()
        else:
            context["can_enroll"] = False
            context["user_review"] = None

        # Add related courses - filter for live and public with prefetch
        related_course_ids = self.related_courses.values_list("id", flat=True)
        context["related_courses"] = (
            ExtendedCoursePage.objects.filter(id__in=related_course_ids)
            .live()
            .public()
            .prefetch_related("categories", "tags")[:3]
        )

        return context

    def get_average_rating(self):
        """Calculate average rating for this course"""
        avg = self.reviews.aggregate(Avg("rating"))["rating__avg"]
        return round(avg, 1) if avg else None

    def get_enrollment_count(self):
        """Get total enrollment count"""
        return CourseEnrollment.objects.filter(course=self).count()

    def can_user_enroll(self, user):
        """
        Check if user can enroll in this course.

        This checks:
        - User doesn't have any enrollment record (active, pending, or cancelled)
        - User is not already enrolled via CourseEnrollment
        - Enrollment limit hasn't been reached
        - All prerequisite courses are completed

        Note: Users with CANCELLED_REFUNDED enrollments cannot automatically
        re-enroll and must contact support for manual re-enrollment.

        Returns:
            bool: True if user can enroll, False otherwise
        """
        # Check for any existing enrollment record (including cancelled/refunded)
        product = getattr(self, "product", None)
        if product:
            has_enrollment = EnrollmentRecord.objects.filter(
                user=user, product=product
            ).exists()

            if has_enrollment:
                return False

        # Check if already enrolled directly via CourseEnrollment
        if CourseEnrollment.objects.filter(user=user, course=self).exists():
            return False

        # Check enrollment limit
        if self.enrollment_limit:
            if self.get_enrollment_count() >= self.enrollment_limit:
                return False

        # Check prerequisites
        for prereq in self.prerequisite_courses.all():
            try:
                enrollment = CourseEnrollment.objects.get(user=user, course=prereq)
                if not enrollment.completed_at:
                    logger.debug(
                        f"User {user.username} cannot enroll in {self.title}: "
                        f"prerequisite {prereq.title} not completed"
                    )
                    return False
            except CourseEnrollment.DoesNotExist:
                logger.debug(
                    f"User {user.username} cannot enroll in {self.title}: "
                    f"not enrolled in prerequisite {prereq.title}"
                )
                return False

        return True

    def get_completion_rate(self):
        """Calculate course completion rate"""
        total = self.get_enrollment_count()
        if total == 0:
            return 0

        completed = CourseEnrollment.objects.filter(
            course=self, completed_at__isnull=False
        ).count()

        return round((completed / total) * 100, 1)


class CourseInstructor(Orderable):
    """Instructors for a course"""

    course = ParentalKey(
        ExtendedCoursePage, on_delete=models.CASCADE, related_name="course_instructors"
    )
    name = models.CharField(max_length=255)
    title = models.CharField(max_length=255, blank=True)
    bio = models.TextField(blank=True)
    photo = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    email = models.EmailField(blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("title"),
        FieldPanel("bio"),
        FieldPanel("photo"),
        FieldPanel("email"),
    ]

    class Meta:
        verbose_name = "Course Instructor"
        verbose_name_plural = "Course Instructors"

    def __str__(self):
        return self.name


class CourseReview(models.Model):
    """User reviews and ratings for courses"""

    course = models.ForeignKey(
        ExtendedCoursePage, on_delete=models.CASCADE, related_name="reviews"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.PositiveIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Moderation - reviews require approval by default for quality control
    is_approved = models.BooleanField(
        default=False,
        help_text="Approve this review to make it visible to other users",
    )

    class Meta:
        verbose_name = "Course Review"
        verbose_name_plural = "Course Reviews"
        unique_together = ("course", "user")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username} - {self.course.title} ({self.rating}/5)"


class LearnerDashboardPage(Page):
    """Dashboard for learners to see their enrolled courses and progress"""

    intro = RichTextField(blank=True, help_text="Introduction text for the dashboard")

    content_panels = [
        *Page.content_panels,
        FieldPanel("intro"),
    ]

    # No child pages allowed
    subpage_types = []

    class Meta:
        verbose_name = "Learner Dashboard"

    def get_context(self, request):
        context = super().get_context(request)

        if request.user.is_authenticated:
            # Get enrolled courses
            enrollments = CourseEnrollment.objects.filter(
                user=request.user
            ).select_related("course")

            # Separate active and completed
            active_enrollments = enrollments.filter(completed_at__isnull=True)
            completed_enrollments = enrollments.filter(completed_at__isnull=False)

            context["active_enrollments"] = active_enrollments
            context["completed_enrollments"] = completed_enrollments
            context["total_courses"] = enrollments.count()
            context["completed_courses"] = completed_enrollments.count()

            # Calculate overall progress
            if enrollments.count() > 0:
                context["completion_percentage"] = round(
                    (completed_enrollments.count() / enrollments.count()) * 100, 1
                )
            else:
                context["completion_percentage"] = 0

        return context
