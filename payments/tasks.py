from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from celery import shared_task
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from lms.models import EnrollmentRecord
from payments.emails import send_refund_confirmation
from payments.models import WebhookEvent

logger = logging.getLogger(__name__)


@transaction.atomic
def cleanup_abandoned_enrollments(*, cutoff: datetime | None = None) -> int:
    """Cancel pending enrollments older than the cutoff.

    Uses select_for_update to prevent race conditions with webhook processing.
    """
    if cutoff is None:
        cutoff = timezone.now() - timedelta(hours=24)

    # Use select_for_update to lock rows and prevent race conditions
    # with concurrent webhook processing
    pending_qs = EnrollmentRecord.objects.select_for_update().filter(
        status=EnrollmentRecord.Status.PENDING_PAYMENT,
        created_at__lt=cutoff,
    )
    count = pending_qs.update(status=EnrollmentRecord.Status.CANCELLED)
    logger.info(
        "Cancelled abandoned enrollments",
        extra={"count": count, "cutoff": cutoff.isoformat()},
    )
    return count


def _send_refund_confirmation_email(
    *,
    enrollment_id: int,
    refund_amount: Decimal,
    original_amount: Decimal,
    refund_date: datetime,
    is_partial: bool = False,
) -> None:
    """Send refund confirmation email."""
    try:
        enrollment = EnrollmentRecord.objects.select_related(
            "user",
            "product__course",
        ).get(id=enrollment_id)
    except EnrollmentRecord.DoesNotExist:
        logger.warning(
            "EnrollmentRecord not found for refund confirmation email",
            extra={"enrollment_id": enrollment_id},
        )
        return

    send_refund_confirmation(
        enrollment,
        refund_amount=refund_amount,
        original_amount=original_amount,
        refund_date=refund_date,
        is_partial=is_partial,
    )


@shared_task
def send_refund_confirmation_email(
    *,
    enrollment_id: int,
    refund_amount: str,
    original_amount: str,
    refund_date: str,
    is_partial: bool = False,
) -> None:
    """Send refund confirmation email via Celery.

    Args:
        refund_amount: Decimal as string.
        original_amount: Decimal as string.
        refund_date: ISO 8601 datetime string.
    """
    try:
        refund_amount_decimal = Decimal(refund_amount)
        original_amount_decimal = Decimal(original_amount)
    except (InvalidOperation, TypeError) as exc:
        logger.warning(
            "Invalid refund amounts for email task",
            extra={
                "enrollment_id": enrollment_id,
                "refund_amount": refund_amount,
                "original_amount": original_amount,
                "error": str(exc),
            },
        )
        return

    parsed_refund_date = parse_datetime(refund_date)
    if parsed_refund_date is None:
        logger.warning(
            "Invalid refund_date for email task",
            extra={"enrollment_id": enrollment_id, "refund_date": refund_date},
        )
        return

    _send_refund_confirmation_email(
        enrollment_id=enrollment_id,
        refund_amount=refund_amount_decimal,
        original_amount=original_amount_decimal,
        refund_date=parsed_refund_date,
        is_partial=is_partial,
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=2,
    retry_kwargs={"max_retries": 5},
)
def process_stripe_webhook_event(self, webhook_event_id: int) -> None:
    """Process a Stripe webhook event asynchronously with retries."""
    try:
        with transaction.atomic():
            webhook_event = WebhookEvent.objects.select_for_update().get(
                id=webhook_event_id
            )
            if webhook_event.success:
                return
            event_data = webhook_event.raw_event_data
        from payments.webhooks import dispatch_event

        dispatch_event(event_data)

        with transaction.atomic():
            webhook_event = WebhookEvent.objects.select_for_update().get(
                id=webhook_event_id
            )
            webhook_event.success = True
            webhook_event.error_message = ""
            webhook_event.save(update_fields=["success", "error_message"])
    except WebhookEvent.DoesNotExist:
        logger.warning(
            "WebhookEvent missing during async processing",
            extra={"webhook_event_id": webhook_event_id},
        )
    except Exception as exc:
        try:
            with transaction.atomic():
                webhook_event = WebhookEvent.objects.select_for_update().get(
                    id=webhook_event_id
                )
                webhook_event.success = False
                webhook_event.error_message = str(exc)
                webhook_event.save(update_fields=["success", "error_message"])
        except WebhookEvent.DoesNotExist:
            logger.warning(
                "WebhookEvent missing while recording async failure",
                extra={"webhook_event_id": webhook_event_id},
            )
            return
        raise
