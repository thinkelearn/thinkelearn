"""Django admin configuration for LMS models"""

from django.contrib import admin

from .models import CourseProduct, CourseReview, EnrollmentRecord


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


@admin.register(CourseProduct)
class CourseProductAdmin(admin.ModelAdmin):
    """Admin interface for course products"""

    list_display = ("course", "base_price", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("course__title",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(EnrollmentRecord)
class EnrollmentRecordAdmin(admin.ModelAdmin):
    """Admin interface for enrollment records"""

    list_display = (
        "user",
        "product",
        "status",
        "pay_what_you_can_amount",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "product__course__title")
    readonly_fields = ("created_at", "updated_at")
