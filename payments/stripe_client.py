from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal


class StripeClientError(Exception):
    """Raised when Stripe API calls fail."""


@dataclass
class StripeSession:
    """Lightweight wrapper for Stripe checkout session response."""

    id: str
    url: str
    payment_intent: str | None = None


class StripeClient:
    """Stripe API wrapper using per-request API keys and retry support."""

    def __init__(self, api_key: str, max_retries: int = 2) -> None:
        self.api_key = api_key
        self.max_retries = max_retries
        self.logger = logging.getLogger(__name__)

    def create_checkout_session(
        self,
        *,
        amount: Decimal,
        currency: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str],
        product_name: str,
        customer_email: str | None = None,
        idempotency_key: str | None = None,
    ) -> StripeSession:
        stripe = self._import_stripe()
        unit_amount = self._to_cents(amount)

        params = {
            "api_key": self.api_key,
            "payment_method_types": ["card"],
            "mode": "payment",
            "line_items": [
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": unit_amount,
                        "product_data": {"name": product_name},
                    },
                }
            ],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": metadata,
        }

        if customer_email:
            params["customer_email"] = customer_email

        for attempt in range(self.max_retries + 1):
            try:
                session = stripe.checkout.Session.create(
                    **params,
                    idempotency_key=idempotency_key,
                )
                return StripeSession(
                    id=session.id,
                    url=session.url,
                    payment_intent=getattr(session, "payment_intent", None),
                )
            except stripe.error.InvalidRequestError as exc:
                self.logger.error(
                    "Stripe invalid request error",
                    extra={"error": str(exc), "attempt": attempt + 1},
                )
                raise StripeClientError(
                    "Payment request was invalid. Please contact support."
                ) from exc
            except (
                stripe.error.APIConnectionError,
                stripe.error.RateLimitError,
                stripe.error.APIError,
                stripe.error.TimeoutError,
            ) as exc:
                self.logger.warning(
                    "Stripe transient error",
                    extra={"error": str(exc), "attempt": attempt + 1},
                )
                if attempt >= self.max_retries:
                    raise StripeClientError(
                        "Stripe API is unavailable. Please try again shortly."
                    ) from exc
                backoff_seconds = min(2**attempt, 8)
                time.sleep(backoff_seconds)
            except stripe.error.StripeError as exc:
                self.logger.error(
                    "Stripe error",
                    extra={"error": str(exc), "attempt": attempt + 1},
                )
                raise StripeClientError(
                    "Payment processing failed. Please try again."
                ) from exc

        return session  # Ensure a return statement is present

    @staticmethod
    def _to_cents(amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1")))

    @staticmethod
    def _import_stripe():
        try:
            import stripe
        except ImportError as exc:
            raise StripeClientError(
                "Stripe SDK is not installed. Please contact support."
            ) from exc
        return stripe


class MockStripeClient:
    """
    Test double for StripeClient.

    Provides a mock implementation that returns configurable StripeSession objects
    without making actual Stripe API calls. Supports optional payment_intent to
    match real Stripe behavior.
    """

    def __init__(
        self,
        session_id: str = "cs_test",
        session_url: str = "https://test",
        payment_intent: str | None = None,
    ):
        """
        Initialize mock Stripe client.

        Args:
            session_id: Mock session ID to return
            session_url: Mock session URL to return
            payment_intent: Optional payment intent ID (matches real Stripe behavior)
        """
        self.session_id = session_id
        self.session_url = session_url
        self.payment_intent = payment_intent

    def create_checkout_session(self, **_kwargs) -> StripeSession:
        """Create a mock checkout session."""
        return StripeSession(
            id=self.session_id, url=self.session_url, payment_intent=self.payment_intent
        )
