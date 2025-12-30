import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from lms.models import EnrollmentRecord
from payments.emails import send_refund_confirmation
from payments.models import Payment

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


def _get_enrollment_from_session(session: dict) -> EnrollmentRecord | None:
    metadata = session.get("metadata") or {}
    enrollment_id = metadata.get("enrollment_record_id")
    if enrollment_id:
        enrollment = (
            EnrollmentRecord.objects.select_related("product", "product__course")
            .filter(id=enrollment_id)
            .first()
        )
        if enrollment:
            return enrollment

    session_id = session.get("id")
    if session_id:
        return (
            EnrollmentRecord.objects.select_related("product", "product__course")
            .filter(stripe_checkout_session_id=session_id)
            .first()
        )
    return None


def _get_payment_for_enrollment(
    enrollment: EnrollmentRecord | None, session: dict
) -> Payment | None:
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
        return (
            Payment.objects.filter(enrollment_record=enrollment)
            .order_by("-created_at")
            .first()
        )

    return None


def handle_checkout_session_completed(event: dict) -> None:
    """Process successful checkout session completion.

    Activates enrollment and creates CourseEnrollment after successful payment.
    Only processes enrollments in PENDING_PAYMENT or PAYMENT_FAILED status.
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

    # Validate enrollment status before processing
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

    payment = _get_payment_for_enrollment(enrollment, session)
    amount_total = _cents_to_decimal(session.get("amount_total"))
    payment_intent = session.get("payment_intent") or ""
    session_id = session.get("id")

    with transaction.atomic():
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
            payment_updates = ["status", "stripe_event_id", "failure_reason"]
            payment.status = Payment.Status.SUCCEEDED
            payment.stripe_event_id = event.get("id", "")
            payment.failure_reason = ""
            if session_id and payment.stripe_checkout_session_id != session_id:
                payment.stripe_checkout_session_id = session_id
                payment_updates.append("stripe_checkout_session_id")
            if payment_intent and payment.stripe_payment_intent_id != payment_intent:
                payment.stripe_payment_intent_id = payment_intent
                payment_updates.append("stripe_payment_intent_id")
            payment.save(update_fields=payment_updates)
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

    payment = _get_payment_for_enrollment(enrollment, session)
    failure_reason = session.get("payment_status") or "Async payment failed"

    with transaction.atomic():
        # Only mark as failed if currently pending payment
        if enrollment.status == EnrollmentRecord.Status.PENDING_PAYMENT:
            enrollment.transition_to(EnrollmentRecord.Status.PAYMENT_FAILED)
        else:
            logger.warning(
                "Async payment failed for enrollment not in pending status",
                extra={
                    "event_id": event.get("id"),
                    "enrollment_id": enrollment.id,
                    "current_status": enrollment.status,
                },
            )

        if payment:
            payment.status = Payment.Status.FAILED
            payment.failure_reason = failure_reason
            payment.stripe_event_id = event.get("id", "")
            payment.save(update_fields=["status", "failure_reason", "stripe_event_id"])
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

    # Validate enrollment status before processing refund
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
            payment.status = Payment.Status.REFUNDED
            payment.stripe_event_id = event.get("id", "")
            payment.failure_reason = "Partial refund" if not is_full_refund else ""
            payment.save(update_fields=["status", "stripe_event_id", "failure_reason"])
        return

    with transaction.atomic():
        if is_full_refund:
            if enrollment.status != EnrollmentRecord.Status.REFUNDED:
                enrollment.transition_to(EnrollmentRecord.Status.REFUNDED)
            if enrollment.course_enrollment_id:
                enrollment.course_enrollment.delete()

        payment.status = Payment.Status.REFUNDED
        payment.stripe_event_id = event.get("id", "")
        payment.failure_reason = "Partial refund" if not is_full_refund else ""
        payment.save(update_fields=["status", "stripe_event_id", "failure_reason"])

    # Send refund confirmation email (don't fail webhook if email fails)
    try:
        send_refund_confirmation(
            enrollment,
            refund_amount=refund_amount,
            original_amount=original_amount,
            refund_date=timezone.now(),
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
