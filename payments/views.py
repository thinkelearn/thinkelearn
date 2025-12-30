import json
import uuid
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


def get_stripe_client() -> StripeClient:
    return StripeClient(api_key=settings.STRIPE_SECRET_KEY)


@require_POST
def create_checkout_session(request):
    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required."}, status=401)

    try:
        payload = json.loads(request.body.decode("utf-8"))
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    product_id = payload.get("product_id")
    success_url = payload.get("success_url")
    cancel_url = payload.get("cancel_url")
    raw_amount = payload.get("amount")

    if not product_id:
        return JsonResponse({"error": "product_id is required."}, status=400)
    if not success_url or not cancel_url:
        return JsonResponse(
            {"error": "success_url and cancel_url are required."}, status=400
        )

    url_validator = URLValidator()
    try:
        url_validator(success_url)
        url_validator(cancel_url)
    except ValidationError:
        return JsonResponse({"error": "Invalid redirect URL."}, status=400)

    amount = None
    if raw_amount is not None:
        try:
            amount = Decimal(str(raw_amount))
        except (InvalidOperation, TypeError):
            return JsonResponse({"error": "Invalid amount."}, status=400)

    try:
        product = CourseProduct.objects.select_related("course").get(pk=product_id)
    except CourseProduct.DoesNotExist:
        return JsonResponse({"error": "Product not found."}, status=404)

    try:
        with transaction.atomic():
            enrollment = EnrollmentRecord.create_for_user(
                request.user,
                product,
                amount=amount,
                idempotency_key=str(uuid.uuid4()),
            )

            if enrollment.status == EnrollmentRecord.Status.ACTIVE:
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
        return JsonResponse({"error": str(exc)}, status=400)
    except IntegrityError:
        return JsonResponse({"error": "Enrollment already exists."}, status=409)
    except StripeClientError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse(
        {
            "status": "pending_payment",
            "enrollment_id": enrollment.id,
            "session_id": session.id,
            "session_url": session.url,
        },
        status=201,
    )
