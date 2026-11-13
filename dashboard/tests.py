from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from orders.models import Order, OrderItem
from products.models import Product, ProductCategory

User = get_user_model()


class DashboardPagesTests(TestCase):
    """Every dashboard page renders for staff, with and without data."""

    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@t.com", password="pass12345", is_staff=True, first_name="Ama"
        )
        self.client.force_login(self.staff)

    def _seed(self):
        cat = ProductCategory.objects.create(name="Chairs")
        product = Product.objects.create(
            name="Green velvet chair", desc="Soft", price="450.00", quantity=2, seller=self.staff, category=cat
        )
        buyer = User.objects.create_user(username="buyer", email="b@t.com", password="pass12345")
        order = Order.objects.create(buyer=buyer)
        OrderItem.objects.create(order=order, product=product, quantity=2)
        return product, order

    def _pages(self, product=None):
        pages = [
            reverse("dashboard:index"),
            reverse("dashboard:orders_list"),
            reverse("dashboard:orders_list") + "?status=P",
            reverse("dashboard:products_list"),
            reverse("dashboard:products_list") + "?q=chair&sort=-price",
            reverse("dashboard:products_list") + "?sort=not_a_field",
            reverse("dashboard:users_list"),
            reverse("dashboard:users_list") + "?q=buy",
            reverse("dashboard:privacy_settings"),
            reverse("dashboard:sound_settings"),
        ]
        if product:
            pages.append(reverse("dashboard:product_detail", args=[product.id]))
        return pages

    def test_pages_render_empty(self):
        for url in self._pages():
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_pages_render_with_data(self):
        product, order = self._seed()
        for url in self._pages(product):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
        home = self.client.get(reverse("dashboard:index")).content.decode()
        self.assertIn("Green velvet chair", home)  # top products
        self.assertIn(f"#{order.id}", home)  # recent orders

    def test_order_status_update_returns_to_filtered_list(self):
        _, order = self._seed()
        back = reverse("dashboard:orders_list") + "?status=P"
        response = self.client.post(
            reverse("dashboard:order_update_status", args=[order.id]), {"status": "C", "next": back}
        )
        self.assertRedirects(response, back)
        order.refresh_from_db()
        self.assertEqual(order.status, "C")

    def test_login_page_renders_and_signs_in(self):
        self.client.logout()
        login = reverse("admin:login")
        page = self.client.get(login + "?next=/dashboard/")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Welcome back")
        bad = self.client.post(login, {"username": "staff", "password": "nope", "next": "/dashboard/"})
        self.assertContains(bad, "We couldn't sign you in")
        ok = self.client.post(login, {"username": "staff", "password": "pass12345", "next": "/dashboard/"})
        self.assertRedirects(ok, "/dashboard/", fetch_redirect_response=False)

    def test_non_staff_is_sent_to_login(self):
        self.client.logout()
        response = self.client.get(reverse("dashboard:index"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response["Location"])


class StorefrontPagesTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(username="staff2", password="pass12345", is_staff=True)
        self.client.force_login(self.staff)

    def test_every_storefront_page_renders(self):
        from dashboard.storefront import RESOURCES

        for slug in RESOURCES:
            with self.subTest(slug=slug):
                self.assertEqual(self.client.get(reverse("dashboard:resource_list", args=[slug])).status_code, 200)
                self.assertEqual(self.client.get(reverse("dashboard:resource_create", args=[slug])).status_code, 200)
        self.assertEqual(self.client.get("/dashboard/store/nope/").status_code, 404)

    def test_new_category_needs_an_image_but_old_ones_can_be_edited(self):
        url = reverse("dashboard:resource_create", args=["categories"])
        response = self.client.post(url, {"name": "Lamps"})
        self.assertContains(response, "A new category needs an image.")
        self.assertFalse(ProductCategory.objects.filter(name="Lamps").exists())

        old = ProductCategory.objects.create(name="Old")
        response = self.client.post(reverse("dashboard:resource_edit", args=["categories", old.pk]), {"name": "Older"})
        self.assertRedirects(response, reverse("dashboard:resource_list", args=["categories"]))
        old.refresh_from_db()
        self.assertEqual(old.name, "Older")

    def test_banner_with_image_url_and_tile_validation(self):
        response = self.client.post(
            reverse("dashboard:resource_create", args=["banners"]),
            {"title": "Sale", "image_url": "https://res.cloudinary.com/demo/image/upload/a.jpg", "link": "/deals", "order": 0, "is_active": "on"},
        )
        self.assertRedirects(response, reverse("dashboard:resource_list", args=["banners"]))
        response = self.client.post(
            reverse("dashboard:resource_create", args=["tiles"]),
            {"title": "Chairs", "placement": "main", "link": "/products", "order": 0},
        )
        self.assertContains(response, "Upload an image or paste an image URL.")

    def test_price_tier_crud(self):
        from products.models import PriceTier

        self.client.post(reverse("dashboard:resource_create", args=["price-tiers"]), {"amount": 500, "order": 1, "is_active": "on"})
        tier = PriceTier.objects.get(amount=500)
        page = self.client.get(reverse("dashboard:resource_list", args=["price-tiers"]))
        self.assertContains(page, "Under GH₵500")
        self.client.post(reverse("dashboard:resource_delete", args=["price-tiers", tier.pk]))
        self.assertFalse(PriceTier.objects.exists())

    def test_password_change(self):
        url = reverse("dashboard:password_change")
        self.assertEqual(self.client.get(url).status_code, 200)
        response = self.client.post(url, {"old_password": "pass12345", "new_password1": "Tamaade-New-2026", "new_password2": "Tamaade-New-2026"})
        self.assertRedirects(response, reverse("dashboard:index"))
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.check_password("Tamaade-New-2026"))


class ErrorPageTests(TestCase):
    def test_404_uses_the_tamaade_page(self):
        from django.test import override_settings

        with override_settings(DEBUG=False):
            response = self.client.get("/this-page-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "This page doesn", status_code=404)


class LogoutPageTests(TestCase):
    def test_logout_shows_the_tamaade_page(self):
        staff = User.objects.create_user(username="staff3", password="pass12345", is_staff=True)
        self.client.force_login(staff)
        response = self.client.post(reverse("admin:logout"))
        self.assertContains(response, "You're signed out")
        self.assertContains(response, "Sign in again")
