# Stripe Payment Integration - Implementation Plan

**Version:** 2.1
**Date:** 2025-12-29
**Status:** Phase 1 COMPLETE ✅ | Phase 2 In Progress
**Related PR:** #26 (Phase 1 implementation)

## Executive Summary

This document outlines a comprehensive plan to implement Stripe payment processing for course enrollments in THINK eLearn. The implementation will support **both pay-what-you-can and fixed-price courses**, maintain data integrity, ensure security, and follow the project's testing standards (55%+ coverage with focus on business logic).

**Implementation Scope:**

- **Pricing Models**: Pay-what-you-can (PWYC), fixed-price, and free courses
- **Payment Flow**: Stripe Checkout Session (redirect flow)
- **Currency**: Canadian Dollar (CAD) with multi-currency design for future expansion
- **Refunds**: Automated 30-day refund window (configurable per product)
- **Timeline**: **6 weeks** to production-ready deployment

**Key Principles:**

- **Security First**: PCI DSS compliance, authorization checks, secure API key handling
- **Data Integrity**: Atomic transactions, idempotency, proper error recovery
- **Test-Driven**: 100% business logic coverage before production deployment
- **Incremental**: Phased rollout with clear milestones and rollback capability

---

## Current State Analysis

### Existing LMS Infrastructure

**Models (lms/models.py):**

- `ExtendedCoursePage`: Course content with prerequisites, enrollment limits
- `CourseEnrollment` (from wagtail-lms): Tracks user enrollment in courses
- `CourseReview`: Student ratings with moderation
- `can_user_enroll()`: Business logic for enrollment eligibility

**Strengths:**

- 32 comprehensive tests with 100% coverage on business logic
- Robust prerequisites and enrollment limit validation
- Well-established patterns for model design

**Pre-Phase 1 Gaps (Now Addressed):**

- ~~No payment processing capability~~ ✅ Implemented in Phase 1
- ~~No concept of "products" or pricing~~ ✅ CourseProduct model with 3 pricing types
- ~~No payment state tracking~~ ✅ EnrollmentRecord with state machine
- ~~No integration with payment providers~~ ⏳ Stripe integration in Phase 2

---

## Architecture Design

### Core Principles

1. **Separation of Concerns**
   - `lms` app: Course content, enrollment eligibility, learning
   - `payments` app: Payment processing, Stripe integration, financial records
   - Clear boundaries with minimal coupling

2. **Data Integrity**
   - All multi-model updates wrapped in database transactions
   - Idempotency keys for Stripe operations
   - State machine for enrollment/payment status
   - Audit trail for all state transitions

3. **Security**
   - Per-request API key configuration (no global state)
   - Authorization checks: verify user owns enrollment before payment
   - Enrollment eligibility checks before creating payment records
   - PCI DSS compliance (never store card details)

4. **Error Resilience**
   - Graceful Stripe API failure handling
   - Webhook replay protection (idempotency)
   - Orphaned record cleanup
   - Retry mechanisms for transient failures

### Data Model Design

