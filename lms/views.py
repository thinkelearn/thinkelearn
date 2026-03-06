"""Views for LMS custom workflows."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from wagtail_lms.models import CourseEnrollment

from .forms import CourseFeedbackForm
from .models import (
    ClientDemoEnrollment,
    ClientDemoInvite,
    CourseReview,
    ExtendedCoursePage,
)


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


@login_required
def client_demo_view(request, token):
    """
    Landing page for a client demo invite.

    - Validates the invite token (404 if missing/expired/inactive).
    - For regular users: idempotently enrolls them in each live demo course,
      recording which enrollments we created so they can be revoked later.
    - For Wagtail editors (staff doing a live demo): skips enrollment entirely
      since editors bypass the enrollment gate in the SCORM/H5P players.
    - Renders a landing page split into private courses and public courses.
    """
    invite = get_object_or_404(ClientDemoInvite, token=token)
    if not invite.is_valid():
        raise Http404

    # Persist the demo token in the session so templates can render the demo
    # mode bar (back link + contextual notice) on any course or lesson page.
    request.session["active_demo_token"] = str(invite.token)

    is_editor = request.user.has_perm("wagtailadmin.access_admin")

    if not is_editor:
        for course in invite.demo_courses.filter(live=True):
            was_enrolled = CourseEnrollment.objects.filter(
                user=request.user, course=course
            ).exists()
            if not was_enrolled:
                CourseEnrollment.objects.get_or_create(user=request.user, course=course)
            ClientDemoEnrollment.objects.get_or_create(
                invite=invite,
                user=request.user,
                course=course,
                defaults={"revoke_on_expiry": not was_enrolled},
            )

    # Build landing page course lists.
    # Editors see the invite's courses directly (no enrollment created).
    # Regular users see all their enrolled courses, split by visibility.
    private_demo = ExtendedCoursePage.Visibility.PRIVATE_DEMO
    if is_editor:
        demo_qs = invite.demo_courses.filter(live=True)
        private_courses = demo_qs.filter(visibility=private_demo)
        public_courses = demo_qs.exclude(visibility=private_demo)
    else:
        enrolled_ids = CourseEnrollment.objects.filter(user=request.user).values_list(
            "course_id", flat=True
        )
        enrolled_qs = ExtendedCoursePage.objects.filter(pk__in=enrolled_ids, live=True)
        private_courses = enrolled_qs.filter(visibility=private_demo)
        public_courses = enrolled_qs.exclude(visibility=private_demo)

    return render(
        request,
        "lms/demo_landing.html",
        {
            "invite": invite,
            "private_courses": private_courses,
            "public_courses": public_courses,
            "is_staff_preview": is_editor,
        },
    )
