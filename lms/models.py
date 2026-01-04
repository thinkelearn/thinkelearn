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
import uuid
from decimal import Decimal

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import IntegrityError, models, transaction
from django.db.models import Avg, Q
from django.urls import reverse
from django.utils import timezone
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

    class PricingType(models.TextChoices):
        """Pricing type options for courses."""

        FREE = "free", "Free"
        FIXED = "fixed", "Fixed Price"
        PWYC = "pwyc", "Pay What You Can"

    class Currency(models.TextChoices):
        """Currency options for pricing."""

        CAD = "CAD", "Canadian Dollar"

    course = models.OneToOneField(
        "lms.ExtendedCoursePage",
        on_delete=models.CASCADE,
        related_name="product",
    )
    pricing_type = models.CharField(
        max_length=20,
        choices=PricingType,
        default=PricingType.PWYC,
        help_text="Pricing model for this course",
    )
    fixed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Fixed price (used when pricing_type='fixed')",
        validators=[MinValueValidator(0)],
    )
    suggested_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Suggested PWYC amount (display only)",
        validators=[MinValueValidator(0)],
    )
    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Minimum PWYC amount (0 to allow free)",
        validators=[MinValueValidator(0)],
    )
    max_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1000,
        help_text="Maximum PWYC amount",
        validators=[MinValueValidator(0)],
    )
    currency = models.CharField(
        max_length=3,
        choices=Currency,
        default=Currency.CAD,
        help_text="Currency for pricing (CAD for launch)",
    )
    refund_window_days = models.IntegerField(
        default=30,
        help_text="Number of days customers can request refunds (max 365 days)",
        validators=[MinValueValidator(0), MaxValueValidator(365)],
    )
    max_refunds_per_user = models.IntegerField(
        default=1,
        help_text="Maximum refunds/cancellations allowed per user for this product",
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
            f"pricing_type={self.pricing_type!r}, "
            f"fixed_price={self.fixed_price!r}, "
            f"currency={self.currency!r}, "
            f"is_active={self.is_active!r})"
        )

    def clean(self):
        """Validate pricing configuration consistency."""
        super().clean()

        # Fixed-price courses must have price > 0
        if self.pricing_type == self.PricingType.FIXED and self.fixed_price == 0:
            raise ValidationError(
                {
                    "fixed_price": "Fixed-price courses must have a price greater than 0. "
                    'Use pricing_type="free" for free courses.'
                }
            )

        # Free courses should have fixed_price = 0
        if self.pricing_type == self.PricingType.FREE and self.fixed_price != 0:
            raise ValidationError(
                {"fixed_price": "Free courses must have fixed_price set to 0."}
            )

        # PWYC courses must have min <= max
        if self.pricing_type == self.PricingType.PWYC:
            if self.min_price > self.max_price:
                raise ValidationError(
                    {
                        "min_price": "Minimum price cannot exceed maximum price.",
                        "max_price": "Maximum price cannot be less than minimum price.",
                    }
                )

            # Suggested price should be within range
            if (
                self.suggested_price < self.min_price
                or self.suggested_price > self.max_price
            ):
                raise ValidationError(
                    {
                        "suggested_price": f"Suggested price must be between {self.min_price} and {self.max_price}."
                    }
                )

    def validate_amount(self, amount: Decimal) -> tuple[bool, str]:
        """Validate payment amount based on pricing type."""
        if self.pricing_type == self.PricingType.FREE:
            is_valid = amount == 0
            msg = (
                "This course is free"
                if is_valid
                else "Amount must be 0 for free courses"
            )
            return (is_valid, msg)

        if self.pricing_type == self.PricingType.FIXED:
            is_valid = amount == self.fixed_price
            msg = (
                "" if is_valid else f"Price must be {self.fixed_price} {self.currency}"
            )
            return (is_valid, msg)

        if self.pricing_type == self.PricingType.PWYC:
            if amount < self.min_price:
                return (False, f"Minimum amount: {self.min_price} {self.currency}")
            if amount > self.max_price:
                return (False, f"Maximum amount: {self.max_price} {self.currency}")
            return (True, "")

        return (False, "Invalid pricing type")

    def is_refund_eligible(self, enrollment_date) -> bool:
        """Check if enrollment is still within refund window."""
        delta = timezone.now() - enrollment_date
        return delta.days <= self.refund_window_days

    def format_price(self) -> str:
        """
        Return formatted price string for display.

        Returns:
            String representation of the price with currency, e.g.:
            - "Free" for free courses
            - "$49.99 CAD" for fixed-price courses
            - "$10.00 - $50.00 CAD" for PWYC courses
        """
        if self.pricing_type == self.PricingType.FREE:
            return "Free"

        if self.pricing_type == self.PricingType.FIXED:
            return f"${self.fixed_price:.2f} {self.currency}"

        if self.pricing_type == self.PricingType.PWYC:
            return f"${self.min_price:.2f} - ${self.max_price:.2f} {self.currency}"

        return "Price unavailable"

    def get_quick_amounts(self) -> list[int]:
        """
        Generate preset amount buttons for PWYC pricing.

        Returns list of 4 integer dollar amounts based on suggested price:
        - Half of suggested (rounded to $5)
        - Suggested amount
        - Double suggested (rounded to $5)
        - Maximum price

        All amounts are clamped to min/max range and deduplicated.
        Returns empty list for non-PWYC pricing types.
        """
        if self.pricing_type != self.PricingType.PWYC:
            return []

        suggested = float(self.suggested_price)
        amounts = [
            suggested * 0.5,
            suggested,
            suggested * 2,
            float(self.max_price),
        ]

        # Round to nearest $5, clamp to range, convert to int
        quick_amounts = []
        for amt in amounts:
            rounded = round(amt / 5) * 5
            clamped = max(float(self.min_price), min(float(self.max_price), rounded))
            quick_amounts.append(int(clamped))

        # Deduplicate while preserving order
        seen = set()
        result = []
        for amt in quick_amounts:
            if amt not in seen:
                seen.add(amt)
                result.append(amt)

        return result[:4]  # Return max 4 buttons


