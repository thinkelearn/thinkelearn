# PR #25 Accounting Review Brief

## TL;DR

- Make accounting invariant-driven and idempotent.
- Derive totals solely from the ledger.
- Enforce uniqueness on Stripe IDs, lock/aggregate atomically, and handle partial/multiple refunds correctly.
- Add targeted tests to pin behaviors and prevent regressions.

## Blockers

### Schema and Invariants

- Files: `payments/models.py`, `payments/migrations/0002_accounting_ledger.py`.
- Enforce Stripe ID uniqueness for idempotency.
  - Add `UniqueConstraint` for `Payment.stripe_charge_id` and `stripe_balance_transaction_id` (conditioned on non-null).
  - Add `UniqueConstraint` for `PaymentLedgerEntry.stripe_charge_id` (when `entry_type=CHARGE`), `stripe_refund_id` (when `entry_type=REFUND`), and `stripe_balance_transaction_id` (global, when present).
- Define and enforce ledger invariants.
  - `CheckConstraint`s by `entry_type` (amount sign bounds; required IDs by type; currency match to `Payment` enforced in `clean()`).
- Totals must be authoritative derivations.
  - `amount_gross=sum(CHARGE.amount)`, `amount_refunded=sum(REFUND.amount)`, `amount_net` from `net_amount` when present, else sum signed amounts (pick one convention and document).
- Prevent over-refunds.
  - `Payment`-level `CheckConstraint`: `amount_refunded <= amount_gross`.

### Webhooks

- File: `payments/webhooks.py`.
- Webhook idempotency and atomicity.
  - Create `WebhookEvent` first (unique `stripe_event_id`), `success=False`; mark `success=True` only after ledger writes + totals recalc commit.
  - Wrap handlers in `transaction.atomic`; `select_for_update` on `Payment` row; use `get_or_create` keyed by unique Stripe IDs.
- Refund handling correctness.
  - Create one REFUND ledger per Stripe refund id; enumerate refunds on `charge.refunded`; handle `refund.created/updated` or ensure fallback path is idempotent.

## High Priority

### Entry Types and Amounts

- File: `payments/models.py`.
- Define `EntryType`: CHARGE, REFUND (optionally FEE, ADJUSTMENT).
- Enforce amount bounds:
  - CHARGE amount > 0.
  - REFUND amount > 0 if stored as absolute, or amount < 0 if using signed model (align constraints and recalc with chosen convention).

### Currency Consistency

- File: `payments/models.py`.
- Enforce ledger currency == payment currency via `clean()`.
- Add index on `(payment, currency)` for audits.

### Processed Timestamps and Indexes

- File: `payments/models.py`.
- `processed_at` non-null.
- Add composite indexes: `(payment, processed_at)`, `(payment, entry_type)`.

### Net/Fee Correctness

- File: `payments/webhooks.py`.
- Prefer `net_amount` from expanded `balance_transaction` on each entry.
- If not expanded, backfill later; until then, keep `net_amount` null and exclude from totals or use a clear fallback.

### Fallback Refunds

- File: `payments/webhooks.py`.
- If only `amount_refunded` present, create a synthetic, idempotent REFUND (e.g., `stripe_refund_id=f"synthetic:{event_id}"`).
- When detailed refunds arrive later, delete/ignore fallback before inserting real ones.

### Avoid Cross-Payment Collisions

- File: `payments/webhooks.py`.
- If a Stripe ID is bound to a different `Payment`, log and no-op; rely on DB uniqueness to guard races.

## Medium Priority

### Admin

- File: `payments/admin.py`.
- `RefundStateFilter`: “Full refunds” must use equality (`amount_refunded = amount_gross`), not `gte`; keep exclude for `gross=0`.
- Performance/UX:
  - `PaymentAdmin`: `list_select_related(enrollment_record, product, course)`, `ordering=(-created_at,)`, `date_hierarchy="created_at"`, `raw_id_fields` or `autocomplete_fields`.
  - Add admin action “Recalculate totals” to run `Payment.recalculate_totals(save=True)` on selection.
  - Inline: `PaymentLedgerEntryInline` ordering by `-created_at`/`-processed_at`; include source/event_id fields if available.
