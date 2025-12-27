from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from django.contrib.auth import get_user_model


class WagtailLmsSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Link social accounts to existing users for Wagtail LMS enrollments."""

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return

        email = (
            sociallogin.account.extra_data.get("email")
            or sociallogin.user.email
            or ""
        ).strip()
        if not email:
            return

        user_model = get_user_model()
        try:
            user = user_model.objects.get(email__iexact=email)
        except user_model.DoesNotExist:
            return

        sociallogin.connect(request, user)
