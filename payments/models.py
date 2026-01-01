from decimal import Decimal

from django.db import models
from django.db.models import Q, Sum


class Payment(models.Model):
    """Individual payment transaction record."""

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    enrollment_record = models.ForeignKey(
        "lms.EnrollmentRecord",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_gross = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_refunded = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    amount_net = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    currency = models.CharField(max_length=10, default="CAD")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
    )
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    stripe_charge_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_balance_transaction_id = models.CharField(
        max_length=255, blank=True, db_index=True
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    failure_reason = models.TextField(blank=True)
    stripe_event_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last Stripe event that updated this payment",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]

    def recalculate_totals(self, *, save: bool = True) -> None:
        """Recalculate gross, refunded, and net totals from ledger entries."""
        totals = (
            self.ledger_entries.values("entry_type")
            .annotate(total=Sum("amount"))
            .values_list("entry_type", "total")
        )
        by_type = {entry_type: total or Decimal("0") for entry_type, total in totals}

        gross = by_type.get(PaymentLedgerEntry.EntryType.CHARGE, Decimal("0"))
        refunded = by_type.get(PaymentLedgerEntry.EntryType.REFUND, Decimal("0"))
        fee = by_type.get(PaymentLedgerEntry.EntryType.FEE, Decimal("0"))
        adjustment = by_type.get(
            PaymentLedgerEntry.EntryType.ADJUSTMENT, Decimal("0")
        )
        net = gross - refunded - fee + adjustment

        self.amount_gross = gross
        self.amount_refunded = refunded
        self.amount_net = net

        if save:
            self.save(update_fields=["amount_gross", "amount_refunded", "amount_net"])


class PaymentLedgerEntry(models.Model):
    """Ledger-style entries for payment accounting."""

    class EntryType(models.TextChoices):
        CHARGE = "charge", "Charge"
        REFUND = "refund", "Refund"
        ADJUSTMENT = "adjustment", "Adjustment"
        FEE = "fee", "Fee"

    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="ledger_entries",
    )
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="CAD")
    net_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    stripe_charge_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_refund_id = models.CharField(max_length=255, blank=True, db_index=True)
    stripe_balance_transaction_id = models.CharField(
        max_length=255, blank=True, db_index=True
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-processed_at", "-created_at"]
        indexes = [
            models.Index(fields=["entry_type", "processed_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["entry_type", "stripe_charge_id"],
                condition=Q(entry_type="charge") & ~Q(stripe_charge_id=""),
                name="unique_charge_entry_per_charge_id",
            ),
            models.UniqueConstraint(
                fields=["entry_type", "stripe_refund_id"],
                condition=Q(entry_type="refund") & ~Q(stripe_refund_id=""),
                name="unique_refund_entry_per_refund_id",
            ),
        ]


class WebhookEvent(models.Model):
    """Track processed webhook events for idempotency."""

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)
    raw_event_data = models.JSONField()
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-processed_at"]
        indexes = [
            models.Index(fields=["event_type", "processed_at"]),
        ]
