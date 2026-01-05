from django.urls import path

from payments import views

app_name = "payments"

urlpatterns = [
    path("checkout-session/", views.create_checkout_session, name="checkout_session"),
    path("webhook/", views.stripe_webhook, name="stripe_webhook"),
    path("checkout/success/", views.checkout_success, name="checkout_success"),
    path("checkout/cancel/", views.checkout_cancel, name="checkout_cancel"),
    path("checkout/failure/", views.checkout_failure, name="checkout_failure"),
    path(
        "refund/request/<int:enrollment_id>/",
        views.refund_request,
        name="refund_request",
    ),
]
