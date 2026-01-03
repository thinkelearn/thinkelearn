from unittest.mock import patch

import pytest
from django.utils import timezone

from accounts.models import UserAccount


@pytest.mark.django_db
def test_user_account_creation_links_user(regular_user):
    account = UserAccount.objects.create(user=regular_user)

    assert account.user == regular_user
    assert regular_user.account_profile == account


@pytest.mark.django_db
def test_mark_for_deletion_sets_fields(regular_user):
    account = UserAccount.objects.create(user=regular_user)

    before = timezone.now()
    account.mark_for_deletion()
    after = timezone.now()

    account.refresh_from_db()
    assert account.pending_deletion is True
    assert before <= account.deletion_requested_at <= after


def test_mark_for_deletion_saves_specific_fields(django_user_model):
    user = django_user_model(username="user", email="user@example.com")
    account = UserAccount(user=user)

    with patch.object(UserAccount, "save", autospec=True) as mocked_save:
        account.mark_for_deletion()

    assert account.pending_deletion is True
    assert account.deletion_requested_at is not None
    mocked_save.assert_called_once()
    assert mocked_save.call_args.kwargs["update_fields"] == [
        "pending_deletion",
        "deletion_requested_at",
    ]


@pytest.mark.django_db
def test_user_account_str_includes_user_id(regular_user):
    account = UserAccount.objects.create(user=regular_user)

    assert str(account) == f"UserAccount({regular_user.id})"
