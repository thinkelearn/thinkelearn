"""
Custom context processors for thinkelearn project.

These processors add variables to the template context globally.
"""

from django.conf import settings


def registration_settings(request):
    """
    Expose registration-related settings to all templates.

    Used to conditionally show/hide signup links based on whether
    registration is open (controlled via ACCOUNT_ALLOW_REGISTRATION env var).
    """
    return {
        "ACCOUNT_ALLOW_REGISTRATION": settings.ACCOUNT_ALLOW_REGISTRATION,
    }
