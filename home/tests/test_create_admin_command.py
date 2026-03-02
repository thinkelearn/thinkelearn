import os
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class CreateAdminCommandSecurityTest(TestCase):
    def test_create_admin_requires_password_env_var(self):
        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "admin",
                "ADMIN_EMAIL": "admin@example.com",
            },
            clear=False,
        ):
            with patch.dict(os.environ, {"ADMIN_PASSWORD": ""}, clear=False):
                with self.assertRaisesMessage(
                    CommandError, "ADMIN_PASSWORD must be set"
                ):
                    call_command("create_admin", "--reset")

    def test_create_admin_succeeds_when_password_is_provided(self):
        with patch.dict(
            os.environ,
            {
                "ADMIN_USERNAME": "secure-admin",
                "ADMIN_EMAIL": "admin@example.com",
                "ADMIN_PASSWORD": "StrongPassword123!",
            },
            clear=False,
        ):
            call_command("create_admin", "--reset")

        user_model = get_user_model()
        self.assertTrue(user_model.objects.filter(username="secure-admin").exists())
