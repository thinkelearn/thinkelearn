from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.test import RequestFactory, override_settings

from thinkelearn.backends.allauth import AccountAdapter, SocialAccountAdapter

User = get_user_model()


@pytest.fixture
def request_factory():
    return RequestFactory()


@pytest.fixture
def adapter():
    return AccountAdapter()


def test_is_open_for_signup_allows_when_enabled(request_factory):
    adapter = AccountAdapter()
    request = request_factory.get("/")

    with override_settings(ACCOUNT_ALLOW_REGISTRATION=True):
        assert adapter.is_open_for_signup(request) is True


def test_is_open_for_signup_blocks_when_disabled(request_factory):
    adapter = AccountAdapter()
    request = request_factory.get("/")

    with override_settings(ACCOUNT_ALLOW_REGISTRATION=False):
        assert adapter.is_open_for_signup(request) is False


def test_social_signup_follows_account_registration_setting(request_factory):
    adapter = SocialAccountAdapter()
    request = request_factory.get("/")
    sociallogin = Mock()

    with override_settings(ACCOUNT_ALLOW_REGISTRATION=False):
        assert adapter.is_open_for_signup(request, sociallogin) is False

    with override_settings(ACCOUNT_ALLOW_REGISTRATION=True):
        assert adapter.is_open_for_signup(request, sociallogin) is True


@pytest.mark.django_db
class TestSaveUser:
    """Test suite for AccountAdapter.save_user method (sets username = email)."""

    def test_sets_username_from_email(self, adapter, request_factory):
        """Should set username = email for email signup."""
        request = request_factory.post("/signup/")
        user = User()

        # Create proper form mock with cleaned_data
        mock_form = Mock()
        mock_form.cleaned_data = {"email": "saveuser1@example.com"}

        saved_user = adapter.save_user(request, user, mock_form, commit=True)

        assert saved_user.email == "saveuser1@example.com"
        assert saved_user.username == "saveuser1@example.com"
        assert User.objects.filter(username="saveuser1@example.com").exists()

    def test_normalizes_email_for_username(self, adapter, request_factory):
        """Should normalize email (lowercase, trim) for username."""
        request = request_factory.post("/signup/")
        user = User()

        mock_form = Mock()
        mock_form.cleaned_data = {"email": "  SaveUser2@Example.COM  "}

        saved_user = adapter.save_user(request, user, mock_form, commit=True)

        assert saved_user.email == "saveuser2@example.com"
        assert saved_user.username == "saveuser2@example.com"

    def test_fallback_username_when_no_email(self, adapter, request_factory):
        """Should generate random username when no email provided."""
        request = request_factory.post("/signup/")
        user = User()

        mock_form = Mock()
        mock_form.cleaned_data = {"email": ""}

        saved_user = adapter.save_user(request, user, mock_form, commit=True)

        # Should have generated a username
        assert saved_user.username.startswith("user_")
        assert len(saved_user.username) == 17  # "user_" + 12 random chars

    def test_commit_false_doesnt_save(self, adapter, request_factory):
        """Should not save to database when commit=False."""
        request = request_factory.post("/signup/")
        user = User()

        mock_form = Mock()
        mock_form.cleaned_data = {"email": "saveuser3@example.com"}

        saved_user = adapter.save_user(request, user, mock_form, commit=False)

        assert saved_user.email == "saveuser3@example.com"
        assert saved_user.username == "saveuser3@example.com"
        # Should not be in database
        assert not User.objects.filter(username="saveuser3@example.com").exists()
