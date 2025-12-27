# Payments (Stripe)

## Configuration

Set the following environment variables (defaults noted where applicable):

- `STRIPE_SECRET_KEY`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_CURRENCY` (default: `usd`)
- `STRIPE_PAY_WHAT_YOU_CAN_MIN` (default: `1.00`)
- `STRIPE_PAY_WHAT_YOU_CAN_MAX` (default: `1000.00`)

## Pay-what-you-can validation

The pay-what-you-can amount is validated server-side in the Stripe checkout/payment
endpoint before any Stripe API call is made. Validation rules:

- Amount must be a numeric value and can include cents.
- Amount must be within the configured range set by
  `STRIPE_PAY_WHAT_YOU_CAN_MIN` and `STRIPE_PAY_WHAT_YOU_CAN_MAX`.
- Requests outside that range return a `400` with an error message.

If an enrollment is free (amount of `0`), skip Stripe and use the existing
free-enrollment flow so the enrollment can be activated immediately.

## Webhooks

The Stripe webhook (`/payments/stripe/webhook/`) processes payment success/failure
notifications and updates both the enrollment record and the payment record
accordingly.
