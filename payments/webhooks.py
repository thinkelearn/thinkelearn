"""Stripe webhook event handlers for payment processing.

This module implements reliable, idempotent webhook processing for Stripe payment
events using Django's atomic transactions and row-level locking.

ARCHITECTURE:
- Event handlers are dispatched through EVENT_HANDLERS registry
- All handlers are idempotent (safe to retry/replay)
- Database operations use atomic transactions with row-level locking
- Pre-check/lock/re-validate pattern prevents race conditions

RELIABILITY FEATURES:
1. Idempotency: WebhookEvent model (in views.py) prevents duplicate processing
2. Race condition safety: select_for_update() ensures atomic status transitions
3. Graceful degradation: Errors logged but don't fail webhook acknowledgment
4. Email isolation: Email failures don't block critical business logic

STATUS VALIDATION:
All handlers validate enrollment status twice:
1. Pre-check (no lock): Fast rejection of invalid states
2. Post-lock validation: Handles concurrent webhooks that changed status

This prevents invalid state transitions from:
- Out-of-order webhook delivery
- Duplicate webhooks (Stripe retries)
- Manual admin actions during webhook processing
"""

import logging
from datetime import UTC
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from lms.models import EnrollmentRecord
from payments.models import Payment, PaymentLedgerEntry
from payments.tasks import send_refund_confirmation_email

logger = logging.getLogger(__name__)

# Constants for currency conversion
CENTS_IN_DOLLAR = Decimal("100")
DECIMAL_PLACES = Decimal("0.01")


def _cents_to_decimal(amount_cents: int | None) -> Decimal | None:
    """Convert Stripe amount in cents to Decimal dollar amount.

    Args:
        amount_cents: Amount in cents (Stripe format)

    Returns:
        Decimal amount in dollars, or None if input is None
    """
    if amount_cents is None:
        return None
    return (Decimal(amount_cents) / CENTS_IN_DOLLAR).quantize(DECIMAL_PLACES)


def _get_enrollment_from_session(
    session: dict, *, lock: bool = False
) -> EnrollmentRecord | None:
    """Get enrollment record from Stripe session data.

    Args:
        session: Stripe session object
        lock: If True, use select_for_update() to lock the row (requires transaction)

    Returns:
        EnrollmentRecord if found, None otherwise
    """
    metadata = session.get("metadata") or {}
    enrollment_id = metadata.get("enrollment_record_id")

    queryset = EnrollmentRecord.objects.select_related("product", "product__course")
    if lock:
        queryset = queryset.select_for_update()

    if enrollment_id:
        enrollment = queryset.filter(id=enrollment_id).first()
        if enrollment:
            return enrollment

    session_id = session.get("id")
    if session_id:
        return queryset.filter(stripe_checkout_session_id=session_id).first()
    return None


def _get_payment_for_enrollment(
    enrollment: EnrollmentRecord | None, session: dict
) -> Payment | None:
    """Get payment record for enrollment from Stripe session data.

    Tries multiple strategies in priority order:
    1. Match by payment_intent (most reliable)
    2. Match by session_id (also reliable)
    3. Fallback: Find PROCESSING payment for enrollment
    4. Last resort: Latest payment by creation time

    Args:
        enrollment: EnrollmentRecord instance or None
        session: Stripe session dict

    Returns:
        Payment instance if found, None otherwise
    """
    payment_intent = session.get("payment_intent")
    if payment_intent:
        payment = Payment.objects.filter(
            stripe_payment_intent_id=payment_intent
        ).first()
        if payment:
            return payment

    session_id = session.get("id")
    if session_id:
        payment = Payment.objects.filter(stripe_checkout_session_id=session_id).first()
        if payment:
            return payment

    if enrollment:
        # Prefer PROCESSING status (likely current payment)
        payment = (
            Payment.objects.filter(
                enrollment_record=enrollment, status=Payment.Status.PROCESSING
            )
            .order_by("-created_at")
            .first()
        )
        if payment:
            return payment

        # Fallback: Latest payment regardless of status
        return (
            Payment.objects.filter(enrollment_record=enrollment)
            .order_by("-created_at")
            .first()
        )

    return None


