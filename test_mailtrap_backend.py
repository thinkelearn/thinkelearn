#!/usr/bin/env python
"""
Test script for Mailtrap API backend.
Tests the email backend without actually sending emails.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "thinkelearn.settings.dev")

import django  # noqa: E402

django.setup()

from django.core.mail import EmailMultiAlternatives, send_mail  # noqa: E402


def test_simple_email():
    """Test simple email sending"""
    print("\n" + "=" * 60)
    print("Test 1: Simple Email")
    print("=" * 60)

    try:
        # This will use console backend in development
        result = send_mail(
            subject="Test Simple Email",
            message="This is a plain text test email.",
            from_email="hello@thinkelearn.com",
            recipient_list=["test@example.com"],
            fail_silently=False,
        )
        print(f"✅ Simple email test passed. Sent count: {result}")
    except Exception as e:
        print(f"❌ Simple email test failed: {e}")
        return False

    return True


def test_html_email():
    """Test HTML email sending"""
    print("\n" + "=" * 60)
    print("Test 2: HTML Email")
    print("=" * 60)

    try:
        email = EmailMultiAlternatives(
            subject="Test HTML Email",
            body="This is the plain text version.",
            from_email="hello@thinkelearn.com",
            to=["test@example.com"],
            cc=["cc@example.com"],
        )
        email.attach_alternative(
            "<h1>HTML Version</h1><p>This is the HTML version.</p>", "text/html"
        )

        result = email.send(fail_silently=False)
        print(f"✅ HTML email test passed. Sent count: {result}")
    except Exception as e:
        print(f"❌ HTML email test failed: {e}")
        return False

    return True


def test_mailtrap_backend_import():
    """Test that the Mailtrap backend can be imported"""
    print("\n" + "=" * 60)
    print("Test 3: Backend Import")
    print("=" * 60)

    try:
        from thinkelearn.backends.mailtrap import MailtrapAPIBackend

        backend = MailtrapAPIBackend(fail_silently=True)
        print("✅ Mailtrap backend import successful")
        print(f"   Backend class: {backend.__class__.__name__}")
        return True
    except Exception as e:
        print(f"❌ Backend import failed: {e}")
        return False


def test_message_conversion():
    """Test Django message to Mailtrap message conversion"""
    print("\n" + "=" * 60)
    print("Test 4: Message Conversion")
    print("=" * 60)

    try:
        from django.core.mail import EmailMessage

        from thinkelearn.backends.mailtrap import MailtrapAPIBackend

        # Create test backend with fake token
        backend = MailtrapAPIBackend(fail_silently=True)
        backend.api_token = "test-token-12345"  # nosec B105

        # Create test message
        message = EmailMessage(
            subject="Test Subject",
            body="Test body",
            from_email="Test Sender <hello@thinkelearn.com>",
            to=["recipient@example.com"],
            cc=["cc@example.com"],
        )

        # Test conversion
        mail = backend._convert_message(message)

        print("✅ Message conversion successful")
        print(f"   Sender: {mail.sender.email}")
        print(f"   To: {[addr.email for addr in mail.to]}")
        print(f"   Subject: {mail.subject}")
        print(f"   Body length: {len(mail.text)} chars")

        return True
    except Exception as e:
        print(f"❌ Message conversion failed: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("MAILTRAP BACKEND TEST SUITE")
    print("=" * 60)

    from django.conf import settings

    print(f"Settings module: {settings.SETTINGS_MODULE}")
    print(f"Email backend: {settings.EMAIL_BACKEND}")

    tests = [
        test_mailtrap_backend_import,
        test_message_conversion,
        test_simple_email,
        test_html_email,
    ]

    results = []
    for test in tests:
        result = test()
        results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ All tests passed!")
        return 0
    else:
        print(f"❌ {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
