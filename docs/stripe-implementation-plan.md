# Stripe Payment Integration - Implementation Plan

**Version:** 2.0
**Date:** 2025-12-29
**Status:** Planning - Updated with Business Decisions
**Related PR:** #21 (superseded by this plan)

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

**Gaps:**

- No payment processing capability
- No concept of "products" or pricing
- No payment state tracking
- No integration with payment providers

### Issues with PR #21

**Critical Issues:**

1. Zero test coverage (839 lines untested)
2. Security vulnerabilities (race conditions, missing auth checks)
3. Data integrity issues (no transactions, orphaned records)
4. Business logic bugs (rejects free enrollments, wrong status mappings)
5. Missing production features (idempotency, audit logging, monitoring)

**Good Aspects:**

- Reasonable model structure (CourseProduct, EnrollmentRecord, Payment)
- Separate payments app (good separation of concerns)
- Pay-what-you-can validation logic
- Stripe webhook handling framework

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

#### CourseProduct (lms/models.py)

```python
class CourseProduct(models.Model):
    """Sellable course product linked to a course page.

    Supports three pricing models:
    - Free: No payment required
    - Fixed: Single price point
    - Pay-What-You-Can (PWYC): Flexible pricing within min/max range
    """

    course = models.OneToOneField(
        "lms.ExtendedCoursePage",
        on_delete=models.CASCADE,
        related_name="product",
    )

    # Pricing strategy
    pricing_type = models.CharField(
        max_length=20,
        choices=[
            ("free", "Free"),
            ("fixed", "Fixed Price"),
            ("pwyc", "Pay What You Can"),
        ],
        default="pwyc",
        help_text="Pricing model for this course",
    )

    # Fixed pricing
    fixed_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Fixed price (used when pricing_type='fixed')",
    )

    # PWYC pricing
    suggested_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Suggested PWYC amount (display only)",
    )
    min_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Minimum PWYC amount (0 to allow free)",
    )
    max_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1000,
        help_text="Maximum PWYC amount",
    )

    # Currency (CAD for launch, designed for expansion)
    currency = models.CharField(
        max_length=3,
        default="CAD",
        choices=[
            ("CAD", "Canadian Dollar"),
            # Future: ("USD", "US Dollar"),
            # Future: ("EUR", "Euro"),
            # Future: ("GBP", "British Pound"),
        ],
        help_text="Currency for pricing (CAD for launch)",
    )

    # Refund policy
    refund_window_days = models.IntegerField(
        default=30,
        help_text="Number of days customers can request refunds",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this product can be purchased",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Course Product"
        verbose_name_plural = "Course Products"

    def validate_amount(self, amount: Decimal) -> tuple[bool, str]:
        """Validate payment amount based on pricing type.

        Returns:
            (is_valid, error_message)
        """
        if self.pricing_type == "free":
            is_valid = amount == 0
            msg = "This course is free" if is_valid else "Amount must be 0 for free courses"
            return (is_valid, msg)

        elif self.pricing_type == "fixed":
            is_valid = amount == self.fixed_price
            msg = "" if is_valid else f"Price must be {self.fixed_price} {self.currency}"
            return (is_valid, msg)

        elif self.pricing_type == "pwyc":
            if amount < self.min_price:
                return (False, f"Minimum amount: {self.min_price} {self.currency}")
            if amount > self.max_price:
                return (False, f"Maximum amount: {self.max_price} {self.currency}")
            return (True, "")

        return (False, "Invalid pricing type")

    def is_refund_eligible(self, enrollment_date) -> bool:
        """Check if enrollment is still within refund window."""
        from django.utils import timezone
        delta = timezone.now() - enrollment_date
        return delta.days <= self.refund_window_days
```

**Key Changes from PR #21:**

- **Pricing flexibility**: Supports free, fixed, and PWYC models via `pricing_type`
- **Multi-currency design**: Currency field (CAD for launch, expandable)
- **Refund automation**: Configurable refund window per product
- **Better validation**: Returns (bool, error_message) tuple for detailed feedback
- **Business logic**: All validation is testable model methods

