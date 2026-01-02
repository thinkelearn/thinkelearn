from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from payments.stripe_client import StripeClient, StripeClientError


class DummyStripeError(Exception):
    pass


class DummyStripe:
    class error:
        class APIConnectionError(DummyStripeError):
            pass

        class RateLimitError(DummyStripeError):
            pass

        class APIError(DummyStripeError):
            pass

        class TimeoutError(DummyStripeError):
            pass

        class InvalidRequestError(DummyStripeError):
            pass

        class StripeError(DummyStripeError):
            pass

    class checkout:
        class Session:
            create = None


class StripeClientErrorHandlingTests(SimpleTestCase):
    def test_retries_transient_errors(self):
        dummy_stripe = DummyStripe()
        session = type("Session", (), {"id": "cs_123", "url": "https://stripe"})
        calls = {"count": 0}

        def create(**_kwargs):
            calls["count"] += 1
            if calls["count"] < 2:
                raise DummyStripe.error.APIConnectionError("Network")
            return session

        DummyStripe.checkout.Session.create = staticmethod(create)

        client = StripeClient(api_key="sk_test", max_retries=2)
        with (
            patch.object(client, "_import_stripe", return_value=dummy_stripe),
            patch("payments.stripe_client.time.sleep") as sleep_mock,
        ):
            result = client.create_checkout_session(
                amount=Decimal("10.00"),
                currency="CAD",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel",
                metadata={},
                product_name="Test",
            )

        self.assertEqual(result.id, "cs_123")
        self.assertEqual(calls["count"], 2)
        sleep_mock.assert_called()

    def test_invalid_request_raises_user_error(self):
        dummy_stripe = DummyStripe()

        def create(**_kwargs):
            raise DummyStripe.error.InvalidRequestError("Bad request")

        DummyStripe.checkout.Session.create = staticmethod(create)

        client = StripeClient(api_key="sk_test", max_retries=1)
        with patch.object(client, "_import_stripe", return_value=dummy_stripe):
            with self.assertRaises(StripeClientError) as ctx:
                client.create_checkout_session(
                    amount=Decimal("10.00"),
                    currency="CAD",
                    success_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                    metadata={},
                    product_name="Test",
                )

        self.assertIn("invalid", str(ctx.exception).lower())

    def test_rate_limit_exhausted_raises_unavailable(self):
        dummy_stripe = DummyStripe()

        def create(**_kwargs):
            raise DummyStripe.error.RateLimitError("Rate limited")

        DummyStripe.checkout.Session.create = staticmethod(create)

        client = StripeClient(api_key="sk_test", max_retries=0)
        with patch.object(client, "_import_stripe", return_value=dummy_stripe):
            with self.assertRaises(StripeClientError) as ctx:
                client.create_checkout_session(
                    amount=Decimal("10.00"),
                    currency="CAD",
                    success_url="https://example.com/success",
                    cancel_url="https://example.com/cancel",
                    metadata={},
                    product_name="Test",
                )

        self.assertIn("unavailable", str(ctx.exception).lower())
