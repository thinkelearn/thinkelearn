from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse

from communications.models import SMSMessage, VoicemailMessage
from communications.views import _is_allowed_twilio_recording_url


class TwilioWebhookSecurityTest(TestCase):
    @patch("communications.views.send_voicemail_notification")
    @patch("communications.views._twilio_signature_is_valid", return_value=True)
    def test_voicemail_webhook_accepts_valid_signature(
        self, _signature_check, _send_notification
    ):
        response = self.client.post(
            reverse("communications:voicemail_webhook"),
            {
                "RecordingUrl": "https://api.twilio.com/recordings/abc",
                "RecordingSid": "RE123456",
                "From": "+15555550123",
                "RecordingDuration": "12",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(VoicemailMessage.objects.count(), 1)

    @patch("communications.views._twilio_signature_is_valid", return_value=False)
    def test_voicemail_webhook_rejects_invalid_signature(self, _signature_check):
        response = self.client.post(
            reverse("communications:voicemail_webhook"),
            {
                "RecordingUrl": "https://api.twilio.com/recordings/abc",
                "RecordingSid": "RE123456",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(VoicemailMessage.objects.count(), 0)

    @patch("communications.views.send_sms_notification")
    @patch("communications.views._twilio_signature_is_valid", return_value=True)
    def test_sms_webhook_accepts_valid_signature(
        self, _signature_check, _send_notification
    ):
        response = self.client.post(
            reverse("communications:sms_webhook"),
            {
                "MessageSid": "SM123456",
                "From": "+15555550123",
                "To": "+15555550199",
                "Body": "hello",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SMSMessage.objects.count(), 1)

    @patch("communications.views._twilio_signature_is_valid", return_value=False)
    def test_sms_webhook_rejects_invalid_signature(self, _signature_check):
        response = self.client.post(
            reverse("communications:sms_webhook"),
            {
                "MessageSid": "SM123456",
                "From": "+15555550123",
                "To": "+15555550199",
                "Body": "hello",
            },
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(SMSMessage.objects.count(), 0)


class RecordingAccessSecurityTest(TestCase):
    def setUp(self):
        self.staff_user = User.objects.create_user(
            username="staff",
            email="staff@example.com",
            password="test-pass",
            is_staff=True,
        )
        self.non_staff_user = User.objects.create_user(
            username="learner",
            email="learner@example.com",
            password="test-pass",
        )
        self.voicemail = VoicemailMessage.objects.create(
            recording_url="https://api.twilio.com/recordings/abc",
            recording_sid="RE123456",
            caller_number="+15555550123",
        )

    def test_recording_proxy_is_staff_only(self):
        self.client.force_login(self.non_staff_user)
        response = self.client.get(
            reverse("communications:recording_proxy", args=[self.voicemail.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_recording_proxy_requires_login(self):
        response = self.client.get(
            reverse("communications:recording_proxy", args=[self.voicemail.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_recording_player_is_staff_only(self):
        self.client.force_login(self.non_staff_user)
        response = self.client.get(
            reverse("communications:recording_player", args=[self.voicemail.id])
        )
        self.assertEqual(response.status_code, 404)

    def test_recording_player_requires_login(self):
        response = self.client.get(
            reverse("communications:recording_player", args=[self.voicemail.id])
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_recording_proxy_blocks_untrusted_recording_host(self):
        self.voicemail.recording_url = "https://example.com/fake.wav"
        self.voicemail.save(update_fields=["recording_url"])
        self.client.force_login(self.staff_user)

        with patch("communications.views.requests.get") as mock_get:
            response = self.client.get(
                reverse("communications:recording_proxy", args=[self.voicemail.id])
            )

        self.assertEqual(response.status_code, 404)
        mock_get.assert_not_called()

    @patch("communications.views.requests.get")
    def test_recording_proxy_blocks_redirect_responses(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 302
        mock_response.headers = {"location": "https://evil.example/target.wav"}
        mock_get.return_value = mock_response

        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("communications:recording_proxy", args=[self.voicemail.id])
        )

        self.assertEqual(response.status_code, 404)
        self.assertFalse(mock_response.raise_for_status.called)

    @patch("communications.views.requests.get")
    def test_recording_proxy_streams_from_trusted_twilio_host(self, mock_get):
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None
        mock_response.headers = {"content-type": "audio/wav", "content-length": "6"}
        mock_response.iter_content.return_value = [b"abc", b"def"]
        mock_get.return_value = mock_response

        self.client.force_login(self.staff_user)
        response = self.client.get(
            reverse("communications:recording_proxy", args=[self.voicemail.id])
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(b"".join(response.streaming_content), b"abcdef")
        self.assertEqual(response["Content-Type"], "audio/wav")


class TwilioRecordingHostAllowlistTest(TestCase):
    @override_settings(TWILIO_RECORDING_ALLOWED_HOSTS=("api.twilio.com",))
    def test_exact_host_mode_does_not_allow_subdomain_by_default(self):
        self.assertFalse(
            _is_allowed_twilio_recording_url(
                "https://sub.api.twilio.com/2010-04-01/Accounts/AC/Recordings/RE"
            )
        )

    @override_settings(TWILIO_RECORDING_ALLOWED_HOSTS=(".api.twilio.com",))
    def test_wildcard_mode_allows_subdomains_when_explicit(self):
        self.assertTrue(
            _is_allowed_twilio_recording_url(
                "https://sub.api.twilio.com/2010-04-01/Accounts/AC/Recordings/RE"
            )
        )
