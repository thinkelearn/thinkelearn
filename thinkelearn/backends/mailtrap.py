"""
Custom email backend for Mailtrap API.

This backend uses Mailtrap's HTTPS API instead of SMTP,
which is required for Railway's Free/Hobby/Trial plans that block SMTP ports.
"""

import logging

import mailtrap as mt
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.message import EmailMessage, EmailMultiAlternatives

logger = logging.getLogger(__name__)


class MailtrapAPIBackend(BaseEmailBackend):
    """
    Email backend that uses Mailtrap API instead of SMTP.

    Required settings:
        MAILTRAP_API_TOKEN: Your Mailtrap API token
        DEFAULT_FROM_EMAIL: Default sender email address
    """

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_token = getattr(settings, "MAILTRAP_API_TOKEN", None)
        if not self.api_token:
            if not self.fail_silently:
                raise ValueError("MAILTRAP_API_TOKEN setting is required")
            logger.warning("MAILTRAP_API_TOKEN not configured")

    def send_messages(self, email_messages: list[EmailMessage]) -> int:
        """
        Send one or more EmailMessage objects and return the number of email
        messages sent.
        """
        if not email_messages:
            return 0

        if not self.api_token:
            if self.fail_silently:
                return 0
            raise ValueError("MAILTRAP_API_TOKEN not configured")

        client = mt.MailtrapClient(token=self.api_token)
        sent_count = 0

        for message in email_messages:
            try:
                # Convert Django EmailMessage to Mailtrap Mail
                mail = self._convert_message(message)

                # Send via Mailtrap API
                response = client.send(mail)

                logger.info(f"Email sent via Mailtrap API: {response}")
                sent_count += 1

            except Exception as e:
                logger.error(f"Failed to send email via Mailtrap API: {e}")
                if not self.fail_silently:
                    raise

        return sent_count

    def _convert_message(self, message: EmailMessage) -> mt.Mail:
        """
        Convert Django EmailMessage to Mailtrap Mail object.
        """
        # Extract sender
        from_email = message.from_email or settings.DEFAULT_FROM_EMAIL
        sender_name = None
        sender_email = from_email

        # Parse "Name <email@example.com>" format
        if "<" in from_email and ">" in from_email:
            sender_name = from_email.split("<")[0].strip()
            sender_email = from_email.split("<")[1].replace(">", "").strip()

        sender = mt.Address(email=sender_email, name=sender_name)

        # Convert recipients
        to_addresses = (
            [mt.Address(email=addr) for addr in message.to] if message.to else []
        )

        cc_addresses = (
            [mt.Address(email=addr) for addr in message.cc] if message.cc else []
        )

        bcc_addresses = (
            [mt.Address(email=addr) for addr in message.bcc] if message.bcc else []
        )

        # Handle HTML content for EmailMultiAlternatives
        html_content = None
        if isinstance(message, EmailMultiAlternatives):
            for content, mimetype in message.alternatives:
                if mimetype == "text/html":
                    html_content = content
                    break

        # Build Mailtrap Mail object
        mail_kwargs = {
            "sender": sender,
            "to": to_addresses,
            "subject": message.subject,
            "text": message.body,
        }

        if cc_addresses:
            mail_kwargs["cc"] = cc_addresses

        if bcc_addresses:
            mail_kwargs["bcc"] = bcc_addresses

        if html_content:
            mail_kwargs["html"] = html_content

        # Add category if available (useful for tracking)
        if hasattr(message, "category"):
            mail_kwargs["category"] = message.category
        else:
            # Default category based on subject or type
            mail_kwargs["category"] = "Django Application"

        return mt.Mail(**mail_kwargs)
