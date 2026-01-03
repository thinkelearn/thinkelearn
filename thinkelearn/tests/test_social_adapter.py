"""
Tests for SocialAccountAdapter.

Verifies email extraction from OAuth providers (Google, Microsoft)
and automatic account linking for social authentication.

Trust model: OAuth providers are implicitly trusted for email verification.
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


class TestGetEmailCandidate:
    """Test suite for _get_email_candidate static method."""

    def test_google_email_in_extra_data(self, adapter, mock_sociallogin):
        """Should return email from extra_data for Google."""
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "email_verified": True,
        }

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "user@example.com"

    def test_microsoft_mail_field(self, adapter, mock_sociallogin):
        """Should extract email from 'mail' field (Microsoft)."""
        mock_sociallogin.account.extra_data = {
            "mail": "f.villegas@thinkelearn.com",
            "userPrincipalName": "f.villegas@thinkelearn.com",
        }

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "f.villegas@thinkelearn.com"

    def test_microsoft_user_principal_name(self, adapter, mock_sociallogin):
        """Should fall back to userPrincipalName when mail is missing."""
        mock_sociallogin.account.extra_data = {"userPrincipalName": "user@company.com"}

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "user@company.com"

    def test_preferred_username_fallback(self, adapter, mock_sociallogin):
        """Should use preferred_username if available."""
        mock_sociallogin.account.extra_data = {"preferred_username": "user@example.com"}

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "user@example.com"

    def test_email_from_user_object(self, adapter, mock_sociallogin):
        """Should fall back to user.email when extra_data is empty."""
        mock_sociallogin.account.extra_data = {}
        mock_sociallogin.user.email = "user@example.com"

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "user@example.com"

    def test_email_normalization(self, adapter, mock_sociallogin):
        """Should normalize email (lowercase, trim whitespace)."""
        mock_sociallogin.account.extra_data = {"email": "  User@Example.COM  "}

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "user@example.com"

    def test_missing_email_returns_empty(self, adapter, mock_sociallogin):
        """Should return empty string when no email is present."""
        mock_sociallogin.account.extra_data = {}
        mock_sociallogin.user.email = ""

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == ""

    def test_none_email_returns_empty(self, adapter, mock_sociallogin):
        """Should handle None email gracefully."""
        mock_sociallogin.account.extra_data = {"email": None}
        mock_sociallogin.user.email = None

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == ""

    def test_microsoft_field_priority(self, adapter, mock_sociallogin):
        """Should prioritize 'email' over 'mail' if both present."""
        mock_sociallogin.account.extra_data = {
            "email": "first@example.com",
            "mail": "second@example.com",
        }

        email = adapter._get_email_candidate(mock_sociallogin)

        assert email == "first@example.com"


@pytest.mark.django_db
class TestPreSocialLogin:
    """
    Test suite for pre_social_login method.

    Trust model: OAuth providers are implicitly trusted, so we connect
    accounts based on email match without requiring verification flags.
    """

    def test_existing_social_login_skipped(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should skip processing when social login already exists."""
        mock_sociallogin.is_existing = True
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should not attempt to connect
        mock_sociallogin.connect.assert_not_called()

    def test_no_email_skipped(self, adapter, mock_request, mock_sociallogin):
        """Should skip processing when no email is available."""
        mock_sociallogin.account.extra_data = {}
        mock_sociallogin.user.email = ""
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should not attempt to connect
        mock_sociallogin.connect.assert_not_called()

    def test_no_matching_user_skipped(self, adapter, mock_request, mock_sociallogin):
        """Should skip processing when no matching user exists."""
        mock_sociallogin.account.extra_data = {
            "email": "nonexistent@example.com",
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should not attempt to connect
        mock_sociallogin.connect.assert_not_called()

    def test_matching_user_connects_google(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should connect Google login to existing user with matching email."""
        user = User.objects.create_user(
            username="user@example.com",
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

    def test_matching_user_connects_microsoft(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should connect Microsoft login to existing user with matching email."""
        user = User.objects.create_user(
            username="microsoft@example.com",
            email="microsoft@example.com",
            password="testpass123",
        )

        # Microsoft uses 'mail' field
        mock_sociallogin.account.extra_data = {
            "mail": "microsoft@example.com",
            "userPrincipalName": "microsoft@example.com",
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should connect to existing user
        mock_sociallogin.connect.assert_called_once_with(mock_request, user)

    def test_case_insensitive_user_matching(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should match user by email case-insensitively."""
        user = User.objects.create_user(
            username="casetest@example.com",
            email="casetest@example.com",
            password="testpass123",
        )

        # Social login provides uppercase email
        mock_sociallogin.account.extra_data = {
            "email": "CaseTest@Example.COM",
        }
        mock_sociallogin.connect = Mock()

        adapter.pre_social_login(mock_request, mock_sociallogin)

        # Should still connect to existing user
        mock_sociallogin.connect.assert_called_once_with(mock_request, user)


@pytest.mark.django_db
class TestPopulateUser:
    """Test suite for populate_user method (sets username = email)."""

    def test_sets_username_from_email_google(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should set username = email for Google OAuth."""
        mock_sociallogin.account.extra_data = {
            "email": "user@example.com",
            "email_verified": True,
        }

        user = adapter.populate_user(mock_request, mock_sociallogin, {})

        assert user.email == "user@example.com"
        assert user.username == "user@example.com"

    def test_sets_username_from_email_microsoft(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should set username = email for Microsoft OAuth."""
        mock_sociallogin.account.extra_data = {
            "mail": "f.villegas@thinkelearn.com",
            "userPrincipalName": "f.villegas@thinkelearn.com",
        }

        user = adapter.populate_user(mock_request, mock_sociallogin, {})

        assert user.email == "f.villegas@thinkelearn.com"
        assert user.username == "f.villegas@thinkelearn.com"

    def test_normalizes_email_for_username(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should normalize email (lowercase, trim) for username."""
        mock_sociallogin.account.extra_data = {"email": "  User@Example.COM  "}

        user = adapter.populate_user(mock_request, mock_sociallogin, {})

        assert user.email == "user@example.com"
        assert user.username == "user@example.com"

    def test_fallback_username_when_no_email(
        self, adapter, mock_request, mock_sociallogin
    ):
        """Should generate random username when no email available."""
        mock_sociallogin.account.extra_data = {}
        mock_sociallogin.user.email = ""

        user = adapter.populate_user(mock_request, mock_sociallogin, {})

        # Should have generated a username
        assert user.username.startswith("user_")
        assert len(user.username) == 17  # "user_" + 12 random chars


@pytest.mark.django_db
class TestGenerateUniqueUsername:
    """Test suite for _generate_unique_username static method."""

    def test_generates_unique_username(self, adapter):
        """Should generate a unique username."""
        username = adapter._generate_unique_username(User)

        assert username.startswith("user_")
        assert len(username) == 17  # "user_" + 12 chars

    def test_avoids_collision(self, adapter):
        """Should generate different username if collision occurs."""
        # Create a user with a specific pattern
        User.objects.create_user(
            username="user_testcollision",
            email="test1@example.com",
            password="test123",
        )

        # Generate should avoid collision
        username1 = adapter._generate_unique_username(User)
        username2 = adapter._generate_unique_username(User)

        assert username1 != username2
        assert not User.objects.filter(username=username1).exists()
        assert not User.objects.filter(username=username2).exists()
