from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from .models import VoicemailMessage, SMSMessage


@admin.register(VoicemailMessage)
class VoicemailMessageAdmin(admin.ModelAdmin):
    list_display = (
        "caller_number",
        "status",
        "assigned_to",
        "duration",
        "created_at",
        "has_recording",
    )
    list_filter = ("status", "created_at", "assigned_to")
    search_fields = ("caller_number", "transcription", "notes")
    readonly_fields = ("recording_sid", "recording_url", "created_at", "audio_player")
    ordering = ["-created_at"]

    fieldsets = (
        ("Call Information", {"fields": ("caller_number", "duration", "created_at")}),
        ("Recording", {"fields": ("recording_sid", "recording_url", "audio_player")}),
        (
            "Follow-up Management",
            {"fields": ("status", "assigned_to", "notes", "followed_up_at")},
        ),
        ("Transcription", {"fields": ("transcription",), "classes": ("collapse",)}),
    )

    @admin.display(description="Recording Available", boolean=True)
    def has_recording(self, obj):
        return bool(obj.recording_url)

    @admin.display(description="Audio Player")
    def audio_player(self, obj):
        if not obj.recording_url:
            return "No recording available"

        recording_url = reverse("communications:recording_proxy", args=[obj.id])
        player_url = reverse("communications:recording_player", args=[obj.id])

        return format_html(
            """
            <div style="margin: 10px 0;">
                <audio controls preload="metadata" style="width: 100%; max-width: 400px;">
                    <source src="{}" type="audio/wav">
                    <source src="{}" type="audio/mpeg">
                    Your browser doesn't support audio playback.
                </audio>
                <div style="margin-top: 10px;">
                    <a href="{}" target="_blank" style="background: #ff6600; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px; margin-right: 10px;">
                        🎧 Open Player
                    </a>
                    <a href="{}" download="voicemail_{}.wav" style="background: #6c757d; color: white; padding: 8px 16px; text-decoration: none; border-radius: 4px;">
                        💾 Download
                    </a>
                </div>
            </div>
            """,
            recording_url,
            recording_url,
            player_url,
            recording_url,
            obj.id,
        )


@admin.register(SMSMessage)
class SMSMessageAdmin(admin.ModelAdmin):
    list_display = (
        "from_number",
        "status",
        "assigned_to",
        "body_preview",
        "created_at",
    )
    list_filter = ("status", "created_at", "assigned_to")
    search_fields = ("from_number", "to_number", "body", "notes")
    readonly_fields = ("message_sid", "created_at")
    ordering = ["-created_at"]

    fieldsets = (
        (
            "Message Information",
            {"fields": ("from_number", "to_number", "body", "media_url", "created_at")},
        ),
        (
            "Follow-up Management",
            {"fields": ("status", "assigned_to", "notes", "followed_up_at")},
        ),
        ("Technical Details", {"fields": ("message_sid",), "classes": ("collapse",)}),
    )

    @admin.display(description="Message Preview")
    def body_preview(self, obj):
        return obj.body[:50] + "..." if len(obj.body) > 50 else obj.body