def _get_payment_for_charge(charge: dict, *, lock: bool = False) -> Payment | None:
    """Get payment record from Stripe charge data.

    Args:
        charge: Stripe charge object
        lock: If True, use select_for_update() to lock the row (requires transaction)

    Returns:
        Payment if found, None otherwise
    """
    payment_intent = charge.get("payment_intent")
    if not payment_intent:
        return None
    queryset = Payment.objects
    if lock:
        queryset = queryset.select_for_update()
    return queryset.filter(stripe_payment_intent_id=payment_intent).first()


def _timestamp_to_datetime(timestamp: int | None) -> timezone.datetime | None:
    """Convert Unix timestamp to timezone-aware datetime.

    Args:
        timestamp: Unix timestamp in seconds (Stripe format)

    Returns:
        Timezone-aware datetime in UTC, or None if input is None
    """
    if timestamp is None:
        return None
    return timezone.datetime.fromtimestamp(timestamp, tz=UTC)


def _sync_charge_metadata(payment: Payment, charge: dict) -> list[str]:
    """Sync Stripe charge metadata to payment record.

    Updates stripe_charge_id and stripe_balance_transaction_id fields
    if they differ from values in charge object. Does NOT save the payment.

    Args:
        payment: Payment record to update (modified in-place)
        charge: Stripe charge object containing metadata

    Returns:
        List of field names that were updated (for use in save(update_fields=...))
    """
    charge_id = charge.get("id") or ""
    balance_transaction = charge.get("balance_transaction") or ""
    payment_updates = []

    if charge_id and payment.stripe_charge_id != charge_id:
        payment.stripe_charge_id = charge_id
        payment_updates.append("stripe_charge_id")
    if (
        balance_transaction
        and payment.stripe_balance_transaction_id != balance_transaction
    ):
        payment.stripe_balance_transaction_id = balance_transaction
        payment_updates.append("stripe_balance_transaction_id")

    return payment_updates


def _ensure_charge_ledger_entry(payment: Payment, charge: dict) -> None:
    """Create ledger entry for a successful charge.

    Uses idempotent get_or_create with unique Stripe charge ID.

    Args:
        payment: Payment record to add ledger entry to
        charge: Stripe charge object containing transaction details
    """
    charge_id = charge.get("id") or ""
    if not charge_id:
        return

    amount = _cents_to_decimal(charge.get("amount")) or Decimal("0")
    currency = (charge.get("currency") or payment.currency or "CAD").upper()
    net_amount = _cents_to_decimal(charge.get("amount_captured"))
    processed_at = _timestamp_to_datetime(charge.get("created"))

    PaymentLedgerEntry.objects.get_or_create(
        payment=payment,
        entry_type=PaymentLedgerEntry.EntryType.CHARGE,
        stripe_charge_id=charge_id,
        defaults={
            "amount": amount,
            "currency": currency,
            "net_amount": net_amount,
            "stripe_balance_transaction_id": charge.get("balance_transaction") or "",
            "processed_at": processed_at,
            "metadata": {"charge_status": charge.get("status")},
        },
    )


