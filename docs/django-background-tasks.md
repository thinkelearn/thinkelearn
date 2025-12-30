# Django Background Tasks - AI Assistant Guide

**Project:** THINK eLearn
**Django Version:** 6.0+
**Framework:** Django native `django.tasks` (NOT Celery, NOT Django-Q2)
**Purpose:** Explicit guidance for AI assistants to avoid framework confusion

---

## ⚠️ CRITICAL: Framework Identification

**This project uses Django 6.0's native background tasks framework.**

### ❌ DO NOT Use These Frameworks:
- **Celery** - Not installed, do not use `@app.task` or `delay()` syntax
- **Django-Q2** - Not installed, do not use `async_task()` or Q_CLUSTER
- **Django-RQ** - Not installed
- **Huey** - Not installed

### ✅ DO Use:
- **Django 6.0 `django.tasks`** - Native framework, use `@task` decorator and `.enqueue()` method

---

## Quick Syntax Reference

### Defining a Background Task

```python
# ✅ CORRECT - Django 6.0 native tasks
from django.tasks import task

@task()
def send_refund_email(enrollment_id: int) -> None:
    """Send refund confirmation email in background."""
    enrollment = EnrollmentRecord.objects.get(pk=enrollment_id)
    # ... email logic ...
```

```python
# ❌ WRONG - This is Celery syntax (DO NOT USE)
from celery import shared_task

@shared_task
def send_refund_email(enrollment_id):
    # DO NOT USE THIS SYNTAX
    pass
```

```python
# ❌ WRONG - This is Django-Q2 syntax (DO NOT USE)
from django_q.tasks import async_task

def send_refund_email(enrollment_id):
    # DO NOT USE THIS SYNTAX
    pass
```

### Enqueueing a Task (Immediate Execution)

```python
# ✅ CORRECT - Django 6.0 native
from payments.tasks import send_refund_email

send_refund_email.enqueue(enrollment_id=123)
```

```python
# ❌ WRONG - Celery syntax
send_refund_email.delay(123)  # DO NOT USE
send_refund_email.apply_async(args=[123])  # DO NOT USE
```

```python
# ❌ WRONG - Django-Q2 syntax
from django_q.tasks import async_task
async_task('payments.tasks.send_refund_email', 123)  # DO NOT USE
```

### Scheduling a Task (Delayed Execution)

```python
# ✅ CORRECT - Django 6.0 native
from django.utils import timezone
from datetime import timedelta

send_refund_email.enqueue(
    enrollment_id=123,
    eta=timezone.now() + timedelta(hours=1)  # Execute in 1 hour
)
```

```python
# ❌ WRONG - Celery syntax
send_refund_email.apply_async(
    args=[123],
    eta=timezone.now() + timedelta(hours=1)
)  # DO NOT USE
```

### Periodic/Scheduled Tasks (Cron-like)

```python
# ✅ CORRECT - Django 6.0 native scheduled tasks
from django.tasks import task
from datetime import timedelta

@task(
    run_every=timedelta(hours=24),  # Run daily
    queue="default"
)
def cleanup_abandoned_enrollments() -> None:
    """Clean up abandoned enrollments daily."""
    from django.utils import timezone
    cutoff = timezone.now() - timedelta(hours=24)

    abandoned = EnrollmentRecord.objects.filter(
        status=EnrollmentRecord.Status.PENDING_PAYMENT,
        created_at__lt=cutoff
    )

    count = abandoned.update(status=EnrollmentRecord.Status.CANCELLED)
    logger.info(f"Cleaned up {count} abandoned enrollments")
```

```python
# ❌ WRONG - Celery beat syntax
from celery.schedules import crontab

@app.task
def cleanup_abandoned_enrollments():
    pass

# Celery beat schedule (DO NOT USE)
app.conf.beat_schedule = {
    'cleanup-every-day': {
        'task': 'payments.tasks.cleanup_abandoned_enrollments',
        'schedule': crontab(hour=0, minute=0),
    },
}
```

