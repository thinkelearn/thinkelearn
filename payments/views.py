import hashlib
import json
import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from lms.models import CourseProduct, EnrollmentRecord
from payments.models import Payment
from payments.stripe_client import StripeClient, StripeClientError

logger = logging.getLogger(__name__)


def get_stripe_client() -> StripeClient:
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

    try:
        with transaction.atomic():
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

            payment = Payment.objects.create(
                enrollment_record=enrollment,
                amount=enrollment.amount_paid,
                currency=product.currency,
                status=Payment.Status.INITIATED,
            )
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
                idempotency_key=enrollment.idempotency_key,
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
        if "already have an enrollment" in error_message:
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
        return JsonResponse({"error": error_message}, status=400)
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
        return JsonResponse({"error": str(exc)}, status=502)

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
