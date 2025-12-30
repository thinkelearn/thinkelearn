"""Django system checks for payments app configuration."""

import sys

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def check_stripe_configuration(app_configs, **kwargs):
    """Validate Stripe configuration for production deployment.

    Ensures required Stripe credentials are configured before deploying
    to production. Missing credentials would cause webhook signature
    verification to fail silently.
    """
    errors = []

    # Skip during test runs
    if "test" in sys.argv:
        return errors

    # Only enforce in production (DEBUG=False)
    if not settings.DEBUG:
        required_settings = {
            "STRIPE_SECRET_KEY": "Stripe secret key",
            "STRIPE_PUBLISHABLE_KEY": "Stripe publishable key",
            "STRIPE_WEBHOOK_SECRET": "Stripe webhook signing secret",
        }

        for setting_name, description in required_settings.items():
            value = getattr(settings, setting_name, None)
            if not value or value == "":
                errors.append(
                    Error(
                        f"{description} is not configured",
                        hint=f"Set {setting_name} in environment variables",
                        id=f"payments.E00{len(errors) + 1}",
                    )
                )

    # Warn if webhook secret looks like test mode in production
    if not settings.DEBUG:
        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        if webhook_secret and webhook_secret.startswith("whsec_test_"):
            errors.append(
                Warning(
                    "Stripe webhook secret appears to be in test mode",
                    hint="Ensure STRIPE_WEBHOOK_SECRET uses production credentials",
                    id="payments.W001",
                )
            )

    return errors