---

## Configuration

### Settings Configuration

```python
# thinkelearn/settings/base.py

# ✅ CORRECT - Django 6.0 native tasks configuration
TASKS = {
    'default': {
        'BACKEND': 'django.tasks.backends.database.DatabaseBackend',
        # Optional: Use Redis for better performance
        # 'BACKEND': 'django.tasks.backends.redis.RedisBackend',
        # 'OPTIONS': {
        #     'url': os.environ.get('REDIS_URL', 'redis://localhost:6379/0'),
        # },
    }
}

# Task worker settings
TASK_WORKER_CONCURRENCY = int(os.environ.get('TASK_WORKER_CONCURRENCY', 4))
TASK_WORKER_LOG_LEVEL = os.environ.get('TASK_WORKER_LOG_LEVEL', 'INFO')
```

### Project Task Inventory

The THINK eLearn LMS uses two task entry points in `payments/tasks.py`:

- `send_refund_confirmation_task`: background email for Stripe refund notices
- `cleanup_abandoned_enrollments_task`: scheduled cleanup of stale enrollments

Example usage:

```python
from payments.tasks import send_refund_confirmation_task

send_refund_confirmation_task.enqueue(
    enrollment_id=123,
    refund_amount="10.00",
    original_amount="49.00",
    refund_date="2025-01-05T12:34:56-05:00",
    is_partial=True,
)
```

Manual cleanup (CLI):

```bash
python manage.py cleanup_abandoned_enrollments --hours 24
```

```python
# ❌ WRONG - Celery configuration (DO NOT USE)
CELERY_BROKER_URL = 'redis://localhost:6379/0'
CELERY_RESULT_BACKEND = 'redis://localhost:6379/0'
# DO NOT USE CELERY SETTINGS
```

```python
# ❌ WRONG - Django-Q2 configuration (DO NOT USE)
Q_CLUSTER = {
    'name': 'thinkelearn',
    'workers': 4,
}
# DO NOT USE DJANGO-Q2 SETTINGS
```

### Running the Task Worker

```bash
# ✅ CORRECT - Django 6.0 native
python manage.py taskworker

# With Docker
docker-compose exec web python manage.py taskworker

# With specific settings
python manage.py taskworker --workers 4 --log-level INFO
```

```bash
# ❌ WRONG - Celery commands
celery -A thinkelearn worker  # DO NOT USE
```

```bash
# ❌ WRONG - Django-Q2 commands
python manage.py qcluster  # DO NOT USE
```

---

## Common Patterns

### Pattern 1: Async Email from Webhook

**Use Case:** Send refund confirmation without blocking webhook response

```python
# payments/webhooks.py

from payments.tasks import send_refund_email_task

def handle_charge_refunded(event):
    """Handle refund webhook event."""
    # ... process refund ...

    # ✅ CORRECT - Enqueue background task
    send_refund_email_task.enqueue(
        enrollment_id=enrollment.id,
        refund_amount=refund_amount
    )

    # Webhook returns immediately (doesn't wait for email)
    return HttpResponse(status=200)
```

```python
# payments/tasks.py

from django.tasks import task
from django.core.mail import send_mail
import logging

logger = logging.getLogger(__name__)

@task()
def send_refund_email_task(enrollment_id: int, refund_amount: str) -> None:
    """Send refund confirmation email in background.

    Args:
        enrollment_id: EnrollmentRecord primary key
        refund_amount: Formatted refund amount string (e.g., "$50.00 CAD")
    """
    try:
        enrollment = EnrollmentRecord.objects.select_related(
            'user', 'product__course'
        ).get(pk=enrollment_id)

        send_mail(
            subject=f"Refund Processed: {enrollment.product.course.title}",
            message=f"Your refund of {refund_amount} has been processed.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[enrollment.user.email],
            fail_silently=False,
        )

        logger.info(f"Refund email sent for enrollment {enrollment_id}")

    except EnrollmentRecord.DoesNotExist:
        logger.error(f"Enrollment {enrollment_id} not found for email")
    except Exception as e:
        logger.error(f"Failed to send refund email: {e}")
        raise  # Re-raise for task retry mechanism
```