#### EnrollmentRecord (lms/models.py)

```python
class EnrollmentRecord(models.Model):
    """Tracks enrollment attempts with payment status."""

    class Status(models.TextChoices):
        # Initial state
        PENDING_PAYMENT = "pending_payment", "Pending Payment"
        # Success states
        ACTIVE = "active", "Active"
        # Failure states
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    product = models.ForeignKey(
        CourseProduct,
        on_delete=models.CASCADE,
        related_name="enrollments",
    )
    course_enrollment = models.OneToOneField(
        CourseEnrollment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="enrollment_record",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING_PAYMENT,
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Actual amount paid (0 for free enrollments)",
    )

    # Stripe references (indexed for webhook lookups)
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,  # Performance: webhook lookups
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,  # Performance: webhook lookups
    )

    # Idempotency and audit
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        help_text="Prevents duplicate enrollments",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Enrollment Record"
        verbose_name_plural = "Enrollment Records"
        unique_together = ("user", "product")
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["user", "status"]),
        ]
```

**Key Changes from PR #21:**

- Separate status values for different failure types
- `amount_paid` instead of `pay_what_you_can_amount` (records actual payment)
- Database indexes for performance
- `idempotency_key` for preventing duplicates
- No automatic CourseEnrollment creation (happens in transaction)

#### Payment (payments/models.py)

```python
class Payment(models.Model):
    """Individual payment transaction record."""

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    enrollment_record = models.ForeignKey(
        "lms.EnrollmentRecord",
        on_delete=models.CASCADE,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default="usd")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
    )

    # Stripe references (indexed)
    stripe_checkout_session_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )
    stripe_payment_intent_id = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
    )

    # Audit trail
    failure_reason = models.TextField(blank=True)
    stripe_event_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Last Stripe event that updated this payment",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "created_at"]),
        ]
```

**Key Changes from PR #21:**

- `PROCESSING` state for in-flight payments
- `failure_reason` for debugging
- `stripe_event_id` for audit trail
- Database indexes

#### WebhookEvent (payments/models.py) - NEW

```python
class WebhookEvent(models.Model):
    """Track processed webhook events for idempotency."""

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)

    # Store raw event for debugging
    raw_event_data = models.JSONField()

    # Processing outcome
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-processed_at"]
        indexes = [
            models.Index(fields=["event_type", "processed_at"]),
        ]
```

**Purpose:**

- Prevents duplicate webhook processing
- Provides audit trail
- Enables webhook replay for debugging

---

## Security Requirements

### 1. API Key Management

**Problem in PR #21:** Global `stripe.api_key` causes race conditions

**Solution:**

```python
# DON'T: Global state (PR #21 approach)
stripe.api_key = settings.STRIPE_SECRET_KEY

# DO: Per-request API key
stripe.checkout.Session.create(
    api_key=settings.STRIPE_SECRET_KEY,
    # ... other params
)
```

**Implementation:**

- Create `StripeClient` wrapper class
- All Stripe calls use per-request API key
- Thread-safe for gunicorn multi-worker deployment

### 2. Authorization Checks

**Problem in PR #21:** Users can create payments for other users' enrollments

**Solution:**

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

**Problem in PR #21:** No validation of prerequisites, enrollment limits

**Solution:**

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

### Phase 1: Foundation & Models (Week 1)

**Goal:** Establish data models with comprehensive test coverage + tax compliance research

**Tasks:**

1. **Tax Compliance Research (1 day) - NEW**
   - [ ] Research Canadian GST/HST requirements for educational courses
   - [ ] Determine if courses are GST/HST exempt
   - [ ] Investigate GST/HST registration threshold ($30k CAD/year)
   - [ ] Review inter-provincial sales tax requirements
   - [ ] Evaluate Stripe Tax integration for Canadian businesses
   - [ ] Document tax handling recommendation for MVP
   - [ ] Identify if accountant consultation is needed

