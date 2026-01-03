from unittest.mock import Mock

import pytest
from django.test import RequestFactory, override_settings

from thinkelearn.backends.allauth import AccountAdapter, SocialAccountAdapter


@pytest.fixture
def request_factory():
    return RequestFactory()


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
