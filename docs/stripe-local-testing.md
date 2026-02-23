# Stripe Local Setup & Test (thinkelearn)

Use this guide to configure Stripe Checkout + webhooks for local development.

## Prereqs

- Local Django server running at `http://127.0.0.1:8000/` (or `make start`)
- Stripe test keys for the THINK eLearn org
- `STRIPE_SECRET_KEY` available in `.env` (for Docker-based Stripe container)

## 1) Set environment variables

Set the test keys for your local shell (or your `.env` if you use one):

```sh
export STRIPE_PUBLISHABLE_KEY="pk_test_..."
export STRIPE_SECRET_KEY="sk_test_..."
```

You will set `STRIPE_WEBHOOK_SECRET` in step 3 after the CLI is listening.

## 2) Start the local server

```sh
uv run python manage.py runserver --settings=thinkelearn.settings.dev
```

Keep this running in a separate terminal.

## 3) Start Stripe webhook forwarding

Preferred (Docker container, already wired in `docker-compose.yml`):

```sh
make start
docker-compose logs -f stripe
```

The Stripe container is started automatically by `start.sh` when
`STRIPE_SECRET_KEY` is set. In the Stripe logs, you will see a webhook signing
secret like:

```text
whsec_...
```

Set it in your shell:

```sh
export STRIPE_WEBHOOK_SECRET="whsec_..."
```

Note: If you restart the `stripe` container, you’ll get a new `whsec_...`.

Manual fallback (local Stripe CLI):

```sh
stripe listen --api-key "$STRIPE_SECRET_KEY" --forward-to http://127.0.0.1:8000/payments/webhook/
```

## 4) Create a Stripe Checkout session from the app

Use the site UI where checkout is triggered (course enrollment). The frontend
calls the backend endpoint:

- `POST /payments/checkout-session/`

You should be redirected to a Stripe-hosted checkout page.

## 5) Test a successful payment

Use Stripe test card:

- Card number: `4242 4242 4242 4242`
- Any future expiry date
- Any CVC
- Any ZIP

After payment, you should land on:

- `http://127.0.0.1:8000/payments/checkout/success/`

In the Stripe logs (`docker-compose logs -f stripe`), you should see a
`checkout.session.completed` event forwarded.

## 6) Verify webhook processing

Webhook endpoint: `POST /payments/webhook/`

Expected behaviors:

- Checkout completion sets the `Payment` status to `SUCCEEDED`.
- Enrollment status should transition from `PENDING_PAYMENT` to `ACTIVE`.

If you need a quick verification, check the Django logs for webhook processing
entries (warnings and errors are logged).

## 7) Test failure and refund flows (optional)

### Async payment failure

Use a test card that triggers async failure and confirm:

- `checkout.session.async_payment_failed` is received
- Enrollment transitions to `PAYMENT_FAILED`

### Refund

From Stripe Dashboard (Test mode), issue a refund for the charge. Confirm:

- `charge.refunded` is received
- Payment status updates to `REFUNDED`

## Troubleshooting

- If you see `Missing Stripe signature`, confirm `STRIPE_WEBHOOK_SECRET` matches
  the `whsec_...` shown in Stripe logs (`docker-compose logs -f stripe`).
- If checkout fails before redirect, confirm `STRIPE_SECRET_KEY` is set and
  correct.
- If the frontend shows a generic error, check Django logs for Stripe API errors.

## Related endpoints and files

- Checkout session endpoint: `payments/checkout-session/`
- Webhook endpoint: `payments/webhook/`
- Stripe client: `payments/stripe_client.py`
- Checkout JS: `thinkelearn/static/js/checkout.js`

## Verification checklist (local)

After a successful test checkout:

- The `checkout.session.completed` event is logged by Stripe CLI.
- `Payment` status is `SUCCEEDED` for the enrollment.
- Enrollment status is `ACTIVE`.
- The user lands on `http://127.0.0.1:8000/payments/checkout/success/`.

After a failed async payment (if tested):

- The `checkout.session.async_payment_failed` event is logged by Stripe CLI.
- `Payment` status is `FAILED` and has a `failure_reason`.
- Enrollment status is `PAYMENT_FAILED`.

After a refund (if tested):

- The `charge.refunded` event is logged by Stripe CLI.
- `Payment` status is `REFUNDED`.

### Quick SQL checks (SQLite)

If you want to verify directly in the local SQLite DB:

```sh
sqlite3 db.sqlite3
```

```sql
-- Latest payments
SELECT id, status, amount, stripe_checkout_session_id, stripe_payment_intent_id, stripe_event_id
FROM payments_payment
ORDER BY created_at DESC
LIMIT 5;

-- Latest enrollment records
SELECT id, status, stripe_checkout_session_id, stripe_payment_intent_id
FROM lms_enrollmentrecord
ORDER BY created_at DESC
LIMIT 5;
```

## Test card numbers (Stripe)

Use these to simulate common card failures during Checkout:

- `4000 0000 0000 0002` (card declined)
- `4000 0000 0000 9995` (insufficient funds)
- `4000 0000 0000 0069` (expired card)

Notes:

- These trigger immediate card failures (not async). For async failures, you must
  enable an async payment method in Checkout and use the method-specific test
  numbers from Stripe docs.
