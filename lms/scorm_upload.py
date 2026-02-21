"""Shared SCORM direct-to-S3 upload handlers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from wagtail_lms.models import SCORMPackage

from .services import (
    create_package_from_s3_key,
    generate_presigned_post,
    get_scorm_upload_prefix,
)

logger = logging.getLogger(__name__)


def s3_upload_enabled() -> bool:
    """Return True when S3-backed storage is configured."""
    return bool(getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""))


def presigned_upload_response(request: HttpRequest) -> JsonResponse:
    """Return presigned POST data for direct-to-S3 upload."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not s3_upload_enabled():
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

    try:
        data = generate_presigned_post(filename)
    except Exception:
        logger.exception("Failed to generate presigned URL")
        return JsonResponse({"error": "Failed to generate upload URL"}, status=500)

    return JsonResponse(data)


def finalize_upload_response(
    request: HttpRequest,
    *,
    redirect_url_builder: Callable[[SCORMPackage], str],
) -> JsonResponse:
    """Create SCORMPackage from an uploaded S3 object and return redirect target."""
    if request.method != "POST":
        return JsonResponse({"error": "POST required"}, status=405)

    if not s3_upload_enabled():
        return JsonResponse({"error": "S3 storage is not configured"}, status=400)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    s3_key = body.get("s3_key", "").strip()
    title = body.get("title", "").strip()

    if not s3_key:
        return JsonResponse({"error": "s3_key is required"}, status=400)
    upload_prefix = get_scorm_upload_prefix()
    if not s3_key.startswith(upload_prefix) or not s3_key.lower().endswith(".zip"):
        return JsonResponse({"error": "Invalid s3_key"}, status=400)
    if not title:
        return JsonResponse({"error": "title is required"}, status=400)

    description = body.get("description", "").strip()

    try:
        package = create_package_from_s3_key(s3_key, title, description)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("Failed to finalize SCORM upload")
        return JsonResponse({"error": "Failed to process SCORM package"}, status=500)

    redirect_url = redirect_url_builder(package)
    return JsonResponse(
        {"success": True, "redirect_url": redirect_url, "id": package.pk}
    )
