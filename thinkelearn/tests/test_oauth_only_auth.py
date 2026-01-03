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


@pytest.mark.django_db
def test_password_set_page_oauth_only_user(client, django_user_model):
    """OAuth-only users should see informational message instead of form."""
    from allauth.socialaccount.models import SocialAccount, SocialApp
    from django.contrib.sites.models import Site

    # Create a social app (required for SocialAccount)
    site = Site.objects.get_current()
    social_app = SocialApp.objects.create(
        provider="google",
        name="Google",
        client_id="test-client-id",
        secret="test-secret",
    )
    social_app.sites.add(site)

    # Create OAuth-only user (no password)
    user = django_user_model.objects.create(
        username="oauth_user",
        email="oauth@example.com",
    )
    user.set_unusable_password()
    user.save()

    # Create social account
    SocialAccount.objects.create(
        user=user,
        provider="google",
        uid="123456",
        extra_data={"email": "oauth@example.com", "email_verified": True},
    )

    # Log in the user
    client.force_login(user)

    # Access password set page
    response = client.get("/accounts/password/set/")

    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show informational message
    assert "Password Not Required" in content
    assert "OAuth-Only Account" in content
    assert "You sign in using your Google or Microsoft account" in content

    # Should NOT show password form
    assert 'name="password1"' not in content
    assert 'name="password2"' not in content
    assert 'type="submit"' not in content or "Set Password" not in content

    # Should show navigation buttons
    assert "Manage Social Accounts" in content
    assert "Back to Account Settings" in content


@pytest.mark.django_db
def test_password_set_page_staff_user_with_password(client, django_user_model):
    """Staff users with passwords get redirected to password change page."""
    # Create staff user with password
    user = django_user_model.objects.create_user(
        username="staff_user",
        email="staff@example.com",
        password="oldpass123",  # nosec
        is_staff=True,
    )

    # Log in the user
    client.force_login(user)

    # Access password set page - should redirect to password change
    response = client.get("/accounts/password/set/")

    # Users with passwords are redirected to password change page
    assert response.status_code == 302
    assert response.url == "/accounts/password/change/"

    # Follow redirect
    response = client.get(response.url)
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show password change form (not password set)
    assert "Change Password" in content
    assert 'name="oldpassword"' in content
    assert 'name="password1"' in content
    assert 'name="password2"' in content

    # Should NOT show OAuth message
    assert "Password Not Required" not in content
    assert "OAuth-Only Account" not in content


@pytest.mark.django_db
def test_password_set_page_user_without_password_no_oauth(client, django_user_model):
    """Users without password and no OAuth should see the password set form."""
    # Create user without password (e.g., created by admin)
    user = django_user_model.objects.create(
        username="nopass_user",
        email="nopass@example.com",
    )
    user.set_unusable_password()
    user.save()

    # Log in the user (no social account)
    client.force_login(user)

    # Access password set page
    response = client.get("/accounts/password/set/")

    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should show password set form (no OAuth message)
    assert "Set Password" in content
    assert 'name="password1"' in content
    assert 'name="password2"' in content
    assert "Password requirements:" in content

    # Should NOT show OAuth message (no social accounts)
    assert "Password Not Required" not in content
    assert "OAuth-Only Account" not in content


@pytest.mark.django_db
def test_password_set_navigation_oauth_user(client, django_user_model):
    """Navigation buttons should work correctly for OAuth users."""
    from allauth.socialaccount.models import SocialAccount, SocialApp
    from django.contrib.sites.models import Site

    # Create a social app
    site = Site.objects.get_current()
    social_app = SocialApp.objects.create(
        provider="google",
        name="Google",
        client_id="test-client-id",
        secret="test-secret",
    )
    social_app.sites.add(site)

    # Create OAuth-only user
    user = django_user_model.objects.create(
        username="oauth_user2",
        email="oauth2@example.com",
    )
    user.set_unusable_password()
    user.save()

    SocialAccount.objects.create(
        user=user,
        provider="google",
        uid="789012",
        extra_data={"email": "oauth2@example.com", "email_verified": True},
    )

    # Log in the user
    client.force_login(user)

    # Access password set page
    response = client.get("/accounts/password/set/")
    content = response.content.decode("utf-8")

    # Check for navigation links (allauth uses /accounts/3rdparty/ for social connections)
    assert 'href="/accounts/3rdparty/"' in content or 'href="/accounts/social/connections/"' in content
    assert 'href="/accounts/email/"' in content


@pytest.mark.django_db
def test_password_set_navigation_staff_user(client, django_user_model):
    """Navigation buttons should work correctly for staff users."""
    # Create staff user with password
    user = django_user_model.objects.create_user(
        username="staff_user2",
        email="staff2@example.com",
        password="pass123",  # nosec
        is_staff=True,
    )

    # Log in the user
    client.force_login(user)

    # Access password set page - will redirect to password change
    response = client.get("/accounts/password/set/", follow=True)
    assert response.status_code == 200
    content = response.content.decode("utf-8")

    # Should be on password change page
    assert "Change Password" in content
    # Check for back link on password change page
    assert 'href="/accounts/email/"' in content or "Back to Account Settings" in content