**Status:** ✅ IMPLEMENTED (Phase 1 - PR #26)

All models have been implemented with comprehensive validation, test coverage (96.64% on lms/models.py), and admin interfaces. See `lms/models.py` and `payments/models.py` for implementation details.

#### CourseProduct (lms/models.py) - IMPLEMENTED ✅

**Implemented Features:**

- **Three pricing models**: Free, Fixed-price, Pay-What-You-Can (PWYC)
- **Business methods**:
  - `validate_amount(amount)`: Validates payment based on pricing type with detailed error messages
  - `is_refund_eligible(enrollment_date)`: Checks if enrollment qualifies for refund
  - `clean()`: Model-level validation for pricing consistency
  - `format_price()`: Returns formatted price strings for display
- **Multi-currency ready**: CAD for launch, expandable design
- **Refund automation**: Configurable 30-day refund window (max 365 days)
- **Admin interface**: Full CRUD with bulk actions

#### EnrollmentRecord (lms/models.py) - IMPLEMENTED ✅

**Implemented Features:**

- **State machine with 5 states**: PENDING_PAYMENT, ACTIVE, PAYMENT_FAILED, CANCELLED, REFUNDED
- **Business methods**:
  - `create_for_user(user, product, amount)`: Creates enrollment with validation
  - `mark_paid()`: Transitions pending enrollment to active with CourseEnrollment creation
  - `transition_to(status)`: Enforces valid state transitions
- **Stripe integration fields**: checkout_session_id, payment_intent_id (both indexed)
- **Idempotency**: Unique idempotency_key prevents duplicate enrollments
- **Database constraints**: UniqueConstraint on (user, product), composite indexes for performance
- **Admin interface**: Full CRUD with 3 bulk actions (cancel, refund, mark failed)

**Key Enhancements:**

- PWYC courses require explicit amount (raises ValidationError if omitted)
- Separate status values for different failure scenarios
- Comprehensive docstrings with state transition examples
- 96.64% test coverage on business logic

#### Payment (payments/models.py) - IMPLEMENTED ✅

**Implemented Features:**

- **Payment states**: INITIATED, PROCESSING, SUCCEEDED, FAILED, REFUNDED
- **Audit trail**: failure_reason, stripe_event_id for debugging
- **Stripe references**: indexed for webhook lookups
- **Admin interface**: Read-only display of payment history

#### WebhookEvent (payments/models.py) - IMPLEMENTED ✅

**Implemented Features:**

- **Idempotency tracking**: Unique stripe_event_id prevents duplicate processing
- **Audit trail**: raw_event_data, success/error tracking
- **Debug support**: Enables webhook replay and troubleshooting
- **Admin interface**: View processed events and outcomes

---

## Security Requirements

### 1. API Key Management

**Requirement:** Thread-safe API key handling for multi-worker deployment

**Implementation:**

```python
# DON'T: Global state (not thread-safe)
stripe.api_key = settings.STRIPE_SECRET_KEY

# DO: Per-request API key
stripe.checkout.Session.create(
    api_key=settings.STRIPE_SECRET_KEY,
    # ... other params
)
```

**Approach:**

- Create `StripeClient` wrapper class
- All Stripe calls use per-request API key
- Thread-safe for gunicorn multi-worker deployment

### 2. Authorization Checks

**Requirement:** Verify user ownership before payment processing

**Implementation:**

```python
def create_checkout_session(request):
    # Verify user owns enrollment OR user is creating new enrollment
    enrollment = get_object_or_404(EnrollmentRecord, pk=enrollment_id)
    if enrollment.user != request.user:
        return JsonResponse({"error": "Unauthorized"}, status=403)
```

**Required Checks:**

1. User is authenticated (`@login_required`)
2. User owns the enrollment record
3. User meets course enrollment eligibility (`can_user_enroll()`)
4. Product is active and available

### 3. Enrollment Eligibility Validation

**Requirement:** Validate prerequisites and enrollment limits before payment

**Implementation:**

```python
# Before creating payment, validate eligibility
course = product.course
if not course.can_user_enroll(request.user):
    # Returns detailed error (already enrolled, prerequisites, limits)
    return JsonResponse(
        {"error": "Not eligible to enroll"},
        status=403
    )
```

### 4. Input Validation

**Requirements:**

- Validate all user inputs (amount, product_id, URLs)
- Sanitize metadata before sending to Stripe
- Rate limiting on payment endpoints (prevent abuse)
- CSRF protection (webhook endpoint exempt only)

### 5. PCI DSS Compliance

**Non-Negotiable Requirements:**

- ✅ Never store card details (use Stripe Elements/Checkout)
- ✅ Use HTTPS for all payment endpoints
- ✅ Validate webhook signatures (prevent spoofing)
- ✅ Log payment events for audit trail
- ✅ Implement access controls on payment data

---

## Implementation Phases

### Phase 1: Foundation & Models ✅ COMPLETE

**Status:** ✅ COMPLETE (PR #26 merged 2025-12-29)

**Goal:** Establish data models with comprehensive test coverage

**Tasks:**

1. **Tax Compliance Research (deferred to Phase 4)**
   - Tax handling deferred pending accountant consultation
   - Will implement in Phase 4 before production deployment

2. **Create Models ✅ COMPLETE**
   - [x] `CourseProduct` model with flexible pricing (free, fixed, PWYC) using TextChoices
   - [x] `CourseProduct` with currency field (CAD launch, multi-currency ready)
   - [x] `CourseProduct` with refund window configuration (30 days default, max 365)
   - [x] `CourseProduct.clean()` validation for pricing consistency
   - [x] `CourseProduct.format_price()` helper method
   - [x] `EnrollmentRecord` model with proper state machine
   - [x] `Payment` model with audit fields
   - [x] `WebhookEvent` model for idempotency
   - [x] Database migrations with proper indexes (consolidated into single migration 0003)
   - [x] Admin interfaces for all models with bulk actions

3. **Write Model Tests ✅ COMPLETE**
   - [x] `CourseProduct.validate_amount()` tests (3 tests)
   - [x] `CourseProduct.is_refund_eligible()` tests
   - [x] `CourseProduct.clean()` validation tests (4 tests)
   - [x] `CourseProduct.format_price()` tests (3 tests)
   - [x] `EnrollmentRecord` state transitions (5 comprehensive tests)
     - All valid transitions
     - Terminal states (cancelled, refunded)
     - Invalid transitions
     - No-op same-status transitions
   - [x] `EnrollmentRecord.create_for_user()` tests (8 tests)
     - Free enrollment, fixed-price, PWYC
     - PWYC amount requirement validation
     - Duplicate prevention
     - Prerequisites and enrollment limits
     - Idempotency key uniqueness
   - [x] Database constraint validation

4. **Integration with LMS ✅ COMPLETE**
   - [x] Add `can_user_enroll()` checks for existing EnrollmentRecord
   - [x] Integration tests for enrollment statuses (active, pending, cancelled, refunded)
   - [x] Ensure wagtail-lms CourseEnrollment compatibility
   - [x] All 71 LMS tests passing

**Deliverables:**

- Migration files: `lms/migrations/0003_courseproduct_enrollmentrecord_and_more.py` ✅
- Migration files: `payments/migrations/0001_initial.py` ✅
- Test files: `lms/tests.py` (71 tests, 96.64% coverage on lms/models.py) ✅
- Documentation: `docs/phase-2-enhancements.md` (merged into this plan) ✅
- Admin improvements: 3 bulk actions (cancel, refund, mark failed) ✅

**Success Criteria:** ✅ ALL MET

- [x] All 71 tests pass with 96.64% coverage on business logic
- [x] No regressions in existing LMS functionality
- [x] Models visible and functional in Django admin
- [x] Support for all three pricing types (free, fixed, PWYC)
- [x] Comprehensive admin bulk actions for enrollment management

---

### Phase 2: Payment Flow - Checkout Session (Week 2)

**Goal:** Implement Stripe Checkout Session flow with tests

**Tasks:**

1. **Stripe Client Wrapper (1 day)**
   - [ ] Create `payments/stripe_client.py`
   - [ ] `StripeClient` class with per-request API key
   - [ ] Error handling wrapper for Stripe API calls
   - [ ] Retry logic for transient failures
   - [ ] Mock client for testing

2. **Checkout Session Endpoint (2 days)**
   - [ ] `create_checkout_session` view
   - [ ] Input validation (product_id, amount, URLs)
   - [ ] Authorization checks (user, eligibility)
   - [ ] Amount validation using `product.validate_amount()`
   - [ ] Idempotency key generation
   - [ ] Atomic transaction:

     ```python
     with transaction.atomic():
         enrollment = EnrollmentRecord.create_for_user(...)
         payment = Payment.create_for_enrollment(...)
         session = stripe_client.create_checkout_session(...)
         enrollment.stripe_checkout_session_id = session.id
         enrollment.save()
     ```

   - [ ] Rollback on Stripe API failure

3. **Free Enrollment Flow (1 day)**
   - [ ] Handle amount=0 without Stripe
   - [ ] Create EnrollmentRecord with ACTIVE status
   - [ ] Create CourseEnrollment immediately
   - [ ] No Payment record needed

4. **Write Integration Tests (2 days)**
   - [ ] Mock Stripe API responses (success, failure)
   - [ ] Test full checkout session flow
   - [ ] Test free enrollment (amount=0)
   - [ ] Test authorization failures
   - [ ] Test eligibility failures (prerequisites, limits)
   - [ ] Test invalid amount (below min, above max)
   - [ ] Test orphaned record cleanup on API failure
   - [ ] Test concurrent enrollment attempts (idempotency)

**Deliverables:**

- `payments/stripe_client.py`
- `payments/views.py` (create_checkout_session)
- `payments/tests/test_checkout_flow.py`
- `payments/tests/test_free_enrollment.py`

**Success Criteria:**

- Can create Stripe Checkout Session in test mode
- Free enrollments work without Stripe
- All error paths tested
- No orphaned records on failures

---

### Phase 3: Webhook Handling + Refunds (Week 3)

**Goal:** Process Stripe webhooks reliably with idempotency + automated refund handling

**Tasks:**

1. **Webhook Infrastructure (1.5 days)**
   - [ ] `stripe_webhook` view with signature verification
   - [ ] Idempotency check using `WebhookEvent` model
   - [ ] Event routing by type
   - [ ] Error handling and logging
   - [ ] Return 200 for unhandled events (prevent retry storms)

2. **Success Handler (1.5 days)**
   - [ ] `checkout.session.completed` handler
   - [ ] Atomic transaction:

     ```python
     with transaction.atomic():
         # Create WebhookEvent first (prevents re-processing)
         WebhookEvent.objects.create(stripe_event_id=event.id, ...)

         # Update enrollment
         enrollment = get_enrollment_from_event(event)
         enrollment.status = EnrollmentRecord.Status.ACTIVE
         enrollment.amount_paid = amount
         enrollment.save()

         # Create CourseEnrollment
         if not enrollment.course_enrollment:
             enrollment.course_enrollment = CourseEnrollment.objects.create(...)
             enrollment.save()

         # Update payment
         payment.status = Payment.Status.SUCCEEDED
         payment.stripe_event_id = event.id
         payment.save()
     ```

   - [ ] Handle missing enrollment gracefully (log warning)

3. **Failure Handler (1 day)**
   - [ ] `checkout.session.async_payment_failed` handler
   - [ ] Set enrollment status to PAYMENT_FAILED
   - [ ] Record failure reason
   - [ ] No CourseEnrollment creation

4. **Refund Handler (1.5 days)**
   - [ ] `charge.refunded` webhook handler
   - [ ] Check refund eligibility using `product.is_refund_eligible()`
   - [ ] Atomic transaction:
     - Set enrollment status to REFUNDED
     - Set payment status to REFUNDED
     - Delete CourseEnrollment (revoke access)
     - Log refund event
   - [ ] Handle partial vs full refunds
   - [ ] Send refund confirmation email

5. **Email Notifications (1 day)**
   - [ ] Create email templates (`emails/refund_confirmation.html`)
   - [ ] Implement `send_refund_confirmation(enrollment)` helper
   - [ ] Email content includes:
     - Course name
     - Original amount paid
     - Refund amount (full vs partial)
     - Refund date
     - Expected processing time (5-10 business days)
     - Contact support link
   - [ ] Trigger from:
     - `charge.refunded` webhook handler
     - Admin bulk refund action
   - [ ] Test email delivery with Mailpit
   - [ ] Add plain text fallback for all emails

   **Future Email Notifications** (Phase 4+):
   - Enrollment confirmation (after successful payment)
   - Payment failed notification
   - Enrollment cancelled notification
   - Refund requested (when user submits refund request form)

6. **Write Webhook Tests (2 days)**
   - [ ] Mock Stripe webhook events
   - [ ] Test signature verification (valid, invalid)
   - [ ] Test idempotency (duplicate event delivery)
   - [ ] Test success flow (enrollment activated)
   - [ ] Test failure flow (enrollment marked failed)
   - [ ] **NEW:** Test refund flow (enrollment revoked, access removed)
   - [ ] **NEW:** Test refund outside refund window
   - [ ] Test missing enrollment handling
   - [ ] Test concurrent webhook processing
   - [ ] Test transaction rollback scenarios

**Deliverables:**

- `payments/views.py` (stripe_webhook)
- `payments/webhooks.py` (handler logic)
- `payments/emails.py` (send_refund_confirmation helper)
- `emails/refund_confirmation.html` (refund email template)
- `payments/tests/test_webhooks.py`
- `payments/tests/test_emails.py`

**Success Criteria:**

- Webhooks process correctly in test mode
- Idempotency prevents duplicate processing
- All database updates are atomic
- Failure scenarios logged and handled
- Refund confirmation emails sent successfully
- Email templates tested with Mailpit

---

### Phase 4: Error Handling + Frontend Integration (Week 4)

**Goal:** Production-ready error handling and frontend integration

**Tasks:**

1. **Orphaned Record Cleanup (1 day)**
   - [ ] Management command: `cleanup_abandoned_enrollments`
   - [ ] Find PENDING_PAYMENT records older than 24 hours
   - [ ] Set status to CANCELLED
   - [ ] Send notification email (optional)
   - [ ] Cron job setup

2. **Stripe API Error Handling (1.5 days)**
   - [ ] Network timeout handling
   - [ ] Rate limit handling (exponential backoff)
   - [ ] Invalid request error handling
   - [ ] Stripe service downtime handling
   - [ ] Comprehensive logging

3. **Settings Validation (0.5 days)**
   - [ ] Django check for required settings:
     - `STRIPE_SECRET_KEY`
     - `STRIPE_PUBLISHABLE_KEY`
     - `STRIPE_WEBHOOK_SECRET`
   - [ ] Validate settings on startup
   - [ ] Provide clear error messages

4. **Frontend Integration (2 days)**
   - [ ] Add "Enroll" button to course pages
   - [ ] Payment amount selection UI (for PWYC courses)
   - [ ] Success/failure/cancel pages
   - [ ] Checkout redirect flow
   - [ ] Error handling on frontend
   - [ ] Loading states
   - [ ] Mobile-responsive design

5. **Documentation (0.5 days)**
   - [ ] Frontend integration guide
   - [ ] Example HTML/JavaScript snippets
   - [ ] Environment variable reference

6. **Write Tests (1.5 days)**
   - [ ] Test cleanup command
   - [ ] Test all error scenarios
   - [ ] Test settings validation
   - [ ] Test frontend templates render correctly

**Deliverables:**

- `payments/management/commands/cleanup_abandoned_enrollments.py`
- `payments/checks.py` (Django system checks)
- `payments/tests/test_error_handling.py`
- `docs/stripe-frontend-integration.md`
- Updated course page templates with enroll buttons
- Success/failure/cancel page templates

**Success Criteria:**

- Graceful handling of all Stripe API errors
- Orphaned records cleaned up automatically
- Clear error messages for misconfiguration
- Frontend can initiate Checkout Session flow
- Mobile-responsive payment UI
- Clear documentation for future developers

---

### Phase 5: Production Preparation (Week 5)

**Goal:** Production deployment readiness

**Tasks:**

1. **Monitoring & Logging (2 days)**
   - [ ] Payment success/failure metrics
   - [ ] Webhook processing metrics
   - [ ] Error rate monitoring
   - [ ] Alert thresholds
   - [ ] Sentry integration for payment errors

2. **Security Audit (2 days)**
   - [ ] Code review for security issues
   - [ ] Penetration testing checklist
   - [ ] Authorization verification
   - [ ] Input validation review
   - [ ] PCI DSS compliance checklist

3. **Performance Testing (1 day)**
   - [ ] Load test payment endpoints
   - [ ] Database query optimization
   - [ ] Index verification
   - [ ] Concurrent request handling

4. **Documentation (2 days)**
   - [ ] Admin user guide
   - [ ] Troubleshooting guide
   - [ ] Runbook for common issues
   - [ ] Stripe webhook setup instructions
   - [ ] Environment configuration guide

**Deliverables:**

- `docs/stripe-admin-guide.md`
- `docs/stripe-troubleshooting.md`
- `docs/stripe-production-deployment.md`
- Security audit report

**Success Criteria:**

- All security checks pass
- Performance acceptable under load
- Complete documentation
- Monitoring in place

---

### Phase 6: Deployment & Validation (Week 6)

**Goal:** Safe production deployment

**Tasks:**

1. **Staging Deployment (2 days)**
   - [ ] Deploy to Railway staging environment
   - [ ] Configure Stripe test mode
   - [ ] Test webhooks from Stripe
   - [ ] End-to-end testing
   - [ ] Fix any deployment issues

2. **Production Deployment (1 day)**
   - [ ] Deploy to production with feature flag (disabled)
   - [ ] Configure Stripe production keys
   - [ ] Set up webhook endpoint in Stripe dashboard
   - [ ] Verify webhook delivery

3. **Controlled Rollout (2 days)**
   - [ ] Enable for test course only
   - [ ] Process test transactions
   - [ ] Monitor for 24 hours
   - [ ] Gradual rollout to all courses

4. **Post-Deployment Validation (2 days)**
   - [ ] Monitor error rates
   - [ ] Verify webhook processing
   - [ ] Check database integrity
   - [ ] Review payment records

**Deliverables:**

- Production deployment
- Monitoring dashboards
- Post-deployment report

**Success Criteria:**

- Zero critical errors
- Webhooks processing correctly
- Successful test transactions
- Team trained on admin operations

---

## Testing Strategy

### Test Coverage Requirements

**Target: 100% coverage on business logic** (following project standards)

**What We Test:**

1. **Business Logic** (100% coverage required)
   - Amount validation (`validate_amount`)
   - Enrollment eligibility checks
   - State transitions (PENDING → ACTIVE, etc.)
   - Free vs paid enrollment logic
   - Idempotency key generation
   - Webhook event routing
   - Error recovery logic

2. **Integration Points** (Critical paths)
   - Stripe API calls (mocked)
   - Database transactions (atomic operations)
   - Webhook signature verification
   - EnrollmentRecord ↔ CourseEnrollment creation

3. **Error Scenarios** (All failure modes)
   - Stripe API failures
   - Network timeouts
   - Invalid inputs
   - Unauthorized access
   - Duplicate requests
   - Database constraint violations

**What We DON'T Test:**

- Django/Stripe framework functionality
- Basic CRUD operations
- Django auth system
- Database itself

### Test Organization

```text
payments/tests/
├── __init__.py
├── test_models.py              # Model business logic
├── test_checkout_flow.py       # Checkout session integration
├── test_payment_intent_flow.py # PaymentIntent integration
├── test_webhooks.py            # Webhook processing
├── test_free_enrollment.py     # Free enrollment flow
├── test_error_handling.py      # Error scenarios
├── test_authorization.py       # Security checks
└── fixtures.py                 # Test data and mocks

lms/tests/
├── test_payment_models.py      # LMS payment model integration
└── test_enrollment_eligibility.py  # Integration with can_user_enroll
```

### Mock Strategy

**Stripe API Mocking:**

```python
# Use unittest.mock for Stripe API calls
from unittest.mock import patch, MagicMock

@patch('payments.stripe_client.stripe.checkout.Session.create')
def test_create_checkout_session_success(mock_create):
    mock_create.return_value = MagicMock(
        id='cs_test_123',
        url='https://checkout.stripe.com/test'
    )
    # Test logic
```

**Webhook Event Fixtures:**

```python
# Create realistic webhook event fixtures
CHECKOUT_SESSION_COMPLETED = {
    "id": "evt_test_123",
    "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": "cs_test_123",
            "payment_status": "paid",
            "metadata": {
                "enrollment_record_id": "1"
            }
        }
    }
}
```

### CI/CD Integration

**GitHub Actions Workflow:**

```yaml
test:
  - name: Run payment tests
    run: |
      docker-compose exec web python manage.py test payments
      docker-compose exec web python manage.py test lms.tests.test_payment_models

  - name: Check coverage
    run: |
      docker-compose exec web pytest --cov=payments --cov-report=term-missing
      # Fail if coverage < 90% on payments app
```

---

## Environment Configuration

### Required Environment Variables

**Stripe Keys:**

```bash
# Required for all environments
STRIPE_SECRET_KEY=sk_test_...              # Test mode for dev/staging
STRIPE_PUBLISHABLE_KEY=pk_test_...         # Test mode for dev/staging
STRIPE_WEBHOOK_SECRET=whsec_...            # From Stripe dashboard

# Production only
STRIPE_SECRET_KEY=sk_live_...              # Live mode
STRIPE_PUBLISHABLE_KEY=pk_live_...         # Live mode
```

**Settings:**

```python
# thinkelearn/settings/base.py

# Stripe configuration
STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.environ.get("STRIPE_PUBLISHABLE_KEY")
STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET")
STRIPE_CURRENCY = os.environ.get("STRIPE_CURRENCY", "usd")

# Validation: Fail fast if missing in production
if not DEBUG:
    required_settings = [
        "STRIPE_SECRET_KEY",
        "STRIPE_PUBLISHABLE_KEY",
        "STRIPE_WEBHOOK_SECRET",
    ]
    missing = [s for s in required_settings if not os.environ.get(s)]
    if missing:
        raise ImproperlyConfigured(
            f"Missing required Stripe settings: {', '.join(missing)}"
        )
```

### Railway Configuration

**railway.toml:**

```toml
[deploy]
startCommand = "gunicorn thinkelearn.wsgi:application"

[build]
builder = "nixpacks"

[environments.production]
# Stripe webhook URL: https://thinkelearn.com/payments/stripe/webhook/
```

**Stripe Webhook Setup:**

1. Go to Stripe Dashboard → Developers → Webhooks
2. Add endpoint: `https://thinkelearn.com/payments/stripe/webhook/`
3. Select events:
   - `checkout.session.completed`
   - `checkout.session.async_payment_failed`
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
4. Copy webhook signing secret to Railway env vars

---

## Rollback Plan

### If Issues Arise in Production

**Phase 1: Immediate Response (< 5 minutes)**

1. Disable payment endpoints via feature flag
2. Post notice on course pages: "Enrollments temporarily unavailable"
3. Notify team via Sentry/Slack

**Phase 2: Investigation (< 30 minutes)**

1. Check Sentry for errors
2. Review payment/enrollment records in admin
3. Check Stripe dashboard for webhook failures
4. Review application logs

**Phase 3: Resolution Options**

**Option A: Quick Fix (< 2 hours)**

- Apply hotfix
- Deploy to staging
- Test thoroughly
- Deploy to production
- Re-enable feature flag

**Option B: Rollback (< 30 minutes)**

- Revert to previous deployment
- Database state already consistent (no schema changes mid-phase)
- Manually process any pending enrollments

**Phase 4: Post-Mortem**

- Document issue and resolution
- Update tests to prevent recurrence
- Review monitoring thresholds

### Database Rollback Considerations

**Migration Rollback:**

```bash
# Each phase has reversible migrations
python manage.py migrate lms 0002  # Rollback Phase 1 migrations
python manage.py migrate payments zero  # Remove payments app
```

**Data Preservation:**

- Payment records preserved (even if app disabled)
- EnrollmentRecords can be manually activated
- No data loss, only feature availability

---

## Success Metrics

### Development Metrics

**Code Quality:**

- [ ] 100% test coverage on business logic
- [ ] Zero critical security vulnerabilities
- [ ] Code review approved by 2+ reviewers

**Performance:**

- [ ] Payment endpoint response time < 500ms (p95)
- [ ] Webhook processing < 200ms (p95)
- [ ] Database queries optimized (< 10 queries per request)

### Production Metrics

**Reliability:**

- [ ] 99.9% payment success rate
- [ ] Zero duplicate charges
- [ ] 100% webhook processing success
- [ ] < 0.1% orphaned enrollments

**Business Metrics:**

- [ ] Course enrollment conversion rate
- [ ] Average payment amount
- [ ] Revenue tracking accuracy
- [ ] Refund rate

**Monitoring:**

- [ ] Payment flow dashboards
- [ ] Error rate alerts
- [ ] Daily reconciliation reports
- [ ] Sentry error tracking

---

## Risk Mitigation

### Identified Risks & Mitigations

**Risk 1: Stripe API Changes**

- **Impact:** High - Could break payment flow
- **Likelihood:** Low - Stripe maintains backward compatibility
- **Mitigation:**
  - Pin Stripe SDK version
  - Subscribe to Stripe API changelog
  - Test against Stripe test mode regularly

**Risk 2: Webhook Delivery Failures**

- **Impact:** High - Enrollments not activated
- **Likelihood:** Medium - Network issues, downtime
- **Mitigation:**
  - Idempotent webhook handling
  - Stripe automatic retry (up to 72 hours)
  - Manual reconciliation script
  - Monitoring and alerts

**Risk 3: Data Inconsistency**

- **Impact:** Critical - Lost revenue, duplicate charges
- **Likelihood:** Low - With proper transactions
- **Mitigation:**
  - Atomic database transactions
  - Idempotency keys
  - Daily reconciliation reports
  - Audit trail (WebhookEvent model)

**Risk 4: Security Breach**

- **Impact:** Critical - PCI DSS violation, data leak
- **Likelihood:** Low - With security audit
- **Mitigation:**
  - Security audit before production
  - Penetration testing
  - Regular security reviews
  - Stripe handles all card data (PCI compliance)

**Risk 5: Performance Degradation**

- **Impact:** Medium - Poor user experience
- **Likelihood:** Medium - Under load
- **Mitigation:**
  - Load testing before production
  - Database indexing
  - Query optimization
  - Horizontal scaling (Railway)

---

## Dependencies & Prerequisites

### External Dependencies

**Stripe Account:**

- [ ] Stripe account created
- [ ] Test mode keys obtained
- [ ] Production mode enabled (requires verification)
- [ ] Webhook endpoint registered

**Environment:**

- [ ] Railway production environment
- [ ] HTTPS enabled (required for Stripe)
- [ ] Domain configured (for webhook endpoint)

### Internal Dependencies

**Codebase:**

- [ ] Django 5.2.3+
- [ ] PostgreSQL database
- [ ] Existing LMS models (ExtendedCoursePage, CourseEnrollment)
- [ ] User authentication system

**Team:**

- [ ] Developer familiar with Stripe (or learning time allocated)
- [ ] QA resources for testing
- [ ] Access to Stripe dashboard

---

## Timeline Summary

**Total Duration:** 6 weeks (reduced from original 8 weeks)

| Phase | Duration | Focus | Deliverables |
| ----- | -------- | ----- | ------------ |
| Phase 1 | Week 1 | Models & Tests + Tax Research | Migrations, 100% model coverage, tax strategy |
| Phase 2 | Week 2 | Checkout Session Flow | Working checkout with tests |
| Phase 3 | Week 3 | Webhooks + Refunds | Reliable webhook processing, automated refunds |
| Phase 4 | Week 4 | Error Handling + Frontend | Production-ready resilience, payment UI |
| Phase 5 | Week 5 | Production Prep | Security audit, monitoring, documentation |
| Phase 6 | Week 6 | Deployment | Safe rollout to production |

**Timeline Changes from Original Plan:**

- **Removed:** Payment Intent flow (Phase 4) - using Checkout Session only
- **Merged:** Frontend integration into Phase 4 (was separate Phase 6)
- **Added:** Tax research in Phase 1, refund handling in Phase 3
- **Result:** 2 weeks faster to production (6 weeks vs 8 weeks)

**Critical Path:**

- Phases 1-3 are sequential (foundation required)
- Phases 4-5 can partially overlap (frontend + production prep)
- Phase 6 requires all previous phases complete

---

## ~~Open Questions &~~ Decisions Made ✅

**All questions have been answered. Ready to proceed with Phase 1.**

### Business Decisions ✅

1. **Pricing Strategy** ✅ DECIDED
   - [x] Support both PWYC and fixed-price courses from day 1
   - [x] Use `pricing_type` field (free/fixed/pwyc) for flexibility
   - [x] Per-product min/max for PWYC (default: $0-$1000 CAD)
   - [x] **Decision:** Launch with PWYC to build userbase, add fixed pricing later
   - [x] **Tax handling:** Research Canadian GST/HST requirements (Phase 1 task)

2. **Refund Policy** ✅ DECIDED
   - [x] Automated refunds (build trust, easy for customers)
   - [x] 30-day refund window (configurable per product via `refund_window_days`)
   - [x] Optional: Collect refund reason for feedback
   - [x] **Decision:** Automated with 30-day default, configurable for flexibility

3. **Free Enrollments** ✅ DECIDED
   - [x] Skip Stripe entirely for $0 enrollments
   - [x] Free courses (pricing_type='free') activate immediately
   - [x] PWYC courses with amount=$0 also skip Stripe
   - [x] **Decision:** No payment method required for free

4. **Revenue Sharing** ✅ DECIDED
   - [x] Not for initial launch (scope reduction)
   - [x] THINK eLearn is sole course creator
   - [x] No external collaborators or partnerships yet
   - [x] **Decision:** Document as future enhancement

### Technical Decisions ✅

1. **Payment Flow** ✅ DECIDED
   - [x] Use Checkout Session only (redirect to Stripe)
   - [x] **Not implementing:** Payment Intent (custom UI)
   - [x] **Rationale:** Simpler, faster to production, PCI compliant, mobile-friendly
   - [x] **Mobile:** Checkout Session is fully mobile-responsive (no app needed)
   - [x] **Decision:** Checkout Session only for MVP

2. **Currency Support** ✅ DECIDED
   - [x] Launch with CAD only (Canadian business, matches bank account)
   - [x] Design supports multi-currency (currency field in model)
   - [x] Stripe handles automatic conversion for international customers
   - [x] **Future:** Add USD, EUR, GBP when needed
   - [x] **Decision:** CAD launch, multi-currency ready

3. **Subscriptions** ✅ DECIDED
   - [x] Not for initial launch (scope reduction)
   - [x] Individual course purchases only
   - [x] **Future:** Add when content library justifies subscriptions
   - [x] **Decision:** Document as future enhancement

4. **Coupon Codes** ✅ DECIDED
   - [x] Not for initial launch (scope reduction)
   - [x] PWYC model serves similar purpose initially
   - [x] **Future:** Add with fixed pricing or subscriptions
   - [x] **Decision:** Document as future enhancement

---

## Future Enhancements (Out of Scope for MVP)

The following features are **not included in the 6-week implementation** but are designed for easy addition later:

### Payment Features

1. **Payment Intent Flow**
   - Custom payment UI (alternative to Checkout redirect)
   - More brand control, complex payment flows
   - **Effort:** ~1 week
   - **When:** If custom payment UI becomes requirement

2. **Coupon/Discount Codes**
   - Stripe Coupon integration or custom system
   - Fixed amount or percentage discounts
   - **Effort:** ~3 days
   - **When:** With fixed pricing rollout

3. **Subscription Billing**
   - Monthly/annual course access subscriptions
   - Stripe Subscriptions API integration
   - **Effort:** ~2 weeks
   - **When:** Sufficient content library (10+ courses)

### Multi-Currency Support

1. **Additional Currencies**
   - USD, EUR, GBP support (model already supports)
   - Per-product currency selection
   - **Effort:** ~2 days (mostly configuration)
   - **When:** Significant international user base

### Revenue Management

1. **Revenue Sharing / Instructor Payouts**
   - Stripe Connect integration
   - Track instructor revenue shares
   - Automated payout scheduling
   - **Effort:** ~2-3 weeks
   - **When:** Third-party course hosting begins

2. **Advanced Tax Handling**
   - Stripe Tax integration for automated tax calculation
   - Multi-jurisdiction tax compliance
   - **Effort:** ~1 week
   - **When:** Revenue exceeds GST/HST threshold or multi-currency support added

### Administrative Features

1. **Refund Management Dashboard**
   - Admin UI for reviewing refund requests
   - Refund analytics and reporting
   - **Effort:** ~3 days
   - **When:** Refund volume warrants manual review

2. **Payment Analytics**
   - Revenue dashboards, cohort analysis
   - Conversion funnel tracking
   - **Effort:** ~1 week
   - **When:** Sufficient transaction volume for insights

**Design Note:** All models are designed to support these features. Currency field, pricing_type flexibility, and clean separation of concerns mean these enhancements require minimal model changes.

---

## Appendix

### Glossary

**Checkout Session:** Stripe hosted payment page (redirect flow)
**Payment Intent:** Server-side payment object for custom UIs
**Idempotency:** Preventing duplicate operations with unique keys
**Webhook:** HTTP callback from Stripe when events occur
**PCI DSS:** Payment Card Industry Data Security Standard

### Related Documentation

- [Stripe API Documentation](https://stripe.com/docs/api)
- [Stripe Webhooks Guide](https://stripe.com/docs/webhooks)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- [Django Transactions](https://docs.djangoproject.com/en/5.0/topics/db/transactions/)

### Project-Specific References

- `docs/lms-implementation-status.md` - Current LMS state
- `CLAUDE.md` - Project overview and standards
- `lms/tests.py` - Testing patterns to follow
- `.github/workflows/ci.yml` - CI/CD pipeline

---

## Approval & Sign-Off

**Plan Author:** Claude Code
**Initial Date:** 2025-12-28
**Updated:** 2025-12-29
**Version:** 2.0 (Updated with business decisions)

**Business Decisions:** ✅ All answered (see "Decisions Made" section)
**Scope:** MVP - 6 weeks to production
**Status:** Ready for Phase 1 implementation

**Implementation Changes from v1.0:**

- [x] All business questions answered
- [x] Timeline reduced from 8 weeks to 6 weeks
- [x] Payment Intent flow removed (Checkout Session only)
- [x] Tax research added to Phase 1
- [x] Refund automation added to Phase 3
- [x] Frontend merged into Phase 4
- [x] Future enhancements documented

**Next Steps:**

1. ✅ ~~Review this plan with stakeholders~~ - COMPLETE
2. ✅ ~~Answer open questions~~ - COMPLETE
3. ✅ **Phase 1: Foundation & Models** - COMPLETE (PR #26)
4. **Phase 2: Payment Flow - Checkout Session** - In Progress

---

**END OF IMPLEMENTATION PLAN**
