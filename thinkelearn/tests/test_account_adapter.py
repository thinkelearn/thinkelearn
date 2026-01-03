"""
Tests for AccountAdapter.

Verifies that the AccountAdapter correctly enforces signup restrictions
based on the ACCOUNT_ALLOW_REGISTRATION setting.
"""

from unittest.mock import Mock

import pytest
from django.test import override_settings

from thinkelearn.backends.allauth import AccountAdapter


@pytest.fixture
def adapter():
    """Return instance of AccountAdapter."""
    return AccountAdapter()


@pytest.fixture
def mock_request():
    """Return mock HTTP request."""
    return Mock()


class TestIsOpenForSignup:
    """Test suite for is_open_for_signup method."""

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=True)
    def test_returns_true_when_registration_allowed(self, adapter, mock_request):
        """Should return True when ACCOUNT_ALLOW_REGISTRATION is True."""
        result = adapter.is_open_for_signup(mock_request)

        assert result is True

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=False)
    def test_returns_false_when_registration_closed(self, adapter, mock_request):
        """Should return False when ACCOUNT_ALLOW_REGISTRATION is False."""
        result = adapter.is_open_for_signup(mock_request)

        assert result is False


@pytest.mark.django_db
class TestSignupPrevention:
    """Test suite for signup prevention when registration is closed."""

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=False)
    def test_direct_signup_prevented_when_closed(self, client):
        """Should prevent direct signups when registration is closed."""
        # Attempt to POST to signup endpoint
        response = client.post(
            "/accounts/signup/",
            {
                "username": "newuser",
                "email": "newuser@example.com",
                "password1": "testpass123!",
                "password2": "testpass123!",
            },
        )

        # Should either redirect or show error, but not create account
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assert not User.objects.filter(username="newuser").exists()

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=True)
    def test_direct_signup_allowed_when_open(self, client):
        """Should allow direct signups when registration is open."""
        # Note: This test verifies that when registration IS open,
        # the adapter allows signup (even though we're using OAuth-only)
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # Get the signup form to check if it's accessible
        response = client.get("/accounts/signup/")

        # Should be accessible when registration is open
        assert response.status_code == 200


@pytest.mark.django_db
class TestSocialAccountSignup:
    """Test suite for social account signups when registration is closed."""

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=False)
    def test_social_signup_flow_accessible_when_registration_closed(self, client):
        """Should allow social account signup flow when registration is closed.

        This test verifies that even when ACCOUNT_ALLOW_REGISTRATION is False,
        users can still initiate OAuth flows (Google/Microsoft) from the login page.
        The social account adapter handles account creation differently and isn't
        blocked by the AccountAdapter.is_open_for_signup check.
        """
        # The login page should be accessible and show OAuth options
        response = client.get("/accounts/login/")

        assert response.status_code == 200
        content = response.content.decode("utf-8")

        # OAuth buttons should still be present
        assert "Continue with Google" in content
        assert "Continue with Microsoft" in content

    @override_settings(ACCOUNT_ALLOW_REGISTRATION=False)
    def test_social_login_endpoints_accessible(self, client):
        """Should allow access to social login endpoints when registration is closed."""
        # Google OAuth endpoint should be accessible
        google_response = client.get("/accounts/google/login/")

        # Should redirect to Google (302) or be accessible (200)
        # The exact behavior depends on allauth configuration
        assert google_response.status_code in [200, 302]

        # Microsoft OAuth endpoint should be accessible
        microsoft_response = client.get("/accounts/microsoft/login/")

        # Should redirect to Microsoft (302) or be accessible (200)
        assert microsoft_response.status_code in [200, 302]