### Pattern 2: Scheduled Cleanup Task

**Use Case:** Daily cleanup of abandoned enrollments

```python
# payments/tasks.py

from django.tasks import task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)

@task(
    run_every=timedelta(hours=24),  # Run once per day
    queue="default"
)
def cleanup_abandoned_enrollments() -> None:
    """Clean up enrollments stuck in PENDING_PAYMENT for >24 hours.

    Runs daily at the time the task worker was started.
    """
    cutoff_time = timezone.now() - timedelta(hours=24)

    abandoned = EnrollmentRecord.objects.filter(
        status=EnrollmentRecord.Status.PENDING_PAYMENT,
        created_at__lt=cutoff_time
    )

    count = abandoned.count()

    if count > 0:
        abandoned.update(
            status=EnrollmentRecord.Status.CANCELLED,
            updated_at=timezone.now()
        )
        logger.info(f"Cleaned up {count} abandoned enrollments")
    else:
        logger.info("No abandoned enrollments to clean up")
```

### Pattern 3: Task with Retry Logic

**Use Case:** Retry failed email sends

```python
# payments/tasks.py

from django.tasks import task
from django.core.mail import send_mail

@task(
    max_retries=3,  # Retry up to 3 times
    retry_backoff=300,  # Wait 5 minutes between retries
)
def send_enrollment_confirmation(enrollment_id: int) -> None:
    """Send enrollment confirmation with retry logic."""
    try:
        enrollment = EnrollmentRecord.objects.get(pk=enrollment_id)

        send_mail(
            subject="Enrollment Confirmed",
            message="You are now enrolled!",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[enrollment.user.email],
            fail_silently=False,
        )

    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise  # Triggers retry
```

---

## Testing Background Tasks

### Test Task Execution Synchronously

```python
# payments/tests/test_tasks.py

import pytest
from django.core import mail
from payments.tasks import send_refund_email_task
from payments.models import EnrollmentRecord

@pytest.mark.django_db
class TestRefundEmailTask:
    """Tests for refund email background task."""

    def test_send_refund_email_success(self, enrollment_factory):
        """Test refund email is sent successfully."""
        enrollment = enrollment_factory(
            status=EnrollmentRecord.Status.REFUNDED,
            amount_paid=50.00
        )

        # Execute task synchronously in tests
        send_refund_email_task(
            enrollment_id=enrollment.id,
            refund_amount="$50.00 CAD"
        )

        # Verify email sent
        assert len(mail.outbox) == 1
        assert enrollment.user.email in mail.outbox[0].to
        assert "Refund Processed" in mail.outbox[0].subject

    def test_send_refund_email_missing_enrollment(self):
        """Test graceful handling of missing enrollment."""
        # Should not raise exception
        send_refund_email_task(
            enrollment_id=99999,
            refund_amount="$50.00 CAD"
        )
```

### Test Async Enqueueing

```python
# payments/tests/test_webhooks.py

import pytest
from unittest.mock import patch, MagicMock
from payments.webhooks import handle_charge_refunded

@pytest.mark.django_db
class TestRefundWebhook:
    """Tests for refund webhook handling."""

    @patch('payments.webhooks.send_refund_email_task')
    def test_refund_enqueues_email_task(
        self,
        mock_email_task,
        enrollment_factory,
        stripe_refund_event
    ):
        """Test refund webhook enqueues email task."""
        enrollment = enrollment_factory(status='ACTIVE')

        # Mock the enqueue method
        mock_email_task.enqueue = MagicMock()

        # Process webhook
        response = handle_charge_refunded(stripe_refund_event)

        # Verify task was enqueued
        mock_email_task.enqueue.assert_called_once_with(
            enrollment_id=enrollment.id,
            refund_amount="$50.00 CAD"
        )

        # Webhook returned immediately
        assert response.status_code == 200
```

