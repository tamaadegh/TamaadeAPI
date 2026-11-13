import io
import shutil
import tempfile
from unittest.mock import patch

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, SimpleTestCase, TestCase, override_settings
from PIL import Image
from rest_framework.test import APIClient

from config import cloudinary_media
from config.cloudinary_media import resized_url
from products.admin import ProductCategoryAdmin
from products.models import HeroBanner, Product, ProductCategory, ProductImage

User = get_user_model()

MEDIA = tempfile.mkdtemp()
CLOUD_URL = "cloudinary://key:secret@demo"


def png(name="icon.png"):
    buf = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def fake_upload(file, folder, **kwargs):
    return {
        "secure_url": f"https://res.cloudinary.com/demo/image/upload/v1/{folder}/x.png",
        "public_id": f"{folder}/x",
    }


class ResizedUrlTests(SimpleTestCase):
    def test_adds_transformation_to_cloudinary_urls(self):
        url = "https://res.cloudinary.com/demo/image/upload/media/images/a_b"
        self.assertEqual(
            resized_url(url, width=600),
            "https://res.cloudinary.com/demo/image/upload/f_auto,q_auto,c_limit,w_600/media/images/a_b",
        )
        self.assertIn("c_fill,w_150,h_150", resized_url(url, width=150, height=150, quality=60))

    def test_leaves_other_urls_alone(self):
        for url in (None, "", "https://ik.imagekit.io/x/a.jpg",
                    "https://res.cloudinary.com/demo/image/upload/w_300,c_fill/a.jpg"):
            self.assertEqual(resized_url(url, width=600), url)


@override_settings(MEDIA_ROOT=MEDIA, CLOUDINARY_URL=CLOUD_URL)
class CloudinaryUploadTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA, ignore_errors=True)

    def setUp(self):
        cloudinary_media._configured = False

    @patch("cloudinary.uploader.upload", side_effect=fake_upload)
    def test_category_icon_goes_to_cloudinary(self, upload):
        category = ProductCategory.objects.create(name="Chairs", icon=png())
        category.refresh_from_db()
        self.assertTrue(category.icon_url.startswith("https://res.cloudinary.com/demo/"))
        self.assertFalse(category.icon)  # local copy dropped
        self.assertEqual(upload.call_args.kwargs["folder"], "tamaade/categories")

        data = APIClient().get("/api/products/categories/").json()
        row = next(c for c in data if c["id"] == category.id)
        self.assertEqual(row["icon"], category.icon_url)
        self.assertNotIn("icon_url", row)

    @patch("cloudinary.uploader.upload", side_effect=fake_upload)
    def test_product_image_and_banner_go_to_cloudinary(self, upload):
        seller = User.objects.create_user(username="s", email="s@t.com", password="pass12345")
        product = Product.objects.create(
            name="Stool", desc="d", price="10.00", quantity=1, seller=seller,
            category=ProductCategory.objects.create(name="Stools"),
        )
        image = ProductImage.objects.create(product=product, file_local=png("p.png"))
        image.refresh_from_db()
        self.assertTrue(image.url.startswith("https://res.cloudinary.com/"))
        self.assertEqual(image.file_id, f"tamaade/products/{product.id}/x")
        self.assertFalse(image.file_local)

        banner = HeroBanner.objects.create(title="Sale", image=png("b.png"))
        banner.refresh_from_db()
        self.assertTrue(banner.image_url.startswith("https://res.cloudinary.com/"))
        self.assertEqual(banner.resolved_image, banner.image_url)

    @override_settings(CLOUDINARY_URL="")
    @patch("cloudinary.uploader.upload", side_effect=fake_upload)
    def test_without_cloudinary_the_file_stays_local(self, upload):
        category = ProductCategory.objects.create(name="Beds", icon=png())
        category.refresh_from_db()
        upload.assert_not_called()
        self.assertEqual(category.icon_url, "")
        self.assertTrue(category.resolved_icon.startswith("/media/"))


class CategoryAdminIconRuleTests(TestCase):
    def setUp(self):
        self.admin = ProductCategoryAdmin(ProductCategory, AdminSite())
        self.request = RequestFactory().get("/")
        self.request.user = User.objects.create_superuser(
            username="root", email="root@t.com", password="pass12345"
        )

    def test_new_category_requires_an_image(self):
        form_class = self.admin.get_form(self.request, obj=None)
        form = form_class(data={"name": "Tables"}, files={})
        self.assertFalse(form.is_valid())
        self.assertIn("icon", form.errors)

    def test_existing_category_can_be_saved_without_one(self):
        category = ProductCategory.objects.create(name="Old")
        form_class = self.admin.get_form(self.request, obj=category)
        form = form_class(data={"name": "Old renamed"}, files={}, instance=category)
        self.assertTrue(form.is_valid(), form.errors)
