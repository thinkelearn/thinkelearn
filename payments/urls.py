from django.urls import path

from payments import views

app_name = "payments"

urlpatterns = [
    path("checkout-session/", views.create_checkout_session, name="checkout_session"),
]
