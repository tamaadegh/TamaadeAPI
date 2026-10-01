from django.urls import include, path
from rest_framework.routers import DefaultRouter

from payment.views import (
    CheckoutAPIView,
    HubtelAppReturnView,
    HubtelCallbackAPIView,
    HubtelCheckoutAPIView,
    HubtelPaymentStatusAPIView,
    PaymentViewSet,
    StripeCheckoutSessionCreateAPIView,
    StripeWebhookAPIView,
)

app_name = "payment"

router = DefaultRouter()
router.register(r"", PaymentViewSet)

urlpatterns = [
    path("hubtel/checkout/", HubtelCheckoutAPIView.as_view(), name="hubtel_checkout"),
    path("hubtel/callback/", HubtelCallbackAPIView.as_view(), name="hubtel_callback"),
    path("hubtel/status/", HubtelPaymentStatusAPIView.as_view(), name="hubtel_status"),
    path("hubtel/app-return/", HubtelAppReturnView.as_view(), name="hubtel_app_return"),
    path(
        "stripe/create-checkout-session/<int:order_id>/",
        StripeCheckoutSessionCreateAPIView.as_view(),
        name="checkout_session",
    ),
    path("stripe/webhook/", StripeWebhookAPIView.as_view(), name="stripe_webhook"),
    path("checkout/<int:pk>/", CheckoutAPIView.as_view(), name="checkout"),
    path("", include(router.urls)),
]
