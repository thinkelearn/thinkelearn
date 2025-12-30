import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_refund_confirmation(
    enrollment,
    *,
    refund_amount,
    original_amount,
    refund_date,
    is_partial: bool = False,
) -> None:
    """Send a refund confirmation email to the enrolled user."""
    recipient = enrollment.user.email
    if not recipient:
        logger.warning(
            "Refund confirmation skipped due to missing email",
            extra={"enrollment_id": enrollment.id},
        )
        return

    # Get current site with fallback if not configured
    try:
        current_site = Site.objects.get_current()
        site_domain = current_site.domain
    except Site.DoesNotExist:
        logger.warning("No Site configured, using default domain")
        site_domain = getattr(settings, "DEFAULT_DOMAIN", "thinkelearn.com")

    support_email = getattr(settings, "SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL)

    context = {
        "enrollment": enrollment,
        "course_name": enrollment.course.title,
        "refund_amount": refund_amount,
        "original_amount": original_amount,
        "refund_date": refund_date,
        "is_partial": is_partial,
        "site_name": getattr(settings, "SITE_NAME", "THINK eLearn"),
        "support_email": support_email,
        "site_domain": site_domain,
    }

    html_message = render_to_string("emails/refund_confirmation.html", context)
    plain_message = render_to_string("emails/refund_confirmation.txt", context)

    subject = f"Refund processed for {enrollment.course.title}"

    send_mail(
        subject=subject,
        message=plain_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[recipient],
        html_message=html_message,
        fail_silently=False,
    )

    logger.info(
        "Refund confirmation email sent",
        extra={"enrollment_id": enrollment.id, "recipient": recipient},
    )