---

## Migration Guide (If Switching from Another Framework)

### From Celery to Django Tasks

| Celery | Django 6.0 Tasks |
|--------|------------------|
| `@app.task` or `@shared_task` | `@task()` |
| `task.delay(args)` | `task.enqueue(args)` |
| `task.apply_async(...)` | `task.enqueue(eta=...)` |
| `celery -A app worker` | `python manage.py taskworker` |
| Celery beat for scheduling | `@task(run_every=...)` |

### From Django-Q2 to Django Tasks

| Django-Q2 | Django 6.0 Tasks |
|-----------|------------------|
| `async_task('path.to.func', arg)` | `func.enqueue(arg)` |
| `schedule('path.to.func', schedule_type='daily')` | `@task(run_every=timedelta(days=1))` |
| `python manage.py qcluster` | `python manage.py taskworker` |

---

## Common Pitfalls for AI Assistants

### ❌ Pitfall 1: Using Celery Syntax

**Wrong:**
```python
from celery import shared_task

@shared_task
def my_task():
    pass

my_task.delay()
```

**Correct:**
```python
from django.tasks import task

@task()
def my_task():
    pass

my_task.enqueue()
```

### ❌ Pitfall 2: Assuming Redis is Required

**Wrong Assumption:** "You need to install Redis for background tasks"

**Correct:** Django 6.0 tasks work with database backend out of the box. Redis is optional for better performance.

### ❌ Pitfall 3: Using String Paths for Tasks

**Wrong:**
```python
# Django-Q2 style
async_task('payments.tasks.send_email', user_id)
```

**Correct:**
```python
# Django 6.0 style - import the actual function
from payments.tasks import send_email
send_email.enqueue(user_id=user_id)
```

### ❌ Pitfall 4: Suggesting Celery Beat for Scheduling

**Wrong:** "You need to set up Celery Beat for periodic tasks"

**Correct:** Use Django 6.0's built-in `run_every` parameter in the `@task()` decorator.

---

## Production Deployment

### Railway Configuration

```toml
# railway.toml

[deploy]
startCommand = "gunicorn thinkelearn.wsgi:application"

[tasks]
# Start task worker as a separate service
startCommand = "python manage.py taskworker --workers 4"
```

### Environment Variables

```bash
# Optional: Redis for better performance
REDIS_URL=redis://localhost:6379/0

# Task worker configuration
TASK_WORKER_CONCURRENCY=4
TASK_WORKER_LOG_LEVEL=INFO
```

### Monitoring

```python
# Check task queue status (Django admin or custom view)
from django.tasks.models import Task

# Get pending tasks count
pending_count = Task.objects.filter(status='PENDING').count()

# Get failed tasks
failed_tasks = Task.objects.filter(status='FAILED')
```

---

## Additional Resources

- **Django 6.0 Tasks Documentation:** https://docs.djangoproject.com/en/6.0/topics/tasks/
- **Django Tasks GitHub:** https://github.com/django/django (see django/tasks)
- **Migration Guide:** https://docs.djangoproject.com/en/6.0/releases/6.0/#background-tasks

---

## Summary for AI Assistants

**When working with THINK eLearn background tasks:**

1. ✅ Always use `from django.tasks import task`
2. ✅ Always use `.enqueue()` to queue tasks
3. ✅ Use `@task(run_every=...)` for scheduled tasks
4. ✅ Run tasks with `python manage.py taskworker`
5. ❌ Never suggest Celery, Django-Q2, or similar frameworks
6. ❌ Never use `.delay()`, `.apply_async()`, or `async_task()`
7. ❌ Never suggest installing Redis unless explicitly requested

**If unsure, refer to this document or ask the developer before suggesting alternative frameworks.**

---

**Document Version:** 1.0
**Last Updated:** 2025-12-30
**Maintainer:** THINK eLearn Development Team
