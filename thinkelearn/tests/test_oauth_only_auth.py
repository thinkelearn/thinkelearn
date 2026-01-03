"""Tests for OAuth-only authentication surfaces."""

import importlib

import pytest
from allauth.socialaccount.models import SocialAccount, SocialApp
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import clear_url_caches

import thinkelearn.urls as thinkelearn_urls

User = get_user_model()


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


@pytest.fixture
def google_social_app(db):
    """Create a Google social app for testing."""
    return SocialApp.objects.create(
        provider="google",
        name="Google",
        client_id="test-client-id",
        secret="test-secret",
    )


@pytest.fixture
def oauth_user(django_user_model, google_social_app):
    """Create an OAuth-only user (with social account, no usable password)."""
    user = django_user_model.objects.create_user(
        username="oauth_user",
        email="oauth@example.com",
    )
    # Set unusable password to simulate OAuth-only user
    user.set_unusable_password()
    user.save()
    
    # Create social account for this user
    SocialAccount.objects.create(
        user=user,
        provider="google",
        uid="123456789",
        extra_data={"email": "oauth@example.com", "email_verified": True},
    )
    
    return user


@pytest.fixture
def password_user(django_user_model):
    """Create a user with a password (e.g., staff user)."""
    return django_user_model.objects.create_user(
        username="password_user",
        email="password@example.com",
        password="testpass123",
        is_staff=True,
    )


@pytest.mark.django_db
def test_password_change_oauth_only_user_sees_info_message(client, oauth_user):
    """OAuth-only users should see informational message instead of password change form."""
    client.force_login(oauth_user)
    response = client.get("/accounts/password/change/")
    
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    
    # Should see OAuth-only messaging
    assert "Password Not Required" in content
    assert "OAuth-Only Account" in content
    assert "You sign in using your Google or Microsoft account" in content
    
    # Should NOT see password form fields
    assert 'name="oldpassword"' not in content
    assert 'name="password1"' not in content
    assert 'name="password2"' not in content
    assert "Current Password" not in content
    assert "New Password" not in content


@pytest.mark.django_db
def test_password_change_oauth_only_user_sees_correct_buttons(client, oauth_user):
    """OAuth-only users should see social account management and back buttons."""
    client.force_login(oauth_user)
    response = client.get("/accounts/password/change/")
    
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    
    # Should see social account management button
    assert "Manage Social Accounts" in content
    assert 'href="/accounts/social/connections/"' in content
    
    # Should see back to account settings button
    assert "Back to Account Settings" in content
    assert 'href="/accounts/email/"' in content
    
    # Should NOT see password change or reset buttons
    assert "Change Password" not in content or content.count("Change Password") == 1  # Only in title
    assert "Reset via email" not in content
    assert "Forgot your password" not in content


@pytest.mark.django_db
def test_password_change_staff_user_sees_form(client, password_user):
    """Staff users with passwords should see the password change form."""
    client.force_login(password_user)
    response = client.get("/accounts/password/change/")
    
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    
    # Should see password change form title and description
    assert "Change Password" in content
    assert "Update your password to keep your account secure" in content
    
    # Should see all password form fields
    assert 'name="oldpassword"' in content
    assert 'name="password1"' in content
    assert 'name="password2"' in content
    assert "Current Password" in content
    assert "New Password" in content
    assert "New Password (again)" in content
    
    # Should see password requirements
    assert "Password requirements:" in content
    assert "at least 8 characters" in content


@pytest.mark.django_db
def test_password_change_staff_user_sees_correct_buttons(client, password_user):
    """Staff users with passwords should see form submit and help buttons."""
    client.force_login(password_user)
    response = client.get("/accounts/password/change/")
    
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    
    # Should see submit button
    assert 'type="submit"' in content
    assert "Change Password" in content
    
    # Should see password reset link
    assert "Forgot your password?" in content
    assert "Reset via email" in content
    assert 'href="/accounts/password/reset/"' in content
    
    # Should see back to account settings link
    assert "Back to Account Settings" in content
    assert 'href="/accounts/email/"' in content
    
    # Should NOT see social account management button
    assert "Manage Social Accounts" not in content


@pytest.mark.django_db
def test_password_change_requires_authentication(client):
    """Password change page should require authentication."""
    response = client.get("/accounts/password/change/")
    
    # Should redirect to login
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]
