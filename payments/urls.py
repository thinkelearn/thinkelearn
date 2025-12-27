from django.urls import path

from . import views

urlpatterns = [
    path("stripe/checkout-session/", views.create_checkout_session, name="stripe_checkout_session"),
    path("stripe/payment-intent/", views.create_payment_intent, name="stripe_payment_intent"),
    path("stripe/webhook/", views.stripe_webhook, name="stripe_webhook"),
]
