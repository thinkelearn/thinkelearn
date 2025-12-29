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

    list_display = ("course", "pricing_type", "fixed_price", "is_active", "updated_at")
    list_filter = ("pricing_type", "is_active", "currency")
    search_fields = ("course__title",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(EnrollmentRecord)
class EnrollmentRecordAdmin(admin.ModelAdmin):
    """Admin interface for enrollment records"""

    list_display = (
        "user",
        "product",
        "status",
        "amount_paid",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "product__course__title")
    readonly_fields = ("created_at", "updated_at")
    actions = ["mark_as_cancelled", "mark_as_refunded", "mark_as_payment_failed"]

    @admin.action(description="Mark selected enrollments as cancelled")
    def mark_as_cancelled(self, request, queryset):
        """Bulk action to cancel enrollments"""
        from django.core.exceptions import ValidationError

        updated = 0
        errors = 0

        for enrollment in queryset:
            try:
                enrollment.transition_to(EnrollmentRecord.Status.CANCELLED)
                updated += 1
            except ValidationError:
                errors += 1

        if updated:
            self.message_user(
                request, f"Successfully cancelled {updated} enrollment(s)."
            )
        if errors:
            self.message_user(
                request,
                f"Failed to cancel {errors} enrollment(s) due to invalid state transitions.",
                level="warning",
            )

    @admin.action(description="Mark selected active enrollments as refunded")
    def mark_as_refunded(self, request, queryset):
        """Bulk action to refund active enrollments"""
        from django.core.exceptions import ValidationError

        updated = 0
        errors = 0

        for enrollment in queryset:
            try:
                enrollment.transition_to(EnrollmentRecord.Status.REFUNDED)
                updated += 1
            except ValidationError:
                errors += 1

        if updated:
            self.message_user(
                request, f"Successfully marked {updated} enrollment(s) as refunded."
            )
        if errors:
            self.message_user(
                request,
                f"Failed to refund {errors} enrollment(s) - only active enrollments can be refunded.",
                level="warning",
            )

    @admin.action(description="Mark selected pending enrollments as payment failed")
    def mark_as_payment_failed(self, request, queryset):
        """Bulk action to mark enrollments as payment failed"""
        from django.core.exceptions import ValidationError

        updated = 0
        errors = 0

        for enrollment in queryset:
            try:
                enrollment.transition_to(EnrollmentRecord.Status.PAYMENT_FAILED)
                updated += 1
            except ValidationError:
                errors += 1

        if updated:
            self.message_user(
                request,
                f"Successfully marked {updated} enrollment(s) as payment failed.",
            )
        if errors:
            self.message_user(
                request,
                f"Failed to mark {errors} enrollment(s) - only pending enrollments can be marked as failed.",
                level="warning",
            )
