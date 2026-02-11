# PR #25 Security Review Brief

## Overall

- Direction is sound (ledger model, per-request Stripe client, webhook idempotency) but there are blocking issues around secrets handling, webhook concurrency/idempotency, signature verification, redirect/CSRF risks, and data/PII handling.

## Blocking Items (Critical/High)

### Secrets in CI/Docker Image

- Files: `.github/workflows/ci.yml`, `Dockerfile`.
- Fix: remove STRIPE_* keys from build args/ENV; use BuildKit secrets; rotate any exposed keys immediately.

### Webhook Idempotency, Locking, and Totals Consistency

- Files: `payments/webhooks.py`, `payments/models.py`.
- Fix:
  - Wrap processing in `transaction.atomic`.
  - Upsert `WebhookEvent` via `get_or_create` with `select_for_update`.
  - Unique index on `stripe_event_id`.
  - Lock `Payment` row (`select_for_update`) while writing `PaymentLedgerEntry`.
  - Treat `IntegrityError` as idempotent success.
  - Recalculate and persist totals inside the same transaction.
  - Add concurrency tests.

### Webhook Return Semantics (Retry Safety)

- Files: `payments/webhooks.py`, `payments/views.py`.
- Fix: return 2xx only after success or when intentionally ignored; return 5xx on transient failures to trigger Stripe retries; or enqueue reliably then 2xx; add failure-path tests.

### Signature Verification and Misconfig Hard-Fail

- Files: `payments/webhooks.py`, `payments/views.py`.
- Fix: verify via `stripe.Webhook.construct_event` with timestamp tolerance; reject if signature missing/invalid (400); fail fast if `STRIPE_WEBHOOK_SECRET` unset; add tests for invalid/missing signatures and replay.

### Enrollment Binding Integrity

- File: `payments/webhooks.py`.
- Fix: do not trust `session.metadata` for enrollment binding; require match on `stripe_checkout_session_id` (and/or user/customer) before changing enrollment state; add tests for spoofed metadata.

### Ledger Integrity: Enforce Non-Blank Stripe IDs

- File: `payments/models.py`.
- Fix: require non-empty `stripe_charge_id` for CHARGE and `stripe_refund_id` for REFUND via model validation + DB CHECK or separate non-nullable fields per type; add tests.

### Email Header Injection Risk

- File: `payments/emails.py`.
- Fix: sanitize subject/header inputs (strip CR/LF, control chars; length-limit); use safe `EmailMessage` APIs; add tests for header injection.

### Open Redirects and CSRF/Credential Exfiltration

- Files: `thinkelearn/static/js/checkout.js`, `thinkelearn/templates/account/login.html`, `thinkelearn/templates/account/signup.html`, `thinkelearn/templates/wagtail_lms/course_page.html`, `payments/views.py`, `docs/stripe-frontend-integration.md`.
- Fix: only allow relative or allowlisted HTTPS redirect URLs (use `url_has_allowed_host_and_scheme`); generate success/cancel URLs server-side; enforce same-origin for `checkoutUrl` and never send CSRF token off-origin; add redirect/CSRF tests.

### Server-Side Validation of Pricing/Amount and AuthZ

- Files: `payments/views.py`, `lms/templates/...`, `docs/stripe-frontend-integration.md`.
- Fix: ignore client-provided amount; validate min/max and product eligibility server-side; require authenticated owner/staff permissions for create/refund actions; add tests for tampered amounts and unauthorized calls.

### Concurrency on Enrollment Creation

- File: `lms/models.py`.
- Fix: make `create_for_user` idempotent (`get_or_create` or catch `IntegrityError`) and/or lock rows; add concurrency tests.

### Hardcoded Credentials in Tests

- File: `home/tests/test_navigation_integration.py`.
- Fix: remove credentials; rotate affected accounts; purge from git history; use factory fixtures/CI secrets.

### Async vs Sync Webhook Processing Contradiction

