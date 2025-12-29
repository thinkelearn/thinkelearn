# Phase 2 Enhancements - Future Features

This document tracks features that are designed for but not implemented in Phase 1. These will be added in subsequent phases of the Stripe integration.

## Email Notifications (Phase 3 - Webhook Integration)

### Refund Confirmation Emails

**Status:** Not implemented in Phase 1
**Planned for:** Phase 3 (Webhook Handling + Refunds)
**Priority:** Medium

**Description:**
When a refund is processed (via webhook or admin action), send confirmation email to the user.

**Implementation Notes:**
- Trigger: `charge.refunded` webhook OR admin action `mark_as_refunded`
- Template: `emails/refund_confirmation.html`
- Content should include:
  - Course name
  - Original amount paid
  - Refund amount (full vs partial)
  - Refund date
  - Expected processing time (5-10 business days)
  - Contact support link

**Technical Approach:**
```python
# In webhook handler or admin action
from django.core.mail import send_mail
from django.template.loader import render_to_string

def send_refund_confirmation(enrollment):
    """Send refund confirmation email to user."""
    context = {
        'user': enrollment.user,
        'course': enrollment.product.course,
        'amount': enrollment.amount_paid,
        'currency': enrollment.product.currency,
        'refund_date': timezone.now(),
    }

    html_message = render_to_string(
        'emails/refund_confirmation.html',
        context
    )

    send_mail(
        subject=f'Refund Confirmation - {enrollment.product.course.title}',
        message='',  # Plain text fallback
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[enrollment.user.email],
        html_message=html_message,
    )
```

**Testing Requirements:**
- Test email sent on refund webhook
- Test email sent on admin bulk refund action
- Test email contains all required information
- Test plain text fallback
- Test with Mailpit in development

---

### Additional Email Notifications (Future)

1. **Enrollment Confirmation** (after successful payment)
   - Priority: High
   - Includes: Course access link, receipt, getting started guide

2. **Payment Failed Notification** (after failed payment attempt)
   - Priority: Medium
   - Includes: Failure reason, retry link, support contact

3. **Enrollment Cancelled** (admin or user-initiated)
   - Priority: Low
   - Includes: Cancellation reason, re-enrollment options

4. **Refund Requested** (when user requests refund via form)
   - Priority: Low (requires refund request UI first)
   - Includes: Request confirmation, processing timeline

---

## Related Documentation

- See `docs/stripe-implementation-plan.md` for full implementation timeline
- Phase 3 webhook handling: Lines 628-709
- Email integration details: To be added in Phase 4

---

**Last Updated:** 2025-12-29
**Author:** Claude Code
**Version:** 1.0
