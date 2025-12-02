"""
Extended LMS models for THINK eLearn.

These models extend the base wagtail-lms functionality with additional features:
- Course catalog pages
- Course prerequisites
- Course reviews and ratings
- Related courses
- Enhanced metadata (duration, difficulty, etc.)
"""

from django import forms
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from modelcluster.fields import ParentalKey, ParentalManyToManyField
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Orderable, Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet
from wagtail_lms.models import CourseEnrollment, CoursePage


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

        # Get all live courses
        courses = (
            ExtendedCoursePage.objects.live()
            .descendant_of(self)
            .order_by("-first_published_at")
        )

        # Filter by category if specified
        category = request.GET.get("category")
        if category:
            courses = courses.filter(categories__slug=category)

        # Filter by tag if specified
        tag = request.GET.get("tag")
        if tag:
            courses = courses.filter(tags__slug=tag)

        # Search
        search_query = request.GET.get("q")
        if search_query:
            courses = courses.search(search_query)

        context["courses"] = courses
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

        # Check if user can enroll
        if request.user.is_authenticated:
            context["can_enroll"] = self.can_user_enroll(request.user)
            context["user_review"] = self.reviews.filter(user=request.user).first()
        else:
            context["can_enroll"] = False
            context["user_review"] = None

        # Add related courses
        context["related_courses"] = self.related_courses.live().public()[:3]

        return context

    def get_average_rating(self):
        """Calculate average rating for this course"""
        avg = self.reviews.aggregate(Avg("rating"))["rating__avg"]
        return round(avg, 1) if avg else None

    def get_enrollment_count(self):
        """Get total enrollment count"""
        return CourseEnrollment.objects.filter(course=self).count()

    def can_user_enroll(self, user):
        """Check if user can enroll in this course"""
        # Check if already enrolled
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
                    return False
            except CourseEnrollment.DoesNotExist:
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

    # Moderation
    is_approved = models.BooleanField(default=True)

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
