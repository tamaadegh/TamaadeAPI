import stripe
import uuid
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from rest_framework import status
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from orders.models import Order, OrderItem
from orders.permissions import IsOrderByBuyerOrAdmin
from payment.models import Payment
from payment.permissions import (
    DoesOrderHaveAddress,
    IsOrderPendingWhenCheckout,
    IsPaymentByUser,
    IsPaymentForOrderNotCompleted,
    IsPaymentPending,
)
from payment.serializers import CheckoutSerializer, PaymentSerializer
from payment.tasks import send_payment_success_email_task

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentViewSet(ModelViewSet):
    """
    CRUD payment for an order
    """

    queryset = Payment.objects.all()
    serializer_class = PaymentSerializer
    permission_classes = [IsPaymentByUser]

    def get_queryset(self):
        res = super().get_queryset()
        user = self.request.user
        return res.filter(order__buyer=user)

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            self.permission_classes += [IsPaymentPending]

        return super().get_permissions()


class CheckoutAPIView(RetrieveUpdateAPIView):
    """
    Create, Retrieve, Update billing address, shipping address and payment of an order
    """

    queryset = Order.objects.all()
    serializer_class = CheckoutSerializer
    permission_classes = [IsOrderByBuyerOrAdmin]

    def get_permissions(self):
        if self.request.method in ("PUT", "PATCH"):
            self.permission_classes += [IsOrderPendingWhenCheckout]

        return super().get_permissions()


