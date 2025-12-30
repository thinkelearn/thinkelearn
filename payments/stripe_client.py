from __future__ import annotations

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
            except (
                stripe.error.APIConnectionError,
                stripe.error.RateLimitError,
                stripe.error.APIError,
            ) as exc:
                if attempt >= self.max_retries:
                    raise StripeClientError(
                        "Stripe API is unavailable. Please try again shortly."
                    ) from exc
            except stripe.error.StripeError as exc:
                raise StripeClientError(str(exc)) from exc

    @staticmethod
    def _to_cents(amount: Decimal) -> int:
        return int((amount * 100).quantize(Decimal("1")))

    @staticmethod
    def _import_stripe():
        try:
            import stripe  # type: ignore
        except ImportError as exc:
            raise StripeClientError(
                "Stripe SDK is not installed. Please contact support."
            ) from exc
        return stripe


class MockStripeClient:
    """Test double for StripeClient."""

    def __init__(self, session_id: str = "cs_test", session_url: str = "https://test"):
        self.session_id = session_id
        self.session_url = session_url

    def create_checkout_session(self, **_kwargs) -> StripeSession:
        return StripeSession(id=self.session_id, url=self.session_url)
