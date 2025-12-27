from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "enrollment_record",
        "amount",
        "currency",
        "status",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "created_at",
    )
    list_filter = ("status", "currency")
    search_fields = (
        "enrollment_record__user__username",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
    )
