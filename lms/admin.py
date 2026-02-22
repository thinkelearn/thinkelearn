"""Django admin configuration for LMS models"""

from django.contrib import admin
from django.urls import path, reverse

from .h5p_upload import (
    h5p_finalize_upload_response,
    h5p_presigned_upload_response,
)
from .models import CourseProduct, CourseReview, EnrollmentRecord
from .scorm_upload import (
    finalize_upload_response,
    presigned_upload_response,
    s3_upload_enabled,
)


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

    list_display = (
        "course",
        "pricing_type",
        "fixed_price",
        "max_refunds_per_user",
        "is_active",
        "updated_at",
    )
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
    actions = ["mark_as_cancelled", "mark_as_payment_failed"]

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


class SCORMPackageUploadAdmin(admin.ModelAdmin):
    """SCORMPackage admin with optional direct-to-S3 upload."""

    list_display = ("title", "version", "created_at", "launch_url")
    list_filter = ("version", "created_at")
    search_fields = ("title", "description")
    readonly_fields = (
        "extracted_path",
        "launch_url",
        "manifest_data",
        "created_at",
        "updated_at",
    )
    change_form_template = "admin/wagtail_lms/scormpackage/change_form.html"

    def get_urls(self):
        custom_urls = [
            path(
                "presigned-upload/",
                self.admin_site.admin_view(self.presigned_upload_view),
                name="scormpackage_presigned_upload",
            ),
            path(
                "finalize-upload/",
                self.admin_site.admin_view(self.finalize_upload_view),
                name="scormpackage_finalize_upload",
            ),
        ]
        return custom_urls + super().get_urls()

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["s3_upload_enabled"] = s3_upload_enabled()
        return super().add_view(request, form_url, extra_context)

    def presigned_upload_view(self, request):
        """Return presigned POST data for direct-to-S3 upload."""
        return presigned_upload_response(request)

    def finalize_upload_view(self, request):
        """Create SCORMPackage from an already-uploaded S3 object."""
        return finalize_upload_response(
            request,
            redirect_url_builder=lambda package: reverse(
                "admin:wagtail_lms_scormpackage_change", args=[package.pk]
            ),
        )


class H5PActivityUploadAdmin(admin.ModelAdmin):
    """H5PActivity admin with optional direct-to-S3 upload."""

    list_display = ("title", "main_library", "created_at")
    list_filter = ("created_at",)
    search_fields = ("title", "description", "main_library")
    readonly_fields = (
        "extracted_path",
        "main_library",
        "h5p_json",
        "created_at",
        "updated_at",
    )
    change_form_template = "admin/wagtail_lms/h5pactivity/change_form.html"

    def get_urls(self):
        custom_urls = [
            path(
                "presigned-upload/",
                self.admin_site.admin_view(self.presigned_upload_view),
                name="h5pactivity_presigned_upload",
            ),
            path(
                "finalize-upload/",
                self.admin_site.admin_view(self.finalize_upload_view),
                name="h5pactivity_finalize_upload",
            ),
        ]
        return custom_urls + super().get_urls()

    def add_view(self, request, form_url="", extra_context=None):
        extra_context = extra_context or {}
        extra_context["s3_upload_enabled"] = s3_upload_enabled()
        return super().add_view(request, form_url, extra_context)

    def presigned_upload_view(self, request):
        """Return presigned POST data for direct-to-S3 H5P upload."""
        return h5p_presigned_upload_response(request)

    def finalize_upload_view(self, request):
        """Create H5PActivity from an already-uploaded S3 object."""
        return h5p_finalize_upload_response(
            request,
            redirect_url_builder=lambda activity: reverse(
                "admin:wagtail_lms_h5pactivity_change", args=[activity.pk]
            ),
        )