def _ensure_refund_ledger_entries(payment: Payment, charge: dict) -> None:
    """Create or update ledger entries for all refunds on a charge.

    Uses idempotent get_or_create with unique Stripe refund IDs.
    Handles fallback case where refund details are unavailable.

    Args:
        payment: Payment record to add ledger entries to
        charge: Stripe charge object containing refund information
    """
    refunds = (charge.get("refunds") or {}).get("data") or []
    charge_id = charge.get("id") or ""
    if not refunds:
        refund_amount = _cents_to_decimal(charge.get("amount_refunded"))
        if refund_amount and refund_amount > 0:
            # Use composite ID for fallback to avoid unique constraint conflict
            fallback_refund_id = f"{charge_id}:fallback" if charge_id else ""
            PaymentLedgerEntry.objects.get_or_create(
                payment=payment,
                entry_type=PaymentLedgerEntry.EntryType.REFUND,
                stripe_refund_id=fallback_refund_id,
                defaults={
                    "amount": refund_amount,
                    "currency": (
                        charge.get("currency") or payment.currency or "CAD"
                    ).upper(),
                    "stripe_charge_id": charge_id,
                    "stripe_balance_transaction_id": charge.get("balance_transaction")
                    or "",
                    "processed_at": _timestamp_to_datetime(charge.get("created")),
                    "metadata": {"fallback": True},
                },
            )
        return

    fallback_refund_id = f"{charge_id}:fallback" if charge_id else ""
    if fallback_refund_id:
        PaymentLedgerEntry.objects.filter(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.REFUND,
            stripe_refund_id=fallback_refund_id,
        ).delete()

    # Optimize with bulk_create for multiple refunds
    entries_to_create = []
    existing_refund_ids = set(
        PaymentLedgerEntry.objects.filter(
            payment=payment,
            entry_type=PaymentLedgerEntry.EntryType.REFUND,
        ).values_list("stripe_refund_id", flat=True)
    )

    for refund in refunds:
        refund_id = refund.get("id") or ""
        if not refund_id or refund_id in existing_refund_ids:
            continue

        refund_amount = _cents_to_decimal(refund.get("amount")) or Decimal("0")
        refund_currency = (
            refund.get("currency")
            or charge.get("currency")
            or payment.currency
            or "CAD"
        ).upper()

        entries_to_create.append(
            PaymentLedgerEntry(
                payment=payment,
                entry_type=PaymentLedgerEntry.EntryType.REFUND,
                stripe_refund_id=refund_id,
                amount=refund_amount,
                currency=refund_currency,
                stripe_charge_id=charge_id,
                stripe_balance_transaction_id=refund.get("balance_transaction") or "",
                processed_at=_timestamp_to_datetime(refund.get("created")),
                metadata={"status": refund.get("status")},
            )
        )

    if entries_to_create:
        PaymentLedgerEntry.objects.bulk_create(
            entries_to_create,
            ignore_conflicts=True,  # Respects unique constraints
        )


def handle_charge_succeeded(event: dict) -> None:
    """Record successful charge in ledger for accounting."""
    charge = event["data"]["object"]
    payment = _get_payment_for_charge(charge)
    if not payment:
        logger.warning(
            "Charge succeeded but payment not found",
            extra={
                "event_id": event.get("id"),
                "payment_intent": charge.get("payment_intent"),
            },
        )
        return

    with transaction.atomic():
        payment = _get_payment_for_charge(charge, lock=True)
        if not payment:
            return

        # Sync metadata fields and collect all updates for single save
        metadata_updates = _sync_charge_metadata(payment, charge)
        _ensure_charge_ledger_entry(payment, charge)

        # Consolidate all updates into single save operation
        update_fields = ["stripe_event_id"] + metadata_updates

        # Update payment status if applicable
        if payment.status in [Payment.Status.INITIATED, Payment.Status.PROCESSING]:
            payment.status = Payment.Status.SUCCEEDED
            payment.failure_reason = ""
            update_fields.extend(["status", "failure_reason"])

        payment.stripe_event_id = event.get("id", "")
        payment.save(update_fields=update_fields)

        payment.recalculate_totals()


