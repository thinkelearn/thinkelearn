# PR #25 Accounting and Reconciliation Review

## payments/admin.py

### High-level summary

Overall shape looks good, especially surfacing the ledger inline, totals, and a refund-state
filter. The critical risk areas are invariants/idempotency and making totals purely derived
from the ledger. Below are PR-style comments with concrete fixes, including model
constraints, webhook write paths, totals recalculation, admin tweaks, and tests to prevent
regressions.

### PR comments

#### RefundStateFilter queryset

- "Full refunds" should use equality, not `gte`. Using `gte` can mislabel over-refunded
  rows (which would indicate a bug) as "full". Keep the exclude for gross=0 as you did to
  avoid classifying free/zero-gross payments as full-refunded.
- Suggested change:
  - replace `amount_refunded__gte=F("amount_gross")` with
    `amount_refunded=F("amount_gross")`
- Rationale: prevents hiding a data integrity problem (over-refund) by classifying it as
  "full".

#### Performance/readability enhancements

- Add `list_select_related` to `PaymentAdmin` for `enrollment_record`,
  `enrollment_record__product`, and `enrollment_record__product__course` to avoid N+1.
- Add `ordering = ("-created_at",)` to keep newest first.
- Add `date_hierarchy = "created_at"`.
- Consider `raw_id_fields = ("enrollment_record",)` or `autocomplete_fields` if configured
  to make searching large datasets manageable.
- Add an admin action "Recalculate totals" to make reconciliation easier for admins.

Example:

```python
class PaymentAdmin(admin.ModelAdmin):
    list_select_related = (
        "enrollment_record",
        "enrollment_record__product",
        "enrollment_record__product__course",
    )
    ordering = ("-created_at",)
    date_hierarchy = "created_at"
    raw_id_fields = ("enrollment_record",)
    actions = ("action_recalculate_totals",)

    def action_recalculate_totals(self, request, queryset):
        updated = 0
        for payment in queryset:
            if hasattr(payment, "recalculate_totals"):
                changed = payment.recalculate_totals(save=True)
                if changed:
                    updated += 1
        self.message_user(request, f"Recalculated totals for {updated} payments.")
```

#### PaymentLedgerEntryInline

- Set `ordering = ("-created_at",)` so the most recent entries are shown first.
- If your model has a `source` or `event_id` field, include it for auditability; if not,
  consider adding to the model (see below).

#### WebhookEventAdmin

- Add `ordering = ("-processed_at",)` and `date_hierarchy = "processed_at"`.
- If `WebhookEvent` is related to `Payment`, add `list_select_related` and
  `raw_id_fields`.

## Model-level comments (payments/models.py)

### PaymentLedgerEntry entry types and constraints

Define explicit entry types and document invariants:

- CHARGE: amount > 0, net_amount between 0 and amount, `stripe_charge_id` required,
  `stripe_refund_id` null.
- REFUND: amount > 0, net_amount between -amount and 0, `stripe_refund_id` required,
  `stripe_charge_id` optional (Stripe links refund to charge).
- Currency invariants: ledger entry currency must equal `payment.currency`.
- Idempotency and uniqueness:
  - `stripe_charge_id` must be globally unique across `PaymentLedgerEntry` where
    entry_type=CHARGE. A charge should not appear on multiple payments.
  - `stripe_refund_id` must be globally unique across `PaymentLedgerEntry` where
    entry_type=REFUND.
  - `stripe_balance_transaction_id` should be globally unique (fees and net are per
    balance transaction).
  - If you support separate FEE entries (not shown in admin fields), ensure uniqueness of
    balance_transaction_id there too. If you don’t, `net_amount` should be sourced from
    the balance transaction on the charge/refund entry itself.
- Processed timestamp: set `processed_at` on creation and make it non-null.

Suggested constraints and indexes:

