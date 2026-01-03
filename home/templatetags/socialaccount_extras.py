"""Template filters for social account display."""

from django import template

register = template.Library()


@register.filter
def social_account_display_name(social_account):
    """
    Extract a user-friendly display name from a social account.

    For Microsoft accounts, tries: mail, userPrincipalName
    For other accounts, tries: email
    Falls back to uid if nothing else is available.
    """
    extra_data = social_account.extra_data or {}

    if social_account.provider == "microsoft":
        # Microsoft-specific fields (ordered by preference)
        return (
            extra_data.get("mail")
            or extra_data.get("userPrincipalName")
            or extra_data.get("email")
            or social_account.uid
        )

    # For other providers (Google, etc.)
    return extra_data.get("email") or social_account.uid
