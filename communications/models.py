from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User


class VoicemailMessage(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("no_action_needed", "No Action Needed"),
    ]

    recording_url = models.URLField()
    recording_sid = models.CharField(max_length=255, unique=True)
    caller_number = models.CharField(max_length=20)
    duration = models.IntegerField(null=True, blank=True)
    transcription = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Staff management fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Staff member assigned to follow up",
    )
    notes = models.TextField(blank=True, help_text="Internal notes for follow-up")
    followed_up_at = models.DateTimeField(
        null=True, blank=True, help_text="When follow-up was completed"
    )

    def __str__(self):
        return f"Voicemail from {self.caller_number} at {self.created_at}"

    class Meta:
        ordering = ["-created_at"]


class SMSMessage(models.Model):
    STATUS_CHOICES = [
        ("new", "New"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
        ("no_action_needed", "No Action Needed"),
    ]

    message_sid = models.CharField(max_length=255, unique=True)
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    body = models.TextField()
    media_url = models.URLField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    # Staff management fields
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="new")
    assigned_to = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Staff member assigned to follow up",
    )
    notes = models.TextField(blank=True, help_text="Internal notes for follow-up")
    followed_up_at = models.DateTimeField(
        null=True, blank=True, help_text="When follow-up was completed"
    )

    def __str__(self):
        return f"SMS from {self.from_number}: {self.body[:50]}..."

    class Meta:
        ordering = ["-created_at"]
