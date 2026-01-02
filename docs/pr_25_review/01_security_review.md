# PR #25 Security Review

## Summary

I reviewed the Django/Wagtail payment/ledger and webhook changes in this PR (payments/*, webhooks, stripe_client, views, models, tests, migrations, and the test suite). Overall the design moves to a proper ledger model, per-request Stripe API usage, and idempotent webhook tracking — all positive security and correctness choices. There are, however, several areas where the implementation as described leaves residual risks around race conditions, webhook processing semantics, secret handling, and metadata/validation that could result in duplicate ledger entries, payment state inconsistencies, or accidental PII leakage.

Below I provide: a concise threat model, prioritized findings (High/Medium/Low) with suggested fixes, and a production readiness checklist focused on authn/authz, input validation, secrets, webhooks, idempotency, and ledger/accounting integrity.

## Threat model (short)

### Assets to protect

- Customer funds / Stripe charges and refunds
- Accounting ledger (Payment, PaymentLedgerEntry) integrity and audit trail
- Enrollment state (grant/revoke access)
- Stripe secret keys and webhook signing secrets
- User PII exposed in logs, metadata, or admin UI

### Adversaries / attack vectors

- Malicious third-party sending fraudulent webhook events (signature forging)
- Replay or duplicate webhooks (network retries) leading to duplicate refunds/entries
- Race conditions from concurrent webhook deliveries or parallel requests causing duplicate ledger entries or inconsistent denormalized totals
- Compromised admin or bug leading to ledger edits or deletion
- Secret leakage in logs, templates, or stored metadata
- Insufficient authorization on endpoints allowing unauthorized payments/refunds/enrollments

### Trust & assumptions

- Stripe will sign webhooks and provide event IDs; server uses signature verification
- Database-level constraints plus application-level checks are relied on for idempotency
- Admin users are trusted but should not be able to silently break audit trail

## Findings and risk-levels with concrete fixes

### High

#### H1 — Race conditions and duplicates when processing concurrent webhooks or concurrent refund updates

- **Issue:**
  - WebhookEvent model uses a uniqueness constraint on stripe_event_id to prevent duplicate processing, and PaymentLedgerEntry has unique constraints on stripe_charge_id / stripe_refund_id. However concurrent delivery of the same event (or very close events: e.g., charge + refund updates) can still cause a race where two worker processes both observe no existing row and both try to insert, resulting in IntegrityError, partial processing, or duplicate side-effects if not handled atomically.
  - Denormalized totals on Payment (amount_gross, amount_refunded, amount_net) are recalculated but updates to Payment may be subject to lost-update races if two processes update simultaneously.
- **Impact:**
  - Duplicate ledger entries, double refunds in local accounting, inconsistent totals, inconsistent enrollment state (revoke twice), or application errors.
- **Fixes (concrete):**
  - When processing a webhook do an atomic get_or_create for WebhookEvent and use the created flag to decide processing; if created is False, return 200 (already processed).
  - For ledger entries:
    - Create ledger entry inside the same transaction used to create/get WebhookEvent and update Payment totals within that same transaction.
    - Use insert with unique constraint and catch IntegrityError: if IntegrityError occurs, load the existing ledger entry and treat as idempotent success rather than raise.
    - Alternatively, use unique constraint + SELECT ... FOR UPDATE on Payment row before modifying denormalized totals so concurrent workers serialize updates.
  - Use database-level locking where necessary:
    - transaction.atomic() and Payment.objects.select_for_update() while adjusting denormalized totals.
    - Consider using advisory locks (Postgres pg_advisory_lock) keyed on payment.id for coarse-grained protection during webhook processing affecting a given payment.
  - Add tests simulating concurrent webhook deliveries and concurrent refund events to ensure idempotency and no duplicates.

Example pattern:

```python
with transaction.atomic():
    obj, created = WebhookEvent.objects.select_for_update().get_or_create(
        stripe_event_id=..., defaults={...}
    )
    if not created and obj.success:
        return HttpResponse(status=200)
    if not created and not obj.success:
        # decide whether to retry / reprocess or fail
        ...
```

#### H2 — Webhook processing semantics: returning 200 for failures hides processing errors and loses retries

- **Issue:**
  - The plan states "Return 200 for unhandled events (prevent retry storms)". Returning 200 when handling logic has errored (e.g., DB transient error) prevents Stripe from retrying, which can cause missed processing and account inconsistencies. Conversely, returning 200 for truly uninteresting events is fine.
- **Impact:**
  - Missing refund processing, missed enrollment activations/revocations without retries; harder to detect outages.
- **Fixes:**
  - Only return 200 when you have confirmed successful processing or intentionally ignoring the event type (log decision). Return 5xx when processing failed due to temporary server/database errors to trigger Stripe retries.
  - For long-running or potentially failure-prone workflows, accept the event and enqueue reliable background processing (e.g., write event to WebhookEvent table with processed=False and schedule background worker to process and mark success). Return 200 immediately after enqueue so Stripe won't retry and background worker guarantees processing with retries and alerts.

#### H3 — Signature verification robustness / replay protection

- **Issue:**
  - Ensure webhook signature verification uses Stripe's expected verify API and enforces timestamp tolerance to limit replays. Also check that the signing secret used is per-environment and not accidentally committed in code or config.
- **Impact:**
  - Forged webhooks or replayed old events could grant/revoke access incorrectly or create false ledger entries.
- **Fixes:**
  - Use stripe.Webhook.construct_event(payload, sig_header, webhook_secret) and wrap with exception handling. Validate the 't' timestamp with a reasonable tolerance (e.g., 5 minutes) if your library doesn't do it automatically.
  - Reject events with missing or invalid signature header explicitly (return 400).
  - Log signature verification failures without storing full payload (see PII guidance).
  - Rotate webhook signing secret on a schedule and support graceful rotation if possible.

### Medium

#### M1 — Metadata handling and PII leakage

- **Issue:**
  - Stripe metadata fields may be used to store application identifiers and possibly user-visible strings. Metadata stored in PaymentLedgerEntry.metadata (JSON) may include PII if you include names/emails/identifiers. Also storing raw_event_data as-is may capture sensitive tokenized data.
- **Impact:**
  - PII leakage in DB backups, logs, admin UI, or sent to third parties; violation of privacy policies.
- **Fixes:**
  - Enforce a metadata policy:
    - Never store full email, full name, or payment method details in Stripe metadata. Use internal IDs (e.g., user_id, enrollment_id) only.
    - Truncate long fields and enforce size limits on metadata before saving (Stripe limits keys/values).
    - Validate metadata keys to a whitelist and sanitize values (strip control chars, length limit).
  - When storing raw_event_data:
    - Persist only necessary fields (event id, type, minimal object IDs and timestamps).
    - Redact or omit any sensitive fields (payment_method details beyond id, card last4 is okay if needed but limit).
  - Ensure admin UI escapes metadata when rendering and marks ledger JSON read-only.

#### M2 — Authorization checks for payment/refund endpoints and admin operations

- **Issue:**
  - The plan mentions authorization checks for create_checkout_session and admin bulk actions, but verify all endpoints that change enrollments or payments enforce the right checks:
    - create_checkout_session should ensure the authenticated user is the owner or allowed to purchase for that user.
    - Refund endpoints (admin or automated) must ensure only staff with explicit permission can trigger refunds.
    - Any view that reads/modifies Payment or Enrollment must enforce ownership or staff permissions.
- **Impact:**
  - Unauthorized users could create enrollments, refund others, or see payment details.
- **Fixes:**
  - Enforce @login_required and check product.is_purchase_allowed(user) or similar.
  - Use Django permissions for admin actions and limit refund endpoints to staff with a dedicated permission (e.g., payments.can_refund).
  - Add unit tests that assert unauthorized users cannot call these endpoints.

#### M3 — No global Stripe api_key but ensure accidental global usage is not present

- **Issue:**
  - The PR explicitly uses per-request api_key in stripe_client.StripeClient — good. But check entire codebase for any stray global stripe.api_key assignment or third-party libs that would set global state.
- **Impact:**
  - Global API key leads to cross-request leakage in multi-threaded/concurrent workers.
- **Fixes:**
  - Ensure stripe.api_key is never set globally anywhere in the codebase or in imported libs during initialization.
  - Enforce use of the StripeClient wrapper by code review and linting. Consider making stripe import private inside the wrapper to avoid accidental usage elsewhere.

#### M4 — Financial reconciliation & totals integrity

- **Issue:**
  - Denormalized totals (amount_gross, amount_refunded, amount_net) are convenient but vulnerable to drift if ledger entries are altered, missing, or duplicated.
- **Impact:**
  - Reports and payouts could be wrong; accountants cannot trust totals.
- **Fixes:**
  - Make Payment.recalculate_totals() a robust function; ensure it is used on any ledger change.
  - Add a nightly reconciliation job that recalculates and compares denormalized totals vs ledger aggregation, and raises alerts on mismatch.
  - Treat ledger entries as append-only: make fields immutable and disallow admin editing (or log edits and require reason).
  - Provide a safe admin action to recalc totals with audit trail and require staff permission.

### Low

#### L1 — Logging sensitive data

- **Issue:**
  - Tests and webhooks may log raw_event_data or stripe responses. Avoid logging secret tokens or card data.
- **Fixes:**
  - Redact or drop sensitive fields before logging (card numbers, tokens, client secrets). Apply safe-logging helper when logging raw_event_data.

#### L2 — Webhook endpoint exposure

- **Issue:**
  - Webhook endpoint is a public URL; ensure mapping is stable and protected by HTTPS. Consider IP filtering for extra protection (Stripe publishes IP ranges but not recommended alone).
- **Fixes:**
  - Enforce HTTPS (production).
  - Optionally restrict via WAF or allow-list by IP range if operationally acceptable.

#### L3 — Admin UI editing of ledger rows

- **Issue:**
  - Admin could edit ledger history or delete rows, breaking audit trail.
- **Fixes:**
  - Make ledger entries read-only in the admin list and change views (exclude add/delete in admin). If changes are necessary, require creating a correcting ADJUSTMENT entry rather than in-place edit.

## Concrete code-level recommendations and patterns to adopt

- **Webhook processing (idempotency pattern):**
  - Use get_or_create or upsert pattern for WebhookEvent within a transaction:
    - obj, created = WebhookEvent.objects.get_or_create(stripe_event_id=..., defaults={raw_event_data:..., processed_at:None,...})
    - If created is False and obj.success is True: return 200.
    - If created is False and obj.success is False: either attempt reprocessing (if safe) or return 5xx so Stripe retries.
  - When creating ledger entries, create them inside the same transaction after acquiring a lock on the Payment row:

```python
with transaction.atomic():
    webhook_event, created = ...
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    try:
        PaymentLedgerEntry.objects.create(...stripe_refund_id=..., payment=payment, ...)
    except IntegrityError:
        # someone else already created; fetch and continue
        ...
```

- After inserting (or finding existing) ledger entries, call payment.recalculate_totals(save=True) while still inside the transaction.

- **Handling IntegrityError gracefully:**
  - Wrap create() that relies on unique constraints in try/except IntegrityError. On IntegrityError fetch the existing row and treat it as idempotent success. Avoid letting raw IntegrityError propagate to 5xx unless it's a real unexpected DB issue.

- **Webhook signature verification & timing:**
  - Use stripe.Webhook.construct_event and catch (ValueError, stripe.error.SignatureVerificationError).
  - Enforce requirement that Stripe signature header exists; return 400 if missing/invalid.
  - Optionally check event['created'] timestamp against now and reject very old events.

- **Metadata validation/sanitization:**
  - Define allowed metadata keys and max length per key (e.g., 200 chars). Sanitize values: strip control characters, remove newline characters.
  - Do not include user email or PII in Stripe metadata. Instead store internal id references (user_pk or uuid).
  - On PaymentLedgerEntry.metadata JSONField, run a small sanitizer that prunes unexpected keys and truncates values.

- **Refund idempotency on Stripe API usage:**
  - When creating refunds via Stripe API, supply an idempotency key derived from local payment id + refund id (or use unique uuid stored locally) to avoid double refunds. Ensure refund jobs persist refund attempt records including idempotency_key and stripe_refund_id after response.

- **Tests to add:**
  - Concurrency tests: simulate concurrent identical webhook deliveries and concurrent refunds to ensure no duplicate ledger entries and totals remain correct.
  - Error path tests: signature mismatch, DB transient failure during processing, ensure Stripe retries when processing actually failed.
  - Reconciliation tests: ensure recalc_totals produces expected results after simulated duplicate insert then integrity repair.

## Production checklist (pre-deploy and ongoing)

Before enabling Stripe webhooks and refunds in prod:

- **Secrets & config:**
  - Store STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET in a secrets manager / environment variables. Never commit to repo.
  - Verify thinkelearn/settings/production.py or env loader does not log secret content.
  - Ensure stripe_client always uses per-call api_key and no code sets stripe.api_key globally.

- **Webhook endpoint & signature:**
  - Confirm endpoint URL is configured in Stripe dashboard and STRIPE_WEBHOOK_SECRET matches.
  - Validate signature verification behavior in staging with actual Stripe test events.
  - Configure logging of invalid signatures with alerting (do not log full payload).

- **Idempotency & DB constraints:**
  - Confirm database-level unique constraints on WebhookEvent.stripe_event_id and PaymentLedgerEntry stripe IDs are present and applied.
  - Implement and test get_or_create/select_for_update and IntegrityError handling in webhook processing.
  - Add an advisory lock or select_for_update around Payment updates.

- **Reconciliation & monitoring:**
  - Deploy reconciliation job that runs nightly:
    - Recalculate Payment totals from ledger and compare with denormalized totals.
    - Alert on mismatches > threshold or any negative net amounts.
  - Monitor metrics:
    - Webhook processing failures (5xx count)
    - Number of duplicate WebhookEvent entries attempted (IntegrityError rate)
    - Unprocessed WebhookEvents (processed=False)
    - Ledger insertion failures and IntegrityError occurrences
  - Install Sentry/exception tracking for webhook handler exceptions and set alerting.

- **Logging & PII:**
  - Ensure logs do not contain Stripe secrets or full raw_event_data with sensitive fields. Redact sensitive fields before logging or storing.
  - Verify admin UI escapes JSON metadata and raw_event_data.

- **Admin hardening:**
  - Make PaymentLedgerEntry and WebhookEvent models read-only in admin (no add/edit/delete), or use controlled forms that append ADJUSTMENT entries rather than mutate historical rows.
  - Require dedicated permission (payments.can_refund) to perform refunds from admin. Watch for bulk actions that perform refunds — enforce audit logging and require reason.

- **Operational safety for refunds:**
  - Ensure refunds performed via admin or automated tasks use:
    - Per-call Stripe API with idempotency key.
    - Persist refund attempt and stripe_refund_id atomically.
    - Mark refund status in ledger only after confirmation from Stripe.
  - Maintain logs/records of idempotency keys used for refunds.

- **Testing & deployment:**
  - Run the new tests, add concurrency tests (simulate parallel webhook deliveries).
  - Canary rollout of webhook handling: enable in staging, validate behaviors, then to small percentage of traffic if possible.
  - Document operational runbook for:
    - Handling webhook failures
    - Manual reconciliation
    - Rotating Stripe keys / webhook secret
    - Investigating duplicated ledger entries and corrective steps

## Short prioritized actionable checklist (what to change ASAP)

- A1: Ensure webhook handler uses get_or_create/select_for_update pattern with transaction.atomic and handles IntegrityError by treating existing record as idempotent success. Add concurrency tests. (High)
- A2: Avoid returning 200 on processing failures. Change to: return 200 only if processed/explicitly ignored; return 5xx to force Stripe retries on transient errors, or use enqueue-and-ack pattern when offloading processing. (High)
- A3: Make Payment updates (recalculate_totals and writes) protected by select_for_update or advisory lock to prevent lost updates. (High)
- A4: Sanitize and whitelist Stripe metadata before storing in DB. Do not store PII in metadata. (Medium)
- A5: Ensure refunds use idempotency keys and persist stripe_refund_id atomically; handle IntegrityError on duplicate refund creation gracefully. (Medium)
- A6: Make ledger/admin read-only for historical entries; require adjustments to be represented as ADJUSTMENT entries. (Low)

## Example patterns (pseudo-code) — implement these in payments/webhooks.py

- **Idempotent webhook entry creation:**

```python
try:
    with transaction.atomic():
        webhook_event, created = WebhookEvent.objects.get_or_create(
            stripe_event_id=event_id,
            defaults={'raw_event_data': minimal_payload, 'received_at': now()},
        )
        if not created and webhook_event.success:
            return HttpResponse(status=200)
        if not created and not webhook_event.success:
            # decide to reprocess or return 5xx
            ...
except IntegrityError:
    # concurrently created — fetch the existing event and proceed idempotently
    ...
```

- **Ledger creation:**

```python
with transaction.atomic():
    payment = Payment.objects.select_for_update().get(pk=payment_id)
    try:
        ledger = PaymentLedgerEntry.objects.create(
            payment=payment,
            stripe_refund_id=...,
            amount=...,
        )
    except IntegrityError:
        ledger = PaymentLedgerEntry.objects.get(stripe_refund_id=...)
    payment.recalculate_totals(save=True)
```

## Final notes

- The PR's architectural decisions (ledger model, WebhookEvent model, per-request Stripe client, idempotency keys) are sound and align with accounting-grade requirements. The key remaining work is making the webhook/ledger processing robust in the face of concurrency and transient failures, hardening metadata handling to avoid PII leakage, and tightening admin / refund authority and auditing.
- If you want, I can:
  - Review the actual webhook handler and stripe_client code (paste key snippets) and produce exact line-level recommendations and example patches for the get_or_create/select_for_update + IntegrityError handling.
  - Produce unit test templates for concurrent webhook processing and refund idempotency.

Would you like me to review specific files (payments/webhooks.py, payments/models.py, payments/stripe_client.py, payments/views.py) line-by-line and propose specific code changes?

## Additional findings (file-specific)

- CRITICAL — .github/workflows/ci.yml
  Suggested fix: Remove hard-coded Stripe keys from build-args. Do not embed secrets in workflow files. Instead, inject secrets at runtime (e.g. via deployment environment variables) or, if a secret is needed during image build, use build-time secret mechanisms (Docker BuildKit `--secret` or the docker/build-push-action secrets feature) so the secret is never written into logs or the image layers. If any real keys were ever used here, rotate them immediately.

- CRITICAL — Dockerfile
  Suggested fix: Do not set STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY / STRIPE_WEBHOOK_SECRET as ENV values from build ARGs (this bakes secrets into image layers and can leak them). Remove these ENV assignments from the Dockerfile. If build-time values are required, use BuildKit secrets or multi-stage build patterns that never persist secrets into final image, and always inject production secrets at container runtime (or via your platform's secret management). If any secrets were used in builds, rotate them immediately.

- Critical — docs/lms-implementation-plan.md / payments/webhooks.py / payments/tasks.py
  Suggested fix: Resolve the contradictory guidance about background tasks (doc says tasks are async in several places but Phase 4 states functions are synchronous). Ensure webhook handlers never perform long-running synchronous work (e.g., sending emails) before returning a 2xx response. Either (a) implement a reliable background worker (or Django tasks) and explicitly enqueue work from webhooks, or (b) if synchronous, change webhook logic to spawn short-lived background work (subprocess, OS job) and immediately respond. Add explicit tests and runtime assertions that webhook handlers return within Stripe's timeout to avoid retries and replay storms.

- High — thinkelearn/settings/base.py / docs/lms-implementation-plan.md / payments/checks.py
  Suggested fix: Do not ship examples/defaults that encourage embedding or defaulting secrets (or local Redis URLs) in source. Enforce STRIPE_*/webhook keys and other secrets are provided via environment variables and fail startup (SystemCheckError) if missing or if a test key is being used in a production configuration. Remove hardcoded credential defaults from committed settings/examples and document secure secret provisioning (env var + secrets manager). Ensure payments/checks.py performs a hard fail for missing/unsafe keys when DEBUG=False.

- Medium — payments/emails.py / payments/tasks.py / thinkelearn/templates/emails/*
  Suggested fix: Email subjects and headers are built with user/product-controlled values (course titles, refund_amount). Sanitize/escape all user-controlled data used in email headers and subjects and render message bodies via safe templates. Use mail libraries that prevent header injection and validate recipient addresses; consider templating libraries with auto-escaping for the email body.

- Medium — payments/webhooks.py / docs/lms-implementation-plan.md
  Suggested fix: The plan states "return 200 for unhandled events (prevent retry storms)". Ensure the webhook implementation first verifies Stripe signatures and only return 2xx after verification. For truly unknown or suspicious events, log at high severity, increment monitoring/alerting metrics, and rate-limit or quarantine repeated unknown events rather than silently swallowing them. Add alerting so unknown/unexpected event types cannot be used to hide malicious activity.

- Low — docs/lms-implementation-plan.md / payments/stripe_client.py
  Suggested fix: The docs recommend per-request API keys — ensure the StripeClient implementation never logs full API keys, never accepts keys from untrusted input, and scopes keys to the minimum privileges required. Add unit tests that assert no API keys are written to logs and add redaction in any error-handling that might include request/response payloads.

- High — home/tests/test_navigation_integration.py — Hardcoded plain-text credentials committed in test code ("<felavid@gmail.com>" / "WZV-bcv4fga5cga8mum"). Suggested fix: remove credentials immediately, rotate any leaked accounts/passwords, purge secrets from git history (git filter-repo / BFG), and replace with non-secret test fixtures (create test user via factory in setup) or load credentials from CI-provided secret env vars.

- High — docs/stripe-frontend-integration.md — Accepting/using client-supplied success_url/cancel_url (full URLs) in the API payload enables open-redirect/phishing risks if backend does not strictly validate. Suggested fix: disallow arbitrary client-provided redirect URLs; accept only server-generated or whitelisted relative paths, or validate origin/host against an allowlist before redirecting.

- Medium — docs/stripe-frontend-integration.md — Returning Stripe session_id in query string (session_id={CHECKOUT_SESSION_ID}) risks leaking Stripe identifiers in logs/referrers. Suggested fix: avoid placing sensitive Stripe identifiers in query parameters; instead map session_id server-side to a short-lived opaque token or look up session state server-side after return, and redact session IDs in logs.

- Medium — docs/stripe-frontend-integration.md — Relying on client-side amount validation (PWYC) is unsafe if backend accepts client-provided amount. Suggested fix: enforce server-side validation of amount/min/max and product pricing for every checkout-session request; authorize that the calling user may purchase the given product.

- Medium — docs/stripe-frontend-integration.md (Background Tasks) — Sending refund emails and other external I/O synchronously during webhook handling can cause timeouts/retries leading to duplicate processing or blocked webhook acknowledgement. Suggested fix: persist the webhook/event and respond 2xx as soon as state is safely stored; offload email sending and long-running work to a background worker/queue and ensure idempotent webhook handling.

- Medium — docs/stripe-local-testing.md & docs/stripe-frontend-integration.md — Documentation demonstrates exporting STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET in shells and copying secrets into env; this risks accidental disclosure or committing of secrets. Suggested fix: instruct use of secret managers (Railway/GitHub Actions secrets) and local .env files excluded from VCS; add a warning to never commit real keys or webhook secrets and rotate any keys that were exposed.

- Medium — docs/stripe-local-testing.md — Local webhook forwarding example and webhook path (/payments/webhook/) are documented without explicit enforcement notes. Suggested fix: ensure webhook endpoint verifies Stripe signatures using raw request body and the stripe-signature header (stripe.Webhook.construct_event or equivalent), disables CSRF for that endpoint, logs failures without acknowledging them, and rate-limits/alerts on repeated invalid attempts.

- High — lms/models.py — The create_for_user() flow checks for existing enrollments then creates a new EnrollmentRecord inside a transaction but does not guard against concurrent requests creating duplicates; IntegrityError can surface (and may lead to duplicate payments or inconsistent state). Suggested fix: make creation idempotent by using get_or_create or by catching IntegrityError and returning the existing record; or acquire a DB lock (select_for_update on a suitable row) or enforce/handle the unique constraint atomically and document behavior to avoid double-charges.

- High — lms/templates/lms/includes/checkout_enroll.html & lms/ views/checkout endpoint (payments backend) — Pricing, min/max and product id are emitted to the client and used to drive checkout flow. Client-side values are easily manipulated; if the server does not re-validate amounts and product pricing, attackers can alter payment amounts. Suggested fix: treat all client-submitted pricing/product data as untrusted — validate product.is_active, pricing_type and final amount server-side (ignore client-sent amount or enforce it against authoritative server-side product data) and verify idempotency before creating payment sessions.

- High — lms/templates/lms/includes/checkout_enroll.html — The checkout flow uses a client-side endpoint (data-checkout-url) to create checkout sessions but the template does not include any CSRF token or explicit protection. Suggested fix: ensure the checkout session creation endpoint enforces CSRF protection (or uses POST with CSRF token or a same-site authenticated API approach), require authentication/authorization and server-side validation of the product and amount before creating payment sessions.

- Medium — lms/models.py — EnrollmentRecord.**str**/**repr** include user.username and course title (PII/business data) which risks leaking user-identifiable information into logs, error messages, or admin displays. Suggested fix: avoid including raw usernames or other PII in **str**/**repr**/logs; use user_id or anonymized identifiers, and ensure logging configuration redacts sensitive fields.

- Medium — lms/models.py & lms/migrations/0003_courseproduct_enrollmentrecord_and_more.py — stripe_checkout_session_id and stripe_payment_intent_id are stored as plain DB fields and may be displayed in admin/listing or logs; these identifiers and related payment metadata should be treated as sensitive. Suggested fix: restrict admin/list displays to exclude these fields, avoid logging them, and consider encrypting sensitive payment identifiers at rest (or storing them in a dedicated secure storage) and applying strict access controls.

- High — payments/emails.py — Subject header injection / unsafe email headers. The subject is built from enrollment.course.title without sanitization, allowing CR/LF or other characters to manipulate email headers. Suggested fix: sanitize/normalize subject content (strip CR/LF, limit length, remove control chars) before passing to send_mail; or use EmailMessage and set headers explicitly. Example: safe_title = re.sub(r'[\r\n]+', ' ', enrollment.course.title).strip() and use that in the subject.

- Medium — payments/emails.py — Attribute access bug causing potential crashes/DoS when SUPPORT_EMAIL or CONTACT_EMAIL are missing. The call getattr(settings, "SUPPORT_EMAIL", settings.CONTACT_EMAIL) evaluates settings.CONTACT_EMAIL even if missing, raising AttributeError. Suggested fix: use chained getattr safely, e.g. support_email = getattr(settings, "SUPPORT_EMAIL", None) or support_email = getattr(settings, "SUPPORT_EMAIL", getattr(settings, "CONTACT_EMAIL", None)); handle None appropriately.

- Medium — payments/migrations/0001_initial.py (WebhookEvent.raw_event_data) — Raw webhook payloads stored unredacted. Storing full Stripe webhook JSON can contain sensitive metadata; exposing it via admin or backups increases risk. Suggested fix: redact or strip sensitive fields before persisting (e.g., card details, PII), add column-level access controls or encryption-at-rest for raw_event_data, and document retention/rotation policies.

- Medium — payments/admin.py — Admin surfaces searchable/payment fields (stripe ids, amounts, refund ids) that could enable data exfiltration via compromised admin accounts. Suggested fix: restrict admin access to minimal privileged users, remove highly sensitive fields from list_display/search_fields where not required, and enforce staff role permission checks and audit logging; consider masking identifiers in admin views.

- Medium — manage.py — Overly-broad detection for test environment: if "test" in sys.argv can match unintended arguments and unintentionally load test settings in non-test commands, causing misconfiguration or accidental use of insecure test settings. Suggested fix: only detect tests when the first positional command equals "test" (e.g., if len(sys.argv) > 1 and sys.argv[1] == "test":) and avoid overwriting DJANGO_SETTINGS_MODULE if already set; prefer os.environ.setdefault for test path if absolutely required.

- Low — payments/emails.py — HTML emails built with template/context containing user-controlled values (course title, enrollment data) without explicit sanitization. This can produce malicious HTML in emails. Suggested fix: ensure email templates use Django autoescaping, explicitly escape/validate user-supplied fields before rendering, and always send a plain-text alternative (already present) as the primary fallback.

- High — payments/models.py — WebhookEvent.raw_event_data stores full webhook payloads (JSONField) without redaction or encryption. Suggested fix: redact or omit any sensitive PCI/PII fields before persisting, enforce a reasonable maximum size, and/or use field-level encryption (e.g., django-encrypted-model-fields or DB-level encryption) for stored webhook payloads.

- High — payments/models.py — Idempotency/integrity bypass: charge/refund uniqueness only enforced when stripe_charge_id/stripe_refund_id are non-empty (fields allow blank). This permits creation of duplicate CHARGE/REFUND entries with empty IDs. Suggested fix: enforce that CHARGE entries must have a non-empty stripe_charge_id and REFUND entries must have a non-empty stripe_refund_id via model validation plus a DB CHECK constraint (or make those fields non-blank and non-null for the corresponding entry_type) to guarantee idempotency at the DB level.

- Medium — payments/models.py — Financial totals recalculation (Payment.recalculate_totals) is not performed atomically with ledger entry changes, leading to possible race conditions and inconsistent denormalized totals. Suggested fix: perform recalculation and totals update inside a transaction/row lock (e.g., transaction.atomic() with select_for_update on the Payment row or aggregate in a single DB UPDATE using a subquery) to ensure consistency under concurrent writes.

- Medium — payments/stripe_client.py — create_checkout_session accepts success_url/cancel_url (and metadata) from callers and passes them directly to Stripe. If those URLs are taken from untrusted client input (tests indicate caller-supplied values), this can enable open-redirect/phishing vectors. Suggested fix: validate/whitelist redirect domains server-side (or generate server-controlled URLs), and sanitize metadata before sending to Stripe.

- Medium — payments/stripe_client.py — API key passed in params to stripe.checkout.Session.create (params includes "api_key": self.api_key) and request/exception logging may risk accidental leakage of the secret. Suggested fix: avoid passing API keys in call parameters; set stripe.api_key in a local stripe client context or use the SDK's secure configuration, and ensure logging excludes secrets.

- Medium — payments/models.py — WebhookEvent.raw_event_data has no size limit and may be abused to bloat the database (DoS). Suggested fix: validate and truncate incoming webhook payloads to a safe maximum size before saving, and consider rate-limiting or pruning old webhook records.

- Low — payments/templates/payments/checkout_success.html — Session ID is rendered from a request-supplied value ({{ session_id }}). If the view ever marks this value as safe or bypasses auto-escaping, this could be a reflected XSS vector. Suggested fix: ensure default auto-escaping is preserved, do not mark session_id as safe, and avoid rendering internal IDs in the UI where unnecessary (or mask them).

- High — payments/webhooks.py — Add DB-enforced idempotency and protect against race conditions when recording/processing webhook events (tests assert WebhookEvent.objects.count() == 1 but rely on app logic). Suggested fix: add a unique constraint on the Stripe event id (e.g. UniqueConstraint(fields=["stripe_event_id"], name="uniq_stripe_event_id")) and make webhook processing atomic: create the WebhookEvent inside a transaction, handle IntegrityError (treat as already-processed), and lock related rows (select_for_update) when updating Payment/Enrollment to prevent double-processing/race conditions.

- High — payments/webhooks.py — Ensure denormalized payment totals are always updated even on "early return" paths (comment references a critical bug where recalculate_totals() was skipped). Suggested fix: always call payment.recalculate_totals() after creating PaymentLedgerEntry records (move/duplicate the call so it cannot be skipped by early-return branches), and perform ledger creation + denormalized updates in the same DB transaction to avoid inconsistent financial state.

- Medium — payments/webhooks.py (and logs) — Tests expect warnings like "enrollment not found" / "payment not found" to be emitted; logging these details may reveal internal identifiers and application state. Suggested fix: avoid logging sensitive identifiers or predictable resource-existence messages. Log only non-sensitive context or redact IDs; if detailed logging is required, restrict access to logs and consider rate-limiting or structured audit logging instead of free-text errors that expose existence.

- Low — payments/webhooks.py — Refund email path may attempt to send confirmation even when the user has no email (test_refund_user_without_email). Suggested fix: validate recipient email before sending (skip sending and record/queue notification for admins if absent), ensure the email-sending function safely handles empty/invalid addresses, and avoid passing empty addresses into mail backends.

- High — payments/webhooks.py — Suggested fix: Do not trust session.metadata["enrollment_record_id"] as a primary means to bind a Stripe session to an internal EnrollmentRecord. Require strong binding such as: accept the session only if its session.id equals an existing enrollment.stripe_checkout_session_id (or verify session.metadata.user_id or session.customer_email matches the enrollment.user), and only then mark the enrollment paid. Re-order_get_enrollment_from_session to prefer resolving by stripe_checkout_session_id first, or add explicit verification checks before updating enrollment records to prevent an attacker from creating a paid Stripe session pointing at someone else’s enrollment.

- High — payments/views.py — Suggested fix: Fail fast when STRIPE_WEBHOOK_SECRET is not configured instead of passing an empty secret to stripe.Webhook.construct_event. Add an explicit check (and log/raise) if settings.STRIPE_WEBHOOK_SECRET is falsy so webhook signature verification cannot be accidentally disabled by misconfiguration.

- Medium — payments/views.py — Suggested fix: Tighten redirect URL validation in create_checkout_session. Replace the generic URLValidator accept-all behaviour with an allowlist of permitted redirect domains and require HTTPS (and/or ensure the redirect host matches SITE_HOST or a configured list). Reject arbitrary external URLs to prevent open-redirect/phishing abuse.

- Medium — payments/views.py — Suggested fix: Avoid logging raw third-party error strings and exception traces that may contain secrets (e.g., stripe errors) at high verbosity. Sanitize or redact sensitive fields from StripeClientError before logging (and drop exc_info=True in production logs), or log only a non-sensitive error code/message and store full details in a secure audit store.

- Medium — payments/views.py — Suggested fix: Do not unconditionally return HTTP 200 on dispatch_event exceptions (which suppresses retries). Either return a 5xx error so Stripe will retry the webhook when processing fails, or implement a controlled retry mechanism plus durable error reporting. At minimum, document and intentionally handle the tradeoff and ensure failures are retried or alerted so an attacker cannot silently prevent processing.

- High — payments/webhooks.py — No Stripe webhook signature verification or explicit replay protection: verify the Stripe-Signature header (use stripe.Webhook.construct_event with your endpoint secret) before dispatching handlers and enforce idempotency (e.g., persist and unique-index stripe_event_id or ledger event id and skip events already processed).

- High — scripts/pr_review_llm.sh — Potential exfiltration of repository contents (including secrets/PII) to external LLM providers via the llm/OpenAI model calls and by writing full diffs to disk: do not send raw diffs to external services; implement automated secret redaction, require an explicit opt-in, or restrict the script to local/self-hosted models only; protect or avoid persistent storage of diffs (use restrictive file perms / ephemeral in-memory processing).

- High — payments/webhooks.py — Missing idempotency checks before destructive side-effects (e.g., deleting course_enrollment): ensure handlers check whether the incoming event has already been applied (by event id / ledger entries) and avoid performing destructive operations unless the event is authenticated and not already processed; add audit logging for destructive changes.

- Medium — payments/webhooks.py — Stripe event id stored but not validated/skipped (risk of duplicate processing): add a database uniqueness constraint on stripe_event_id (or separate WebhookEvent table with unique event id) and check before applying changes; ensure ledger entry creation is idempotent.

- Medium — thinkelearn/backends/allauth.py — Auto-linking social accounts to existing users based only on provider-supplied email_verified flags can enable account takeover if the provider's verification is untrusted: require additional confirmation (e.g., send confirmation email to existing account), restrict auto-linking to trusted providers, or validate provider-specific verification claims before connecting accounts.

- Medium — requirements.txt & pyproject.toml — Dev/test tools and potentially outdated/unsafe package pins (e.g., cffi==2.0.0, adding many dev deps into requirements) increase attack surface if installed in production: separate production requirements from dev/test dependencies, remove or move playwright/pytest/dev-only packages out of production installs, and review/upgrade any very old packages to versions without known CVEs.

- Low — payments/webhooks.py — Detailed error logging (including str(exc)) when email sending fails may expose sensitive data in logs: avoid logging sensitive payloads or stack traces to info/error logs, sanitize/log minimal error metadata, and ensure log storage/retention policies limit exposure.

- High — thinkelearn/settings/base.py: AUTHENTICATION_BACKENDS ordering + invalid setting allows unintended username authentication.
  Suggested fix: remove the invalid ACCOUNT_LOGIN_METHODS setting and replace with the correct allauth setting:
  - ACCOUNT_AUTHENTICATION_METHOD = "email"
  - ACCOUNT_USERNAME_REQUIRED = False
  Ensure your User model uses EMAIL as USERNAME_FIELD (or adjust accordingly). Reorder AUTHENTICATION_BACKENDS so the allauth backend is evaluated first (e.g. ["allauth.account.auth_backends.AuthenticationBackend", "django.contrib.auth.backends.ModelBackend"]) or otherwise ensure ModelBackend cannot be used to bypass email-only authentication.

- Medium — thinkelearn/settings/base.py: SecurityMiddleware is not first in MIDDLEWARE, reducing guarantees that HSTS/SSL/other security headers are applied consistently.
  Suggested fix: move "django.middleware.security.SecurityMiddleware" to the top of the MIDDLEWARE list (before CommonMiddleware and any middleware that may set or depend on security-related headers).

- Medium — thinkelearn/settings/base.py & thinkelearn/settings/production.py: SOCIALACCOUNT_PROVIDERS (Google) uses os.environ.get for client_id/secret but production does not validate these creds; leaving APP values as None can cause silent misconfiguration and unexpected auth behavior.
  Suggested fix: add explicit checks in production.py to require GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET when social login is expected (raise ImproperlyConfigured if missing), and avoid leaving provider APP credentials set to None.

- Medium — thinkelearn/settings/base.py: ACCOUNT_USER_MODEL_USERNAME_FIELD = None may be incompatible with the default User model and could lead to unexpected authentication/creation behavior.
  Suggested fix: if you rely on email-only accounts, ensure you use a custom User model with USERNAME_FIELD = "email" and set ACCOUNT_USERNAME_REQUIRED = False; otherwise set ACCOUNT_USER_MODEL_USERNAME_FIELD to the actual username field name.

- INFO — assets/css/styles.css — Suggested fix: No security-relevant issues found in this diff; no remediation required.

- Medium — assets/css/main.css — Removal of iframe sizing rules (.max-w-full iframe, .video-container-vertical) can allow embedded third-party iframes to overflow layout and overlap UI, increasing risk of clickjacking or UI-based spoofing.
  Suggested fix: restore responsive iframe CSS (max-width:100%; width:100%; height:auto; aspect-ratio as required) and in HTML/templating add proper iframe hardening (sandbox attribute with minimal allowances, referrerpolicy, allowfullscreen only if needed). Enforce CSP frame-src/frame-ancestors restrictions to limit allowed iframe sources.

- Medium — assets/css/main.css — Deletion of pointer-events: none on overlay/zoom UI (.gallery-zoom-icon) may allow overlays to become interactive and capture clicks, enabling accidental navigation or malicious click targets over site controls.
  Suggested fix: restore pointer-events: none for purely decorative overlays or explicitly set pointer-events only on intended interactive elements. Review any overlay z-index and event handling to ensure overlays do not intercept clicks accidentally.