- `WebhookEventAdmin`: ordering/date_hierarchy; `list_select_related`/`raw_id_fields` when related to `Payment`.

### Totals Recalculation

- File: `payments/models.py`.
- `Payment.recalculate_totals(save=True)`:
  - Aggregate in DB; run under transaction + `select_for_update`.
  - Return whether fields changed.
  - Save with `update_fields` including `updated_at` (and status if derived).
- Optionally set status based on totals (succeeded/partially_refunded/refunded) within recalc for coherence.

### Migration Follow-Ups

- File: `payments/migrations/0002_accounting_ledger.py`.
- Add `Payment` amounts non-negative `CheckConstraint`.

## Webhooks Implementation Notes

### charge.succeeded

- Retrieve with `expand=["balance_transaction"]`.
- `get_or_create` CHARGE by `stripe_charge_id`.
- Set `net_amount` from `balance_transaction.net` if expanded.
- Set `stripe_balance_transaction_id` on entry.
- Recalculate totals.
- Record `WebhookEvent` success at end.

### charge.refunded

- Retrieve with `expand=["refunds.data.balance_transaction"]`.
- For each refund: `get_or_create` REFUND by refund id; set `net_amount` from refund balance transaction net; recalc totals.
- If no refunds list: create synthetic fallback; replace later when details arrive.

### Concurrency

- In both handlers: `select_for_update` on `Payment` row; wrap entire flow in atomic transaction.

## Missing Tests to Add

### Idempotency/Replay

- `charge.succeeded` replay → single CHARGE ledger; totals unchanged; `WebhookEvent` de-dup. (payments/tests/test_webhooks.py)
- `charge.refunded` replay → no duplicate REFUNDs; totals unchanged.

### Partial/Multiple Refunds

- Two partial refunds aggregate; status reflects partial/full; `RefundStateFilter` equality verified.

### Early-Return Regression

- When enrollment branching causes early return, ledger and totals are still written.

### Constraints

- Unique charge/refund id enforced; unique `balance_transaction_id` enforced; currency mismatch rejected; over-refund prevented.

### Totals Recalculation

- Aggregates correct with/without `net_amount`.
- `save=False` doesn’t persist.
- `save=True` includes `updated_at`.
- Returns changed flag.

### Fallback Refunds Lifecycle

- Create fallback when only `amount_refunded` present.
- Later detailed refunds replace fallback; no double count.

### Out-of-Order Events

- Refund arrives before charge → safe behavior and later reconciliation.

### Payment-Level Uniqueness

- `stripe_charge_id` and `stripe_balance_transaction_id` unique across payments (migration-level).

## Concrete Code Changes Requested

### `payments/admin.py`

- Fix `RefundStateFilter` equality.
- Add `list_select_related`, ordering, `date_hierarchy`, `raw_id_fields`/`autocomplete_fields`.
- Add recalc totals action.
- Inline ordering and audit fields.

### `payments/models.py`

- Add `EntryType` choices and `CheckConstraint`s (ID requirements, amount bounds, currency match).
- Add `UniqueConstraint`s (Stripe IDs and `balance_transaction_id`).
- `processed_at` non-null; indexes.
- Implement robust `recalculate_totals` as above.

### `payments/migrations/0002_accounting_ledger.py`

- Alter Stripe ID fields to `null=True` + unique or conditional unique.
- Add constraints and indexes.
- Add non-negative totals constraint.

### `payments/webhooks.py`

- Implement `WebhookEvent` uniqueness and lifecycle.
- `transaction.atomic` + `select_for_update`.
- Idempotent `get_or_create` on Stripe IDs.
- Enumerate refunds.
- Expand `balance_transaction` for `net_amount`.
- Handle fallback refunds.
- Avoid overwriting `payment.stripe_balance_transaction_id` in refund path.
- Recalculate totals before any early return.

These changes harden accounting against Stripe replay/out-of-order delivery, keep totals auditably derived from the ledger, and improve admin operability.
