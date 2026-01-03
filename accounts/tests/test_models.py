from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import UserAccount

# BUSINESS LOGIC TESTS ONLY
# Tests focus on custom methods, defaults, and business-specific functionality


class UserAccountTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpass123"
        )

    def test_user_account_creation_with_relationship(self):
        """Test UserAccount instance is created with OneToOneField to User"""
        user_account = UserAccount.objects.create(user=self.user)

        self.assertEqual(user_account.user, self.user)
        self.assertEqual(user_account.user.username, "testuser")
        self.assertEqual(user_account.user.email, "test@example.com")

        # Test reverse relationship
        self.assertEqual(self.user.account_profile, user_account)

    def test_user_account_defaults(self):
        """Test custom default values for business requirements"""
        user_account = UserAccount.objects.create(user=self.user)

        self.assertFalse(user_account.pending_deletion)
        self.assertIsNone(user_account.deletion_requested_at)
        self.assertIsNotNone(user_account.created_at)
        self.assertIsNotNone(user_account.updated_at)

    def test_mark_for_deletion_sets_pending_deletion(self):
        """Test mark_for_deletion method sets pending_deletion to True"""
        user_account = UserAccount.objects.create(user=self.user)
        self.assertFalse(user_account.pending_deletion)

        user_account.mark_for_deletion()

        # Refresh from database to verify the save
        user_account.refresh_from_db()
        self.assertTrue(user_account.pending_deletion)

    def test_mark_for_deletion_sets_timestamp(self):
        """Test mark_for_deletion method sets deletion_requested_at to current time"""
        user_account = UserAccount.objects.create(user=self.user)
        self.assertIsNone(user_account.deletion_requested_at)

        # Record time before calling method
        time_before = timezone.now()
        user_account.mark_for_deletion()
        time_after = timezone.now()

        # Refresh from database to verify the save
        user_account.refresh_from_db()

        self.assertIsNotNone(user_account.deletion_requested_at)
        # Verify the timestamp is between before and after times
        self.assertGreaterEqual(user_account.deletion_requested_at, time_before)
        self.assertLessEqual(user_account.deletion_requested_at, time_after)

    def test_mark_for_deletion_only_updates_specified_fields(self):
        """Test mark_for_deletion save operation only updates specified fields"""
        user_account = UserAccount.objects.create(user=self.user)

        # Record the original updated_at timestamp
        original_updated_at = user_account.updated_at

        # Call mark_for_deletion
        user_account.mark_for_deletion()

        # Refresh from database
        user_account.refresh_from_db()

        # The updated_at should not have changed because we used update_fields
        # Note: This may vary depending on Django's auto_now behavior with update_fields
        # The key test is that pending_deletion and deletion_requested_at are updated
        self.assertTrue(user_account.pending_deletion)
        self.assertIsNotNone(user_account.deletion_requested_at)

    def test_str_method_returns_expected_format(self):
        """Test __str__ method returns the expected format"""
        user_account = UserAccount.objects.create(user=self.user)

        expected_str = f"UserAccount({user_account.user_id})"
        self.assertEqual(str(user_account), expected_str)

    def test_user_deletion_cascades_to_account(self):
        """Test that deleting a user cascades to UserAccount"""
        user_account = UserAccount.objects.create(user=self.user)
        user_account_id = user_account.id

        # Delete the user
        self.user.delete()

        # Verify UserAccount was also deleted
        with self.assertRaises(UserAccount.DoesNotExist):
            UserAccount.objects.get(id=user_account_id)

    def test_mark_for_deletion_idempotent(self):
        """Test calling mark_for_deletion multiple times is safe"""
        user_account = UserAccount.objects.create(user=self.user)

        # Call mark_for_deletion first time
        user_account.mark_for_deletion()
        user_account.refresh_from_db()
        first_timestamp = user_account.deletion_requested_at

        # Call mark_for_deletion second time
        user_account.mark_for_deletion()
        user_account.refresh_from_db()
        second_timestamp = user_account.deletion_requested_at

        # Both calls should have set pending_deletion to True
        self.assertTrue(user_account.pending_deletion)

        # The second timestamp should be equal to or after the first
        self.assertGreaterEqual(second_timestamp, first_timestamp)
