"""Django admin configuration for LMS models"""

import json
import logging

from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from wagtail_lms.models import SCORMPackage

from .models import CourseProduct, CourseReview, EnrollmentRecord

logger = logging.getLogger(__name__)


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


# Override wagtail-lms's SCORMPackageAdmin to support presigned S3 uploads.
# This is needed because Railway/Cloudflare enforces a 100 MB upload limit,
# and SCORM packages can exceed that.
admin.site.unregister(SCORMPackage)


def _s3_configured():
    return bool(getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""))


@admin.register(SCORMPackage)
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
        extra_context["s3_upload_enabled"] = _s3_configured()
        return super().add_view(request, form_url, extra_context)

    def presigned_upload_view(self, request):
        """Return presigned POST data for direct-to-S3 upload."""
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        if not _s3_configured():
            return JsonResponse({"error": "S3 storage is not configured"}, status=400)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        filename = body.get("filename", "").strip()
        if not filename:
            return JsonResponse({"error": "filename is required"}, status=400)

        if not filename.lower().endswith(".zip"):
            return JsonResponse({"error": "Only .zip files are accepted"}, status=400)

        from .services import generate_presigned_post

        try:
            data = generate_presigned_post(filename)
        except Exception:
            logger.exception("Failed to generate presigned URL")
            return JsonResponse({"error": "Failed to generate upload URL"}, status=500)

        return JsonResponse(data)

    def finalize_upload_view(self, request):
        """Create SCORMPackage from an already-uploaded S3 object."""
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)

        if not _s3_configured():
            return JsonResponse({"error": "S3 storage is not configured"}, status=400)

        try:
            body = json.loads(request.body)
        except (json.JSONDecodeError, ValueError):
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        s3_key = body.get("s3_key", "").strip()
        title = body.get("title", "").strip()

        if not s3_key:
            return JsonResponse({"error": "s3_key is required"}, status=400)
        if not title:
            return JsonResponse({"error": "title is required"}, status=400)

        description = body.get("description", "").strip()

        from .services import create_package_from_s3_key

        try:
            package = create_package_from_s3_key(s3_key, title, description)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("Failed to finalize SCORM upload")
            return JsonResponse(
                {"error": "Failed to process SCORM package"}, status=500
            )

        from django.urls import reverse

        redirect_url = reverse(
            "admin:wagtail_lms_scormpackage_change", args=[package.pk]
        )
        return JsonResponse(
            {"success": True, "redirect_url": redirect_url, "id": package.pk}
        )
