import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from lms.models import EnrollmentRecord
from payments.emails import send_refund_confirmation
from payments.models import Payment

logger = logging.getLogger(__name__)


def _cents_to_decimal(amount_cents: int | None) -> Decimal | None:
    if amount_cents is None:
        return None
    return (Decimal(amount_cents) / Decimal("100")).quantize(Decimal("0.01"))


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
        if enrollment.status == EnrollmentRecord.Status.PENDING_PAYMENT:
            enrollment.transition_to(EnrollmentRecord.Status.PAYMENT_FAILED)

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
    is_full_refund = bool(charge.get("refunded")) or refund_amount >= original_amount

    if not enrollment.product.is_refund_eligible(enrollment.created_at):
        logger.warning(
            "Refund processed outside refund window",
            extra={
                "event_id": event.get("id"),
                "enrollment_id": enrollment.id,
                "refund_window_days": enrollment.product.refund_window_days,
            },
        )

    with transaction.atomic():
        if is_full_refund:
            if enrollment.status != EnrollmentRecord.Status.REFUNDED:
                enrollment.transition_to(EnrollmentRecord.Status.REFUNDED)
            if enrollment.course_enrollment_id:
                enrollment.course_enrollment.delete()

        payment.status = Payment.Status.REFUNDED
        payment.stripe_event_id = event.get("id", "")
        payment.failure_reason = (
            "Partial refund"
            if not is_full_refund
            else ""
        )
        payment.save(update_fields=["status", "stripe_event_id", "failure_reason"])

    send_refund_confirmation(
        enrollment,
        refund_amount=refund_amount,
        original_amount=original_amount,
        refund_date=timezone.now(),
        is_partial=not is_full_refund,
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
