from decimal import Decimal
from unittest.mock import Mock, patch

import requests
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from orders.models import Order
from payment.hubtel import (
    HubtelError,
    hubtel_data,
    hubtel_error_detail,
    hubtel_is_configured,
    hubtel_response_code,
    initiate_checkout,
    sanitize_description,
)
from payment.models import Payment
from payment.views import _complete_paid_order
from products.models import Product, ProductCategory

User = get_user_model()

HUBTEL_SETTINGS = dict(
    HUBTEL_API_ID="test-id",
    HUBTEL_API_KEY="test-key",
    HUBTEL_COLLECTION_ACCOUNT_NUMBER="2032167",
    HUBTEL_CHECKOUT_BASE="https://payproxyapi.hubtel.com",
    BACKEND_DOMAIN="http://localhost:8000",
    FRONTEND_DOMAIN="http://localhost:3000",
)


class HubtelHelperTests(SimpleTestCase):
    def test_sanitize_description_strips_symbols_and_truncates(self):
        text = sanitize_description("Tamaade order #12 — café!!! extra-long " + ("x" * 120))
        self.assertNotIn("#", text)
        self.assertNotIn("—", text)
        self.assertLessEqual(len(text), 100)
        self.assertTrue(text.startswith("Tamaade order 12"))

    def test_sanitize_description_falls_back_when_empty(self):
        self.assertEqual(sanitize_description(""), "Tamaade order")
        self.assertEqual(sanitize_description("!!!"), "Tamaade order")

    def test_hubtel_data_reads_camel_and_pascal_case(self):
        self.assertEqual(hubtel_data({"data": {"checkoutUrl": "a"}}), {"checkoutUrl": "a"})
        self.assertEqual(hubtel_data({"Data": {"Status": "Paid"}}), {"Status": "Paid"})
        self.assertEqual(hubtel_data("not-a-dict"), {})
        self.assertEqual(hubtel_data({"data": "x"}), {})

    def test_hubtel_error_detail_from_field_list(self):
        detail = hubtel_error_detail(
            400,
            {
                "responseCode": "4000",
                "data": [{"field": "ClientReference", "errorMessage": "Duplicated client reference. Please try again."}],
            },
        )
        self.assertEqual(detail, "Duplicated client reference. Please try again.")

    def test_hubtel_response_code_from_root_or_data(self):
        self.assertEqual(hubtel_response_code({"responseCode": "0000"}), "0000")
        self.assertEqual(hubtel_response_code({"ResponseCode": "0001"}), "0001")
        self.assertEqual(hubtel_response_code({"data": {"responseCode": "0000"}}), "0000")
        self.assertEqual(hubtel_response_code({}), "")
        self.assertEqual(hubtel_response_code(None), "")

    @override_settings(HUBTEL_API_ID="", HUBTEL_API_KEY="", HUBTEL_COLLECTION_ACCOUNT_NUMBER="")
    def test_not_configured_without_credentials(self):
        self.assertFalse(hubtel_is_configured())

    @override_settings(**HUBTEL_SETTINGS)
    def test_configured_with_credentials(self):
        self.assertTrue(hubtel_is_configured())

    @override_settings(**HUBTEL_SETTINGS)
    @patch("payment.hubtel.requests.post")
    def test_initiate_checkout_posts_online_checkout_payload(self, mock_post):
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: {"responseCode": "0000", "data": {"checkoutUrl": "https://pay.hubtel.com/x"}},
            text="",
        )
        body = initiate_checkout(
            total_amount="45.5",
            description="Tamaade order #9!",
            callback_url="http://localhost:8000/api/user/payments/hubtel/callback/",
            return_url="http://localhost:3000/checkout/success?ref=abc",
            cancellation_url="http://localhost:3000/checkout/cancel?ref=abc",
            client_reference="TMD" + "x" * 40,
            payee_name="Ama Buyer",
            payee_mobile_number="+233201234567",
            payee_email="ama@test.com",
        )
        self.assertEqual(body["responseCode"], "0000")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], "https://payproxyapi.hubtel.com/items/initiate")
        payload = kwargs["json"]
        self.assertEqual(payload["totalAmount"], 45.5)
        self.assertEqual(payload["description"], "Tamaade order 9")
        self.assertEqual(payload["merchantAccountNumber"], "2032167")
        self.assertEqual(len(payload["clientReference"]), 32)
        self.assertEqual(payload["payeeName"], "Ama Buyer")
        self.assertEqual(payload["payeeMobileNumber"], "+233201234567")
        self.assertTrue(kwargs["headers"]["Authorization"].startswith("Basic "))
        self.assertEqual(kwargs["timeout"], 30)

    @override_settings(**HUBTEL_SETTINGS)
    @patch("payment.hubtel.requests.post")
    def test_initiate_checkout_raises_on_http_error(self, mock_post):
        mock_post.return_value = Mock(
            status_code=400,
            json=lambda: {
                "responseCode": "4000",
                "data": [{"field": "ClientReference", "errorMessage": "Duplicated client reference. Please try again."}],
            },
            text="",
        )
        with self.assertRaises(HubtelError) as ctx:
            initiate_checkout(
                total_amount=10,
                description="Order",
                callback_url="http://cb",
                return_url="http://ok",
                cancellation_url="http://cancel",
                client_reference="REF1",
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Duplicated client reference", str(ctx.exception))

    @override_settings(**HUBTEL_SETTINGS)
    @patch("payment.hubtel.requests.post", side_effect=requests.ConnectionError("offline"))
    def test_initiate_checkout_raises_on_network_error(self, _mock_post):
        with self.assertRaises(HubtelError) as ctx:
            initiate_checkout(
                total_amount=10,
                description="Order",
                callback_url="http://cb",
                return_url="http://ok",
                cancellation_url="http://cancel",
                client_reference="REF1",
            )
        self.assertIn("offline", str(ctx.exception))


@override_settings(**HUBTEL_SETTINGS)
class HubtelPaymentAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username="seller-pay",
            email="seller-pay@test.com",
            password="pass12345",
        )
        self.buyer = User.objects.create_user(
            username="buyer-pay@test.com",
            email="buyer-pay@test.com",
            password="BuyerPass123!",
            first_name="Ama",
            last_name="Buyer",
        )
        self.other = User.objects.create_user(
            username="other-pay@test.com",
            email="other-pay@test.com",
            password="BuyerPass123!",
            first_name="Kojo",
            last_name="Other",
        )
        EmailAddress.objects.create(
            user=self.buyer, email=self.buyer.email, verified=True, primary=True
        )
        EmailAddress.objects.create(
            user=self.other, email=self.other.email, verified=True, primary=True
        )
        category = ProductCategory.objects.create(name="Pay")
        self.product = Product.objects.create(
            seller=self.seller,
            category=category,
            name="Kettle",
            desc="Electric kettle",
            price=Decimal("45.00"),
            quantity=5,
        )

    def _login(self, email="buyer-pay@test.com"):
        login = self.client.post(
            "/api/user/login/",
            {"email": email, "password": "BuyerPass123!"},
            format="json",
        )
        token = login.json().get("access") or login.json().get("access_token")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def _cart(self, quantity=1):
        self._login()
        response = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": quantity}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return Order.objects.get(id=response.json()["id"])

    def _hubtel_ok(self):
        return {
            "responseCode": "0000",
            "data": {
                "checkoutUrl": "https://pay.hubtel.com/checkout/abc",
                "checkoutDirectUrl": "https://pay.hubtel.com/direct/abc",
                "checkoutId": "chk-1",
            },
        }

    def test_checkout_requires_authentication(self):
        response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 401)

    def test_checkout_rejects_empty_basket(self):
        self._login()
        response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("empty", response.json()["detail"].lower())

    @override_settings(HUBTEL_API_ID="", HUBTEL_API_KEY="", HUBTEL_COLLECTION_ACCOUNT_NUMBER="")
    def test_checkout_unavailable_when_hubtel_not_configured(self):
        self._cart()
        response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 503)

    def test_checkout_returns_hubtel_url_and_creates_payment(self):
        order = self._cart()
        with patch("payment.hubtel.initiate_checkout", return_value=self._hubtel_ok()) as mock_init:
            response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["checkout_url"], "https://pay.hubtel.com/checkout/abc")
        self.assertEqual(data["checkout_id"], "chk-1")
        self.assertEqual(data["order_id"], order.id)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_option, Payment.HUBTEL)
        self.assertEqual(payment.status, Payment.PENDING)
        self.assertEqual(payment.checkout_url, data["checkout_url"])
        self.assertTrue(payment.client_reference.startswith("TMD"))
        self.assertLessEqual(len(payment.client_reference), 32)
        kwargs = mock_init.call_args.kwargs
        self.assertEqual(kwargs["total_amount"], order.total_cost)
        self.assertIn("/api/user/payments/hubtel/callback/", kwargs["callback_url"])
        self.assertIn(payment.client_reference, kwargs["return_url"])
        self.assertIn(payment.client_reference, kwargs["cancellation_url"])

    def test_checkout_rotates_client_reference_on_retry(self):
        order = self._cart()
        with patch("payment.hubtel.initiate_checkout", return_value=self._hubtel_ok()):
            first = self.client.post("/api/user/payments/hubtel/checkout/")
            second = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertNotEqual(first.json()["client_reference"], second.json()["client_reference"])
        self.assertEqual(Payment.objects.filter(order=order).count(), 1)

    def test_checkout_surfaces_duplicate_client_reference_error(self):
        self._cart()
        body = {
            "responseCode": "4000",
            "status": "Error",
            "data": [
                {
                    "field": "ClientReference",
                    "errorMessage": "Duplicated client reference. Please try again.",
                }
            ],
        }
        with patch(
            "payment.hubtel.initiate_checkout",
            side_effect=HubtelError(
                hubtel_error_detail(400, body),
                status_code=400,
                body=body,
            ),
        ):
            response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 502)
        self.assertIn("Duplicated client reference", response.json()["detail"])

    def test_checkout_rejects_already_paid_order(self):
        order = self._cart()
        Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            status=Payment.COMPLETED,
            client_reference="TMDALREADYPAID1",
        )
        response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 400)
        self.assertIn("already paid", response.json()["detail"].lower())

    def test_checkout_marks_failed_when_hubtel_errors(self):
        order = self._cart()
        with patch(
            "payment.hubtel.initiate_checkout",
            side_effect=HubtelError("down", status_code=502, body={"err": True}),
        ):
            response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 502)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.status, Payment.FAILED)

    def test_checkout_marks_failed_when_hubtel_omits_url(self):
        order = self._cart()
        with patch(
            "payment.hubtel.initiate_checkout",
            return_value={"responseCode": "2001", "data": {}},
        ):
            response = self.client.post("/api/user/payments/hubtel/checkout/")
        self.assertEqual(response.status_code, 502)
        self.assertEqual(Payment.objects.get(order=order).status, Payment.FAILED)

    def test_callback_marks_order_paid_and_decrements_stock(self):
        order = self._cart()
        payment = Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDTESTREF123",
            status=Payment.PENDING,
        )
        response = self.client.post(
            "/api/user/payments/hubtel/callback/",
            {
                "ResponseCode": "0000",
                "Data": {
                    "CheckoutId": "d052f6e53f6a4052bf98fed445c80c1a",
                    "ClientReference": "TMDTESTREF123",
                    "Status": "Success",
                    "Amount": 45.00,
                },
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "paid")
        payment.refresh_from_db()
        order.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(payment.status, Payment.COMPLETED)
        self.assertEqual(order.status, Order.COMPLETED)
        self.assertEqual(self.product.quantity, 4)

    def test_callback_accepts_paid_status(self):
        order = self._cart()
        Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDPPAIDSTATUS1",
            status=Payment.PENDING,
        )
        response = self.client.post(
            "/api/user/payments/hubtel/callback/",
            {
                "responseCode": "0000",
                "data": {"clientReference": "TMDPPAIDSTATUS1", "status": "Paid"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Payment.objects.get(client_reference="TMDPPAIDSTATUS1").status, Payment.COMPLETED)

    def test_callback_is_idempotent(self):
        order = self._cart()
        payment = Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDIDEMPOTENT01",
            status=Payment.PENDING,
        )
        payload = {
            "ResponseCode": "0000",
            "Data": {"ClientReference": "TMDIDEMPOTENT01", "Status": "Success"},
        }
        first = self.client.post("/api/user/payments/hubtel/callback/", payload, format="json")
        second = self.client.post("/api/user/payments/hubtel/callback/", payload, format="json")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        payment.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(payment.status, Payment.COMPLETED)
        self.assertEqual(self.product.quantity, 4)

    def test_callback_marks_failed_when_hubtel_reports_failure(self):
        order = self._cart()
        payment = Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDFAILSTATUS01",
            status=Payment.PENDING,
        )
        response = self.client.post(
            "/api/user/payments/hubtel/callback/",
            {
                "ResponseCode": "0000",
                "Data": {"ClientReference": "TMDFAILSTATUS01", "Status": "Unpaid"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "failed")
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, Payment.FAILED)
        self.assertEqual(order.status, Order.PENDING)

    def test_callback_does_not_unpay_completed_order(self):
        order = self._cart()
        payment = Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDKEEPPAID0001",
            status=Payment.PENDING,
        )
        _complete_paid_order(payment)
        response = self.client.post(
            "/api/user/payments/hubtel/callback/",
            {
                "ResponseCode": "2001",
                "Data": {"ClientReference": "TMDKEEPPAID0001", "Status": "Unpaid"},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.COMPLETED)

    def test_callback_requires_client_reference(self):
        response = self.client.post(
            "/api/user/payments/hubtel/callback/",
            {"ResponseCode": "0000", "Data": {"Status": "Success"}},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_callback_returns_404_for_unknown_reference(self):
        response = self.client.post(
            "/api/user/payments/hubtel/callback/",
            {"ResponseCode": "0000", "Data": {"ClientReference": "UNKNOWNREF", "Status": "Success"}},
            format="json",
        )
        self.assertEqual(response.status_code, 404)

    def test_status_requires_authentication(self):
        response = self.client.get("/api/user/payments/hubtel/status/?ref=TMDX")
        self.assertEqual(response.status_code, 401)

    def test_status_requires_reference(self):
        self._login()
        response = self.client.get("/api/user/payments/hubtel/status/")
        self.assertEqual(response.status_code, 400)

    def test_checkout_get_without_payment_or_address(self):
        order = self._cart()
        response = self.client.get(f"/api/user/payments/checkout/{order.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["payment"])
        self.assertIsNone(data["shipping_address"])
        self.assertIsNone(data["billing_address"])

    def test_checkout_patch_payment_only(self):
        order = self._cart()
        response = self.client.patch(
            f"/api/user/payments/checkout/{order.id}/",
            {"payment": {"payment_option": Payment.HUBTEL}},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        payment = Payment.objects.get(order=order)
        self.assertEqual(payment.payment_option, Payment.HUBTEL)
        self.assertEqual(payment.status, Payment.PENDING)

    def test_stripe_webhook_missing_signature_returns_400(self):
        response = self.client.post("/api/user/payments/stripe/webhook/", {}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_status_returns_pending_and_paid(self):
        order = self._cart()
        payment = Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDSTATUSREF001",
            status=Payment.PENDING,
        )
        pending = self.client.get("/api/user/payments/hubtel/status/?ref=TMDSTATUSREF001")
        self.assertEqual(pending.status_code, 200)
        self.assertFalse(pending.json()["paid"])
        self.assertEqual(pending.json()["status"], Payment.PENDING)

        payment.status = Payment.COMPLETED
        payment.save(update_fields=["status"])
        paid = self.client.get("/api/user/payments/hubtel/status/?ref=TMDSTATUSREF001")
        self.assertTrue(paid.json()["paid"])
        self.assertEqual(paid.json()["order_id"], order.id)

    def test_status_hides_other_buyers_payment(self):
        order = self._cart()
        Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDOTHERBUYER01",
            status=Payment.PENDING,
        )
        self._login("other-pay@test.com")
        response = self.client.get("/api/user/payments/hubtel/status/?ref=TMDOTHERBUYER01")
        self.assertEqual(response.status_code, 404)

    def test_complete_paid_order_does_not_go_negative(self):
        order = self._cart(quantity=5)
        self.product.quantity = 2
        self.product.save(update_fields=["quantity"])
        payment = Payment.objects.create(
            order=order,
            payment_option=Payment.HUBTEL,
            client_reference="TMDNEGSTOCK0001",
            status=Payment.PENDING,
        )
        _complete_paid_order(payment)
        self.product.refresh_from_db()
        self.assertEqual(self.product.quantity, 0)
