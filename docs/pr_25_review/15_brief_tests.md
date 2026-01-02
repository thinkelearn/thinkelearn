# PR #25 Tests Review Brief

## Critical Gaps to Address First (Phase 5 Accounting)

- Add focused unit/regression tests for:
  - Partial refund persistence: `refunded_amount` persists after `refresh_from_db()`.
  - Multiple refunds aggregation: cumulative partials update `refunded_amount` and status; handle full refund transition.
  - Idempotency: duplicate webhook/event processing and repeated service calls do not duplicate ledger entries or double-count amounts; key by external refund id/event id.
  - Early-return regression: ensure `recalculate_totals()` is invoked on the early-return path; assert call count and stable totals.
  - Over-refund handling: reject or clamp `sum(refunds) > amount_gross`; assert log/behavior.
  - Currency/rounding: mismatched currency handling and Decimal precision (no float drift).

## File-by-File Actions

### `payments/tests/test_webhooks.py`

- Add missing cases:
  - Multiple partials that sum to full refund; assert `amount_refunded == amount_gross`, `amount_net == 0`, enrollment status REFUNDED, correct email behavior.
  - Over-refund payloads; assert clamp/reject + logged warning.
  - Out-of-order refund events and dedup keyed by Stripe refund id (not event id); truncated refunds list then full list.
  - Payloads without `refunds[].data` but with `amount_refunded` set.
  - Duplicate webhook with same top-level event id; assert `WebhookEvent` de-dup prevents reprocessing.
- Assert Stripe IDs on ledger rows: `stripe_refund_id` and `stripe_charge_id` populated and match payload; assert uniqueness set equals expected.
- Rounding/currency edges: refund currency != payment currency; half-cent/quantization tests if any division occurs.
- Stability:
  - Replace `int(timezone.now().timestamp())` with fixed constants or freeze time.
  - Assert `recalculate_totals()` is called on early-return path (patch/spying).
  - Reduce brittle `assertLogs` substring checks; prefer regex or record inspection.
  - Assert `processed_at` presence and monotonicity when creating entries in sequence.
- Avoid relying on factory defaults for amounts/currency; set explicit values in tests.

### `home/tests/test_navigation_integration.py`

- Remove hardcoded credentials and UI login dependency; switch to cookie/token injection or test-only fast-login endpoint.
- Replace hidden-class checks with `aria-expanded` + `to_be_visible`/`to_be_hidden`; wait for specific selectors post-login.
- Stabilize interactions: avoid absolute coordinate clicks; use `getComputedStyle` for transforms or assert rotated class; isolate per-test browser context and restore viewport.
- Avoid brittle exact counts for menu items; assert presence-by-text or roles; add `aria-controls`/id cross-checks and activation/closing behavior tests.

### `thinkelearn/tests/test_social_adapter.py`

- Add Phase 5 accounting tests (see Critical Gaps).
- Expand adapter edge cases:
  - Precedence between `extra_data.email` and `email_addresses`; conflicting verified flags; string/int truthy flags.
  - Multiple verified addresses and casing; deterministic selection.
  - Multiple users with same email; deterministic or safe behavior.
- Test robustness:
  - Use separate `SocialLogin` mocks per call or real `SocialLogin` instances; assert connect args by pk, not instance equality; avoid username param for custom user models (use `USERNAME_FIELD`).

### `payments/tests/test_models.py`

- Add tests:
  - Multiple REFUND entries aggregate; incremental recalc persists state.
  - Idempotency: duplicate external ids or re-processing doesn’t double-count.
  - Over-refund rule; currency mismatch behavior.
  - Early-return regression: calling `recalculate_totals` twice yields stable persisted totals; spy to ensure intended calls.
- Idempotency of `recalculate_totals` (no duplicate side effects when no ledger changes).
- Avoid hard-coded default currency; read from settings or assert 3-letter code. Minimize Wagtail root coupling unless needed.

### `payments/tests/test_checkout_flow.py`

- Add refund/ledger tests: partial refund persistence, multiple refund aggregation, idempotent refund and charge processing, and early-return recalc regression via patch.
- Fix duplicate-enrollment test to keep Stripe client patched across both requests; assert no external calls if short-circuit is expected.
- Relax brittle auth status assertion (401 vs 302) or standardize via APIClient.
- Use explicit lookups (by Stripe IDs) over `.first()`; assert amount/currency/user fields; centralize patch target for Stripe client.

### `payments/tests/test_error_handling.py`

- Add Phase 5 accounting idempotency tests (duplicate ledger creation on retries).
- Cover retry exhaustion and more error classes (`APIError`, `TimeoutError`, generic `StripeError`, non-Stripe exceptions); assert types/attributes over message substrings; assert expected sleep call counts.
- Replace global mutation of `DummyStripe` with per-test `patch.object`; patch the exact attribute used by implementation.

### `payments/tests/test_tasks.py`

- Add tests: partial refund persists on enrollment/payment; multiple refunds aggregate and drive status transitions; idempotent ledger creation on repeated task runs; early-return recalc regression (spy).
- Strengthen email test: assert `called_once_with` with expected args.
- Stabilize time logic: compute cutoff once or freeze time.

### `payments/tests/test_free_enrollment.py`

- Add Phase 5 accounting tests via non-free path (partial/aggregate refunds, idempotency, recalc regression).
- Add idempotent checkout test (no duplicate enrollments); free product with non-zero client amount handling.
- Harden assertions: user/product linkage, payment is None, no ledger rows; reduce Wagtail coupling; avoid brittle copy assertions.

### `payments/tests/test_emails.py`

- Exercise real refund flow triggering email; add persistence/aggregation/idempotency and recalc regression tests.
- Improve email assertions: recipient, amounts present, partial vs full template; freeze time or inject timestamp; prefer regex/case-insensitive checks.

### `payments/tests/test_frontend.py`

- Add accounting tests elsewhere (unit/service level as above).
- Expand view tests: missing/invalid `session_id`, idempotency (success page hit twice), side-effect checks, mock Stripe; assert template/context keys rather than literal copy.

## Cross-Cutting Stability Fixes

- Freeze time or use fixed timestamps; avoid wall-clock dependencies.
- Use `Decimal` with explicit quantization; assert `Decimal` types.
- Assert uniqueness by external ids (webhook event id, Stripe refund id) and that those ids are stored on ledger rows.
- Prefer deterministic selectors/roles over CSS classes or inline styles in UI tests.
- Add concurrency-aware/idempotency tests where possible or at least simulate duplicate processing.

## Minimal Test Additions to Unblock Phase 5 (Recommended Order)

1. Cumulative full refund test (two partial refunds → full) with status and email assertions (`payments/tests/test_webhooks.py` or `payments/tests/test_models.py`).
2. Refund idempotency: same refund id in repeated events does not duplicate ledger or totals (`payments/tests/test_webhooks.py`/`payments/tests/test_models.py`).
3. Over-refund behavior and currency mismatch handling (`payments/tests/test_webhooks.py`/`payments/tests/test_models.py`).
4. Early-return regression: assert `recalculate_totals()` invoked and totals stable (`payments/tests/test_models.py`/`payments/tests/test_webhooks.py`/`payments/tests/test_tasks.py`).
5. Duplicate top-level webhook id de-dup (`payments/tests/test_webhooks.py`).
