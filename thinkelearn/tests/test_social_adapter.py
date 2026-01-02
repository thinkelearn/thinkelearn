"""
Tests for SocialAccountAdapter.

Verifies email verification logic and automatic account linking
for social authentication (Google OAuth).
"""

from unittest.mock import Mock

import pytest
from allauth.socialaccount.models import SocialLogin
from django.contrib.auth import get_user_model

from thinkelearn.backends.allauth import SocialAccountAdapter

User = get_user_model()


@pytest.fixture
def adapter():
    """Return instance of SocialAccountAdapter."""
    return SocialAccountAdapter()


@pytest.fixture
def mock_request():
    """Return mock HTTP request."""
    return Mock()


@pytest.fixture
def mock_sociallogin():
    """Return mock SocialLogin object with default values."""
    sociallogin = Mock(spec=SocialLogin)
    sociallogin.is_existing = False
    sociallogin.account = Mock()
    sociallogin.account.extra_data = {}
    sociallogin.user = Mock()
    sociallogin.user.email = ""
    sociallogin.email_addresses = []
    return sociallogin


class TestGetVerifiedEmail:
    """Test suite for _get_verified_email static method."""

    def test_email_verified_in_extra_data(self, adapter, mock_sociallogin):
        """Should return email when email_verified is True in extra_data."""
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "email_verified": True,
        }

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == "user@example.com"

    def test_verified_email_in_extra_data(self, adapter, mock_sociallogin):
        """Should return email when verified_email is True in extra_data."""
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "verified_email": True,
        }

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == "user@example.com"

    def test_email_from_user_object_with_verification(self, adapter, mock_sociallogin):
        """Should return email from user object when verified in email_addresses."""
        mock_sociallogin.user.email = "user@example.com"
        mock_sociallogin.account.extra_data = {}

        # Mock email address with verification
        mock_email_address = Mock()
        mock_email_address.email = "user@example.com"
        mock_email_address.verified = True
        mock_sociallogin.email_addresses = [mock_email_address]

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == "user@example.com"

    def test_case_insensitive_email_matching(self, adapter, mock_sociallogin):
        """Should match email addresses case-insensitively."""
        mock_sociallogin.user.email = "User@Example.COM"
        mock_sociallogin.account.extra_data = {}

        # Email address stored in lowercase
        mock_email_address = Mock()
        mock_email_address.email = "user@example.com"
        mock_email_address.verified = True
        mock_sociallogin.email_addresses = [mock_email_address]

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == "User@Example.COM"  # Returns original casing

    def test_email_not_verified_returns_empty(self, adapter, mock_sociallogin):
        """Should return empty string when email is not verified."""
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "email_verified": False,
        }

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == ""

    def test_missing_email_returns_empty(self, adapter, mock_sociallogin):
        """Should return empty string when no email is present."""
        mock_sociallogin.account.extra_data = {}
        mock_sociallogin.user.email = ""

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == ""

    def test_whitespace_trimming(self, adapter, mock_sociallogin):
        """Should trim whitespace from email addresses."""
        mock_sociallogin.account.extra_data = {
            "email": "  user@example.com  ",
            "email_verified": True,
        }

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == "user@example.com"

    def test_none_email_returns_empty(self, adapter, mock_sociallogin):
        """Should handle None email gracefully."""
        mock_sociallogin.account.extra_data = {"email": None}
        mock_sociallogin.user.email = None

        email = adapter._get_verified_email(mock_sociallogin)

        assert email == ""


@pytest.mark.django_db
class TestPreSocialLogin:
    """Test suite for pre_social_login method."""

    def test_existing_social_login_skipped(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should skip processing when social login already exists."""
        mock_sociallogin.is_existing = True
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should not attempt to connect
        mock_sociallogin.connect.assert_not_called()

    def test_no_verified_email_skipped(self, adapter, mock_request, mock_sociallogin):
        """Should skip processing when no verified email is found."""
        mock_sociallogin.account.extra_data = {"email": "user@example.com"}
        # No email_verified or verified_email flag
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should not attempt to connect
        mock_sociallogin.connect.assert_not_called()

    def test_no_matching_user_skipped(self, adapter, mock_request, mock_sociallogin):
        """Should skip processing when no matching user exists."""
        mock_sociallogin.account.extra_data = {
            "email": "nonexistent@example.com",
            "email_verified": True,
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should not attempt to connect
        mock_sociallogin.connect.assert_not_called()

    def test_matching_user_connects(self, adapter, mock_request, mock_sociallogin):
        """Should connect social login to existing user with matching email."""
        # Create existing user (username required by Django's default User model)
        user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="testpass123",
        )

        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "email_verified": True,
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should connect to existing user
        mock_sociallogin.connect.assert_called_once_with(mock_request, user)

    def test_case_insensitive_user_matching(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should match user by email case-insensitively."""
        # Create user with lowercase email (username required by Django's default User model)
        user = User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="testpass123",
        )

        # Social login provides uppercase email
        mock_sociallogin.account.extra_data = {
            "email": "User@Example.COM",
            "email_verified": True,
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should still connect to existing user
        mock_sociallogin.connect.assert_called_once_with(mock_request, user)

    def test_multiple_verification_methods(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should work with both email_verified and verified_email flags."""
        User.objects.create_user(
            username="testuser",
            email="user@example.com",
            password="testpass123",
        )

        # Test with email_verified
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "email_verified": True,
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)
        mock_sociallogin.connect.assert_called_once()
        mock_sociallogin.connect.reset_mock()

        # Test with verified_email
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "verified_email": True,
        }

        adapter.pre_social_login(mock_request, mock_sociallogin)
        mock_sociallogin.connect.assert_called_once()
