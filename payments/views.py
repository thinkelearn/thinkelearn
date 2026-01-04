import hashlib
import json
import logging
import time
from decimal import Decimal, InvalidOperation

import stripe
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from lms.models import CourseProduct, EnrollmentRecord
from payments.models import Payment, WebhookEvent
from payments.stripe_client import StripeClient, StripeClientError
from payments.tasks import process_stripe_webhook_event

logger = logging.getLogger(__name__)

ALLOWED_STRIPE_METADATA_KEYS = {
    "enrollment_record_id",
    "user_id",
    "product_id",
}

SAFE_STRIPE_OBJECT_KEYS = {
    "id",
    "object",
    "amount",
    "amount_refunded",
    "amount_total",
    "currency",
    "payment_intent",
    "balance_transaction",
    "refunded",
    "status",
    "payment_status",
}


def _sanitize_stripe_event(event_data: dict) -> dict:
    """Minimize Stripe webhook payload storage to reduce PII exposure."""
    if settings.STRIPE_WEBHOOK_STORE_FULL_PAYLOAD:
        return event_data

    data_object = (event_data.get("data") or {}).get("object") or {}
    sanitized_object = {
        key: data_object.get(key)
        for key in SAFE_STRIPE_OBJECT_KEYS
        if key in data_object
    }

    metadata = data_object.get("metadata") or {}
    if metadata:
        sanitized_object["metadata"] = {
            key: value
            for key, value in metadata.items()
            if key in ALLOWED_STRIPE_METADATA_KEYS
        }

    refunds = data_object.get("refunds")
    if isinstance(refunds, dict):
        refund_items = refunds.get("data") or []
        sanitized_refunds = []
        for refund in refund_items:
            if not isinstance(refund, dict):
                continue
            sanitized_refunds.append(
                {
                    "id": refund.get("id"),
                    "amount": refund.get("amount"),
                    "currency": refund.get("currency"),
                    "balance_transaction": refund.get("balance_transaction"),
                    "created": refund.get("created"),
                    "status": refund.get("status"),
                }
            )
        sanitized_object["refunds"] = {"data": sanitized_refunds}

    return {
        "id": event_data.get("id"),
        "type": event_data.get("type"),
        "created": event_data.get("created"),
        "livemode": event_data.get("livemode"),
        "data": {"object": sanitized_object},
    }


def get_stripe_client() -> StripeClient:
    """
    Create and return a configured StripeClient instance.

    This factory function centralizes Stripe client creation to ensure consistent
    configuration across all Stripe API calls. The client uses the STRIPE_SECRET_KEY
    from Django settings.

    Returns:
        StripeClient: Configured client for making Stripe API calls

    Raises:
        ImproperlyConfigured: If STRIPE_SECRET_KEY is not set (handled at settings level)
    """
    return StripeClient(api_key=settings.STRIPE_SECRET_KEY)


def generate_idempotency_key(user_id: int, product_id: int, amount: Decimal) -> str:
    """
    Generate a deterministic idempotency key for enrollment requests.

    This ensures that retry attempts for the same enrollment request (same user,
    product, and amount) will use the same idempotency key, preventing duplicate
    enrollments and Stripe charges.

    Args:
        user_id: ID of the user making the enrollment request
        product_id: ID of the course product being purchased
        amount: Payment amount (Decimal)

    Returns:
        A 32-character hexadecimal hash suitable for use as an idempotency key
    """
    # Create a deterministic string from request parameters
    key_source = f"{user_id}:{product_id}:{amount}"
    # Hash to create a unique but reproducible key
    return hashlib.sha256(key_source.encode()).hexdigest()[:32]


