from django.test import TestCase
from django.urls import reverse


class CheckoutPageTests(TestCase):
    def test_checkout_success_page(self):
        response = self.client.get(
            reverse("payments:checkout_success"), {"session_id": "cs_123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enrollment confirmed")

    def test_checkout_cancel_page(self):
        response = self.client.get(reverse("payments:checkout_cancel"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Checkout canceled")

    def test_checkout_failure_page(self):
        response = self.client.get(reverse("payments:checkout_failure"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Payment error")
