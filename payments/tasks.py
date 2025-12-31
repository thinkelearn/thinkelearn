from __future__ import annotations

import logging
from datetime import datetime, timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from lms.models import EnrollmentRecord
from payments.emails import send_refund_confirmation

logger = logging.getLogger(__name__)


@transaction.atomic
def cleanup_abandoned_enrollments(*, cutoff: datetime | None = None) -> int:
    """Cancel pending enrollments older than the cutoff.

    Uses select_for_update to prevent race conditions with webhook processing.

    Note: This function is called synchronously for now due to django-tasks
    compatibility issues with Wagtail 7.2.1. Background task processing will be
    added when Wagtail supports django-tasks 0.10.0+.
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


def send_refund_confirmation_email(
    *,
    enrollment_id: int,
    refund_amount: Decimal,
    original_amount: Decimal,
    refund_date: datetime,
    is_partial: bool = False,
) -> None:
    """Send refund confirmation email.

    Note: This function is called synchronously for now due to django-tasks
    compatibility issues with Wagtail 7.2.1. Background task processing will be
    added when Wagtail supports django-tasks 0.10.0+.
    """
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
