from decimal import Decimal

from django.db import models
from django.db.models import F, Q, Sum


class Payment(models.Model):
    """Individual payment transaction record.

    Tracks the lifecycle of a single payment transaction from initiation through
    completion, refund, or failure. Uses both immutable fields (amount) and
    denormalized fields (amount_gross, amount_refunded, amount_net) for performance.

    Fields:
        amount: Initial payment amount from enrollment (immutable, set at creation).
        amount_gross: Calculated gross amount from CHARGE ledger entries (dynamic).
        amount_refunded: Total refunded from REFUND ledger entries (dynamic).
        amount_net: Net amount after refunds/fees (gross - refunded - fees + adjustments).

    The denormalized amount fields are automatically updated via recalculate_totals()
    whenever ledger entries are created or modified. This provides fast queries without
    needing to aggregate ledger entries every time.
    """

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
        choices=Status,
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
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_refunded__lte=F("amount_gross")),
                name="payment_refunded_lte_gross",
            ),
        ]

    def recalculate_totals(self, *, save: bool = True) -> None:
        """Recalculate gross, refunded, and net totals from ledger entries.

        Aggregates all ledger entries by type and updates the denormalized total
        fields on this Payment instance.

        Args:
            save: When True (default), persist the recalculated totals to the
                database using save(update_fields=[...]). When False, update
                the in-memory amount_gross, amount_refunded, and amount_net
                attributes without saving the instance, which can be useful
                for batching updates or handling persistence separately.
        """
        totals = (
            self.ledger_entries.values("entry_type")
            .annotate(total=Sum("amount"))
            .values_list("entry_type", "total")
        )
        by_type = {entry_type: total or Decimal("0") for entry_type, total in totals}

        gross = by_type.get(PaymentLedgerEntry.EntryType.CHARGE, Decimal("0"))
        refunded = by_type.get(PaymentLedgerEntry.EntryType.REFUND, Decimal("0"))
        fee = by_type.get(PaymentLedgerEntry.EntryType.FEE, Decimal("0"))
        adjustment = by_type.get(PaymentLedgerEntry.EntryType.ADJUSTMENT, Decimal("0"))
        net = gross - refunded - fee + adjustment

        self.amount_gross = gross
        self.amount_refunded = refunded
        self.amount_net = net

        if save:
            # Use update_fields to prevent race conditions where other fields
            # might be modified concurrently. Only save the denormalized totals.
            self.save(update_fields=["amount_gross", "amount_refunded", "amount_net"])


class PaymentLedgerEntry(models.Model):
    """Ledger-style entries for payment accounting.

    Each entry records a single money movement (charge, refund, fee, or adjustment)
    in double-entry bookkeeping style. Entries are immutable once created and provide
    a complete audit trail of all payment activity.

    Entry Types:
        CHARGE: Money received from customer (positive amount).
        REFUND: Money returned to customer (positive amount, subtracted in calculations).
        FEE: Processing fees charged by payment provider (positive amount, subtracted).
        ADJUSTMENT: Manual corrections or adjustments (can be positive or negative).

    Fields:
        amount: Transaction amount in the major currency unit (e.g., dollars) stored
            as a Decimal with 2 decimal places.
        net_amount: Amount after Stripe fees deducted (optional, for reconciliation).
        stripe_charge_id: Unique Stripe charge identifier (required for CHARGE entries).
        stripe_refund_id: Unique Stripe refund identifier (required for REFUND entries).
        stripe_balance_transaction_id: Stripe balance transaction ID for reconciliation.

    Constraints:
        - One charge entry per stripe_charge_id (prevents duplicate charge entries).
        - One refund entry per stripe_refund_id (prevents duplicate refund entries).

    These constraints ensure idempotency - processing the same webhook multiple times
    won't create duplicate ledger entries.
    """

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
            models.CheckConstraint(
                condition=(
                    Q(entry_type__in=["charge", "refund", "fee"], amount__gte=0)
                    | Q(entry_type="adjustment")
                ),
                name="ledger_entry_amount_non_negative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(entry_type="charge") & ~Q(stripe_charge_id="")
                    | ~Q(entry_type="charge")
                ),
                name="ledger_entry_charge_requires_stripe_charge_id",
            ),
            models.CheckConstraint(
                condition=(
                    Q(entry_type="refund") & ~Q(stripe_refund_id="")
                    | ~Q(entry_type="refund")
                ),
                name="ledger_entry_refund_requires_stripe_refund_id",
            ),
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

    def __str__(self):
        return f"{self.get_entry_type_display()} - {self.amount} {self.currency}"


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
