"""Shared H5P direct-to-S3 upload handlers."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from wagtail_lms.models import H5PActivity

from .services import (
    create_h5p_activity_from_s3_key,
    generate_h5p_presigned_post,
    get_h5p_upload_prefix,
)

logger = logging.getLogger(__name__)


def s3_upload_enabled() -> bool:
    """Return True when S3-backed storage is configured."""
    return bool(getattr(settings, "AWS_STORAGE_BUCKET_NAME", ""))


def h5p_presigned_upload_response(request: HttpRequest) -> JsonResponse:
    """Return presigned POST data for direct-to-S3 H5P upload."""
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

    if not filename.lower().endswith(".h5p"):
        return JsonResponse({"error": "Only .h5p files are accepted"}, status=400)

    try:
        data = generate_h5p_presigned_post(filename)
    except Exception:
        logger.exception("Failed to generate H5P presigned URL")
        return JsonResponse({"error": "Failed to generate upload URL"}, status=500)

    return JsonResponse(data)


def h5p_finalize_upload_response(
    request: HttpRequest,
    *,
    redirect_url_builder: Callable[[H5PActivity], str],
) -> JsonResponse:
    """Create H5PActivity from an uploaded S3 object and return redirect target."""
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
    upload_prefix = get_h5p_upload_prefix()
    if not s3_key.startswith(upload_prefix) or not s3_key.lower().endswith(".h5p"):
        return JsonResponse({"error": "Invalid s3_key"}, status=400)
    if not title:
        return JsonResponse({"error": "title is required"}, status=400)

    description = body.get("description", "").strip()

    try:
        activity = create_h5p_activity_from_s3_key(s3_key, title, description)
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("Failed to finalize H5P upload")
        return JsonResponse({"error": "Failed to process H5P package"}, status=500)

    redirect_url = redirect_url_builder(activity)
    return JsonResponse(
        {"success": True, "redirect_url": redirect_url, "id": activity.pk}
    )
