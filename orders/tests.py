from decimal import Decimal

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from orders.models import Order
from payment.models import Payment
from products.models import Product, ProductCategory

User = get_user_model()


class OrderApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username="seller2",
            email="seller2@test.com",
            password="pass12345",
            first_name="Sell",
            last_name="Er",
        )
        self.buyer = User.objects.create_user(
            username="buyer2",
            email="buyer2@test.com",
            password="BuyerPass123!",
            first_name="Ama",
            last_name="Buyer",
        )
        EmailAddress.objects.create(
            user=self.buyer,
            email=self.buyer.email,
            verified=True,
            primary=True,
        )
        category = ProductCategory.objects.create(name="Kitchen")
        self.product = Product.objects.create(
            seller=self.seller,
            category=category,
            name="Blender",
            desc="Kitchen blender",
            price=Decimal("59.00"),
            quantity=8,
        )

    def _auth(self):
        login = self.client.post(
            "/api/user/login/",
            {"email": "buyer2@test.com", "password": "BuyerPass123!"},
            format="json",
        )
        token = login.json().get("access") or login.json().get("access_token")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

    def test_create_order_requires_auth(self):
        response = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": 1}]},
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_create_pending_order(self):
        self._auth()
        response = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": 2}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["status"], "P")
        self.assertEqual(len(data["order_items"]), 1)
        self.assertEqual(data["order_items"][0]["quantity"], 2)

    def test_pending_cart_persists_after_relogin(self):
        self._auth()
        created = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        order_id = created.json()["id"]

        self.client.credentials()
        self._auth()

        response = self.client.get("/api/user/orders/")
        self.assertEqual(response.status_code, 200)
        pending = [item for item in response.json() if item["status"] == "P"]
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], order_id)
        self.assertEqual(pending[0]["order_items"][0]["product"], self.product.id)
        self.assertEqual(pending[0]["order_items"][0]["quantity"], 1)

    def test_second_create_reuses_pending_cart(self):
        self._auth()
        first = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": 1}]},
            format="json",
        )
        second = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": 2}]},
            format="json",
        )
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(second.json()["order_items"][0]["quantity"], 3)

    def _create_cart(self, quantity=1):
        self._auth()
        response = self.client.post(
            "/api/user/orders/",
            {"order_items": [{"product": self.product.id, "quantity": quantity}]},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

    def test_patch_order_item_quantity(self):
        order = self._create_cart(quantity=1)
        item_id = order["order_items"][0]["id"]
        response = self.client.patch(
            f"/api/user/orders/{order['id']}/order-items/{item_id}/",
            {"quantity": 3},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["quantity"], 3)
        self.assertEqual(Decimal(str(data["cost"])), Decimal("177.00"))

    def test_patch_order_item_quantity_with_pending_payment(self):
        order = self._create_cart(quantity=1)
        Payment.objects.create(
            order_id=order["id"],
            status=Payment.PENDING,
            payment_option=Payment.HUBTEL,
        )
        item_id = order["order_items"][0]["id"]
        response = self.client.patch(
            f"/api/user/orders/{order['id']}/order-items/{item_id}/",
            {"quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quantity"], 2)

    def test_patch_order_item_quantity_with_failed_payment(self):
        order = self._create_cart(quantity=1)
        Payment.objects.create(
            order_id=order["id"],
            status=Payment.FAILED,
            payment_option=Payment.HUBTEL,
        )
        item_id = order["order_items"][0]["id"]
        response = self.client.patch(
            f"/api/user/orders/{order['id']}/order-items/{item_id}/",
            {"quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["quantity"], 2)

    def test_patch_order_item_on_paid_order_returns_400(self):
        order = self._create_cart(quantity=1)
        Order.objects.filter(id=order["id"]).update(status=Order.COMPLETED)
        Payment.objects.create(
            order_id=order["id"],
            status=Payment.COMPLETED,
            payment_option=Payment.HUBTEL,
        )
        item_id = order["order_items"][0]["id"]
        response = self.client.patch(
            f"/api/user/orders/{order['id']}/order-items/{item_id}/",
            {"quantity": 2},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("paid", str(response.json()).lower())

    def test_patch_quantity_exceeds_stock(self):
        order = self._create_cart(quantity=1)
        item_id = order["order_items"][0]["id"]
        response = self.client.patch(
            f"/api/user/orders/{order['id']}/order-items/{item_id}/",
            {"quantity": 99},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
