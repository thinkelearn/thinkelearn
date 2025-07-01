from django.db import models
from django.utils import timezone


class VoicemailMessage(models.Model):
    recording_url = models.URLField()
    recording_sid = models.CharField(max_length=255, unique=True)
    caller_number = models.CharField(max_length=20)
    duration = models.IntegerField(null=True, blank=True)
    transcription = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Voicemail from {self.caller_number} at {self.created_at}"

    class Meta:
        ordering = ["-created_at"]


class SMSMessage(models.Model):
    message_sid = models.CharField(max_length=255, unique=True)
    from_number = models.CharField(max_length=20)
    to_number = models.CharField(max_length=20)
    body = models.TextField()
    media_url = models.URLField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"SMS from {self.from_number}: {self.body[:50]}..."

    class Meta:
        ordering = ["-created_at"]
