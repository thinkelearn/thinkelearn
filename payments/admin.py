from django.contrib import admin

from payments.models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment_record",
        "amount",
        "currency",
        "status",
        "created_at",
    )
    list_filter = ("status", "currency", "created_at")
    search_fields = (
        "enrollment_record__user__username",
        "enrollment_record__product__course__title",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
    )
    readonly_fields = ("created_at", "updated_at")


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "success", "processed_at")
    list_filter = ("event_type", "success", "processed_at")
    search_fields = ("stripe_event_id",)
    readonly_fields = ("processed_at",)
