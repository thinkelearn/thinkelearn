# PR #25 Holistic Review

## Summary (high-level)

- This merge implements the full payments stack (Phases 1-5): Stripe client + Checkout, webhook handling and refunds, enrollment models and integrations, and a new accounting ledger + reconciliation support.
- New/changed modules of interest: `payments/models.py` (Payment, WebhookEvent, EnrollmentRecord, LedgerEntry), `payments/migrations/0002_accounting_ledger.py`, `payments/webhooks.py`, `payments/admin.py`, `payments/views.py`, `payments/stripe_client.py`, `payments/tasks.py`, and a large suite of tests (especially `payments/tests/test_webhooks.py`).
- Docs and tests added for Stripe flows, local testing, and the overall LMS implementation plan.

## Top risks (ranked)

1. Ledger correctness and reconciliation (HIGH)
   - Does the ledger implement appropriate double-entry accounting or at least an auditable set of immutable entries? If ledger entries are single-sided or allow in-place balance adjustments, this is a critical correctness and auditability risk.
   - Concurrency risk when maintaining running balances on a ledger row (race conditions, inconsistent balances) unless updates use locking (`select_for_update`) or are computed at query time.
   - Reconciliation with Stripe (balance transactions, fees, partial refunds, chargebacks): if the reconciliation logic is missing or incomplete we risk mismatches (net vs gross, platform fees).
2. Refund / reversal handling and immutability (HIGH)
   - Creating refund effects must not delete or mutate historical ledger entries or the original Payment record; reversals should be new immutable entries that link to prior entries.
   - Deleting CourseEnrollment on refund (as described in plan) is risky for audit/history; soft-revoke is preferable to hard delete.
3. Webhook idempotency and ordering (HIGH)
   - Webhook processing needs robust idempotency (unique event id stored) and correct coupling with ledger entries and payment/enrollment status transitions. Duplicate or out-of-order events must not create inconsistent ledger states.
4. Decimal/currency math and rounding (MED-HIGH)
   - All arithmetic should use Decimal with an explicit quantize/scale consistent with currency decimal_places. Missing quantization or using floats is a correctness risk for money.
   - Multi-currency handling: code may assume CAD only; ensure currency is tracked on ledger and payments to avoid mixing amounts.
5. Atomic transactions and rollback (MED)
   - Checkout implementation must wrap enrollment, Payment, and Stripe session creation in transactions and roll back on Stripe errors. Webhook handlers must also be atomic when updating multiple models.
6. Tests vs reality mismatch (MED)
   - Tests can mock Stripe APIs heavily. Manual/QA flows with real Stripe may reveal new edge cases (for example, delayed settlement and balance transactions).
7. Admin bulk actions and permissioning (MED)
   - Bulk refund/cancel actions must validate eligibility and perform idempotent operations; ensure they cannot accidentally issue duplicate refunds or bypass refund-window checks.
8. Time zones, timestamps, and audit fields (LOW-MED)
   - All timestamps should be timezone-aware UTC. Any local time use is a future repro risk.

## Suggested review order (focused and efficient)

1. `payments/models.py` - core domain; verify data model, fields, relationships, immutability, Decimal types, statuses, methods for ledger creation and reversal, unique constraints for idempotency.
2. `payments/migrations/0002_accounting_ledger.py` - ensure migration matches model intent: indexes, constraints, decimal precision, nullability, foreign keys, and default values (no accidental defaults that mask bugs).
3. `payments/webhooks.py` - critical behavior for reconciliation and refunds; check idempotency store (WebhookEvent), `transaction.atomic` usage, error handling, and logging.
4. `payments/views.py` (`create_checkout_session`) - atomicity of creating EnrollmentRecord/Payment and calling Stripe; idempotency keys; guardrails for free enrollments vs paid.
5. `payments/stripe_client.py` - ensure proper signature verification wrapper, retry/backoff semantics, no API key leakage.
6. `payments/admin.py` - admin bulk actions (cancel, refund, mark failed): verify they call the same business logic as webhooks/views and are idempotent.
7. `payments/tasks.py` and `payments/checks.py` - reconciliation tasks or health checks; scheduled reconciliation if present.
8. `payments/tests/*` - review tests focusing on webhooks, ledger entries, refund flows to ensure test assertions align with intended ledger semantics.
9. `payments/emails.py` - refund email content and invocation (should not be on success-critical path if external mail delivery fails).
10. Documentation (`docs/stripe-*`, `docs/lms-implementation-plan.md`) - confirm operational guidance for reconciliation and production Stripe keys is present.

## Suggested manual test plan (prioritized)

Note: run tests first (existing automated tests are extensive). Then perform the manual flows below.

### A. Baseline checks

