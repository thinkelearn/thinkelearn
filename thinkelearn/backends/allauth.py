from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model


class WagtailLmsSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Link verified social accounts to existing users for Wagtail LMS enrollments."""

    @staticmethod
    def _get_verified_email(sociallogin):
        extra_data = sociallogin.account.extra_data
        email = (extra_data.get("email") or sociallogin.user.email or "").strip()
        if not email:
            return ""

        verified = extra_data.get("email_verified") or extra_data.get("verified_email")
        if verified is True:
            return email

        for email_address in sociallogin.email_addresses:
            if email_address.email.lower() == email.lower() and email_address.verified:
                return email

        return ""

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return

        email = self._get_verified_email(sociallogin)
        if not email:
            return

        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return

        sociallogin.connect(request, user)
