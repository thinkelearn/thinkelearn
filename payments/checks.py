"""Django system checks for payments app configuration."""

from django.conf import settings
from django.core.checks import CheckMessage, Error, Tags, Warning, register


@register(Tags.security, deploy=True)
def check_stripe_configuration(app_configs, **kwargs):
    """Validate Stripe configuration for production deployment.

    Ensures required Stripe credentials are configured before deploying
    to production. Missing credentials would cause webhook signature
    verification to fail silently.

    This check is tagged with 'deploy' so it only runs with --deploy flag
    or in production mode (DEBUG=False).
    """
    errors: list[CheckMessage] = []

    # Only enforce when explicitly checking for deployment readiness
    # or in production (DEBUG=False)
    if settings.DEBUG:
        return errors

    # At this point we're in production mode or running deployment checks
    required_settings = {
        "STRIPE_SECRET_KEY": ("Stripe secret key", "payments.E001"),
        "STRIPE_PUBLISHABLE_KEY": ("Stripe publishable key", "payments.E002"),
        "STRIPE_WEBHOOK_SECRET": ("Stripe webhook signing secret", "payments.E003"),
    }

    for setting_name, (description, error_id) in required_settings.items():
        value = getattr(settings, setting_name, None)
        if not value or value == "":
            errors.append(
                Error(
                    f"{description} is not configured",
                    hint=f"Set {setting_name} in environment variables",
                    id=error_id,
                )
            )

    # Warn if webhook secret looks like test mode in production
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
