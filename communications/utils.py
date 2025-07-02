import logging

from django.conf import settings
from django.contrib.sites.models import Site
from django.core.mail import send_mail
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)


def send_voicemail_notification(voicemail):
    """Send email notification for new voicemail."""
    try:
        current_site = Site.objects.get_current()
        domain = current_site.domain

        # Create the audio player URL
        recording_url = f"https://{domain}/communications/recording/{voicemail.id}/"

        # Prepare email context
        context = {
            "voicemail": voicemail,
            "recording_url": recording_url,
            "admin_url": f"https://{domain}/django-admin/communications/voicemailmessage/{voicemail.id}/change/",
            "site_name": getattr(settings, "SITE_NAME", "THINK eLearn"),
        }

        # Render email templates
        html_message = render_to_string(
            "communications/emails/voicemail_notification.html", context
        )
        plain_message = render_to_string(
            "communications/emails/voicemail_notification.txt", context
        )

        # Get recipient emails
        recipients = getattr(settings, "VOICEMAIL_NOTIFICATION_EMAILS", [])
        if not recipients:
            logger.warning("No VOICEMAIL_NOTIFICATION_EMAILS configured")
            return

        # Send email
        send_mail(
            subject=f"New Voicemail from {voicemail.caller_number}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"Voicemail notification sent for {voicemail.id}")

    except Exception as e:
        logger.error(f"Failed to send voicemail notification: {e}")


def send_sms_notification(sms):
    """Send email notification for new SMS."""
    try:
        current_site = Site.objects.get_current()
        domain = current_site.domain

        # Prepare email context
        context = {
            "sms": sms,
            "admin_url": f"https://{domain}/django-admin/communications/smsmessage/{sms.id}/change/",
            "site_name": getattr(settings, "SITE_NAME", "THINK eLearn"),
        }

        # Render email templates
        html_message = render_to_string(
            "communications/emails/sms_notification.html", context
        )
        plain_message = render_to_string(
            "communications/emails/sms_notification.txt", context
        )

        # Get recipient emails
        recipients = getattr(settings, "SMS_NOTIFICATION_EMAILS", [])
        if not recipients:
            logger.warning("No SMS_NOTIFICATION_EMAILS configured")
            return

        # Send email
        send_mail(
            subject=f"New SMS from {sms.from_number}",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            html_message=html_message,
            fail_silently=False,
        )

        logger.info(f"SMS notification sent for {sms.id}")

    except Exception as e:
        logger.error(f"Failed to send SMS notification: {e}")
