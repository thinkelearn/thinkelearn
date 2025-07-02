from datetime import timedelta

import factory
from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from communications.models import SMSMessage, VoicemailMessage


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user{n}")
    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class VoicemailMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = VoicemailMessage

    recording_url = factory.Faker("url")
    recording_sid = factory.Sequence(lambda n: f"RE{n:032d}")
    caller_number = factory.Faker("phone_number")
    duration = factory.Faker("random_int", min=10, max=300)
    transcription = factory.Faker("text", max_nb_chars=500)


class SMSMessageFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = SMSMessage

    message_sid = factory.Sequence(lambda n: f"SM{n:032d}")
    from_number = factory.Faker("phone_number")
    to_number = factory.Faker("phone_number")
    body = factory.Faker("text", max_nb_chars=160)


class VoicemailMessageTest(TestCase):
    def test_can_create_voicemail(self):
        voicemail = VoicemailMessageFactory()
        self.assertIsInstance(voicemail, VoicemailMessage)
        self.assertTrue(voicemail.recording_sid.startswith("RE"))
        self.assertIsNotNone(voicemail.caller_number)

    def test_voicemail_defaults(self):
        voicemail = VoicemailMessage(
            recording_url="https://example.com/recording.mp3",
            recording_sid="RE123456789",
            caller_number="+1234567890",
        )
        self.assertEqual(voicemail.status, "new")
        self.assertIsNone(voicemail.assigned_to)
        self.assertEqual(voicemail.notes, "")
        self.assertIsNone(voicemail.followed_up_at)

    def test_voicemail_str_method(self):
        voicemail = VoicemailMessageFactory(caller_number="+1234567890")
        str_representation = str(voicemail)
        self.assertIn("+1234567890", str_representation)
        self.assertIn("Voicemail from", str_representation)

    def test_voicemail_status_choices(self):
        valid_statuses = ["new", "in_progress", "completed", "no_action_needed"]
        for status in valid_statuses:
            voicemail = VoicemailMessageFactory(status=status)
            voicemail.full_clean()  # This should not raise ValidationError

    def test_voicemail_assignment(self):
        user = UserFactory()
        voicemail = VoicemailMessageFactory(assigned_to=user)
        self.assertEqual(voicemail.assigned_to, user)

    def test_voicemail_follow_up_tracking(self):
        user = UserFactory()
        follow_up_time = timezone.now()

        voicemail = VoicemailMessageFactory(
            assigned_to=user,
            status="completed",
            followed_up_at=follow_up_time,
            notes="Called back and resolved issue",
        )

        self.assertEqual(voicemail.status, "completed")
        self.assertEqual(voicemail.followed_up_at, follow_up_time)
        self.assertEqual(voicemail.notes, "Called back and resolved issue")

    def test_voicemail_ordering(self):
        # Create voicemails with different timestamps
        older_voicemail = VoicemailMessageFactory()
        older_voicemail.created_at = timezone.now() - timedelta(hours=1)
        older_voicemail.save()

        newer_voicemail = VoicemailMessageFactory()

        voicemails = VoicemailMessage.objects.all()
        self.assertEqual(voicemails.first(), newer_voicemail)
        self.assertEqual(voicemails.last(), older_voicemail)

    def test_recording_sid_unique(self):
        VoicemailMessageFactory(recording_sid="UNIQUE123")

        # Creating another with same recording_sid should fail
        with self.assertRaises((ValueError, Exception)):
            VoicemailMessageFactory(recording_sid="UNIQUE123")


