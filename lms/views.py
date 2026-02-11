"""Views for LMS custom workflows."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST
from wagtail_lms.models import CourseEnrollment
from wagtail_lms.views import ServeScormContentView

from .forms import CourseFeedbackForm
from .models import CourseReview, ExtendedCoursePage

logger = logging.getLogger(__name__)


class SafeRedirectScormContentView(ServeScormContentView):
    """Guard against S3 URL generation failures in production.

    The upstream view lets default_storage.url() exceptions propagate as 500s.
    We catch them and return 404 with logging so media playback degrades
    gracefully when AWS credentials expire or S3 is unreachable.
    """

    def get_redirect_url(self, storage_path):
        try:
            return super().get_redirect_url(storage_path)
        except Exception:
            logger.exception("Failed to generate presigned URL for %s", storage_path)
            raise Http404("File not found") from None


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
