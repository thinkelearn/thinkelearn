from django.conf import settings
from django.db import models
from django.utils import timezone


class UserAccount(models.Model):
    """Profile extension for parent-requested deletion tracking."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="account_profile",
    )

    pending_deletion = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def mark_for_deletion(self):
        self.pending_deletion = True
        self.deletion_requested_at = timezone.now()
        self.save(update_fields=["pending_deletion", "deletion_requested_at"])

    def __str__(self):
        return f"UserAccount({self.user_id})"