class SMSMessageTest(TestCase):
    def test_can_create_sms(self):
        sms = SMSMessageFactory()
        self.assertIsInstance(sms, SMSMessage)
        self.assertTrue(sms.message_sid.startswith("SM"))
        self.assertIsNotNone(sms.from_number)
        self.assertIsNotNone(sms.to_number)

    def test_sms_defaults(self):
        sms = SMSMessage(
            message_sid="SM123456789",
            from_number="+1234567890",
            to_number="+0987654321",
            body="Test message",
        )
        self.assertEqual(sms.status, "new")
        self.assertIsNone(sms.assigned_to)
        self.assertEqual(sms.notes, "")
        self.assertIsNone(sms.followed_up_at)

    def test_sms_str_method(self):
        sms = SMSMessageFactory(
            from_number="+1234567890",
            body="This is a test message for string representation",
        )
        str_representation = str(sms)
        self.assertIn("+1234567890", str_representation)
        self.assertIn("SMS from", str_representation)
        self.assertIn("This is a test message for string repr", str_representation)

    def test_sms_status_choices(self):
        valid_statuses = ["new", "in_progress", "completed", "no_action_needed"]
        for status in valid_statuses:
            sms = SMSMessageFactory(status=status)
            sms.full_clean()  # This should not raise ValidationError

    def test_sms_assignment(self):
        user = UserFactory()
        sms = SMSMessageFactory(assigned_to=user)
        self.assertEqual(sms.assigned_to, user)

    def test_sms_follow_up_tracking(self):
        user = UserFactory()
        follow_up_time = timezone.now()

        sms = SMSMessageFactory(
            assigned_to=user,
            status="completed",
            followed_up_at=follow_up_time,
            notes="Replied to inquiry via phone call",
        )

        self.assertEqual(sms.status, "completed")
        self.assertEqual(sms.followed_up_at, follow_up_time)
        self.assertEqual(sms.notes, "Replied to inquiry via phone call")

    def test_sms_ordering(self):
        # Create SMS messages with different timestamps
        older_sms = SMSMessageFactory()
        older_sms.created_at = timezone.now() - timedelta(hours=1)
        older_sms.save()

        newer_sms = SMSMessageFactory()

        messages = SMSMessage.objects.all()
        self.assertEqual(messages.first(), newer_sms)
        self.assertEqual(messages.last(), older_sms)

    def test_message_sid_unique(self):
        SMSMessageFactory(message_sid="UNIQUE123")

        # Creating another with same message_sid should fail
        with self.assertRaises((ValueError, Exception)):
            SMSMessageFactory(message_sid="UNIQUE123")

    def test_sms_with_media_url(self):
        sms = SMSMessageFactory(media_url="https://example.com/image.jpg")
        self.assertEqual(sms.media_url, "https://example.com/image.jpg")

    def test_sms_without_media_url(self):
        sms = SMSMessageFactory()
        self.assertEqual(sms.media_url, "")


class CommunicationsModelsIntegrationTest(TestCase):
    def test_both_models_use_same_status_choices(self):
        """Ensure both models have consistent status choices"""
        voicemail_statuses = [choice[0] for choice in VoicemailMessage.STATUS_CHOICES]
        sms_statuses = [choice[0] for choice in SMSMessage.STATUS_CHOICES]

        self.assertEqual(voicemail_statuses, sms_statuses)

    def test_both_models_assignable_to_same_users(self):
        """Test that both message types can be assigned to the same users"""
        user = UserFactory()

        voicemail = VoicemailMessageFactory(assigned_to=user)
        sms = SMSMessageFactory(assigned_to=user)

        self.assertEqual(voicemail.assigned_to, user)
        self.assertEqual(sms.assigned_to, user)

    def test_workflow_simulation(self):
        """Simulate a typical workflow with both message types"""
        staff_user = UserFactory(username="staff_member")

        # Receive voicemail
        voicemail = VoicemailMessageFactory(
            caller_number="+1234567890", transcription="Hi, I need help with my account"
        )
        self.assertEqual(voicemail.status, "new")

        # Assign and start working on it
        voicemail.assigned_to = staff_user
        voicemail.status = "in_progress"
        voicemail.notes = "Customer needs account reset"
        voicemail.save()

        # Receive SMS from same number
        sms = SMSMessageFactory(
            from_number="+1234567890", body="Following up on my voicemail"
        )

        # Link both messages by assigning to same staff
        sms.assigned_to = staff_user
        sms.status = "in_progress"
        sms.save()

        # Complete both
        completion_time = timezone.now()
        voicemail.status = "completed"
        voicemail.followed_up_at = completion_time
        voicemail.save()

        sms.status = "completed"
        sms.followed_up_at = completion_time
        sms.save()

        # Verify workflow
        self.assertEqual(voicemail.status, "completed")
        self.assertEqual(sms.status, "completed")
        self.assertEqual(voicemail.assigned_to, sms.assigned_to)
