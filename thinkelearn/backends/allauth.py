import uuid

from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.crypto import get_random_string


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """
    Social auth policy:
    - Always use email as username when available (normalized).
    - If an existing user has the same email, connect the social account to that user.
    - Assume provider is trustworthy; do not require email 'verified' flags.
    """

    @staticmethod
    def _get_email_candidate(sociallogin) -> str:
        extra = sociallogin.account.extra_data or {}
        # Microsoft can send email-like identifiers in multiple places.
        return normalize_email(
            extra.get("email")
            or extra.get("mail")
            or extra.get("preferred_username")
            or extra.get("userPrincipalName")
            or getattr(sociallogin.user, "email", "")
        )

    @staticmethod
    def _generate_unique_username(
        user_model, prefix: str = "user_", length: int = 12
    ) -> str:
        for _ in range(10):
            candidate = f"{prefix}{get_random_string(length=length)}"
            if not user_model.objects.filter(username=candidate).exists():
                return candidate
        return f"{prefix}{uuid.uuid4().hex[:length]}"

    def pre_social_login(self, request, sociallogin):
        # If this social account is already linked, nothing to do.
        if sociallogin.is_existing:
            return

        email = self._get_email_candidate(sociallogin)
        if not email:
            return

        # If there's an existing user with this email, attach the social login to it.
        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return

        sociallogin.connect(request, user)

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)

        email = normalize_email(
            getattr(user, "email", "")
        ) or self._get_email_candidate(sociallogin)
        if email:
            user.email = email
            # Default Django User.username must be unique and non-empty.
            user.username = email
        else:
            # Rare fallback: provider didn't give any usable email
            user_model = get_user_model()
            user.username = self._generate_unique_username(user_model)

        return user


class AccountAdapter(DefaultAccountAdapter):
    """Disable direct signups when registration is closed; auto-fill username from email."""

    def is_open_for_signup(self, request):
        return settings.ACCOUNT_ALLOW_REGISTRATION

    def save_user(self, request, user, form, commit=True):
        user = super().save_user(request, user, form, commit=False)

        email = normalize_email(getattr(user, "email", ""))
        if email:
            user.email = email
            # Always set username = email (don't check if username exists)
            user.username = email
        else:
            # Rare fallback: no email provided
            user_model = get_user_model()
            user.username = SocialAccountAdapter._generate_unique_username(user_model)

        if commit:
            user.save()
        return user
