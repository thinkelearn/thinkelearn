import pytest
from allauth.socialaccount.models import SocialAccount
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.urls import reverse


@pytest.mark.django_db
def test_password_change_oauth_only_user_shows_message(django_user_model):
    user = django_user_model.objects.create_user(
        username="oauth-user",
        email="oauth@example.com",
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    SocialAccount.objects.create(user=user, provider="google", uid="google-1")

    request = RequestFactory().get(reverse("account_change_password"))
    request.user = user
    content = render_to_string("account/password_change.html", request=request)

    assert "Password Not Required" in content
    assert 'name="oldpassword"' not in content
    assert reverse("socialaccount_connections") in content
    assert reverse("account_email") in content


@pytest.mark.django_db
def test_password_change_staff_user_sees_form(client, staff_user):
    client.force_login(staff_user)
    response = client.get(reverse("account_change_password"))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert 'name="oldpassword"' in content
    assert 'name="password1"' in content
    assert 'name="password2"' in content
    assert reverse("account_reset_password") in content


@pytest.mark.django_db
def test_password_set_oauth_only_user_shows_message(django_user_model):
    user = django_user_model.objects.create_user(
        username="oauth-set-user",
        email="oauth-set@example.com",
    )
    user.set_unusable_password()
    user.save(update_fields=["password"])
    SocialAccount.objects.create(user=user, provider="google", uid="google-2")

    request = RequestFactory().get(reverse("account_set_password"))
    request.user = user
    content = render_to_string("account/password_set.html", request=request)

    assert "Password Not Required" in content
    assert 'name="password1"' not in content
    assert reverse("socialaccount_connections") in content
    assert reverse("account_email") in content


@pytest.mark.django_db
def test_password_set_staff_user_sees_form(staff_user):
    request = RequestFactory().get(reverse("account_set_password"))
    request.user = staff_user
    content = render_to_string("account/password_set.html", request=request)

    assert 'name="password1"' in content
    assert 'name="password2"' in content
    assert "Back to Dashboard" in content
    assert 'href="/dashboard/"' in content
