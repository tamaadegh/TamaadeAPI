from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from products.models import HeroBanner, HomeSection, MerchTile, NavLink, PriceTier, Product, ProductCategory, StorefrontPromo

User = get_user_model()


class ProductApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.seller = User.objects.create_user(
            username="seller",
            email="seller@test.com",
            password="pass12345",
            first_name="Sell",
            last_name="Er",
        )
        self.category = ProductCategory.objects.create(name="Electronics")
        self.product = Product.objects.create(
            seller=self.seller,
            category=self.category,
            name="Test Headphones",
            desc="A pair of headphones",
            price=Decimal("49.99"),
            quantity=10,
        )

    def test_list_products(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        names = [item["name"] for item in data]
        self.assertIn("Test Headphones", names)

    def test_retrieve_product(self):
        response = self.client.get(f"/api/products/{self.product.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Test Headphones")
        self.assertEqual(response.json()["category"], "Electronics")

    def test_list_categories(self):
        response = self.client.get("/api/products/categories/")
        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.json()]
        self.assertIn("Electronics", names)

    def test_list_active_banners_only(self):
        HeroBanner.objects.create(
            title="Active sale",
            image_url="https://example.com/active.jpg",
            link="/deals",
            order=1,
            is_active=True,
        )
        HeroBanner.objects.create(
            title="Hidden sale",
            image_url="https://example.com/hidden.jpg",
            link="/deals",
            order=2,
            is_active=False,
        )
        HeroBanner.objects.create(
            title="No image yet",
            link="/deals",
            order=3,
            is_active=True,
        )

        response = self.client.get("/api/products/banners/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        titles = [item["title"] for item in data]
        self.assertIn("Active sale", titles)
        self.assertIn("No image yet", titles)
        self.assertNotIn("Hidden sale", titles)
        self.assertEqual(data[0]["image"], "https://example.com/active.jpg")
        self.assertEqual(data[0]["link"], "/deals")
        untitled = next(item for item in data if item["title"] == "No image yet")
        self.assertIsNone(untitled["image"])

    def test_product_promo_fields_from_backend(self):
        self.product.compare_at_price = Decimal("99.98")
        self.product.promo_label = "UP TO 50% OFF"
        self.product.brand = "Tamaade Audio"
        self.product.is_new = True
        self.product.is_express = True
        self.product.save()

        response = self.client.get(f"/api/products/{self.product.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["compare_at_price"], "99.98")
        self.assertEqual(data["discount_percent"], 50)
        self.assertEqual(data["promo_label"], "UP TO 50% OFF")
        self.assertEqual(data["brand"], "Tamaade Audio")
        self.assertTrue(data["is_new"])
        self.assertTrue(data["is_express"])

    def test_product_without_promo_has_no_discount(self):
        response = self.client.get(f"/api/products/{self.product.id}/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsNone(data["compare_at_price"])
        self.assertIsNone(data["discount_percent"])
        self.assertEqual(data["promo_label"], "")
        self.assertFalse(data["is_new"])

    def test_list_active_price_tiers_only(self):
        PriceTier.objects.create(amount=50, order=0, is_active=True)
        PriceTier.objects.create(amount=999, order=1, is_active=False)
        response = self.client.get("/api/products/price-tiers/")
        self.assertEqual(response.status_code, 200)
        amounts = [item["amount"] for item in response.json()]
        self.assertIn(50, amounts)
        self.assertNotIn(999, amounts)

    def test_list_active_storefront_promos_only(self):
        StorefrontPromo.objects.create(
            key="top_strip",
            title="Wardrobe refresh",
            highlight="35%–50% OFF",
            cta_label="shop now",
            link="/deals",
            is_active=True,
        )
        StorefrontPromo.objects.create(
            key="hidden",
            title="Hidden",
            is_active=False,
        )
        response = self.client.get("/api/products/promos/")
        self.assertEqual(response.status_code, 200)
        keys = [item["key"] for item in response.json()]
        self.assertIn("top_strip", keys)
        self.assertNotIn("hidden", keys)

    def test_list_merch_tiles_by_placement(self):
        MerchTile.objects.create(
            placement="main",
            title="Appliances",
            image_url="https://example.com/a.jpg",
            link="/products?category=Appliances",
            order=1,
            is_active=True,
        )
        MerchTile.objects.create(
            placement="featured",
            title="Shoes",
            image_url="https://example.com/s.jpg",
            order=1,
            is_active=True,
        )
        MerchTile.objects.create(
            placement="main",
            title="Hidden",
            is_active=False,
        )
        response = self.client.get("/api/products/merch-tiles/?placement=main")
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()]
        self.assertIn("Appliances", titles)
        self.assertNotIn("Shoes", titles)
        self.assertNotIn("Hidden", titles)

    def test_list_home_sections_by_location(self):
        HomeSection.objects.create(
            key="hot-arrivals",
            location="home",
            title="Hot Arrivals!",
            product_source="newest",
            is_active=True,
        )
        HomeSection.objects.create(
            key="bundles",
            location="deals",
            title="Shop By Bundles",
            is_active=True,
        )
        response = self.client.get("/api/products/home-sections/?location=home")
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()]
        self.assertIn("Hot Arrivals!", titles)
        self.assertNotIn("Shop By Bundles", titles)

    def test_list_nav_links_active_only(self):
        NavLink.objects.create(label="Electronics", link="/products?category=Electronics", order=0)
        NavLink.objects.create(label="Hidden", link="/", is_active=False, order=1)
        response = self.client.get("/api/products/nav-links/")
        self.assertEqual(response.status_code, 200)
        labels = [item["label"] for item in response.json()]
        self.assertIn("Electronics", labels)
        self.assertNotIn("Hidden", labels)

    def test_patch_product_name_only(self):
        self.client.force_authenticate(self.seller)
        response = self.client.patch(
            f"/api/products/{self.product.id}/",
            {"name": "Renamed Headphones"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Renamed Headphones")

    def test_non_seller_cannot_patch_product(self):
        buyer = User.objects.create_user(
            username="buyer-prod",
            email="buyer-prod@test.com",
            password="pass12345",
        )
        self.client.force_authenticate(buyer)
        response = self.client.patch(
            f"/api/products/{self.product.id}/",
            {"name": "Hacked"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_staff_can_patch_other_sellers_product(self):
        staff = User.objects.create_user(
            username="staff-prod",
            email="staff-prod@test.com",
            password="pass12345",
            is_staff=True,
        )
        self.client.force_authenticate(staff)
        response = self.client.patch(
            f"/api/products/{self.product.id}/",
            {"name": "Staff rename"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Staff rename")

    def test_seller_can_create_product_image_without_file(self):
        self.client.force_authenticate(self.seller)
        response = self.client.post(
            "/api/products/images/",
            {"product": self.product.id, "order": 0},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["product"], self.product.id)
        self.assertIsNone(response.json().get("url"))

    def test_list_products_without_image_is_ok(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)
        item = next(row for row in response.json() if row["id"] == self.product.id)
        self.assertFalse(item["image"])
        self.assertEqual(item["images"], [])