- Confirm the DB has the new ledger tables and constraints after migrations.
- Verify admin lists for Payment, WebhookEvent, LedgerEntry, and EnrollmentRecord are visible and editable only where intended.

### B. Happy path: paid checkout + webhook

1. Create a fixed-price CourseProduct (for example, CAD 50). Ensure `product.refund_window` is set.
2. From UI, start Checkout for a signed-in user; ensure `create_checkout_session` returns a Stripe session URL.
3. Complete checkout in Stripe test mode (or simulate webhook event if using mock).
4. Deliver Stripe webhook `checkout.session.completed` (signed) to `/stripe/webhook` endpoint.
5. Verify:
   - EnrollmentRecord moved from `PENDING_PAYMENT` to `ACTIVE`.
   - CourseEnrollment created (user has access).
   - Payment status updated (`PAID`/`SETTLED`).
   - One or more LedgerEntry rows created: gross sale, Stripe fee, net settlement (or entries that represent gross + fee + net).
   - Ledger entries link to Payment and EnrollmentRecord (foreign keys).
   - Timestamps are UTC and audit fields set (created_by/system).
   - WebhookEvent recorded with event id; duplicate delivery does not create duplicate effects.

### C. Duplicate and out-of-order webhooks

1. Re-send `checkout.session.completed` (same id) - confirm idempotency prevents duplicate ledger entries or duplicate enrollment activation.
2. Simulate `async_payment_failed` before `checkout.completed` - verify state transitions to `PAYMENT_FAILED`, then `checkout.completed` moves to `ACTIVE` (if code supports retry) without duplicating payments.

### D. Full refund (Stripe dashboard -> `charge.refunded` webhook)

1. Issue a full refund from Stripe (test dashboard) or via admin refund action.
2. Deliver/trigger `charge.refunded` webhook.
3. Verify:
   - EnrollmentRecord status -> `REFUNDED`.
   - Payment status -> `REFUNDED`.
   - A reversal/credit LedgerEntry created (do not mutate original ledger entry).
   - CourseEnrollment access revoked: confirm whether it's hard-deleted or soft-flagged. If hard-deleted, confirm there is an audit trail elsewhere. Prefer soft-revoke/flag.
   - Refund confirmation email sent (check content for amount, refund date, course info).
   - Partial refund handling: if partial amount refunded, confirm net ledger and payment partial refund handling, and enrollment behavior (should typically remain active unless full refund).

### E. Refund window enforcement

- Attempt to refund via admin or test webhook outside the refund window (`product.is_refund_eligible` should block); verify refund rejected and ledger not altered; email/notice logged.

### F. Partial refunds and fees

- Issue partial refund via Stripe -> ensure ledger captures original fee allocation correctly (Stripe fee handling: sometimes fees are not refunded). Verify net effect and audit trail.

### G. Free enrollment

- Enroll in a free product; confirm no Payment created, no ledger entries for money; EnrollmentRecord and CourseEnrollment created directly.

### H. Concurrent checkouts and idempotency

- Trigger two simultaneous checkout session creations for the same user + idempotency key and verify duplicate prevention.

### I. Reconciliation (if present)

- Run the reconciliation task (if implemented) that fetches Stripe balance / balance_transactions and compare to ledger. Verify it reconciles: marks items matched/unmatched and creates corrective entries if necessary. If reconciliation task is missing, flag as required.

### J. Edge cases

- Simulate dispute/chargeback webhook (if implemented) and check ledger and enrollment handling.
- Confirm that private Stripe keys are not visible in UI, logs, or CI artifacts.

## Phase 5 accounting and ledger-specific checklist (code-level checks)

- Ledger model fields:
  - Amounts use DecimalField with appropriate max_digits and decimal_places and Python Decimal usage in code.
  - Currency field exists and is respected on every ledger entry (no mixing currencies).
  - Ledger entries are append-only: no in-place edits allowed in normal flows; if admin can edit, ensure audit trail exists (created_by/updated_by and change logs).
  - There is a link to Payment and EnrollmentRecord and (optionally) to WebhookEvent.
  - If a running balance is stored on entries, ensure updates use row-level locking (`select_for_update`) or use ledger-only append and compute running balance at read time.
- Reversal semantics:
  - Refunds create new ledger entries of opposite sign and reference the original entry (`reversal_of` field), do not modify the original entry amount.
  - For partial refunds, reversal entry amount equals refunded amount; fees handling is explicit (fees may or may not be refundable).
- Fees:
  - Stripe fee is recorded as its own ledger entry with a proper account attribution.
  - The net settlement amount should be represented (gross - fees) and reconcilable to Stripe BalanceTransaction data.
- Idempotency:
  - WebhookEvent model has a unique constraint on `stripe_event_id`; handlers use `get_or_create` to avoid reprocessing.
