from django.db import models


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
    currency = models.CharField(max_length=10, default="CAD")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
    )
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


class WebhookEvent(models.Model):
    """Track processed webhook events for idempotency."""

    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        db_index=True,
    )
    event_type = models.CharField(max_length=100)
    processed_at = models.DateTimeField(auto_now_add=True)
    raw_event_data = models.JSONField()
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-processed_at"]
        indexes = [
            models.Index(fields=["event_type", "processed_at"]),
        ]
