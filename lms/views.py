"""Views for LMS custom workflows."""

import logging
import mimetypes
import posixpath

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import default_storage
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from wagtail_lms import conf
from wagtail_lms.models import CourseEnrollment

from .forms import CourseFeedbackForm
from .models import CourseReview, ExtendedCoursePage

logger = logging.getLogger(__name__)

# MIME types that should be redirected to S3 instead of proxied
_REDIRECT_MIME_PREFIXES = ("video/", "audio/")


def _is_s3_storage():
    """Check if the default storage backend is S3 or S3-compatible."""
    return hasattr(default_storage, "bucket_name")


def _cache_control_for_mime(content_type):
    """Return an appropriate Cache-Control header value for the MIME type."""
    if content_type.startswith("text/html"):
        return "no-cache"
    if content_type in ("application/javascript", "text/javascript", "text/css"):
        return "max-age=86400"
    if content_type.startswith("image/") or content_type.startswith("font/"):
        return "max-age=604800"
    return "max-age=86400"


@login_required
def serve_scorm_content(request, content_path):
    """Serve SCORM content files with caching headers and S3 redirect for media.

    Overrides wagtail_lms's serve_scorm_content to:
    - Redirect video/audio requests to presigned S3 URLs (avoids proxying large files)
    - Add Cache-Control headers for browser caching of proxied assets
    - Preserve all security checks from the original view
    """
    # Path traversal security: normalize separators then reject ".." and
    # absolute paths. Backslashes are replaced to catch Windows-style attacks.
    normalized = content_path.replace("\\", "/")
    normalized = posixpath.normpath(normalized)
    if normalized.startswith("/") or normalized.startswith(".."):
        raise Http404("File not found")

    # Build storage-relative path
    content_base = conf.WAGTAIL_LMS_CONTENT_PATH.rstrip("/")
    storage_path = posixpath.join(content_base, normalized)

    # Get the MIME type
    content_type, _ = mimetypes.guess_type(content_path)
    if content_type is None:
        content_type = "application/octet-stream"

    # For video/audio on S3: redirect to presigned URL instead of proxying.
    # S3 bucket CORS must allow GET/HEAD from our origin for <video crossorigin>
    # elements to work — see docs/aws-s3-iam-setup.md.
    if _is_s3_storage() and any(
        content_type.startswith(p) for p in _REDIRECT_MIME_PREFIXES
    ):
        try:
            url = default_storage.url(storage_path)
        except Exception:
            logger.exception("Failed to generate presigned URL for %s", storage_path)
            raise Http404("File not found") from None
        return HttpResponseRedirect(url)

    # Everything else: proxy through Django with caching headers
    try:
        fh = default_storage.open(storage_path, "rb")
    except (FileNotFoundError, OSError):
        raise Http404("File not found") from None

    response = FileResponse(fh, content_type=content_type)

    # Set headers to allow iframe embedding
    response["X-Frame-Options"] = "SAMEORIGIN"
    response["Content-Security-Policy"] = "frame-ancestors 'self'"

    # Add caching headers
    response["Cache-Control"] = _cache_control_for_mime(content_type)

    return response


@login_required
@require_POST
def submit_course_feedback(request, course_id):
    """Allow enrolled learners to submit or update feedback for a course."""
    course = get_object_or_404(ExtendedCoursePage, pk=course_id)
    redirect_url = f"{course.url}#course-feedback"

    is_enrolled = CourseEnrollment.objects.filter(
        user=request.user,
        course=course,
    ).exists()
    if not is_enrolled:
        messages.error(
            request,
            "You can submit feedback after enrolling in this course.",
        )
        return redirect(redirect_url)

    existing_review = CourseReview.objects.filter(
        course=course,
        user=request.user,
    ).first()
    form = CourseFeedbackForm(request.POST, instance=existing_review)

    if not form.is_valid():
        error_list: list[str] = []
        for field_errors in form.errors.values():
            error_list.extend(str(error) for error in field_errors)
        messages.error(
            request, "Please fix the feedback form: " + ", ".join(error_list)
        )
        return redirect(redirect_url)

    review = form.save(commit=False)
    review.course = course
    review.user = request.user
    if existing_review:
        # Edited feedback goes back to moderation before being shown publicly.
        review.is_approved = False
    review.save()

    messages.success(
        request,
        "Thanks for sharing your feedback. It has been submitted for review.",
    )
    return redirect(redirect_url)