class EnrollmentRecord(models.Model):
    """Tracks enrollment attempts with payment status."""

    class Status(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        ACTIVE = "active", "Active"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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
        choices=Status,
        default=Status.PENDING_PAYMENT,
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Actual amount paid (0 for free enrollments)",
        validators=[MinValueValidator(0)],
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    has_refund = models.BooleanField(
        default=False,
        help_text="True if any refund was processed for this enrollment",
    )
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        default=uuid.uuid4,
        help_text="Prevents duplicate enrollments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enrollment Record"
        verbose_name_plural = "Enrollment Records"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                condition=Q(status__in=["pending_payment", "active"]),
                name="unique_active_or_pending_enrollment",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.product.course.title} ({self.status})"

    def __repr__(self):
        return (
            f"<EnrollmentRecord id={self.id!r} "
            f"user_id={self.user_id!r} "
            f"product_id={self.product_id!r} "
            f"status={self.status!r} "
            f"course_enrollment_id={self.course_enrollment_id!r} "
            f"amount_paid={self.amount_paid!r}>"
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
    def create_for_user(cls, user, product, amount=None, idempotency_key=None):
        """
        Create a new enrollment for a user.

        This method creates a new enrollment record and will NOT update existing
        enrollments. Active or pending enrollments block duplicate creation. Cancelled
        or refunded enrollments are allowed based on refund/cancellation limits.

        For free enrollments (amount=0), this automatically creates the corresponding
        CourseEnrollment and sets status to ACTIVE. For paid enrollments (amount>0),
        the status is set to PENDING_PAYMENT and CourseEnrollment is created only
        after calling mark_paid().

        Args:
            user: The user to enroll
            product: The CourseProduct to enroll in
            amount: Optional payment amount. Required for PWYC courses. For fixed-price
                   courses, defaults to fixed_price. For free courses, defaults to 0.
            idempotency_key: Optional idempotency key for enrollment creation

        Returns:
            EnrollmentRecord instance

        Raises:
            ValidationError: If amount is missing for PWYC, user already has enrollment,
                           or user doesn't meet course prerequisites/limits
        """
        if not product.is_active:
            raise ValidationError("This course product is not currently available.")

        # Determine amount based on pricing type
        if amount is None:
            if product.pricing_type == CourseProduct.PricingType.FIXED:
                amount = product.fixed_price
            elif product.pricing_type == CourseProduct.PricingType.FREE:
                amount = Decimal("0")
            elif product.pricing_type == CourseProduct.PricingType.PWYC:
                raise ValidationError(
                    "Amount is required for pay-what-you-can courses. "
                    f"Please provide an amount between {product.min_price} and {product.max_price} {product.currency}."
                )
            else:
                raise ValidationError(f"Unknown pricing type: {product.pricing_type}")

        is_valid, message = product.validate_amount(amount)
        if not is_valid:
            raise ValidationError(message)

        existing = cls.objects.filter(user=user, product=product)
        if existing.filter(
            status__in=[cls.Status.PENDING_PAYMENT, cls.Status.ACTIVE]
        ).exists():
            raise ValidationError(
                "You already have an active or pending enrollment for this course."
            )

        refund_count = existing.filter(
            Q(status__in=[cls.Status.CANCELLED, cls.Status.REFUNDED])
            | Q(has_refund=True)
        ).count()
        if refund_count > product.max_refunds_per_user:
            raise ValidationError("Refund/cancellation limit reached for this course.")

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
            amount_paid=amount,
            idempotency_key=idempotency_key or str(uuid.uuid4()),
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
            ValidationError: If enrollment is cancelled or refunded
        """
        if self.status == self.Status.ACTIVE:
            return  # Already active

        if self.status in {self.Status.CANCELLED, self.Status.REFUNDED}:
            raise ValidationError(
                "Cannot mark a cancelled/refunded enrollment as paid."
            )

        # Create course enrollment if needed
        self._create_course_enrollment()

        # Update status
        self.transition_to(self.Status.ACTIVE)

    def transition_to(self, new_status):
        """
        Transition enrollment to a new status, enforcing valid transitions.

        This method implements a state machine to ensure enrollments only transition
        through valid states. Valid transitions are:
        - PENDING_PAYMENT → ACTIVE, PAYMENT_FAILED, or CANCELLED
        - ACTIVE → REFUNDED
        - PAYMENT_FAILED → CANCELLED
        - CANCELLED and REFUNDED are terminal states (no further transitions)

        Args:
            new_status: The target Status to transition to

        Raises:
            ValidationError: If the transition is not allowed from the current status

        Examples:
            >>> enrollment.status = Status.PENDING_PAYMENT
            >>> enrollment.transition_to(Status.ACTIVE)  # Valid
            >>> enrollment.transition_to(Status.REFUNDED)  # Raises ValidationError
        """
        transitions = {
            self.Status.PENDING_PAYMENT: {
                self.Status.ACTIVE,
                self.Status.PAYMENT_FAILED,
                self.Status.CANCELLED,
            },
            self.Status.ACTIVE: {self.Status.REFUNDED},
            self.Status.PAYMENT_FAILED: {self.Status.CANCELLED},
            self.Status.CANCELLED: set(),
            self.Status.REFUNDED: set(),
        }

        allowed = transitions.get(self.status, set())
        if new_status not in allowed and new_status != self.status:
            raise ValidationError(
                f"Invalid status transition from {self.status} to {new_status}."
            )

        self.status = new_status
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
            .prefetch_related("reviews")
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

    class Difficulty(models.TextChoices):
        """Difficulty levels for courses."""

        BEGINNER = "beginner", "Beginner"
        INTERMEDIATE = "intermediate", "Intermediate"
        ADVANCED = "advanced", "Advanced"

    difficulty = models.CharField(
        max_length=20,
        choices=Difficulty,
        default=Difficulty.BEGINNER,
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

        product = getattr(self, "product", None)
        context["product"] = product
        context["checkout_success_url"] = request.build_absolute_uri(
            reverse("payments:checkout_success")
        )
        context["checkout_cancel_url"] = request.build_absolute_uri(
            reverse("payments:checkout_cancel")
        )
        context["checkout_failure_url"] = request.build_absolute_uri(
            reverse("payments:checkout_failure")
        )

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
            .public()[:3]
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
        - User doesn't have any active or pending enrollment record
        - User is not already enrolled via CourseEnrollment
        - Enrollment limit hasn't been reached
        - All prerequisite courses are completed

        Note: Cancelled/refunded enrollments are allowed up to the product's
        max_refunds_per_user limit.

        Returns:
            bool: True if user can enroll, False otherwise
        """
        # Check for active or pending enrollment record
        product = getattr(self, "product", None)
        if product:
            enrollments = EnrollmentRecord.objects.filter(user=user, product=product)
            if enrollments.filter(
                status__in=[
                    EnrollmentRecord.Status.PENDING_PAYMENT,
                    EnrollmentRecord.Status.ACTIVE,
                ]
            ).exists():
                return False

            refund_count = enrollments.filter(
                Q(
                    status__in=[
                        EnrollmentRecord.Status.CANCELLED,
                        EnrollmentRecord.Status.REFUNDED,
                    ]
                )
                | Q(has_refund=True)
            ).count()
            if refund_count > product.max_refunds_per_user:
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
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
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
        constraints = [
            models.UniqueConstraint(
                fields=["course", "user"],
                name="unique_course_user_review",
            ),
        ]
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
