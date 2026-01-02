from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch

import stripe
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from wagtail.models import Page

from lms.models import (
    CourseProduct,
    CoursesIndexPage,
    EnrollmentRecord,
    ExtendedCoursePage,
)
from payments.models import Payment, PaymentLedgerEntry, WebhookEvent


class StripeWebhookTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="stripehook", email="stripehook@example.com", password="pass"
        )
        root_page = Page.add_root(title="Root")
        courses_index = CoursesIndexPage(title="Courses", slug="courses")
        root_page.add_child(instance=courses_index)

        self.course = ExtendedCoursePage(
            title="Webhook Course",
            slug="webhook-course",
            difficulty="beginner",
            is_published=True,
        )
        courses_index.add_child(instance=self.course)
        self.course.save_revision().publish()

        self.product = CourseProduct.objects.create(
            course=self.course,
            pricing_type=CourseProduct.PricingType.FIXED,
            fixed_price=Decimal("49.00"),
        )
        self.url = reverse("payments:stripe_webhook")

    def _post_webhook(self, event_data):
        mock_event = Mock()
        mock_event.to_dict.return_value = event_data
        with patch(
            "payments.views.stripe.Webhook.construct_event", return_value=mock_event
        ):
            return self.client.post(
                self.url,
                data=b"{}",
                content_type="application/json",
                headers={"stripe-signature": "test-signature"},
            )

    def test_webhook_requires_signature(self):
        response = self.client.post(
            self.url, data=b"{}", content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    def test_webhook_invalid_signature(self):
        with patch(
            "payments.views.stripe.Webhook.construct_event",
            side_effect=stripe.error.SignatureVerificationError("Invalid", "sig"),
        ):
            response = self.client.post(
                self.url,
                data=b"{}",
                content_type="application/json",
                headers={"stripe-signature": "invalid"},
            )

        self.assertEqual(response.status_code, 400)

    def test_checkout_session_completed_activates_enrollment(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
        )
        event_data = {
            "id": "evt_success",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_123",
                    "amount_total": 4900,
                    "payment_intent": "pi_123",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertIsNotNone(enrollment.course_enrollment)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.stripe_event_id, "evt_success")
        self.assertEqual(WebhookEvent.objects.count(), 1)

    def test_webhook_idempotency(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
        )
        event_data = {
            "id": "evt_idempotent",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_456",
                    "amount_total": 4900,
                    "payment_intent": "pi_456",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        self._post_webhook(event_data)
        response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(WebhookEvent.objects.count(), 1)
        self.assertEqual(
            EnrollmentRecord.objects.filter(course_enrollment__isnull=False).count(),
            1,
        )

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_refund_fallback_replaced_by_refund_ids(self, mock_send_email):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_refund_fallback",
        )

        fallback_event = {
            "id": "evt_refund_fallback",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_refund_fallback",
                    "payment_intent": "pi_refund_fallback",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                }
            },
        }
        self._post_webhook(fallback_event)

        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, stripe_refund_id="ch_refund_fallback:fallback"
            ).count(),
            1,
        )

        detailed_event = {
            "id": "evt_refund_fallback_details",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_refund_fallback",
                    "payment_intent": "pi_refund_fallback",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                    "refunds": {
                        "data": [
                            {
                                "id": "re_1",
                                "amount": 2000,
                                "currency": "cad",
                                "created": 1_700_000_000,
                                "status": "succeeded",
                            }
                        ]
                    },
                }
            },
        }
        self._post_webhook(detailed_event)

        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, stripe_refund_id="ch_refund_fallback:fallback"
            ).count(),
            0,
        )
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, stripe_refund_id="re_1"
            ).count(),
            1,
        )
        mock_send_email.assert_called()

    def test_async_payment_failed_marks_enrollment_failed(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
        )
        event_data = {
            "id": "evt_failed",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed",
                    "payment_status": "unpaid",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PAYMENT_FAILED)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failure_reason, "unpaid")

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_charge_refunded_revokes_access(self, mock_send_email):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_refund",
        )

        event_data = {
            "id": "evt_refund",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_refund",
                    "payment_intent": "pi_refund",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.REFUNDED)
        self.assertIsNone(enrollment.course_enrollment)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(payment.amount_refunded, Decimal("49.00"))
        self.assertEqual(payment.amount_net, Decimal("0"))
        mock_send_email.assert_called_once()
        _, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["enrollment_id"], enrollment.id)
        self.assertEqual(kwargs["refund_amount"], "49.00")
        self.assertEqual(kwargs["original_amount"], "49.00")
        self.assertIn("refund_date", kwargs)
        self.assertFalse(kwargs["is_partial"])

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_partial_refund_keeps_enrollment_active(self, mock_send_email):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_partial",
        )

        event_data = {
            "id": "evt_partial",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_partial",
                    "payment_intent": "pi_partial",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertEqual(payment.failure_reason, "")
        mock_send_email.assert_called_once()
        _, kwargs = mock_send_email.call_args
        self.assertEqual(kwargs["enrollment_id"], enrollment.id)
        self.assertEqual(kwargs["refund_amount"], "20.00")
        self.assertEqual(kwargs["original_amount"], "49.00")
        self.assertIn("refund_date", kwargs)
        self.assertTrue(kwargs["is_partial"])
        self.assertEqual(payment.amount_refunded, Decimal("20.00"))
        self.assertEqual(payment.amount_net, Decimal("29.00"))
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.REFUND
            ).count(),
            1,
        )

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_refund_outside_window_logs_warning(self, mock_send_email):
        self.product.refund_window_days = 0
        self.product.save(update_fields=["refund_window_days"])

        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        EnrollmentRecord.objects.filter(pk=enrollment.pk).update(
            created_at=timezone.now() - timedelta(days=3)
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_old_refund",
        )

        event_data = {
            "id": "evt_old_refund",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_old_refund",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING"):
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.REFUNDED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        mock_send_email.assert_called_once()

    def test_checkout_completed_enrollment_not_found(self):
        """Test checkout completed webhook when enrollment doesn't exist."""
        event_data = {
            "id": "evt_no_enrollment",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_nonexistent",
                    "amount_total": 4900,
                    "payment_intent": "pi_nonexistent",
                    "metadata": {"enrollment_record_id": "99999"},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("enrollment not found" in log.lower() for log in logs.output)
        )

    def test_checkout_completed_payment_not_found(self):
        """Test checkout completed webhook when payment doesn't exist."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )

        event_data = {
            "id": "evt_no_payment",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_no_payment",
                    "amount_total": 4900,
                    "payment_intent": "pi_no_payment",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()

        # Enrollment should still be activated even without payment record
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertTrue(any("payment not found" in log.lower() for log in logs.output))

    def test_checkout_completed_already_active_enrollment(self):
        """Test checkout completed webhook for already active enrollment."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()  # Already active

        Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
        )

        event_data = {
            "id": "evt_already_active",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_duplicate",
                    "amount_total": 4900,
                    "payment_intent": "pi_duplicate",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()

        # Should log warning and not process duplicate
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertTrue(
            any("not in pending/failed status" in log.lower() for log in logs.output)
        )

    def test_async_payment_failed_enrollment_not_found(self):
        """Test async payment failed webhook when enrollment doesn't exist."""
        event_data = {
            "id": "evt_failed_no_enrollment",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed_nonexistent",
                    "payment_status": "unpaid",
                    "metadata": {"enrollment_record_id": "99999"},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("enrollment not found" in log.lower() for log in logs.output)
        )

    def test_async_payment_failed_already_active(self):
        """Test async payment failed for already active enrollment."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()  # Already active

        event_data = {
            "id": "evt_failed_active",
            "type": "checkout.session.async_payment_failed",
            "data": {
                "object": {
                    "id": "cs_test_failed_active",
                    "payment_status": "unpaid",
                    "metadata": {"enrollment_record_id": str(enrollment.id)},
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()

        # Should not change status from ACTIVE to PAYMENT_FAILED
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
        self.assertTrue(
            any("not in pending status" in log.lower() for log in logs.output)
        )

    def test_refund_payment_not_found(self):
        """Test refund webhook when payment doesn't exist."""
        event_data = {
            "id": "evt_refund_no_payment",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_nonexistent",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(any("payment not found" in log.lower() for log in logs.output))

    def test_refund_missing_payment_intent(self):
        """Test refund webhook missing payment_intent field."""
        event_data = {
            "id": "evt_refund_no_intent",
            "type": "charge.refunded",
            "data": {
                "object": {
                    # Missing payment_intent
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            any("missing payment_intent" in log.lower() for log in logs.output)
        )

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_refund_user_without_email(self, mock_send_email):
        """Test refund email handling when user has no email address."""
        user_no_email = User.objects.create_user(
            username="noemail", email="", password="pass"
        )
        enrollment = EnrollmentRecord.create_for_user(
            user_no_email, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()

        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_no_email",
        )

        event_data = {
            "id": "evt_refund_no_email",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_no_email",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        # Refund should still process successfully
        self.assertEqual(response.status_code, 200)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.REFUNDED)
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

        mock_send_email.assert_called_once()

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_refund_invalid_enrollment_status(self, mock_send_email):
        """Test refund for enrollment in invalid status (not ACTIVE/REFUNDED)."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        # Keep enrollment in PENDING_PAYMENT status

        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_invalid_status",
        )

        event_data = {
            "id": "evt_refund_invalid_status",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "payment_intent": "pi_invalid_status",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                }
            },
        }

        with self.assertLogs("payments.webhooks", level="WARNING") as logs:
            response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        # Payment should be updated, but enrollment status should not change
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT
        )  # Unchanged
        self.assertEqual(payment.status, Payment.Status.REFUNDED)
        self.assertTrue(
            any("not in active/refunded status" in log.lower() for log in logs.output)
        )
        mock_send_email.assert_not_called()

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_refund_ledger_idempotent(self, mock_send_email):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_refund_dupe",
        )
        event_data = {
            "id": "evt_refund_dupe",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_dupe",
                    "payment_intent": "pi_refund_dupe",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                    "refunds": {
                        "data": [
                            {
                                "id": "re_dupe",
                                "amount": 2000,
                                "currency": "cad",
                                "created": int(timezone.now().timestamp()),
                            }
                        ]
                    },
                }
            },
        }
        event_data_retry = {
            **event_data,
            "id": "evt_refund_dupe_retry",
        }

        self._post_webhook(event_data)
        response = self._post_webhook(event_data_retry)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.REFUND
            ).count(),
            1,
        )
        mock_send_email.assert_called()

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_refund_recalculates_totals_on_early_return(self, mock_send_email):
        """Test that recalculate_totals() is called even when enrollment status changes after lock.

        This tests the critical bug where refund ledger entries are created but
        denormalized totals aren't updated when the early return path is taken
        (line 727 in webhooks.py).
        """
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()

        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_early_return",
            stripe_charge_id="ch_early_return",
        )

        # Create initial charge ledger entry
        PaymentLedgerEntry.objects.create(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.CHARGE,
            amount=Decimal("49.00"),
            currency=self.product.currency,
            stripe_charge_id="ch_early_return",
            processed_at=timezone.now(),
        )
        payment.recalculate_totals()
        payment.refresh_from_db()

        # Verify initial state
        self.assertEqual(payment.amount_gross, Decimal("49.00"))
        self.assertEqual(payment.amount_refunded, Decimal("0.00"))
        self.assertEqual(payment.amount_net, Decimal("49.00"))

        # Change enrollment to invalid status before refund webhook
        # This simulates a race condition or admin action
        enrollment.status = EnrollmentRecord.Status.PENDING_PAYMENT
        enrollment.save()

        event_data = {
            "id": "evt_early_return",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_early_return",
                    "payment_intent": "pi_early_return",
                    "amount": 4900,
                    "amount_refunded": 4900,
                    "refunded": True,
                    "refunds": {
                        "data": [
                            {
                                "id": "re_early_return",
                                "amount": 4900,
                                "currency": "cad",
                                "created": int(timezone.now().timestamp()),
                            }
                        ]
                    },
                }
            },
        }

        response = self._post_webhook(event_data)

        enrollment.refresh_from_db()
        payment.refresh_from_db()

        # Verify the webhook succeeded
        self.assertEqual(response.status_code, 200)

        # Verify enrollment status didn't change (invalid status, early return path)
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.PENDING_PAYMENT)

        # Verify payment status was updated
        self.assertEqual(payment.status, Payment.Status.REFUNDED)

        # CRITICAL: Verify denormalized totals were updated despite early return
        # This is the bug being tested - without recalculate_totals() call,
        # these values would be incorrect
        self.assertEqual(payment.amount_gross, Decimal("49.00"))
        self.assertEqual(payment.amount_refunded, Decimal("49.00"))
        self.assertEqual(payment.amount_net, Decimal("0.00"))

        # Verify refund ledger entry was created
        refund_entries = PaymentLedgerEntry.objects.filter(
            payment=payment, entry_type=PaymentLedgerEntry.EntryType.REFUND
        )
        self.assertEqual(refund_entries.count(), 1)
        self.assertEqual(refund_entries.first().amount, Decimal("49.00"))

        # Email should not be sent (invalid enrollment status)
        mock_send_email.assert_not_called()

    def test_charge_succeeded_creates_ledger_entry(self):
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
            stripe_payment_intent_id="pi_charge",
        )
        event_data = {
            "id": "evt_charge",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_123",
                    "payment_intent": "pi_charge",
                    "amount": 4900,
                    "currency": "cad",
                    "created": int(timezone.now().timestamp()),
                }
            },
        }

        response = self._post_webhook(event_data)

        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        self.assertEqual(payment.amount_gross, Decimal("49.00"))
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.CHARGE
            ).count(),
            1,
        )

    def test_charge_succeeded_syncs_stripe_ids(self):
        """Test that charge.succeeded syncs stripe_charge_id and stripe_balance_transaction_id."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
            stripe_payment_intent_id="pi_charge_sync",
        )
        event_data = {
            "id": "evt_charge_sync",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_sync_123",
                    "payment_intent": "pi_charge_sync",
                    "amount": 4900,
                    "currency": "cad",
                    "created": int(timezone.now().timestamp()),
                    "balance_transaction": "txn_balance_123",
                }
            },
        }

        response = self._post_webhook(event_data)

        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        # Verify Stripe metadata was synced
        self.assertEqual(payment.stripe_charge_id, "ch_sync_123")
        self.assertEqual(payment.stripe_balance_transaction_id, "txn_balance_123")
        self.assertEqual(payment.amount_gross, Decimal("49.00"))

    def test_charge_succeeded_idempotency(self):
        """Test that processing charge.succeeded multiple times creates only one ledger entry."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.PROCESSING,
            stripe_payment_intent_id="pi_charge_idem",
        )
        event_data = {
            "id": "evt_charge_idem_1",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_idem_123",
                    "payment_intent": "pi_charge_idem",
                    "amount": 4900,
                    "currency": "cad",
                    "created": int(timezone.now().timestamp()),
                }
            },
        }

        # Process same charge twice with different event IDs
        self._post_webhook(event_data)
        event_data["id"] = "evt_charge_idem_2"  # Different event ID
        response = self._post_webhook(event_data)

        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        # Should only have one charge ledger entry despite two webhook events
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.CHARGE
            ).count(),
            1,
        )
        self.assertEqual(payment.amount_gross, Decimal("49.00"))

    def test_charge_succeeded_already_succeeded_payment(self):
        """Test that charge.succeeded doesn't overwrite status for already-succeeded payments."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,  # Already succeeded
            stripe_payment_intent_id="pi_charge_existing",
        )
        event_data = {
            "id": "evt_charge_existing",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_existing_123",
                    "payment_intent": "pi_charge_existing",
                    "amount": 4900,
                    "currency": "cad",
                    "created": int(timezone.now().timestamp()),
                }
            },
        }

        response = self._post_webhook(event_data)

        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        # Status should remain SUCCEEDED (not overwritten)
        self.assertEqual(payment.status, Payment.Status.SUCCEEDED)
        # Ledger entry should still be created
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.CHARGE
            ).count(),
            1,
        )

    def test_charge_succeeded_failed_payment(self):
        """Test that charge.succeeded doesn't update status for failed payments."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=enrollment.amount_paid,
            currency=self.product.currency,
            status=Payment.Status.FAILED,  # Already failed
            failure_reason="Card declined",
            stripe_payment_intent_id="pi_charge_failed",
        )
        event_data = {
            "id": "evt_charge_failed",
            "type": "charge.succeeded",
            "data": {
                "object": {
                    "id": "ch_failed_123",
                    "payment_intent": "pi_charge_failed",
                    "amount": 4900,
                    "currency": "cad",
                    "created": int(timezone.now().timestamp()),
                }
            },
        }

        response = self._post_webhook(event_data)

        payment.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        # Status should remain FAILED (not overwritten)
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertEqual(payment.failure_reason, "Card declined")
        # Ledger entry should still be created for accounting
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.CHARGE
            ).count(),
            1,
        )

    @patch("payments.webhooks.send_refund_confirmation_email.delay")
    def test_multiple_partial_refunds(self, mock_send_email):
        """Test that multiple partial refunds correctly aggregate in amount_refunded."""
        enrollment = EnrollmentRecord.create_for_user(
            self.user, self.product, amount=Decimal("49.00")
        )
        enrollment.mark_paid()
        payment = Payment.objects.create(
            enrollment_record=enrollment,
            amount=Decimal("49.00"),
            currency=self.product.currency,
            status=Payment.Status.SUCCEEDED,
            stripe_payment_intent_id="pi_multi_refund",
        )

        # First refund: $20.00
        event1 = {
            "id": "evt_refund_1",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_multi",
                    "payment_intent": "pi_multi_refund",
                    "amount": 4900,
                    "amount_refunded": 2000,
                    "refunded": False,
                    "refunds": {
                        "data": [
                            {
                                "id": "re_1",
                                "amount": 2000,
                                "currency": "cad",
                                "created": int(timezone.now().timestamp()),
                            }
                        ]
                    },
                }
            },
        }

        # Second refund: $10.00
        event2 = {
            "id": "evt_refund_2",
            "type": "charge.refunded",
            "data": {
                "object": {
                    "id": "ch_multi",
                    "payment_intent": "pi_multi_refund",
                    "amount": 4900,
                    "amount_refunded": 3000,
                    "refunded": False,
                    "refunds": {
                        "data": [
                            {
                                "id": "re_1",
                                "amount": 2000,
                                "currency": "cad",
                                "created": int(timezone.now().timestamp()),
                            },
                            {
                                "id": "re_2",
                                "amount": 1000,
                                "currency": "cad",
                                "created": int(timezone.now().timestamp()),
                            },
                        ]
                    },
                }
            },
        }

        self._post_webhook(event1)
        self._post_webhook(event2)

        payment.refresh_from_db()

        # Should have 2 separate refund entries
        self.assertEqual(
            PaymentLedgerEntry.objects.filter(
                payment=payment, entry_type=PaymentLedgerEntry.EntryType.REFUND
            ).count(),
            2,
        )

        # Total refunded should be $30.00
        self.assertEqual(payment.amount_refunded, Decimal("30.00"))
        self.assertEqual(payment.amount_net, Decimal("19.00"))
        # Enrollment should still be active (partial refund)
        enrollment.refresh_from_db()
        self.assertEqual(enrollment.status, EnrollmentRecord.Status.ACTIVE)