2. **Create Models (2 days)**
   - [ ] `CourseProduct` model with flexible pricing (free, fixed, PWYC)
   - [ ] `CourseProduct` with currency field (CAD launch, multi-currency ready)
   - [ ] `CourseProduct` with refund window configuration
   - [ ] `EnrollmentRecord` model with proper state machine
   - [ ] `Payment` model with audit fields
   - [ ] `WebhookEvent` model for idempotency
   - [ ] Database migrations with proper indexes
   - [ ] Admin interfaces for all models

3. **Write Model Tests (2 days)**
   - [ ] `CourseProduct.validate_amount()` tests
     - Free pricing: amount must be 0
     - Fixed pricing: amount must match fixed_price
     - PWYC: within min/max range, edge cases
   - [ ] `CourseProduct.is_refund_eligible()` tests
     - Within refund window, outside window
   - [ ] `EnrollmentRecord` state transitions
     - Valid transitions (PENDING → ACTIVE, PENDING → FAILED, REFUNDED)
     - Invalid transitions (ACTIVE → PENDING)
   - [ ] `EnrollmentRecord.create_for_user()` tests
     - Free enrollment (amount=0, no Stripe)
     - Fixed-price enrollment
     - PWYC enrollment
     - Duplicate prevention (unique_together)
     - Idempotency key uniqueness
   - [ ] `Payment` creation and state management
   - [ ] Database constraint validation

4. **Integration with LMS (0.5 days)**
   - [ ] Add `can_user_enroll()` check for existing EnrollmentRecord
   - [ ] Update LMS tests to account for new models
   - [ ] Ensure wagtail-lms CourseEnrollment still works

**Deliverables:**

- **NEW:** `docs/stripe-tax-compliance-research.md` (tax research findings)
- Migration files: `lms/migrations/0003_courseproduct_enrollmentrecord.py`
- Migration files: `payments/migrations/0001_initial.py`
- Test files: `lms/tests/test_payment_models.py`
- Test files: `payments/tests/test_models.py`
- **Target:** 100% coverage on business logic

**Success Criteria:**

- Tax handling strategy documented and approved
- All tests pass
- No regressions in existing LMS functionality
- Models visible and functional in Django admin
- Support for all three pricing types (free, fixed, PWYC)

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

4. **Refund Handler (1.5 days) - NEW**
   - [ ] `charge.refunded` webhook handler
   - [ ] Check refund eligibility using `product.is_refund_eligible()`
   - [ ] Atomic transaction:
     - Set enrollment status to REFUNDED
     - Set payment status to REFUNDED
     - Delete CourseEnrollment (revoke access)
     - Log refund event
   - [ ] Handle partial vs full refunds
   - [ ] Send refund confirmation email (optional)

5. **Write Webhook Tests (2 days)**
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
- `payments/tests/test_webhooks.py`

**Success Criteria:**

- Webhooks process correctly in test mode
- Idempotency prevents duplicate processing
- All database updates are atomic
- Failure scenarios logged and handled

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
- [ ] All Copilot comments from PR #21 addressed
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

4. **Additional Currencies**
   - USD, EUR, GBP support (model already supports)
   - Per-product currency selection
   - **Effort:** ~2 days (mostly configuration)
   - **When:** Significant international user base

### Revenue Management

5. **Revenue Sharing / Instructor Payouts**
   - Stripe Connect integration
   - Track instructor revenue shares
   - Automated payout scheduling
   - **Effort:** ~2-3 weeks
   - **When:** Third-party course hosting begins

6. **Advanced Tax Handling**
   - Stripe Tax integration for automated tax calculation
   - Multi-jurisdiction tax compliance
   - **Effort:** ~1 week
   - **When:** Revenue exceeds GST/HST threshold or multi-currency support added

### Administrative Features

7. **Refund Management Dashboard**
   - Admin UI for reviewing refund requests
   - Refund analytics and reporting
   - **Effort:** ~3 days
   - **When:** Refund volume warrants manual review

8. **Payment Analytics**
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
3. **Assign resources** - Ready to proceed
4. **Begin Phase 1: Tax research + models + tests** - Week 1
5. PR #21 closed - Superseded by this implementation plan

---

**END OF IMPLEMENTATION PLAN**
