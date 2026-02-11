import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


def send_course_review_notification(review, *, created: bool) -> None:
    """Notify staff when a course review is created or updated."""
    recipients = getattr(settings, "COURSE_REVIEW_NOTIFICATION_EMAILS", [])
    if not recipients:
        logger.warning("No COURSE_REVIEW_NOTIFICATION_EMAILS configured")
        return

    action = "New" if created else "Updated"
    subject = f"{action} course review for {review.course.title}"

    base_url = getattr(settings, "WAGTAILADMIN_BASE_URL", "").rstrip("/")
    admin_path = f"/django-admin/lms/coursereview/{review.id}/change/"
    admin_url = f"{base_url}{admin_path}" if base_url else admin_path

    review_text = review.review_text.strip() or "(No written feedback provided)"

    message = (
        f"{action} course review submitted.\n\n"
        f"Course: {review.course.title}\n"
        f"User: {review.user.get_username()} ({review.user.email or 'no email'})\n"
        f"Rating: {review.rating}/5\n"
        f"Approved: {'Yes' if review.is_approved else 'No'}\n"
        f"Review text:\n{review_text}\n\n"
        f"Admin link: {admin_url}\n"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            fail_silently=False,
        )
        logger.info(
            "Course review notification sent",
            extra={
                "review_id": review.id,
                "review_created": created,
                "recipients": recipients,
            },
        )
    except Exception:
        logger.exception(
            "Failed to send course review notification",
            extra={"review_id": review.id, "review_created": created},
        )
