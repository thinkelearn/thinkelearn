from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

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
    stripe_checkout_session_id = models.CharField(max_length=255, blank=True)
    stripe_payment_intent_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return (
            f"Payment {self.pk} - {self.enrollment_record.user} - "
            f"{self.amount} {self.currency}"
        )

    def mark_succeeded(self) -> None:
        self.status = self.Status.SUCCEEDED
        self.save(update_fields=["status", "updated_at"])

    def mark_failed(self) -> None:
        self.status = self.Status.FAILED
        self.save(update_fields=["status", "updated_at"])

    @classmethod
    def create_for_enrollment(cls, enrollment_record, amount):
        return cls.objects.create(
            enrollment_record=enrollment_record,
            amount=amount,
            currency=getattr(settings, "STRIPE_CURRENCY", "usd"),
        )
