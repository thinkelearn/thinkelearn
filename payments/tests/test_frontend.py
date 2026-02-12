from django.test import TestCase
from django.urls import reverse


class CheckoutPageTests(TestCase):
    def test_checkout_success_page(self):
        response = self.client.get(reverse("payments:checkout_success"))
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

    def test_checkout_success_with_course_url(self):
        response = self.client.get(
            reverse("payments:checkout_success"),
            {"course": "/courses/my-course/"},
        )
        self.assertContains(response, 'href="/courses/my-course/"')
        self.assertContains(response, "Go to course")

    def test_checkout_success_without_course_url(self):
        response = self.client.get(reverse("payments:checkout_success"))
        self.assertNotContains(response, "Go to course")

    def test_checkout_success_rejects_absolute_url(self):
        response = self.client.get(
            reverse("payments:checkout_success"),
            {"course": "https://evil.com/"},
        )
        self.assertNotContains(response, "evil.com")
        self.assertNotContains(response, "Go to course")

    def test_checkout_success_rejects_protocol_relative_url(self):
        response = self.client.get(
            reverse("payments:checkout_success"),
            {"course": "//evil.com/"},
        )
        self.assertNotContains(response, "evil.com")
        self.assertNotContains(response, "Go to course")
