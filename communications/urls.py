from django.urls import path
from .views import (
    VoicemailWebhookView,
    SMSWebhookView,
    recording_proxy_view,
    recording_player_view,
)

app_name = "communications"

urlpatterns = [
    # Webhook endpoints
    path("handle-recording/", VoicemailWebhookView.as_view(), name="voicemail_webhook"),
    path(
        "handle-recording",
        VoicemailWebhookView.as_view(),
        name="voicemail_webhook_no_slash",
    ),
    path("sms-webhook/", SMSWebhookView.as_view(), name="sms_webhook"),
    path("sms-webhook", SMSWebhookView.as_view(), name="sms_webhook_no_slash"),
    # Recording access endpoints
    path("recording/<int:voicemail_id>/", recording_proxy_view, name="recording_proxy"),
    path("player/<int:voicemail_id>/", recording_player_view, name="recording_player"),
]