- Files: `docs/lms-implementation-plan.md`, `payments/webhooks.py`, `payments/tasks.py`.
- Fix: standardize on short-ack + background worker for long tasks (email, I/O); enforce handler timeout; add tests ensuring handler latency stays under Stripe limits.

### Supply Chain and Framework Upgrade Risk

- Files: `uv.lock`, `poetry.lock`.
- Fix: review Django 6.0 changes; pin to latest patched 6.x; run full regression/security tests; ensure deps (allauth, oauthlib, PyJWT, stripe) are pinned to patched versions and scanned.

### Data Exfiltration via Tooling

- File: `scripts/pr_review_llm.sh`.
- Fix: avoid sending diffs to external LLMs; add secret redaction, opt-in flag, and restrictive permissions.

## Key Medium/Low Follow-Ups

### PII/Metadata and Raw Webhook Payload Storage

- Files: `payments/models.py` (`WebhookEvent.raw_event_data`, `PaymentLedgerEntry.metadata`), `payments/migrations/0001_initial.py`.
- Fix: whitelist metadata keys; prohibit PII; redact sensitive fields from stored payloads; cap size; consider field-level encryption; limit admin exposure; add sanitizer tests.

### Refund Idempotency and Stripe Client Safety

- Files: `payments/stripe_client.py`, `payments/webhooks.py`.
- Fix: use Stripe idempotency keys for refunds (derived from local IDs); avoid logging API keys; prefer SDK key configuration over passing in params; add tests ensuring no secrets in logs.

### Admin Hardening and Auditability

- File: `payments/admin.py`.
- Fix: make ledger/WebhookEvent read-only; require ADJUSTMENT entries for corrections; restrict sensitive fields in list/search; audit log admin actions.

### Logging Redaction

- Files: `payments/webhooks.py`, `payments/views.py`, `payments/emails.py`.
- Fix: redact secrets/identifiers in logs; reduce exception verbosity in prod; add redaction tests.

### Settings Hardening

- Files: `thinkelearn/settings/base.py`, `thinkelearn/settings/production.py`.
- Fix: correct allauth settings (ACCOUNT_AUTHENTICATION_METHOD=email, disable username if intended); ensure `SecurityMiddleware` is first; validate provider creds; add system checks to fail on missing/unsafe Stripe keys when `DEBUG=False`.

### Front-End Hardening

- File: `assets/css/main.css`.
- Fix: restore safe iframe styling and apply sandbox/CSP; ensure overlays don’t intercept clicks unless intended.

## Must-Add Tests

- Concurrency/idempotency: parallel delivery of identical webhooks/refunds; verify single ledger entry and correct totals.
- Failure paths: signature mismatch; DB transient error; ensure 5xx triggers Stripe retries; background-queue retry behavior.
- Enrollment binding: spoofed metadata vs `checkout_session_id` verification.
- Redirect/CSRF: reject off-origin `checkoutUrl`; allowlisted success/cancel URLs only; open-redirect via `next` parameter.
- Amount tampering: client-sent amount vs server validation; unauthorized purchase/refund attempts.
- Secrets/logging: assert API keys/session IDs are redacted from logs.
- Email injection: CR/LF in titles/headers safely handled.
- Admin immutability: ledger entries read-only; adjustments recorded as new entries.

## DB/Schema Actions

- Add unique constraint on `WebhookEvent.stripe_event_id`.
- Add CHECKs (or per-type non-null fields) enforcing non-empty `stripe_charge_id`/`stripe_refund_id` by entry_type.
- Consider size limits on `raw_event_data` and `metadata` fields.

## Quick Wins

- Wrap webhook processing with `transaction.atomic` + `select_for_update`; handle `IntegrityError` idempotently.
- Enforce signature verification and 5xx on failure; fail on missing `STRIPE_WEBHOOK_SECRET`.
- Remove secrets from CI/Docker; rotate keys.
- Lock down redirects/CSRF in `checkout.js` and templates; validate server-side redirects and pricing.
- Sanitize metadata and email headers; redact stored webhook payloads.
