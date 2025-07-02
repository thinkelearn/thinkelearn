from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from communications.models import SMSMessage, VoicemailMessage

# BUSINESS LOGIC TESTS ONLY
# Tests focus on custom Twilio integration workflows and business-specific functionality


class VoicemailMessageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_voicemail_defaults(self):
        """Test custom default values for business workflow"""
        voicemail = VoicemailMessage(
            recording_url="https://example.com/recording.mp3",
            recording_sid="RE123456789",
            caller_number="+15551234567",
            duration=120,
        )
        # Test custom business defaults
        self.assertEqual(voicemail.status, "new")
        self.assertIsNone(voicemail.assigned_to)

    def test_voicemail_str_method(self):
        """Test custom string representation for business workflow"""
        voicemail = VoicemailMessage.objects.create(
            recording_url="https://example.com/recording.mp3",
            recording_sid="RE123456789",
            caller_number="+15551234567",
            duration=120,
        )
        str_repr = str(voicemail)
        self.assertIn("Voicemail from +15551234567", str_repr)
        self.assertIn("at", str_repr)

    def test_voicemail_status_choices(self):
        """Test custom business status workflow"""
        voicemail = VoicemailMessage(
            recording_url="https://example.com/recording.mp3",
            recording_sid="RE123456789",
            caller_number="+15551234567",
            duration=120,
        )

        # Test business workflow status transitions
        voicemail.status = "new"
        voicemail.save()
        self.assertEqual(voicemail.status, "new")

        voicemail.status = "in_progress"
        voicemail.save()
        self.assertEqual(voicemail.status, "in_progress")

    def test_voicemail_assignment_tracking(self):
        """Test custom assignment workflow logic"""
        voicemail = VoicemailMessage.objects.create(
            recording_url="https://example.com/recording.mp3",
            recording_sid="RE123456789",
            caller_number="+15551234567",
            duration=120,
            assigned_to=self.user,
            notes="Customer inquiry about services",
        )

        self.assertEqual(voicemail.assigned_to, self.user)
        self.assertEqual(voicemail.notes, "Customer inquiry about services")

    def test_voicemail_ordering(self):
        """Test custom ordering for business needs"""
        # Create voicemails with different timestamps
        old_voicemail = VoicemailMessage.objects.create(
            recording_url="https://example.com/old.mp3",
            recording_sid="RE111111111",
            caller_number="+15551111111",
            duration=60,
        )
        old_voicemail.created_at = timezone.now() - timedelta(hours=2)
        old_voicemail.save()

        new_voicemail = VoicemailMessage.objects.create(
            recording_url="https://example.com/new.mp3",
            recording_sid="RE222222222",
            caller_number="+15552222222",
            duration=90,
        )

        # Test business ordering (newest first)
        voicemails = VoicemailMessage.objects.all()
        self.assertEqual(voicemails.first(), new_voicemail)


class SMSMessageTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_sms_defaults(self):
        """Test custom default values for business workflow"""
        sms = SMSMessage(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Test message",
        )
        # Test custom business defaults
        self.assertEqual(sms.status, "new")
        self.assertIsNone(sms.assigned_to)

    def test_sms_str_method(self):
        """Test custom string representation for business workflow"""
        sms = SMSMessage(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Test message content",
        )
        expected = "SMS from +15551234567: Test message content..."
        self.assertEqual(str(sms), expected)

    def test_sms_status_choices(self):
        """Test custom business status workflow"""
        sms = SMSMessage(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Test message",
        )

        # Test business workflow status transitions
        sms.status = "new"
        sms.save()
        self.assertEqual(sms.status, "new")

        sms.status = "completed"
        sms.save()
        self.assertEqual(sms.status, "completed")

    def test_sms_assignment_tracking(self):
        """Test custom assignment workflow logic"""
        sms = SMSMessage.objects.create(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Test message",
            assigned_to=self.user,
            notes="Follow up required",
        )

        self.assertEqual(sms.assigned_to, self.user)
        self.assertEqual(sms.notes, "Follow up required")

    def test_sms_ordering(self):
        """Test custom ordering for business needs"""
        # Create SMS messages with different timestamps
        old_sms = SMSMessage.objects.create(
            message_sid="SM111111111",
            from_number="+15551111111",
            to_number="+15559876543",
            body="Old message",
        )
        old_sms.created_at = timezone.now() - timedelta(hours=1)
        old_sms.save()

        new_sms = SMSMessage.objects.create(
            message_sid="SM222222222",
            from_number="+15552222222",
            to_number="+15559876543",
            body="New message",
        )

        # Test business ordering (newest first)
        messages = SMSMessage.objects.all()
        self.assertEqual(messages.first(), new_sms)

    def test_sms_with_media_url(self):
        """Test custom media handling logic"""
        sms = SMSMessage.objects.create(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Check out this image",
            media_url="https://example.com/image.jpg",
        )

        self.assertEqual(sms.media_url, "https://example.com/image.jpg")
        self.assertIn("image", sms.body)

    def test_sms_without_media_url(self):
        """Test text-only message handling"""
        sms = SMSMessage.objects.create(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Text only message",
        )

        self.assertEqual(
            sms.media_url, ""
        )  # Blank field returns empty string, not None


class CommunicationsModelsIntegrationTest(TestCase):
    def setUp(self):
        self.user1 = User.objects.create_user(
            username="user1", email="user1@example.com", password="testpass123"
        )
        self.user2 = User.objects.create_user(
            username="user2", email="user2@example.com", password="testpass123"
        )

    def test_both_models_use_same_status_choices(self):
        """Test custom business consistency across models"""
        voicemail = VoicemailMessage(
            recording_url="https://example.com/recording.mp3",
            recording_sid="RE123456789",
            caller_number="+15551234567",
            duration=120,
            status="in_progress",
        )

        sms = SMSMessage(
            message_sid="SM123456789",
            from_number="+15551234567",
            to_number="+15559876543",
            body="Test message",
            status="in_progress",
        )

        # Both should use same status values for consistent workflow
        self.assertEqual(voicemail.status, sms.status)

        # Test that both have the same status choices available
        voicemail_choices = [choice[0] for choice in VoicemailMessage.STATUS_CHOICES]
        sms_choices = [choice[0] for choice in SMSMessage.STATUS_CHOICES]
        self.assertEqual(voicemail_choices, sms_choices)

    def test_workflow_simulation(self):
        """Test complete business workflow integration"""
        # Simulate a customer inquiry workflow

        # 1. Customer leaves voicemail
        voicemail = VoicemailMessage.objects.create(
            recording_url="https://example.com/inquiry.mp3",
            recording_sid="RE123456789",
            caller_number="+15551234567",
            duration=180,
            transcription="Hi, I'm interested in your services...",
        )

        # 2. Staff member takes ownership
        voicemail.assigned_to = self.user1
        voicemail.status = "in_progress"
        voicemail.notes = "Customer inquiry - need to call back"
        voicemail.save()

        # 3. Customer sends follow-up SMS
        sms = SMSMessage.objects.create(
            message_sid="SM123456789",
            from_number="+15551234567",  # Same number as voicemail
            to_number="+15559876543",
            body="Following up on my voicemail...",
        )

        # 4. Assign SMS to same staff member for continuity
        sms.assigned_to = self.user1
        sms.status = "completed"
        sms.notes = "Responded to customer inquiry"
        sms.save()

        # Verify workflow state
        self.assertEqual(voicemail.assigned_to, sms.assigned_to)
        self.assertEqual(voicemail.status, "in_progress")
        self.assertEqual(sms.status, "completed")

        # Verify both are from same customer
        self.assertEqual(voicemail.caller_number, sms.from_number)

        # Test follow-up completion
        voicemail.followed_up_at = timezone.now()
        voicemail.status = "completed"
        voicemail.save()

        self.assertIsNotNone(voicemail.followed_up_at)
        self.assertEqual(voicemail.status, "completed")
