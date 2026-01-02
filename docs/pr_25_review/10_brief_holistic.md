# PR #25 Holistic Review Brief

## Scope Summary

- Implements full payments stack (Phases 1–5): Stripe Checkout + webhooks, refunds, enrollments, accounting ledger + reconciliation support.
- Key files: `payments/models.py`, `payments/migrations/0002_accounting_ledger.py`, `payments/webhooks.py`, `payments/views.py`, `payments/stripe_client.py`, `payments/admin.py`, `payments/tasks.py`, `payments/tests/test_webhooks.py`, and docs.

## Priority Risks

### Ledger Correctness and Reconciliation (High)

- Ensure append-only immutable entries, `reversal_of` links, currency on every row, Decimal precision/quantize, and reconciliation to Stripe balance transactions/fees/refunds.
- Files: `payments/models.py`, `payments/migrations/0002_accounting_ledger.py`, `payments/tasks.py`.

### Refund/Reversal Handling and Immutability (High)

- Refunds must create reversal entries; do not mutate originals.
- Avoid hard delete of enrollments; prefer soft revoke + audit trail.
- Files: `payments/models.py`, `payments/webhooks.py`, `payments/admin.py`.

### Webhook Idempotency and Ordering (High)

- Unique `stripe_event_id`, `get_or_create` pattern, early persistence + `transaction.atomic`, out-of-order handling.
- Files: `payments/webhooks.py`.

### Decimal/Currency Math and Rounding (Med–High)

- Use `Decimal`, quantize to currency scale, and keep multi-currency safe fields.
- Files: `payments/models.py`, `payments/webhooks.py`, `payments/views.py`.

### Atomic Transactions and Rollback (Med)

- Use `transaction.atomic` across multi-model updates; implement error handling and retries.
- Files: `payments/webhooks.py`, `payments/views.py`, `payments/admin.py`.

### Admin Bulk Actions and Permissioning (Med)

- Idempotent refunds/cancels with eligibility checks (refund window).
- Files: `payments/admin.py`.

### Tests vs. Reality Mismatch (Med)

- Stripe sandbox parity; reconciliation and concurrency gaps.
- Files: `payments/tests/*`.

### Timezones and Audit Fields (Low–Med)

- `timezone.now()` UTC; created/updated by/system fields.
- Files: `payments/models.py`.

## Review Focus Order

1. `payments/models.py` — immutability, `DecimalField` precision, currency, `reversal_of` FK, links to `Payment`/`EnrollmentRecord`/`WebhookEvent`, status transitions.
2. `payments/migrations/0002_accounting_ledger.py` — constraints, indexes, unique keys, nullability; prevent accidental defaults.
3. `payments/webhooks.py` — idempotency store, `transaction.atomic`, error/logging, duplicate/out-of-order behavior.
4. `payments/views.py` — `create_checkout_session` atomicity, idempotency keys, free vs paid.
5. `payments/stripe_client.py` — signature verification, retries/backoff, no key leakage.
6. `payments/admin.py` — actions reuse same business logic, idempotent, eligibility enforced.
7. `payments/tasks.py` — reconciliation job exists and matches Stripe balance transactions by ids.
8. `payments/tests/*` — webhook, ledger, refunds, idempotency, concurrency, reconciliation coverage.
9. `payments/emails.py` — non-critical path, accurate content.
10. Docs — operational runbooks for reconciliation and keys.

## Gaps vs. Phase 5 Requirements

- Potential single-sided ledger (High): if only a single amount field exists, add `account_type` or implement double-entry; ensure fee and revenue accounts are explicit. File: `payments/models.py`.
- Enrollment hard-deletion on refund (High): switch to soft revoke/end + audit link to refund ledger entry. Files: `payments/models.py`, enrollment integration.
- Reconciliation task missing or incomplete (High): implement scheduled reconciliation using Stripe `balance_transaction_id`/`charge_id`/`refund_id`, produce unmatched report, no destructive edits. Files: `payments/tasks.py`.
- Partial refund + fee behavior (Med–High): capture Stripe fee refund rules as separate ledger entries. Files: `payments/webhooks.py`, `payments/models.py`.
- Admin refund path idempotency (Med): use same logic/events as webhook, record Stripe refund id, guard against double-refund. File: `payments/admin.py`.
- Persist Stripe IDs for matching (Med): store `charge_id`, `refund_id`, `balance_transaction_id` on ledger entries or `Payment`. Files: `payments/models.py`.

## Targeted Code Actions

### Ledger and Money Handling

- `LedgerEntry`: `DecimalField(max_digits, decimal_places)`, currency, `reversal_of` FK, immutable entries; separate fee entries; optional running balance only if using row locks.
- `WebhookEvent`: `unique(stripe_event_id)` index; create/get before side effects; handlers wrapped in `transaction.atomic`.
- Quantization helper: `money_quantize(amount, currency)` and use everywhere.

### Enrollment and Admin

- `CourseEnrollment`: soft revoke/end_on + reason; do not hard delete; audit fields linking to `Payment`/`LedgerEntry`.
- Admin actions: eligibility checks, idempotent operations, reuse service layer; record Stripe refund id and WebhookEvent-like log.

### Reconciliation and Observability

- Reconciliation task: fetch Stripe balance transactions, match by ids, mark matched/unmatched, produce report; no mutation of historical entries except appending corrective entries.
- Logging/metrics: webhook outcomes, idempotency skips, reconciliation mismatches.
- Comments noting tax deferred; schema extensible for tax lines.

## Missing Tests to Add

- Ledger immutability and `reversal_of` semantics; prevent edits to historical rows.
- Reconciliation happy path and mismatches; matching by `balance_transaction_id`; corrective entry flow (if implemented).
- Admin refund idempotency and refund window enforcement; duplicate admin clicks.
- Webhook duplicate and out-of-order sequences; ensure no duplicate ledger entries or status flapping.
- Decimal rounding edge cases (0.005, 3-decimal currencies if supported); multi-currency separation.
- Concurrency: two concurrent checkout sessions for same user/product with idempotency key; overlapping webhook + admin refund.
- Partial refunds with non-refunded fees; validate ledger reflects Stripe behavior.
- Timezone: ensure UTC timestamps on created entries and events.

## Manual Test Checklist (Stripe Sandbox)

- Migrations/admin: tables present; admin visibility and perms correct.
- Happy path: checkout → webhook → enrollment active; `Payment` PAID; ledger entries for gross/fee/net; `WebhookEvent` created; duplication safe.
- Duplicate/out-of-order webhooks: resend same `checkout.completed`; send failed then completed; verify consistent states and no dupes.
- Full refund: trigger via Stripe; enrollment soft-revoked; `Payment` REFUNDED; reversal ledger entries; email sent; audit linkage present.
- Partial refund: correct amounts; fee handling captured; enrollment behavior correct.
- Refund window: attempt refund outside window; blocked without ledger mutation.
- Free enrollment: no `Payment`/ledger; enrollment created.
- Concurrent checkouts: idempotency prevents duplicates.
- Reconciliation: run task; items matched by ids; unmatched report generated.
- Edge: dispute/chargeback webhook behavior; secrets not logged.

## Go/No-Go Criteria

- Ledger immutability + reversal semantics, idempotent webhooks, and reconciliation task in place and tested.
- Decimal/currency correctness verified; atomic transactions throughout.
- Admin actions safe and idempotent; enrollment revocation is soft/auditable.
- Tests added/passing for the critical paths above.
