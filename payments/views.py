import json
import logging
from decimal import Decimal, InvalidOperation

import stripe
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from lms.models import CourseProduct, EnrollmentRecord

from .models import Payment

logger = logging.getLogger(__name__)


def _amount_to_cents(amount: Decimal) -> int:
    quantized = amount.quantize(Decimal("0.01"))
    return int(quantized * 100)


def _validate_amount(amount_value: str | int | float | Decimal) -> Decimal:
    try:
        amount = Decimal(str(amount_value))
    except (InvalidOperation, TypeError):
        raise ValueError("Invalid amount format")

    minimum = Decimal(
        str(getattr(settings, "STRIPE_PAY_WHAT_YOU_CAN_MIN", "1.00"))
    )
    maximum = Decimal(
        str(getattr(settings, "STRIPE_PAY_WHAT_YOU_CAN_MAX", "1000.00"))
    )

    if amount < minimum or amount > maximum:
        raise ValueError("Amount outside allowed range")

    return amount


def _get_request_payload(request):
    try:
        return json.loads(request.body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {}


def _configure_stripe():
    stripe.api_key = settings.STRIPE_SECRET_KEY


def _create_enrollment(user, product, amount: Decimal) -> EnrollmentRecord:
    enrollment = EnrollmentRecord.create_for_user(
        user=user,
        product=product,
        pay_what_you_can_amount=amount,
    )
    if amount > 0 and enrollment.status == EnrollmentRecord.Status.ACTIVE:
        enrollment.status = EnrollmentRecord.Status.PENDING_PAYMENT
        enrollment.save(update_fields=["status"])
    return enrollment


@login_required
@require_POST
def create_checkout_session(request):
    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({"error": "Stripe is not configured"}, status=500)

    payload = _get_request_payload(request)
    product_id = payload.get("product_id")
    success_url = payload.get("success_url")
    cancel_url = payload.get("cancel_url")

    if not product_id or not success_url or not cancel_url:
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    try:
        amount = _validate_amount(payload.get("amount"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        product = CourseProduct.objects.select_related("course").get(
            pk=product_id, is_active=True
        )
    except CourseProduct.DoesNotExist:
        return JsonResponse({"error": "Course product not found"}, status=404)

    enrollment = _create_enrollment(request.user, product, amount)
    payment = Payment.create_for_enrollment(enrollment, amount)

    _configure_stripe()
    metadata = {
        "enrollment_record_id": str(enrollment.id),
        "payment_id": str(payment.id),
        "user_id": str(request.user.id),
        "product_id": str(product.id),
    }

    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=request.user.email or None,
        line_items=[
            {
                "quantity": 1,
                "price_data": {
                    "currency": settings.STRIPE_CURRENCY,
                    "unit_amount": _amount_to_cents(amount),
                    "product_data": {
                        "name": product.course.title,
                    },
                },
            }
        ],
        metadata=metadata,
        payment_intent_data={
            "metadata": metadata,
        },
    )

    enrollment.stripe_checkout_session_id = session.id
    enrollment.save(update_fields=["stripe_checkout_session_id"])
    payment.stripe_checkout_session_id = session.id
    payment.save(update_fields=["stripe_checkout_session_id"])

    return JsonResponse({"session_id": session.id, "url": session.url})


@login_required
@require_POST
def create_payment_intent(request):
    if not settings.STRIPE_SECRET_KEY:
        return JsonResponse({"error": "Stripe is not configured"}, status=500)

    payload = _get_request_payload(request)
    product_id = payload.get("product_id")

    if not product_id:
        return JsonResponse({"error": "Missing required parameters"}, status=400)

    try:
        amount = _validate_amount(payload.get("amount"))
    except ValueError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    try:
        product = CourseProduct.objects.select_related("course").get(
            pk=product_id, is_active=True
        )
    except CourseProduct.DoesNotExist:
        return JsonResponse({"error": "Course product not found"}, status=404)

    enrollment = _create_enrollment(request.user, product, amount)
    payment = Payment.create_for_enrollment(enrollment, amount)

    _configure_stripe()
    metadata = {
        "enrollment_record_id": str(enrollment.id),
        "payment_id": str(payment.id),
        "user_id": str(request.user.id),
        "product_id": str(product.id),
    }

    intent = stripe.PaymentIntent.create(
        amount=_amount_to_cents(amount),
        currency=settings.STRIPE_CURRENCY,
        metadata=metadata,
    )

    enrollment.stripe_payment_intent_id = intent.id
    enrollment.save(update_fields=["stripe_payment_intent_id"])
    payment.stripe_payment_intent_id = intent.id
    payment.save(update_fields=["stripe_payment_intent_id"])

    return JsonResponse({"client_secret": intent.client_secret})


@csrf_exempt
@require_POST
def stripe_webhook(request):
    if not settings.STRIPE_WEBHOOK_SECRET:
        return HttpResponse(status=500)

    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET,
        )
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook error: %s", exc)
        return HttpResponse(status=400)

    event_type = event.get("type")
    data_object = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        if data_object.get("payment_status") == "paid":
            _handle_success(session=data_object)
    elif event_type == "payment_intent.succeeded":
        _handle_success(payment_intent=data_object)
    elif event_type in {
        "payment_intent.payment_failed",
        "checkout.session.async_payment_failed",
    }:
        _handle_failure(
            session=data_object if "session" in event_type else None,
            payment_intent=data_object if "payment_intent" in event_type else None,
        )

    return HttpResponse(status=200)


def _handle_success(*, session=None, payment_intent=None):
    enrollment = _get_enrollment_from_event(
        session=session,
        payment_intent=payment_intent,
    )
    if not enrollment:
        return

    stripe_session_id = session.get("id") if session else None
    stripe_intent_id = (
        session.get("payment_intent") if session else payment_intent.get("id")
    )

    enrollment.mark_paid(
        stripe_checkout_session_id=stripe_session_id,
        stripe_payment_intent_id=stripe_intent_id,
    )

    payment = _get_payment_from_event(session=session, payment_intent=payment_intent)
    if payment:
        if stripe_session_id and not payment.stripe_checkout_session_id:
            payment.stripe_checkout_session_id = stripe_session_id
        if stripe_intent_id and not payment.stripe_payment_intent_id:
            payment.stripe_payment_intent_id = stripe_intent_id
        payment.mark_succeeded()


def _handle_failure(*, session=None, payment_intent=None):
    enrollment = _get_enrollment_from_event(
        session=session,
        payment_intent=payment_intent,
    )
    if enrollment:
        enrollment.status = EnrollmentRecord.Status.CANCELLED_REFUNDED
        enrollment.save(update_fields=["status"])

    payment = _get_payment_from_event(session=session, payment_intent=payment_intent)
    if payment:
        payment.mark_failed()


def _get_enrollment_from_event(*, session=None, payment_intent=None):
    metadata = {}
    if session:
        metadata = session.get("metadata", {})
        stripe_session_id = session.get("id")
        stripe_intent_id = session.get("payment_intent")
    else:
        metadata = payment_intent.get("metadata", {})
        stripe_session_id = None
        stripe_intent_id = payment_intent.get("id")

    enrollment_id = metadata.get("enrollment_record_id")
    if enrollment_id:
        return EnrollmentRecord.objects.filter(id=enrollment_id).first()

    if stripe_intent_id:
        enrollment = EnrollmentRecord.objects.filter(
            stripe_payment_intent_id=stripe_intent_id
        ).first()
        if enrollment:
            return enrollment

    if stripe_session_id:
        return EnrollmentRecord.objects.filter(
            stripe_checkout_session_id=stripe_session_id
        ).first()

    return None


def _get_payment_from_event(*, session=None, payment_intent=None):
    metadata = {}
    stripe_session_id = None
    stripe_intent_id = None

    if session:
        metadata = session.get("metadata", {})
        stripe_session_id = session.get("id")
        stripe_intent_id = session.get("payment_intent")
    elif payment_intent:
        metadata = payment_intent.get("metadata", {})
        stripe_intent_id = payment_intent.get("id")

    payment_id = metadata.get("payment_id")
    if payment_id:
        return Payment.objects.filter(id=payment_id).first()

    if stripe_intent_id:
        payment = Payment.objects.filter(
            stripe_payment_intent_id=stripe_intent_id
        ).first()
        if payment:
            return payment

    if stripe_session_id:
        return Payment.objects.filter(
            stripe_checkout_session_id=stripe_session_id
        ).first()

    return None