```python
from django.db.models import Q, UniqueConstraint, CheckConstraint
from django.db.models.functions import Coalesce

class PaymentLedgerEntry(models.Model):
    class EntryType(models.TextChoices):
        CHARGE = "charge", "Charge"
        REFUND = "refund", "Refund"

    payment = models.ForeignKey("Payment", related_name="ledger_entries", on_delete=models.PROTECT)
    entry_type = models.CharField(max_length=16, choices=EntryType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3)
    stripe_charge_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    stripe_refund_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    stripe_balance_transaction_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    processed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            # One of charge or refund ids depending on entry_type
            CheckConstraint(
                name="ple_charge_requires_charge_id",
                check=Q(entry_type="charge", stripe_charge_id__isnull=False) | ~Q(entry_type="charge"),
            ),
            CheckConstraint(
                name="ple_refund_requires_refund_id",
                check=Q(entry_type="refund", stripe_refund_id__isnull=False) | ~Q(entry_type="refund"),
            ),
            CheckConstraint(
                name="ple_no_both_charge_and_refund_id",
                check=~(Q(stripe_charge_id__isnull=False) & Q(stripe_refund_id__isnull=False)),
            ),
            # Positive amount at input
            CheckConstraint(name="ple_amount_positive", check=Q(amount__gt=0)),
            # Currency matches parent Payment
            CheckConstraint(
                name="ple_currency_matches_payment",
                check=Q(currency=F("payment__currency")),
            ),
            # Net amount sign constraints
            CheckConstraint(
                name="ple_net_within_charge_bounds",
                check=Q(entry_type="charge", net_amount__gte=0, net_amount__lte=F("amount"))
                | ~Q(entry_type="charge"),
            ),
            CheckConstraint(
                name="ple_net_within_refund_bounds",
                check=Q(entry_type="refund", net_amount__lte=0, net_amount__gte=-F("amount"))
                | ~Q(entry_type="refund"),
            ),
        ]
        indexes = [
            models.Index(fields=("payment", "created_at")),
            models.Index(fields=("entry_type", "created_at")),
        ]
        constraints += [
            UniqueConstraint(
                fields=["stripe_charge_id"],
                condition=Q(entry_type="charge", stripe_charge_id__isnull=False),
                name="uniq_ple_stripe_charge_id",
            ),
            UniqueConstraint(
                fields=["stripe_refund_id"],
                condition=Q(entry_type="refund", stripe_refund_id__isnull=False),
                name="uniq_ple_stripe_refund_id",
            ),
            UniqueConstraint(
                fields=["stripe_balance_transaction_id"],
                condition=Q(stripe_balance_transaction_id__isnull=False),
                name="uniq_ple_balance_txn_id",
            ),
        ]
```

### Payment totals invariants and derivation

Define these as authoritative derivations from the ledger:

- `amount_gross = sum(amount for entry_type=CHARGE)`
- `amount_refunded = sum(amount for entry_type=REFUND)`
- `amount_net = sum(Coalesce(net_amount, 0) for all ledger entries)`

Notes:

- Do not hand-edit totals; only recalculate from ledger.
- If any `net_amount` is null, you can fallback to amount for charges and -amount for
  refunds, or better, backfill `net_amount` from Stripe balance transaction in the
  webhook handler so totals are correct and audit-ready.

### Payment.recalculate_totals(save=True) correctness

- Must be atomic and use `SELECT ... FOR UPDATE` on the `Payment` row to avoid races
  (especially during concurrent refunds).
- Compute via aggregation to avoid Python loops and quantization issues.
- Honor save flag; when `save=True`, call `save(update_fields=[...])`. Include
  `updated_at` explicitly to ensure it is written.
- Return a boolean indicating whether any totals actually changed, so callers can skip
  extra writes.

Example:

```python
from django.db import transaction
from django.db.models import Sum
from django.db.models.functions import Coalesce

class Payment(models.Model):
    ...
    def recalculate_totals(self, save=False):
        with transaction.atomic():
            # Lock the row to avoid race during concurrent webhook processing
            type(self).objects.select_for_update().filter(pk=self.pk).get()

            qs = self.ledger_entries.all()
            gross = qs.filter(entry_type="charge").aggregate(
                s=Coalesce(Sum("amount"), 0)
            )["s"]
            refunded = qs.filter(entry_type="refund").aggregate(
                s=Coalesce(Sum("amount"), 0)
            )["s"]
            net = qs.aggregate(s=Coalesce(Sum("net_amount"), 0))["s"]

            changed = (
                self.amount_gross != gross
                or self.amount_refunded != refunded
                or self.amount_net != net
            )
            self.amount_gross = gross
            self.amount_refunded = refunded
            self.amount_net = net

            # Optionally adjust status here based on totals
            new_status = self._derive_status()
            status_changed = new_status != self.status
            if status_changed:
                self.status = new_status

            if save and (changed or status_changed):
                self.save(update_fields=[
                    "amount_gross",
                    "amount_refunded",
                    "amount_net",
                    "status",
                    "updated_at",
                ])
            return changed or status_changed
```

### Stripe fee handling

- Prefer storing `net_amount` straight from Stripe’s `balance_transaction.net` on each
  entry; that gives you fees implicitly as `(amount - net_amount)` for charges and
  `(-amount - net_amount)` for refunds. This avoids having to model "fee" entries and
  makes `amount_net` additive across the whole ledger.
- If `balance_transaction` is not immediately available in the event payload, use expand
  when fetching charge/refund, or schedule a backfill worker to fetch and patch
  `net_amount` later. Until backfilled, `net_amount` can be null and excluded from
  `amount_net` using `Coalesce(..., 0)`.

## Webhook handling (payments/webhooks.py or views.py)

### charge.succeeded

- Idempotency: guard on unique `stripe_charge_id` and unique
  `WebhookEvent.stripe_event_id`. If either exists, short-circuit without creating
  duplicate ledger entries.
- Fetch charge with `expand=["balance_transaction"]` to populate net. Create exactly one
  CHARGE ledger entry with:
  - payment resolved by mapping `charge.payment_intent` or your own `stripe_charge_id`
    linkage (ensure unique mapping).
  - amount = `charge.amount` (converted to your storage unit) and currency =
    `charge.currency`.
