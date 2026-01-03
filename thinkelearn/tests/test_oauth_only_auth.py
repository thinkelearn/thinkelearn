"""Tests for OAuth-only authentication surfaces."""

import importlib

import pytest
from django.test import override_settings
from django.urls import clear_url_caches

import thinkelearn.urls as thinkelearn_urls


def reload_urls():
    """Reload URL patterns after settings changes."""
    clear_url_caches()
    importlib.reload(thinkelearn_urls)


@pytest.mark.django_db
def test_login_page_oauth_only(client):
    response = client.get("/accounts/login/")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Continue with Google" in content
    assert "Continue with Microsoft" in content
    assert 'name="password"' not in content
    assert "Forgot your password" not in content


@pytest.mark.django_db
def test_signup_page_oauth_only(client):
    with override_settings(ACCOUNT_ALLOW_REGISTRATION=True):
        reload_urls()
        response = client.get("/accounts/signup/")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Sign up with Google" in content
    assert "Sign up with Microsoft" in content
    assert 'name="password1"' not in content
    assert "Create account" not in content

    reload_urls()


@pytest.mark.django_db
def test_signup_page_closed_message(client):
    with override_settings(ACCOUNT_ALLOW_REGISTRATION=False):
        reload_urls()
        response = client.get("/accounts/signup/")

    if response.status_code == 302:
        follow_response = client.get(response["Location"])
        content = follow_response.content.decode("utf-8")
        assert "Continue with Google" in content
        assert "Continue with Microsoft" in content
        assert "Sign up with Google" not in content
    else:
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "Registration is currently closed." in content
        assert "Sign up with Google" not in content

    reload_urls()


@pytest.mark.django_db
def test_parent_help_page(client):
    response = client.get("/parent-help/")

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Google Family Link" in content
    assert "Microsoft Family Safety" in content
