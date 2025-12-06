#!/usr/bin/env python
"""
Quick email test script for production environment.
Run this on Railway to test email configuration.
"""

import os

import django
from django.conf import settings
from django.core.mail import send_mail

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thinkelearn.settings.production")
django.setup()


def test_email():
    """Test email sending with current configuration"""
    print("=" * 60)
    print("Email Configuration Test")
    print("=" * 60)
    print(f"EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
    print(f"DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")

    if hasattr(settings, "MAILTRAP_API_TOKEN"):
        api_token = getattr(settings, "MAILTRAP_API_TOKEN", None)
        print(f"MAILTRAP_API_TOKEN: {'✅ Set' if api_token else '❌ Not set'}")
    else:
        print(f"EMAIL_HOST: {settings.EMAIL_HOST}")
        print(f"EMAIL_PORT: {settings.EMAIL_PORT}")
        print(f"EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}")
        print(f"EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")

    print("=" * 60)

    recipient = input("Enter recipient email address: ")

    try:
        print("\nSending test email...")
        send_mail(
            subject="Test Email from THINK eLearn",
            message="This is a test email to verify email configuration.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[recipient],
            fail_silently=False,
        )
        print("✅ Email sent successfully!")
        print(f"Check {recipient} inbox (including spam folder)")
    except Exception as e:
        print(f"❌ Email failed: {e}")
        print("\nTroubleshooting:")
        print("1. Verify Mailtrap API token is valid")
        print("2. Verify sender domain is verified in Mailtrap")
        print("3. Check Railway logs for detailed errors")


if __name__ == "__main__":
    test_email()