def handle_checkout_session_completed(event: dict) -> None:
    """Process successful checkout session completion.

    Activates enrollment and creates CourseEnrollment after successful payment.
    Only processes enrollments in PENDING_PAYMENT or PAYMENT_FAILED status.

    DESIGN DECISIONS:
    - Pre-check/lock/re-validate pattern: Prevents unnecessary row locking when
      enrollment is in invalid state, while ensuring atomic status changes.
    - Early validation: First check is cheap (no lock), second check (after lock)
      handles race conditions from concurrent webhooks.
    - Row-level locking: Prevents duplicate activations from concurrent webhook
      deliveries (Stripe retries, replay attacks, etc.).
    """
    session = event["data"]["object"]
    enrollment = _get_enrollment_from_session(session)
    if not enrollment:
        logger.warning(
            "Checkout session completed but enrollment not found",
            extra={
                "event_id": event.get("id"),
                "session_id": session.get("id"),
            },
        )
        return

    # Pre-check status to avoid unnecessary locking (performance optimization)
    if enrollment.status not in [
        EnrollmentRecord.Status.PENDING_PAYMENT,
        EnrollmentRecord.Status.PAYMENT_FAILED,
    ]:
        logger.warning(
            "Checkout completed for enrollment not in pending/failed status",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "current_status": enrollment.status,
            },
        )
        return

    amount_total = _cents_to_decimal(session.get("amount_total"))
    payment_intent = session.get("payment_intent") or ""
    session_id = session.get("id")

    with transaction.atomic():
        # Re-fetch with row-level lock to prevent race conditions
        enrollment = _get_enrollment_from_session(session, lock=True)
        if not enrollment:
            logger.error(
                "Enrollment disappeared during webhook processing",
                extra={"event_id": event.get("id"), "session_id": session_id},
            )
            return

        # Re-validate status after acquiring lock
        if enrollment.status not in [
            EnrollmentRecord.Status.PENDING_PAYMENT,
            EnrollmentRecord.Status.PAYMENT_FAILED,
        ]:
            logger.info(
                "Enrollment status changed after acquiring lock (likely processed by concurrent webhook)",
                extra={
                    "event_id": event.get("id"),
                    "enrollment_id": enrollment.id,
                    "current_status": enrollment.status,
                },
            )
            return

        payment = _get_payment_for_enrollment(enrollment, session)

        update_fields = []
        if amount_total is not None and enrollment.amount_paid != amount_total:
            enrollment.amount_paid = amount_total
            update_fields.append("amount_paid")
        if session_id and enrollment.stripe_checkout_session_id != session_id:
            enrollment.stripe_checkout_session_id = session_id
            update_fields.append("stripe_checkout_session_id")
        if payment_intent and enrollment.stripe_payment_intent_id != payment_intent:
            enrollment.stripe_payment_intent_id = payment_intent
            update_fields.append("stripe_payment_intent_id")
        if update_fields:
            enrollment.save(update_fields=update_fields)

        enrollment.mark_paid()

        if payment:
            # Re-fetch payment with row-level lock to prevent concurrent updates
            try:
                locked_payment = Payment.objects.select_for_update().get(id=payment.id)
            except Payment.DoesNotExist:
                logger.warning(
                    "Checkout session completed but payment disappeared during processing",
                    extra={
                        "event_id": event.get("id"),
                        "enrollment_id": enrollment.id,
                        "session_id": session_id,
                    },
                )
            else:
                payment_updates = ["status", "stripe_event_id", "failure_reason"]
                locked_payment.status = Payment.Status.SUCCEEDED
                locked_payment.stripe_event_id = event.get("id", "")
                locked_payment.failure_reason = ""
                if (
                    session_id
                    and locked_payment.stripe_checkout_session_id != session_id
                ):
                    locked_payment.stripe_checkout_session_id = session_id
                    payment_updates.append("stripe_checkout_session_id")
                if (
                    payment_intent
                    and locked_payment.stripe_payment_intent_id != payment_intent
                ):
                    locked_payment.stripe_payment_intent_id = payment_intent
                    payment_updates.append("stripe_payment_intent_id")
                locked_payment.save(update_fields=payment_updates)
        else:
            logger.warning(
                "Checkout session completed but payment not found",
                extra={
                    "event_id": event.get("id"),
                    "enrollment_id": enrollment.id,
                    "session_id": session_id,
                },
            )


def handle_checkout_session_async_payment_failed(event: dict) -> None:
    """Process async payment failure.

    Marks enrollment as PAYMENT_FAILED when payment fails after checkout.
    Only processes enrollments currently in PENDING_PAYMENT status.

    DESIGN DECISIONS:
    - Strict status validation: Only transitions from PENDING_PAYMENT to avoid
      incorrect status changes from late webhooks (e.g., failure webhook arriving
      after successful payment webhook).
    - Pre-check/lock/re-validate: Same pattern as checkout completed for
      consistency and race condition safety.
    """
    session = event["data"]["object"]
    enrollment = _get_enrollment_from_session(session)
    if not enrollment:
        logger.warning(
            "Async payment failed but enrollment not found",
            extra={
                "event_id": event.get("id"),
                "session_id": session.get("id"),
            },
        )
        return

    # Pre-check status to avoid unnecessary locking
    if enrollment.status != EnrollmentRecord.Status.PENDING_PAYMENT:
        logger.warning(
            "Async payment failed for enrollment not in pending status",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "current_status": enrollment.status,
            },
        )
        return

    failure_reason = session.get("payment_status") or "Async payment failed"

    with transaction.atomic():
        # Re-fetch with row-level lock to prevent race conditions
        enrollment = _get_enrollment_from_session(session, lock=True)
        if not enrollment:
            logger.error(
                "Enrollment disappeared during webhook processing",
                extra={
                    "event_id": event.get("id"),
                    "session_id": session.get("id"),
                },
            )
            return

        # Re-validate status after acquiring lock
        if enrollment.status != EnrollmentRecord.Status.PENDING_PAYMENT:
            logger.info(
                "Enrollment status changed after acquiring lock (likely processed by concurrent webhook)",
                extra={
                    "event_id": event.get("id"),
                    "enrollment_id": enrollment.id,
                    "current_status": enrollment.status,
                },
            )
            return

        enrollment.transition_to(EnrollmentRecord.Status.PAYMENT_FAILED)

        payment = _get_payment_for_enrollment(enrollment, session)
        if payment:
            # Re-fetch payment with row-level lock to prevent concurrent updates
            try:
                locked_payment = Payment.objects.select_for_update().get(id=payment.id)
            except Payment.DoesNotExist:
                logger.warning(
                    "Async payment failed but payment disappeared during processing",
                    extra={
                        "event_id": event.get("id"),
                        "enrollment_id": enrollment.id,
                    },
                )
            else:
                locked_payment.status = Payment.Status.FAILED
                locked_payment.failure_reason = failure_reason
                locked_payment.stripe_event_id = event.get("id", "")
                locked_payment.save(
                    update_fields=["status", "failure_reason", "stripe_event_id"]
                )
        else:
            logger.warning(
                "Async payment failed but payment not found",
                extra={
                    "event_id": event.get("id"),
                    "enrollment_id": enrollment.id,
                },
            )


