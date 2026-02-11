# PR #25 Final Review

## Executive summary

- Ships Phases 1–5 end-to-end: pricing model, enrollment lifecycle, Stripe Checkout, robust webhook handling with refunds, and an accounting ledger + reconciliation scaffolding. LMS integration is complete (71 tests green, no regressions). Admin bulk actions (cancel, refund, mark failed) landed.
- Phase 5 focus: introduce an append-only ledger tied to Stripe objects, derive payment totals from ledger, and add reconciliation to Stripe balance transactions. Accounting correctness and idempotency must be locked down before merge.

## Key wins

- Solid LMS integration and coverage: 71 tests with 96.64% on core logic; explicit state-transition tests and DB constraint validations.
- Checkout flow is atomic with clear error handling; free-enrollment short-circuit path implemented and tested.
- Stripe client wrapper with retries/mocking; orphaned record cleanup on API failure.
- Admin bulk actions for common enrollment operations.
- Documentation updated to reflect the multi-phase plan and behavior.

## Top risks (ranked)

1. Ledger correctness and idempotency: uniqueness on Stripe IDs, immutability/reversal semantics, currency and Decimal precision, prevention of over-refunds, totals derived solely from ledger.
2. Webhook idempotency and ordering: unique event store, atomic processing with row locks, duplicate/out-of-order handling, and signature verification.
3. Reconciliation task completeness: matching to balance transactions (including fees, partial refunds), unmatched report, and non-destructive corrective entries.
4. Admin refund path: idempotency, permission gating, reuse of service/webhook logic, eligibility windows.
5. Enrollment/accounting integrity in DB: PROTECT FKs, conditional uniqueness for active enrollments, race-safe create_for_user, no hard deletes.
6. Security posture: secrets exposure in CI/Docker/logs, open redirects/CSRF, email header injection, PII in stored payloads.

## Blocking issues

### Accounting (Phase 5) schema and invariants

- Add UniqueConstraint(s) for Stripe IDs (conditionally unique when non-null):
  - Payment.stripe_charge_id, Payment.stripe_balance_transaction_id.
  - PaymentLedgerEntry.stripe_charge_id (CHARGE), stripe_refund_id (REFUND), and stripe_balance_transaction_id (global).
- Enforce ledger entry invariants via DB CheckConstraints:
  - EntryType choices (CHARGE, REFUND, optionally FEE/ADJUSTMENT); amount sign/absolute convention enforced; required Stripe IDs by type; processed_at non-null; currency stored on every row and matches Payment.
- Prevent over-refunds: Payment-level CheckConstraint amount_refunded <= amount_gross; totals must be derived from ledger aggregation.

### Webhooks

- WebhookEvent uniqueness on stripe_event_id; create first (success=False), wrap handler in transaction.atomic; lock Payment via select_for_update; mark success=True only after ledger writes + totals persist.
- Idempotent get_or_create for ledger rows keyed by Stripe charge/refund IDs; handle duplicates and out-of-order events safely.
- Verify signatures with stripe.Webhook.construct_event and hard-fail if STRIPE_WEBHOOK_SECRET missing.

### Reconciliation

- Implement/complete scheduled reconciliation: match by balance_transaction_id/charge_id/refund_id; derive net/fees from expanded balance transactions; generate unmatched report; no destructive edits.

### Admin/LMS integrity

- Permission-gate admin actions; disable delete and delete_selected for EnrollmentRecord; wrap actions in transaction.atomic with select_for_update; make ledger entries read-only (adjustments via new entries only).
- Migrations: switch EnrollmentRecord.user/product FKs to PROTECT; replace unique(user, product) with conditional unique excluding terminal states; idempotency_key as UUIDField(unique=True).
- lms.models: make create_for_user race-safe with idempotency and atomicity; add finalize_payment method with currency enforcement.

### Security

- Remove any STRIPE_* secrets from CI/Docker build args/env; rotate exposed keys. Replace logout GET with POST + CSRF. Lock down redirect URLs to allowlisted origins. Sanitize email headers. Reject client-supplied amount; validate server-side.

## Accounting & reconciliation notes (Phase 5)

### Ledger model

- Append-only entries with EntryType (CHARGE, REFUND, FEE/ADJUSTMENT optional). Enforce sign/absolute convention and required external IDs by type.
- Store currency on every entry; quantize Decimals to currency scale; add helper money_quantize and use consistently.
- Persist Stripe identifiers: charge_id, refund_id, balance_transaction_id on entries; index and (conditionally) unique.
- Link reversal_of for refunds/adjustments to preserve auditability; never mutate or delete historical rows.

### Totals and status

- Derive Payment.amount_gross, amount_refunded, amount_net from ledger aggregation in Payment.recalculate_totals(save=True) under transaction + select_for_update. Optionally set status (paid/partial/refunded) based on totals.

### Webhooks

- charge.succeeded: expand balance_transaction; create/get CHARGE entry with gross/net/currency and bt id.
- charge.refunded: expand refunds[].balance_transaction; create/get one REFUND per refund id; support partials and multiple refunds; optional synthetic fallback only if necessary and replaced later.
- Treat IntegrityError on unique collisions as idempotent success; always recalc totals before returning 2xx.

