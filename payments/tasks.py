from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.tasks import task
from django.utils import timezone

from lms.models import EnrollmentRecord
from payments.emails import send_refund_confirmation

logger = logging.getLogger(__name__)


def cleanup_abandoned_enrollments(*, cutoff: datetime | None = None) -> int:
    """Cancel pending enrollments older than the cutoff."""
    if cutoff is None:
        cutoff = timezone.now() - timedelta(hours=24)

    pending_qs = EnrollmentRecord.objects.filter(
        status=EnrollmentRecord.Status.PENDING_PAYMENT,
        created_at__lt=cutoff,
    )
    count = pending_qs.update(status=EnrollmentRecord.Status.CANCELLED)
    logger.info(
        "Cancelled abandoned enrollments",
        extra={"count": count, "cutoff": cutoff.isoformat()},
    )
    return count


@task(run_every=timedelta(hours=24), queue="default")
def cleanup_abandoned_enrollments_task() -> int:
    """Scheduled task to clean up abandoned enrollments."""
    return cleanup_abandoned_enrollments()


@task()
def send_refund_confirmation_task(
    *,
    enrollment_id: int,
    refund_amount: str,
    original_amount: str,
    refund_date: str,
    is_partial: bool = False,
) -> None:
    """Send refund confirmation email asynchronously."""
    enrollment = EnrollmentRecord.objects.select_related(
        "user",
        "product__course",
    ).get(id=enrollment_id)

    refund_amount_decimal = Decimal(refund_amount)
    original_amount_decimal = Decimal(original_amount)

    refund_datetime = datetime.fromisoformat(refund_date)
    if timezone.is_naive(refund_datetime):
        refund_datetime = timezone.make_aware(refund_datetime)

    send_refund_confirmation(
        enrollment,
        refund_amount=refund_amount_decimal,
        original_amount=original_amount_decimal,
        refund_date=refund_datetime,
        is_partial=is_partial,
    )