@require_POST
def create_checkout_session(request):
    """
    Create a Stripe Checkout Session or free enrollment for a course product.

    This endpoint accepts JSON POST requests and returns JSON responses. It handles
    both paid enrollments (via Stripe Checkout Session) and free enrollments.

    **CSRF Protection**: This view uses Django's CSRF middleware. Frontend JavaScript
    must include the CSRF token in the X-CSRFToken header for all requests.

    **Authentication**: Requires authenticated user (returns 401 if not authenticated).

    **Request Body** (JSON):
        - product_id (required): ID of the CourseProduct to enroll in
        - amount (optional): Payment amount for PWYC courses
        - success_url (required): Redirect URL after successful checkout
        - cancel_url (required): Redirect URL if user cancels

    **Response** (JSON):
        Success cases:
        - 201 Created: Returns enrollment details and Stripe session URL (paid)
                      or confirmation (free)

        Error cases:
        - 400 Bad Request: Invalid input, validation errors
        - 401 Unauthorized: User not authenticated
        - 404 Not Found: Product not found
        - 409 Conflict: Duplicate enrollment
        - 502 Bad Gateway: Stripe API unavailable

    **Idempotency**: Requests with identical user_id, product_id, and amount
    use the same idempotency key to prevent duplicate enrollments and charges
    on network retries.

    **Security**:
        - All inputs validated before processing
        - Negative amounts rejected
        - URL validation for redirect parameters
        - Comprehensive logging for security monitoring
        - Atomic database transactions with automatic rollback on errors

    Returns:
        JsonResponse: JSON object with enrollment/session details or error message
    """
    if not request.user.is_authenticated:
        logger.warning(
            "Unauthenticated checkout session attempt",
            extra={
                "ip": request.META.get("REMOTE_ADDR"),
                "user_agent": request.headers.get("user-agent"),
            },
        )
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        logger.warning(
            "Invalid JSON payload in checkout session",
            extra={
                "user_id": request.user.id,
                "ip": request.META.get("REMOTE_ADDR"),
            },
        )
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    product_id = payload.get("product_id")
    success_url = payload.get("success_url")
    cancel_url = payload.get("cancel_url")
    raw_amount = payload.get("amount")

    if not product_id:
        logger.warning(
            "Missing product_id in checkout session request",
            extra={"user_id": request.user.id},
        )
        return JsonResponse({"error": "product_id is required."}, status=400)
    if not success_url or not cancel_url:
        logger.warning(
            "Missing redirect URLs in checkout session request",
            extra={"user_id": request.user.id, "product_id": product_id},
        )
        return JsonResponse(
            {"error": "success_url and cancel_url are required."}, status=400
        )

    url_validator = URLValidator()
    try:
        url_validator(success_url)
        url_validator(cancel_url)
    except ValidationError:
        logger.warning(
            "Invalid redirect URL in checkout session",
            extra={
                "user_id": request.user.id,
                "product_id": product_id,
                "success_url": success_url,
                "cancel_url": cancel_url,
            },
        )
        return JsonResponse({"error": "Invalid redirect URL."}, status=400)

    amount = None
    if raw_amount is not None:
        try:
            amount = Decimal(str(raw_amount))
            # Validate amount is non-negative
            if amount < 0:
                logger.warning(
                    "Negative amount in checkout session",
                    extra={
                        "user_id": request.user.id,
                        "product_id": product_id,
                        "raw_amount": raw_amount,
                    },
                )
                return JsonResponse(
                    {"error": "Amount must be non-negative."}, status=400
                )
        except (InvalidOperation, TypeError):
            logger.warning(
                "Invalid amount in checkout session",
                extra={
                    "user_id": request.user.id,
                    "product_id": product_id,
                    "raw_amount": raw_amount,
                },
            )
            return JsonResponse({"error": "Invalid amount."}, status=400)

    try:
        product = CourseProduct.objects.select_related("course").get(pk=product_id)
    except CourseProduct.DoesNotExist:
        logger.warning(
            "Product not found in checkout session",
            extra={"user_id": request.user.id, "product_id": product_id},
        )
        return JsonResponse({"error": "Product not found."}, status=404)

    # Determine the actual amount for idempotency key generation
    # This matches the logic in EnrollmentRecord.create_for_user
    if amount is None:
        if product.pricing_type == CourseProduct.PricingType.FIXED:
            actual_amount = product.fixed_price
        elif product.pricing_type == CourseProduct.PricingType.FREE:
            actual_amount = Decimal("0")
        else:
            # PWYC requires amount to be provided
            actual_amount = Decimal("0")  # Fallback for idempotency key
    else:
        actual_amount = amount

    # Generate deterministic idempotency key to prevent duplicate enrollments on retry
    idempotency_key = generate_idempotency_key(
        request.user.id, product.id, actual_amount
    )

    # Check for existing pending enrollment before creating new one
    existing_pending = EnrollmentRecord.objects.filter(
        user=request.user,
        product=product,
        status=EnrollmentRecord.Status.PENDING_PAYMENT,
    ).first()

    try:
        with transaction.atomic():
            # If user has existing pending enrollment, create new checkout session for it
            # instead of creating duplicate enrollment
            if existing_pending:
                enrollment = existing_pending
                logger.info(
                    "Resuming pending enrollment with new checkout session",
                    extra={
                        "user_id": request.user.id,
                        "product_id": product.id,
                        "enrollment_id": enrollment.id,
                        "old_session_id": enrollment.stripe_checkout_session_id,
                    },
                )
            else:
                enrollment = EnrollmentRecord.create_for_user(
                    request.user,
                    product,
                    amount=amount,
                    idempotency_key=idempotency_key,
                )

            if enrollment.status == EnrollmentRecord.Status.ACTIVE:
                logger.info(
                    "Free course enrollment created successfully",
                    extra={
                        "user_id": request.user.id,
                        "product_id": product.id,
                        "course_id": product.course.id,
                        "enrollment_id": enrollment.id,
                    },
                )
                return JsonResponse(
                    {
                        "status": "free",
                        "enrollment_id": enrollment.id,
                    },
                    status=201,
                )

            # For resumed enrollments, create new Payment record
            # For new enrollments, create new Payment record
            payment = Payment.objects.create(
                enrollment_record=enrollment,
                amount=enrollment.amount_paid,
                currency=product.currency,
                status=Payment.Status.INITIATED,
            )

            # Generate unique Stripe idempotency key
            # For resumed enrollments, we need a NEW key (old session expired)
            # For new enrollments, use the enrollment's idempotency_key
            if existing_pending:
                # Include timestamp to ensure uniqueness for resumed sessions
                stripe_idempotency_key = (
                    f"{enrollment.idempotency_key}:{int(time.time())}"
                )
            else:
                stripe_idempotency_key = enrollment.idempotency_key

            stripe_client = get_stripe_client()
            session = stripe_client.create_checkout_session(
                amount=enrollment.amount_paid,
                currency=product.currency,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "enrollment_record_id": str(enrollment.id),
                    "user_id": str(request.user.id),
                    "product_id": str(product.id),
                },
                product_name=product.course.title,
                customer_email=request.user.email or None,
                idempotency_key=stripe_idempotency_key,
            )

            enrollment.stripe_checkout_session_id = session.id
            enrollment.save(update_fields=["stripe_checkout_session_id"])

            payment.status = Payment.Status.PROCESSING
            payment.stripe_checkout_session_id = session.id
            payment.stripe_payment_intent_id = session.payment_intent or ""
            payment.save(
                update_fields=[
                    "status",
                    "stripe_checkout_session_id",
                    "stripe_payment_intent_id",
                ]
            )

    except ValidationError as exc:
        error_message = str(exc)
        # Check if this is a duplicate enrollment error
        if (
            "already have an enrollment" in error_message
            or "active or pending enrollment" in error_message
        ):
            logger.warning(
                "Duplicate enrollment attempt",
                extra={
                    "user_id": request.user.id,
                    "product_id": product_id,
                },
            )
            return JsonResponse({"error": "Enrollment already exists."}, status=409)

        logger.warning(
            "Validation error in checkout session",
            extra={
                "user_id": request.user.id,
                "product_id": product_id,
                "error": error_message,
            },
        )
        # Sanitize validation errors to prevent leaking internal implementation details
        # while preserving user-relevant business logic errors
        if any(
            phrase in error_message.lower()
            for phrase in [
                "amount is required",
                "not currently available",
                "do not meet the requirements",
                "between",  # Price range info
            ]
        ):
            # These are business validation errors meant for users
            return JsonResponse({"error": error_message}, status=400)
        # Generic error for other validation failures
        return JsonResponse(
            {"error": "Invalid request. Please check your input and try again."},
            status=400,
        )
    except IntegrityError:
        logger.warning(
            "Duplicate enrollment attempt",
            extra={
                "user_id": request.user.id,
                "product_id": product_id,
            },
        )
        return JsonResponse({"error": "Enrollment already exists."}, status=409)
    except StripeClientError as exc:
        logger.error(
            "Stripe API error in checkout session",
            extra={
                "user_id": request.user.id,
                "product_id": product_id,
                "error": str(exc),
            },
            exc_info=True,
        )
        # Sanitize Stripe errors to prevent leaking integration details
        # Full error details are logged for debugging
        return JsonResponse(
            {
                "error": "Payment processing is temporarily unavailable. Please try again in a few moments."
            },
            status=502,
        )

    logger.info(
        "Stripe checkout session created successfully",
        extra={
            "user_id": request.user.id,
            "product_id": product.id,
            "course_id": product.course.id,
            "enrollment_id": enrollment.id,
            "session_id": session.id,
            "amount": str(enrollment.amount_paid),
            "currency": product.currency,
        },
    )
    return JsonResponse(
        {
            "status": "pending_payment",
            "enrollment_id": enrollment.id,
            "session_id": session.id,
            "session_url": session.url,
        },
        status=201,
    )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    """Process Stripe webhook events with signature verification and idempotency."""
    payload = request.body
    signature = request.headers.get("stripe-signature")

    if not signature:
        logger.warning("Stripe webhook missing signature header")
        return JsonResponse({"error": "Missing Stripe signature."}, status=400)

    # Get webhook secret (tests mock construct_event so empty value is acceptable)
    # Production deployment checks ensure this is configured (see payments/checks.py)
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=webhook_secret,
        )
    except ValueError:
        logger.warning("Invalid Stripe webhook payload")
        return JsonResponse({"error": "Invalid payload."}, status=400)
    except stripe.error.SignatureVerificationError:
        logger.warning("Invalid Stripe webhook signature")
        return JsonResponse({"error": "Invalid signature."}, status=400)

    event_data = event.to_dict()
    stored_event_data = _sanitize_stripe_event(event_data)
    event_id = event_data.get("id")
    event_type = event_data.get("type")

    if not event_id:
        logger.warning("Stripe webhook missing event ID")
        return JsonResponse({"error": "Missing event ID."}, status=400)

    already_processed = False
    webhook_event_id = None

    with transaction.atomic():
        # Handle race conditions: try get first, create if not found, retry get if create races
        try:
            webhook_event = WebhookEvent.objects.select_for_update().get(
                stripe_event_id=event_id
            )
            created = False
        except WebhookEvent.DoesNotExist:
            try:
                webhook_event = WebhookEvent.objects.create(
                    stripe_event_id=event_id,
                    event_type=event_type or "unknown",
                    raw_event_data=stored_event_data,
                    success=False,
                )
                created = True
            except IntegrityError:
                # Another transaction created the same event concurrently - retry get
                webhook_event = WebhookEvent.objects.select_for_update().get(
                    stripe_event_id=event_id
                )
                created = False

        if not created and webhook_event.success:
            already_processed = True
        else:
            if not created:
                webhook_event.event_type = event_type or webhook_event.event_type
            webhook_event.raw_event_data = stored_event_data
            webhook_event.error_message = ""
            webhook_event.save(
                update_fields=["event_type", "raw_event_data", "error_message"]
            )
            webhook_event_id = webhook_event.id

    if already_processed:
        logger.info(
            "Stripe webhook already processed",
            extra={"event_id": event_id, "event_type": event_type},
        )
        return JsonResponse({"status": "ignored"}, status=200)

    if webhook_event_id is None:
        logger.error(
            "Stripe webhook event ID missing after persistence",
            extra={"event_id": event_id, "event_type": event_type},
        )
        return JsonResponse({"status": "error"}, status=500)

    try:
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            process_stripe_webhook_event.apply(args=[webhook_event_id])
        else:
            process_stripe_webhook_event.delay(webhook_event_id)
    except Exception:
        logger.exception(
            "Stripe webhook enqueue failed",
            extra={"event_id": event_id, "event_type": event_type},
        )
        return JsonResponse({"status": "error"}, status=503)

    return JsonResponse({"status": "ok"}, status=200)


def checkout_success(request):
    """Render checkout success page."""
    return render(
        request,
        "payments/checkout_success.html",
        {
            "session_id": request.GET.get("session_id"),
            "is_free": request.GET.get("free") == "1",
        },
    )


def checkout_cancel(request):
    """Render checkout cancel page."""
    return render(request, "payments/checkout_cancel.html")


def checkout_failure(request):
    """Render checkout failure page."""
    return render(request, "payments/checkout_failure.html")
