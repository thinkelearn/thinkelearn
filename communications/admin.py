from django.contrib import admin
from .models import VoicemailMessage, SMSMessage


@admin.register(VoicemailMessage)
class VoicemailMessageAdmin(admin.ModelAdmin):
    list_display = ("caller_number", "duration", "created_at")
    list_filter = ("created_at",)
    search_fields = ("caller_number", "transcription")
    readonly_fields = ("recording_sid", "recording_url", "created_at")
    ordering = ["-created_at"]


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = ("from_number", "to_number", "body_preview", "created_at")
    list_filter = ("created_at",)
    search_fields = ("from_number", "to_number", "body")
    readonly_fields = ("message_sid", "created_at")
    ordering = ["-created_at"]

    @admin.display(description="Message Preview")
    def body_preview(self, obj):
        return obj.body[:50] + "..." if len(obj.body) > 50 else obj.body