def handle_charge_refunded(event: dict) -> None:
    """Process charge refund webhook.

    Handles both full and partial refunds. Full refunds revoke course access,
    partial refunds keep enrollment active. Sends email confirmation in both cases.
    Only processes refunds for enrollments in ACTIVE or REFUNDED status.

    DESIGN DECISIONS:
    - Email failure isolation: Wrapped in try/except to prevent email delivery
      issues from blocking critical business logic (refund processing).
    - Status-based processing: Only ACTIVE/REFUNDED enrollments trigger full
      processing. Other statuses still update payment records but skip enrollment
      changes to maintain data integrity.
    - No select_related with locks: select_for_update() doesn't support nullable
      outer joins (course_enrollment), so we omit select_related when locking.
    - Partial refund handling: Keeps enrollment ACTIVE and logs as "Partial refund"
      in payment.failure_reason for accounting purposes.
    - CourseEnrollment deletion safety: Try/except handles already-deleted objects
      (e.g., manual admin deletions, concurrent operations).
    """
    charge = event["data"]["object"]
    payment_intent = charge.get("payment_intent")

    if not payment_intent:
        logger.warning(
            "Refund webhook missing payment_intent",
            extra={"event_id": event.get("id")},
        )
        return

    payment = (
        Payment.objects.select_related(
            "enrollment_record",
            "enrollment_record__product",
            "enrollment_record__course_enrollment",
            "enrollment_record__product__course",
            "enrollment_record__user",
        )
        .filter(stripe_payment_intent_id=payment_intent)
        .first()
    )

    if not payment:
        logger.warning(
            "Refund webhook received but payment not found",
            extra={
                "event_id": event.get("id"),
                "payment_intent": payment_intent,
            },
        )
        return

    enrollment = payment.enrollment_record
    refund_amount = _cents_to_decimal(charge.get("amount_refunded")) or Decimal("0")
    original_amount = _cents_to_decimal(charge.get("amount")) or payment.amount
    is_full_refund = bool(charge.get("refunded")) or (
        refund_amount >= original_amount and refund_amount > 0
    )

    if not enrollment.product.is_refund_eligible(enrollment.created_at):
        logger.warning(
            "Refund processed outside refund window",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "refund_window_days": enrollment.product.refund_window_days,
            },
        )

    # Pre-check enrollment status before acquiring lock
    if enrollment.status not in [
        EnrollmentRecord.Status.ACTIVE,
        EnrollmentRecord.Status.REFUNDED,
    ]:
        logger.warning(
            "Refund received for enrollment not in active/refunded status",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "current_status": enrollment.status,
            },
        )
        # Still process payment status update but skip enrollment changes
        with transaction.atomic():
            payment = Payment.objects.select_for_update().get(id=payment.id)

            # Sync metadata fields and collect all updates for single save
            metadata_updates = _sync_charge_metadata(payment, charge)
            _ensure_charge_ledger_entry(payment, charge)
            _ensure_refund_ledger_entries(payment, charge)

            payment.status = Payment.Status.REFUNDED
            payment.stripe_event_id = event.get("id", "")
            payment.failure_reason = ""

            # Consolidate all updates into single save operation
            update_fields = [
                "status",
                "stripe_event_id",
                "failure_reason",
            ] + metadata_updates
            payment.save(update_fields=update_fields)

            payment.recalculate_totals()
        return

    with transaction.atomic():
        # Re-fetch enrollment and payment with row-level locks
        # Note: Can't use select_related with nullable relations when using select_for_update
        enrollment = EnrollmentRecord.objects.select_for_update().get(id=enrollment.id)
        payment = Payment.objects.select_for_update().get(id=payment.id)

        # Sync metadata fields and collect all updates for single save
        metadata_updates = _sync_charge_metadata(payment, charge)
        _ensure_charge_ledger_entry(payment, charge)
        _ensure_refund_ledger_entries(payment, charge)

        # Re-validate status after acquiring lock
        if enrollment.status not in [
            EnrollmentRecord.Status.ACTIVE,
            EnrollmentRecord.Status.REFUNDED,
        ]:
            logger.info(
                "Enrollment status changed after acquiring lock (likely processed by concurrent webhook)",
                extra={
                    "event_id": event.get("id"),
                    "enrollment_id": enrollment.id,
                    "current_status": enrollment.status,
                },
            )
            # Still update payment status
            payment.status = Payment.Status.REFUNDED
            payment.stripe_event_id = event.get("id", "")
            payment.failure_reason = ""

            # Consolidate all updates into single save operation
            update_fields = [
                "status",
                "stripe_event_id",
                "failure_reason",
            ] + metadata_updates
            payment.save(update_fields=update_fields)
            payment.recalculate_totals()
            return

        if is_full_refund:
            if enrollment.status != EnrollmentRecord.Status.REFUNDED:
                enrollment.transition_to(EnrollmentRecord.Status.REFUNDED)
            if enrollment.course_enrollment_id:
                try:
                    enrollment.course_enrollment.delete()
                except ObjectDoesNotExist:
                    logger.warning(
                        "CourseEnrollment already deleted (concurrent deletion or manual admin action)",
                        extra={
                            "enrollment_id": enrollment.id,
                            "course_enrollment_id": enrollment.course_enrollment_id,
                        },
                    )

        payment.status = Payment.Status.REFUNDED
        payment.stripe_event_id = event.get("id", "")
        payment.failure_reason = ""

        # Consolidate all updates into single save operation
        update_fields = [
            "status",
            "stripe_event_id",
            "failure_reason",
        ] + metadata_updates
        payment.save(update_fields=update_fields)

        payment.recalculate_totals()

    # Re-fetch enrollment with related objects for email (avoid N+1 queries)
    # Transaction has committed, so we can use select_related safely
    enrollment = EnrollmentRecord.objects.select_related("user", "product__course").get(
        id=enrollment.id
    )

    # Send refund confirmation email (don't fail webhook if email fails)
    try:
        send_refund_confirmation_email.delay(
            enrollment_id=enrollment.id,
            refund_amount=str(refund_amount),
            original_amount=str(original_amount),
            refund_date=timezone.now().isoformat(),
            is_partial=not is_full_refund,
        )
    except Exception as exc:
        logger.error(
            "Refund confirmation email failed to send",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "error": str(exc),
            },
            exc_info=True,
        )

    if not is_full_refund:
        logger.info(
            "Partial refund processed",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "refund_amount": str(refund_amount),
                "original_amount": str(original_amount),
            },
        )


EVENT_HANDLERS = {
    "checkout.session.completed": handle_checkout_session_completed,
    "checkout.session.async_payment_failed": handle_checkout_session_async_payment_failed,
    "charge.succeeded": handle_charge_succeeded,
    "charge.refunded": handle_charge_refunded,
}


def dispatch_event(event: dict) -> None:
    event_type = event.get("type")
    handler = EVENT_HANDLERS.get(event_type)
    if handler:
        handler(event)
    else:
        logger.info(
            "Unhandled Stripe webhook event",
            extra={"event_id": event.get("id"), "event_type": event_type},
        )