class StripeCheckoutSessionCreateAPIView(APIView):
    """
    Create and return checkout session ID for order payment of type 'Stripe'
    """

    permission_classes = (
        IsPaymentForOrderNotCompleted,
        DoesOrderHaveAddress,
    )

    def post(self, request, *args, **kwargs):
        order = get_object_or_404(Order, id=self.kwargs.get("order_id"))
        if not order.order_items.exists():
            return Response(
                {"detail": "Your basket is empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order_items = []

        for order_item in order.order_items.all():
            product = order_item.product
            quantity = order_item.quantity
            images = []
            if product.image:
                images.append(f"{settings.BACKEND_DOMAIN}{product.image.url}")

            data = {
                "price_data": {
                    "currency": "usd",
                    "unit_amount_decimal": product.price,
                    "product_data": {
                        "name": product.name,
                        "description": product.desc or product.name,
                        "images": images,
                    },
                },
                "quantity": quantity,
            }

            order_items.append(data)

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=order_items,
            metadata={"order_id": order.id},
            mode="payment",
            success_url=settings.PAYMENT_SUCCESS_URL,
            cancel_url=settings.PAYMENT_CANCEL_URL,
        )

        return Response(
            {"sessionId": checkout_session["id"]}, status=status.HTTP_201_CREATED
        )


class StripeWebhookAPIView(APIView):
    """
    Stripe webhook API view to handle checkout session completed and other events.
    """

    def post(self, request, format=None):
        payload = request.body
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")
        if not sig_header:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        event = None

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
        except ValueError:
            return Response(status=status.HTTP_400_BAD_REQUEST)
        except stripe.error.SignatureVerificationError:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            customer_email = (session.get("customer_details") or {}).get("email")
            order_id = (session.get("metadata") or {}).get("order_id")
            if not order_id:
                return Response(status=status.HTTP_400_BAD_REQUEST)

            payment = get_object_or_404(Payment, order=order_id)
            payment.status = "C"
            payment.save()

            order = get_object_or_404(Order, id=order_id)
            order.status = "C"
            order.save()

            if customer_email:
                send_payment_success_email_task.delay(customer_email)

        # Can handle other events here.

        return Response(status=status.HTTP_200_OK)


def _complete_paid_order(payment):
    if payment.status == Payment.COMPLETED:
        return
    payment.status = Payment.COMPLETED
    payment.save(update_fields=["status", "updated_at"])
    order = payment.order
    if order.status != Order.COMPLETED:
        for item in order.order_items.select_related("product"):
            product = item.product
            product.quantity = max(0, product.quantity - item.quantity)
            product.save(update_fields=["quantity"])
        order.status = Order.COMPLETED
        order.save(update_fields=["status", "updated_at"])


def _sync_pending_order(user, items):
    """Replace the buyer's pending order items with `items`
    ([{product, name, quantity}]). Returns an error message or None."""
    from products.models import Product

    if not isinstance(items, list) or not items:
        return "Your basket is empty."

    resolved = {}
    for raw in items:
        if not isinstance(raw, dict):
            return "Invalid basket item."
        try:
            quantity = int(raw.get("quantity") or 0)
        except (TypeError, ValueError):
            return "Invalid quantity."
        if quantity <= 0:
            continue
        product = None
        product_id = raw.get("product")
        name = str(raw.get("name") or "").strip()
        if product_id not in (None, ""):
            product = Product.objects.filter(pk=product_id).first()
        # The app ships a bundled catalog whose ids can differ from this
        # database, so the name is the fallback key.
        if product is not None and name and product.name.lower() != name.lower():
            product = None
        if product is None and name:
            product = Product.objects.filter(name__iexact=name).order_by("pk").first()
        if product is None:
            return f'"{name or product_id}" is no longer available.'
        if product.seller_id == user.pk:
            return "Adding your own product to your order is not allowed."
        resolved[product.pk] = (product, resolved.get(product.pk, (None, 0))[1] + quantity)

    if not resolved:
        return "Your basket is empty."
    for product, quantity in resolved.values():
        if quantity > product.quantity:
            return f'Only {product.quantity} left in stock for "{product.name}".'

    with transaction.atomic():
        order = Order.objects.filter(buyer=user, status=Order.PENDING).first()
        if order is None:
            order = Order.objects.create(buyer=user)
        order.order_items.all().delete()
        OrderItem.objects.bulk_create(
            [OrderItem(order=order, product=p, quantity=q) for p, q in resolved.values()]
        )
    return None


class HubtelCheckoutAPIView(APIView):
    """Start Hubtel Online Checkout for the buyer's pending cart."""

    def post(self, request, *args, **kwargs):
        from payment.hubtel import (
            HubtelError,
            hubtel_data,
            hubtel_is_configured,
            hubtel_response_code,
            initiate_checkout,
        )

        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        if not hubtel_is_configured():
            return Response(
                {"detail": "Hubtel is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        platform = str(request.data.get("platform") or "web").lower()
        items = request.data.get("items")
        if items is not None:
            # Mobile keeps its cart locally and sends it with the checkout request.
            error = _sync_pending_order(request.user, items)
            if error:
                return Response({"detail": error}, status=status.HTTP_400_BAD_REQUEST)

        order = (
            Order.objects.filter(buyer=request.user, status=Order.PENDING)
            .prefetch_related("order_items__product")
            .first()
        )
        if not order or not order.order_items.exists():
            return Response({"detail": "Your basket is empty."}, status=status.HTTP_400_BAD_REQUEST)

        payment, _ = Payment.objects.get_or_create(
            order=order,
            defaults={"payment_option": Payment.HUBTEL, "status": Payment.PENDING},
        )
        if payment.status == Payment.COMPLETED:
            return Response({"detail": "This order is already paid."}, status=status.HTTP_400_BAD_REQUEST)

        payment.payment_option = Payment.HUBTEL
        payment.status = Payment.PENDING
        # Hubtel rejects reused clientReference (HTTP 400 / code 4000).
        payment.client_reference = f"TMD{order.id}{uuid.uuid4().hex}"[:32]
        payment.save()

        backend = settings.BACKEND_DOMAIN.rstrip("/")
        frontend = settings.FRONTEND_DOMAIN.rstrip("/")
        callback_url = f"{backend}/api/user/payments/hubtel/callback/"
        if platform in ("android", "ios", "mobile"):
            # Hubtel only accepts http(s) URLs, so bounce through the backend,
            # which sends the browser back into the app (tamaade://checkout/result).
            app_return = f"{backend}/api/user/payments/hubtel/app-return/"
            return_url = f"{app_return}?ref={payment.client_reference}&result=success"
            cancel_url = f"{app_return}?ref={payment.client_reference}&result=cancel"
        else:
            return_url = f"{frontend}/checkout/success?ref={payment.client_reference}"
            cancel_url = f"{frontend}/checkout/cancel?ref={payment.client_reference}"
        payee_name = request.user.get_full_name() or request.user.email
        phone = ""
        phone_record = getattr(request.user, "phone", None)
        if phone_record is not None:
            phone_value = getattr(phone_record, "phone_number", None)
            phone = str(phone_value).lstrip("+") if phone_value else ""

        try:
            hubtel_response = initiate_checkout(
                total_amount=order.total_cost,
                description=f"Tamaade order {order.id}",
                callback_url=callback_url,
                return_url=return_url,
                cancellation_url=cancel_url,
                client_reference=payment.client_reference,
                payee_name=payee_name,
                payee_mobile_number=phone or None,
                payee_email=request.user.email,
            )
        except HubtelError as exc:
            payment.status = Payment.FAILED
            payment.save(update_fields=["status", "updated_at"])
            return Response(
                {"detail": str(exc), "hubtel": exc.body},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        data = hubtel_data(hubtel_response)
        code = hubtel_response_code(hubtel_response)
        checkout_url = data.get("checkoutUrl") or data.get("CheckoutUrl")
        checkout_direct_url = data.get("checkoutDirectUrl") or data.get("CheckoutDirectUrl")
        checkout_id = data.get("checkoutId") or data.get("CheckoutId") or ""

        if code not in ("0000", "0001") or not checkout_url:
            payment.status = Payment.FAILED
            payment.save(update_fields=["status", "updated_at"])
            return Response(
                {"detail": "Hubtel rejected the checkout request.", "hubtel": hubtel_response},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        payment.checkout_id = str(checkout_id)
        payment.checkout_url = checkout_url
        payment.status = Payment.PENDING
        payment.save(update_fields=["checkout_id", "checkout_url", "status", "updated_at"])

        return Response(
            {
                "checkout_url": checkout_url,
                "checkout_direct_url": checkout_direct_url,
                "checkout_id": checkout_id,
                "client_reference": payment.client_reference,
                "order_id": order.id,
                "amount": str(order.total_cost),
            },
            status=status.HTTP_201_CREATED,
        )


class HubtelCallbackAPIView(APIView):
    """Hubtel Online Checkout server-to-server callback."""

    authentication_classes = []
    permission_classes = []

    def post(self, request, *args, **kwargs):
        from payment.hubtel import hubtel_data, hubtel_response_code

        payload = request.data if isinstance(request.data, dict) else {}
        data = hubtel_data(payload)
        client_reference = str(
            data.get("ClientReference")
            or data.get("clientReference")
            or payload.get("ClientReference")
            or payload.get("clientReference")
            or ""
        )
        if not client_reference:
            return Response({"ok": False, "detail": "Missing clientReference"}, status=status.HTTP_400_BAD_REQUEST)

        payment = Payment.objects.filter(client_reference=client_reference).select_related("order").first()
        if not payment:
            return Response({"ok": False, "detail": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

        code = hubtel_response_code(payload)
        payment_status = str(data.get("Status") or data.get("status") or "").lower()
        success = code == "0000" and payment_status in {"", "success", "paid"}

        if success:
            _complete_paid_order(payment)
            return Response({"ok": True, "status": "paid"})

        if payment.status != Payment.COMPLETED:
            payment.status = Payment.FAILED
            payment.save(update_fields=["status", "updated_at"])
        return Response({"ok": True, "status": "failed"})


class HubtelPaymentStatusAPIView(APIView):
    """Buyer-facing status after returning from Hubtel checkout."""

    def get(self, request, *args, **kwargs):
        ref = request.query_params.get("ref") or request.query_params.get("client_reference")
        if not request.user.is_authenticated:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)
        if not ref:
            return Response({"detail": "Missing payment reference."}, status=status.HTTP_400_BAD_REQUEST)
        payment = Payment.objects.filter(
            client_reference=ref,
            order__buyer=request.user,
        ).select_related("order").first()
        if not payment:
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "status": payment.status,
                "order_id": payment.order_id,
                "client_reference": payment.client_reference,
                "paid": payment.status == Payment.COMPLETED,
            }
        )


class HubtelAppReturnView(APIView):
    """Hubtel return/cancel URL for the mobile app: sends the browser back to
    the app with tamaade://checkout/result. The app then asks the status API,
    so nothing here is trusted as proof of payment."""

    authentication_classes = []
    permission_classes = []

    def get(self, request, *args, **kwargs):
        ref = "".join(ch for ch in str(request.query_params.get("ref", "")) if ch.isalnum())[:32]
        result = "success" if request.query_params.get("result") == "success" else "cancel"
        deep_link = f"tamaade://checkout/result?{urlencode({'ref': ref, 'result': result})}"
        return render(
            request,
            "payment/app_return.html",
            {"deep_link": deep_link, "success": result == "success"},
        )