### Reconciliation

- Background task to fetch Stripe balance transactions and match entries by ids; record matched/unmatched state; produce report/metrics; never overwrite history—append corrective entries if needed.
- Explicitly capture Stripe fee behavior (fees and fee refunds) as separate entries to make net derivation auditable.

## Security notes

- Webhooks: enforce signature verification with tolerance; 5xx on transient failures to trigger Stripe retries; cap payload storage size, redact sensitive fields, and avoid PII in stored metadata.
- Secrets: remove from CI/Docker and logs; ensure settings fail closed if webhook secret or API keys are missing in production.
- Redirect/CSRF: allowlist success/cancel URLs and next=; generate server-side; do not leak CSRF tokens cross-origin.
- Authorization/validation: ignore client-provided amounts; validate pricing and eligibility strictly server-side; bind events via checkout_session/customer, not only metadata.
- Email safety: sanitize headers (strip CR/LF, length limits).
- Logging: redact keys/identifiers; reduce verbosity in prod.

## Suggested follow-ups (small, concrete)

- Add DB constraints/indexes:
  - Conditional unique on Stripe IDs and WebhookEvent.stripe_event_id; CHECKs for entry types/amounts; PROTECT FKs; UUIDField for idempotency_key.
- Implement Payment.recalculate_totals(save=True) with DB aggregation; add admin action “Recalculate totals.”
- Wrap webhook handlers in transaction.atomic; lock Payment via select_for_update; mark WebhookEvent success at end only.
- Add reconciliation task + admin report; store matched_at/notes.
- Harden admin:
  - Make ledger and WebhookEvent read-only; permission-gate sensitive actions; inline ordering by -processed_at.
- Tests to add now:
  - Duplicate/replayed webhooks (charge/refund) don’t duplicate ledger or totals.
  - Multiple partial refunds -> full refund transition; over-refund constraint.
  - Out-of-order refund before charge; idempotent admin refund path.
  - Currency mismatch rejection; Decimal quantization edges (0.005).
  - Reconciliation happy/mismatch paths.
- Security hardening:
  - Enforce webhook signature tests; remove GET logout; redirect allowlist; sanitize email headers; ensure no secrets in logs.

## Manual test plan (step-by-step)

1. Migrations/admin
   - Apply migrations; verify Payment, PaymentLedgerEntry, WebhookEvent visible; ledger inline read-only; EnrollmentRecord delete disabled.
2. Checkout happy path (paid)
   - Start checkout for fixed-price course; ensure server validates amount and eligibility; complete Stripe test payment.
   - Observe: Enrollment ACTIVE; Payment PAID; ledger has CHARGE with correct gross/currency and balance_transaction_id; WebhookEvent recorded success.
3. Duplicate webhook replay
   - Resend the same charge.succeeded event via Stripe dashboard; expect 200 but no new ledger rows; totals unchanged.
4. Free enrollment
   - Enroll with amount=0; Enrollment ACTIVE; no Payment/ledger rows; LMS course enrollment created.
5. Partial refund
   - Issue a partial refund in Stripe; webhook processes REFUND entry with correct amount/currency and bt id; Payment status PARTIALLY_REFUNDED; Enrollment soft-revoked only if business rule requires on full refund.
6. Multiple partials to full
   - Issue a second partial refund to reach full; totals match gross; status REFUNDED; Enrollment soft-revoked; refund email sent.
7. Over-refund attempt
   - Attempt refund beyond gross; verify rejection or clamped behavior; no ledger mutation beyond allowed; error logged.
8. Out-of-order delivery
   - Deliver refund webhook before charge (manually trigger via Stripe test tools); system should record idempotently and reconcile once charge arrives; totals end correct.
9. Admin refund path
   - Use admin “Refund” on an eligible payment; action is permission-gated, idempotent, and records Stripe refund id; subsequent webhook does not duplicate ledger; messages show accurate updated/skipped counts.
10. Concurrency/idempotency
    - Fire two concurrent checkout requests for same user/product with the same idempotency key; only one Payment/Enrollment created; no duplicate ledger rows.
11. Reconciliation
    - Run reconciliation task; entries match Stripe balance transactions; unmatched report generated without mutating history; fee entries reflected in net.
12. Security checks
    - Webhook with invalid/missing signature -> 400; with transient DB error -> 5xx and Stripe retries.
    - Verify success/cancel/next redirects are allowlisted; logout requires POST; server ignores client-supplied amount.
13. Logging/PII
    - Inspect logs for a run: no API keys or raw card/customer PII; webhook payloads stored redacted/capped.

## Overall

Strong progress and test discipline through Phases 1–4. To merge Phase 5 safely, please address the blockers around ledger invariants, Stripe ID uniqueness, webhook atomicity/signature verification, reconciliation completeness, and admin/LMS integrity. Once these are in and covered by the targeted tests above, we’re go for merge.
