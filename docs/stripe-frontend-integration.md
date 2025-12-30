# Stripe Frontend Integration Guide

**App:** `payments` + `lms`
**Flow:** Course page → Checkout Session → Redirect → Success/Cancel pages

---

## Overview

Course pages now use a lightweight JavaScript flow that posts to
`/payments/checkout-session/` and redirects the user to Stripe Checkout.
All UI state and validation are handled in `thinkelearn/static/js/checkout.js`.

Key components:

- **Course template include:** `lms/templates/lms/includes/checkout_enroll.html`
- **JavaScript:** `thinkelearn/static/js/checkout.js`
- **Backend endpoint:** `payments.views.create_checkout_session`
- **Redirect pages:**
  - `payments:checkout_success`
  - `payments:checkout_cancel`
  - `payments:checkout_failure`

---

## Template Integration

The course templates (`thinkelearn/templates/wagtail_lms/course_page.html`
and `lms/templates/lms/extended_course_page.html`) include:

```django
{% include "lms/includes/checkout_enroll.html" %}
```

This include reads:

- `product` (CourseProduct)
- `checkout_success_url`
- `checkout_cancel_url`
- `checkout_failure_url`

These are injected by `ExtendedCoursePage.get_context()` in `lms/models.py`.

---

## JavaScript Flow

The checkout script:

1. Validates the PWYC amount (if applicable)
2. POSTs JSON to `/payments/checkout-session/`
3. Redirects to `session_url` (Stripe Checkout)
4. Redirects to success page if the course is free

The script is loaded via:

```django
{% block extra_js %}
    {{ block.super }}
    <script src="{% static 'js/checkout.js' %}" defer></script>
{% endblock %}
```

---

## Success/Cancel Pages

Templates:

- `payments/templates/payments/checkout_success.html`
- `payments/templates/payments/checkout_cancel.html`
- `payments/templates/payments/checkout_failure.html`

The success page accepts the optional query string:

- `session_id` (Stripe Checkout Session ID)
- `free=1` (for free enrollments)

---

## API Payload

Example request from the frontend:

```json
{
  "product_id": 42,
  "amount": 25.00,
  "success_url": "https://example.com/payments/checkout/success/?session_id={CHECKOUT_SESSION_ID}",
  "cancel_url": "https://example.com/payments/checkout/cancel/"
}
```

`amount` is required only for PWYC courses.

---

## Error Handling

Frontend behavior:

- Displays inline error text for validation or API errors
- Shows a loading state while the request is in flight
- Leaves users on the page if Stripe cannot be reached

Backend behavior:

- Returns sanitized JSON errors (e.g., `{"error": "Invalid amount."}`)
- Uses Stripe retry/backoff logic in `payments/stripe_client.py`

---

## Environment Variables

| Variable | Purpose |
| --- | --- |
| `STRIPE_SECRET_KEY` | Stripe secret key used for server-side API calls |
| `STRIPE_PUBLISHABLE_KEY` | Stripe publishable key for frontend usage (reserved) |
| `STRIPE_WEBHOOK_SECRET` | Stripe webhook signing secret |
| `STRIPE_CURRENCY` | Default currency (CAD for launch) |
| `TASK_WORKER_CONCURRENCY` | Background task worker concurrency |
| `TASK_WORKER_LOG_LEVEL` | Background task worker log level |

## Railway Deployment

### Task Worker Service Setup

Background tasks (refund emails, abandoned enrollment cleanup) require a separate worker service in Railway to process the task queue.

**Steps to configure Railway task worker:**

1. **In Railway Dashboard:**
   - Navigate to your project
   - Click "New Service" → "Empty Service"
   - Name it "taskworker" (or similar)

2. **Configure the worker service:**
   - **Root Directory:** Same as web service (project root)
   - **Build Command:** `pip install uv && uv sync --frozen`
   - **Start Command:** `uv run python manage.py taskworker`
   - **Environment Variables:** Link to the same environment as your web service (Railway can share env vars across services)

3. **Environment variables required:**
   - `DATABASE_URL` (automatically provided by Railway PostgreSQL)
   - `DJANGO_SETTINGS_MODULE=thinkelearn.settings.production`
   - All Stripe variables (`STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, etc.)
   - `MAILTRAP_API_TOKEN` (for sending refund emails)
   - Optional: `TASK_WORKER_CONCURRENCY` (default: 4)
   - Optional: `TASK_WORKER_LOG_LEVEL` (default: INFO)

4. **Health Monitoring:**
   - The task worker runs continuously
   - Monitor logs via `railway logs taskworker`
   - Scheduled cleanup runs every 24 hours automatically

**Alternative: Railway CLI setup**

```bash
# Add worker service using Railway CLI
railway service create
# Name: taskworker
# Start command: uv run python manage.py taskworker

# Link environment variables
railway variables --service taskworker
```

**Verify deployment:**

```bash
# Check worker logs
railway logs -s taskworker

# You should see:
# INFO: Task worker started with 4 concurrent workers
# INFO: Listening for tasks...
```

---

## Local Testing Checklist

1. Create a Course + CourseProduct in Wagtail admin.
2. Visit the course page and verify the checkout card renders.
3. Use a Stripe test key and validate redirect behavior.
4. Confirm success/cancel pages render.
5. Start local task worker: `uv run python manage.py taskworker`
6. Verify background tasks process (check console for task logs).