- Atomicity:
  - Handlers wrap DB updates in `transaction.atomic()` and create WebhookEvent before applying business logic.
- Time zones:
  - Use timezone-aware timestamps (`django.utils.timezone.now()`) and store UTC consistently.
- Decimal rounding:
  - Use quantize with Decimal("0.01") for currencies; set proper rounding mode.
- Admin actions:
  - Admin refund action must:
    - Validate refund eligibility (refund window, payment status).
    - Create a refund in Stripe and record the Stripe refund object id.
    - Create ledger reversal(s) and Payment.status update atomically.
    - Be idempotent (admin action cannot double-refund).
- Reconciliation process:
  - There should be a task that reconciles ledger entries with Stripe BalanceTransaction and Charge/Refund objects; if missing, add as a high-priority item.
  - Reconciliation should detect unmatched items and allow manual investigation without mutating original entries until human confirms corrective entries.

## Inconsistencies with Phase 5 requirements (observations and recommendations)

- Potential single-sided ledger vs double-entry: The plan asked for an "accounting ledger + reconciliation". If `payments/models.py` implements only single-line `LedgerEntry(amount, payment, ...)`, that is insufficient for reliable accounting and reconciliation. Recommendation: model entries with `account_type` (for example, revenue, fees, refunds, stripe_holdings) or implement dual-entry (debit/credit entries per transaction).
- Hard deletion of CourseEnrollment on refund: plan says "Delete CourseEnrollment (revoke access)". Deleting the enrollment will remove provenance for audits (who had access and when). Recommendation: mark CourseEnrollment as revoked/ended or soft-delete, and keep an audit record linking to refund ledger entry.
- No explicit reconciliation task visible in top riskiest files list: expect a scheduled task to compare Stripe BalanceTransactions (and refunds/fees) to ledger entries and create mismatch reports or corrective entries. If `payments/tasks.py` exists, confirm it fetches Stripe balance transactions and matches by Stripe transaction id.
- Tax handling deferred (note in plan): acceptable deferral, but ensure ledger and payment schemas are extensible to include tax line items per entry and that refunds reverse tax appropriately once taxes are implemented.
- Partial refund and fees semantics: plan says "Handle partial vs full refunds". Ensure code reflects Stripe behavior where refunded fees may or may not be returned, depending on Stripe account settings. Ledger logic must capture fee refund status accurately.
- Idempotency around admin refund path: webhook handlers are idempotent, but admin-triggered refunds that call Stripe API should also create WebhookEvent or equivalent idempotency record to avoid double-processing if Stripe later sends a `charge.refunded` webhook.
- Reconciliation matching keys: ensure ledger entries store Stripe `balance_transaction_id`, `charge_id`, and `refund_id` where applicable. Reconciliation must use those ids to match; matching by amount + timestamp is fragile.
- Tests appear very large and thorough; however, ensure tests also include reconciliation coverage and concurrency tests (simulated overlapping webhooks and admin refunds) for ledger correctness under race.

## Quick actionable recommendations (prioritized)

1. Verify ledger supports immutable reversal entries (`reversal_of` FK) and that no code updates historical amounts.
2. Ensure CourseEnrollment is soft-revoked on refund, not hard-deleted. If deletion is implemented, change to revoke/mark_end and add an audit record.
3. Add or verify reconciliation task that pulls Stripe BalanceTransaction and Charge/Refund ids and matches to ledger entries by Stripe ids. Add reports for unmatched entries.
4. Ensure all money math uses Decimal and quantize to two decimal places consistently; add tests for rounding edge cases.
5. Ensure `transaction.atomic` and `select_for_update` used where running balance or concurrent updates exist.
6. Make admin refund action idempotent and use same codepath as webhook refund handling to reduce divergence.
7. Confirm WebhookEvent has a unique index and is created/locked early in processing; verify good logging and monitoring for unhandled events.
8. Add an explicit comment in codebase that tax handling is deferred, and ensure ledger entries support tax line items in future (schema extension).

## Optional follow-ups

- Do a targeted code walkthrough for `payments/models.py` + 0002 migration + `payments/webhooks.py` and produce a line-by-line list of concrete issues to fix.
- Generate a checklist of unit and integration tests to add (reconciliation, concurrency, partial fee behaviors).
- Provide a sample DB schema for a minimal double-entry ledger design and sample reversal entry patterns.

## Bottom line

The PR is comprehensive and includes a lot of the necessary pieces (idempotency, tests, webhook handling). The highest business risk is the ledger/reconciliation semantics (immutability, double-entry vs single entry, correct fee/refund handling, and reconciliation with Stripe). Focus review and manual testing on those areas before merging to production.
