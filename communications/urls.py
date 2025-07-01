from django.urls import path
from .views import VoicemailWebhookView, SMSWebhookView

app_name = "communications"

urlpatterns = [
    path("handle-recording/", VoicemailWebhookView.as_view(), name="voicemail_webhook"),
    path(
        "handle-recording",
        VoicemailWebhookView.as_view(),
        name="voicemail_webhook_no_slash",
    ),
    path("sms-webhook/", SMSWebhookView.as_view(), name="sms_webhook"),
    path("sms-webhook", SMSWebhookView.as_view(), name="sms_webhook_no_slash"),
]
