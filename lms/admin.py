"""Django admin configuration for LMS models"""

from django.contrib import admin

from .models import CourseReview


@admin.register(CourseReview)
class CourseReviewAdmin(admin.ModelAdmin):
    """Admin interface for course reviews"""

    list_display = ("course", "user", "rating", "created_at", "is_approved")
    list_filter = ("rating", "is_approved", "created_at")
    search_fields = ("course__title", "user__username", "review_text")
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "created_at"

    fieldsets = (
        (
            None,
            {
                "fields": ("course", "user", "rating", "review_text"),
            },
        ),
        (
            "Moderation",
            {
                "fields": ("is_approved",),
            },
        ),
        (
            "Timestamps",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )
