from django.contrib import admin
from django.db.models import F

from payments.models import Payment, PaymentLedgerEntry, WebhookEvent


class PaymentLedgerEntryInline(admin.TabularInline):
    model = PaymentLedgerEntry
    extra = 0
    fields = (
        "entry_type",
        "amount",
        "currency",
        "net_amount",
        "stripe_charge_id",
        "stripe_refund_id",
        "stripe_balance_transaction_id",
        "processed_at",
        "created_at",
    )
    readonly_fields = fields
    show_change_link = True
    can_delete = False


class RefundStateFilter(admin.SimpleListFilter):
    title = "refund state"
    parameter_name = "refund_state"

    def lookups(self, request, model_admin):
        return [
            ("none", "No refunds"),
            ("partial", "Partial refunds"),
            ("full", "Full refunds"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "none":
            return queryset.filter(amount_refunded=0)
        if self.value() == "partial":
            return queryset.filter(
                amount_refunded__gt=0, amount_refunded__lt=F("amount_gross")
            )
        if self.value() == "full":
            return queryset.filter(amount_refunded__gte=F("amount_gross")).exclude(
                amount_gross=0
            )
        return queryset


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "enrollment_record",
        "amount",
        "amount_gross",
        "amount_refunded",
        "amount_net",
        "currency",
        "status",
        "created_at",
    )
    list_filter = (
        "status",
        RefundStateFilter,
        "currency",
        "enrollment_record__product",
        "enrollment_record__product__course",
        "created_at",
    )
    search_fields = (
        "enrollment_record__user__username",
        "enrollment_record__product__course__title",
        "stripe_checkout_session_id",
        "stripe_payment_intent_id",
        "stripe_charge_id",
    )
    readonly_fields = (
        "amount_gross",
        "amount_refunded",
        "amount_net",
        "created_at",
        "updated_at",
    )
    inlines = [PaymentLedgerEntryInline]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ("stripe_event_id", "event_type", "success", "processed_at")
    list_filter = ("event_type", "success", "processed_at")
    search_fields = ("stripe_event_id",)
    readonly_fields = ("processed_at",)
