from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from .models import BackgroundSound, PrivacyPolicy, SoundSettings

User = get_user_model()


class PrivacyPolicyAPITests(TestCase):
    def test_returns_default_content_when_empty(self):
        response = APIClient().get("/api/content/privacy/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["title"], "Privacy Policy")
        self.assertIn("only collect", response.json()["content"])
        self.assertEqual(PrivacyPolicy.objects.count(), 1)

    def test_returns_edited_content(self):
        policy = PrivacyPolicy.load()
        policy.content = "Edited"
        policy.save()
        self.assertEqual(APIClient().get("/api/content/privacy/").json()["content"], "Edited")


class BackgroundMusicAPITests(TestCase):
    def setUp(self):
        self.sound = BackgroundSound.objects.create(
            title="Chill", audio_data=b"0123456789", content_type="audio/mpeg", size=10, is_active=True
        )

    def test_returns_active_track(self):
        data = APIClient().get("/api/content/background-music/").json()
        self.assertTrue(data["enabled"])
        self.assertEqual(data["track"]["title"], "Chill")
        self.assertTrue(data["track"]["url"].startswith("http://testserver/api/content/sounds/"))
        self.assertAlmostEqual(data["track"]["volume"], 0.4)

    def test_disabled_globally(self):
        settings_obj = SoundSettings.load()
        settings_obj.music_enabled = False
        settings_obj.save()
        data = APIClient().get("/api/content/background-music/").json()
        self.assertEqual(data, {"enabled": False, "track": None})

    def test_no_active_track(self):
        self.sound.is_active = False
        self.sound.save()
        self.assertEqual(APIClient().get("/api/content/background-music/").json()["track"], None)

    def test_activating_one_sound_deactivates_others(self):
        other = BackgroundSound.objects.create(title="Other", audio_data=b"x", is_active=True)
        self.sound.refresh_from_db()
        self.assertFalse(self.sound.is_active)
        self.assertTrue(other.is_active)

    def test_audio_full_and_range(self):
        url = f"/api/content/sounds/{self.sound.pk}/audio/"
        full = self.client.get(url)
        self.assertEqual(full.status_code, 200)
        self.assertEqual(full.content, b"0123456789")
        self.assertEqual(full["Accept-Ranges"], "bytes")
        part = self.client.get(url, HTTP_RANGE="bytes=2-4")
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, b"234")
        self.assertEqual(part["Content-Range"], "bytes 2-4/10")
        tail = self.client.get(url, HTTP_RANGE="bytes=-3")
        self.assertEqual(tail.content, b"789")
        bad = self.client.get(url, HTTP_RANGE="bytes=50-")
        self.assertEqual(bad.status_code, 416)


class DashboardSoundTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="staff", email="staff@test.com", password="pass12345", is_staff=True
        )
        self.client.force_login(self.staff)

    def test_upload_edit_activate_delete(self):
        upload = SimpleUploadedFile("song.mp3", b"ID3fake", content_type="audio/mpeg")
        response = self.client.post(
            "/dashboard/settings/sound/",
            {"action": "create", "title": "Song", "volume": "0.5", "is_active": "on", "audio_file": upload},
        )
        self.assertEqual(response.status_code, 302)
        sound = BackgroundSound.objects.get()
        self.assertEqual(bytes(sound.audio_data), b"ID3fake")
        self.assertTrue(sound.is_active)

        response = self.client.post(
            f"/dashboard/settings/sound/{sound.pk}/update/",
            {f"s{sound.pk}-title": "Renamed", f"s{sound.pk}-volume": "0.3", f"s{sound.pk}-is_active": "on"},
        )
        sound.refresh_from_db()
        self.assertEqual(sound.title, "Renamed")
        self.assertEqual(bytes(sound.audio_data), b"ID3fake")

        second = BackgroundSound.objects.create(title="B", audio_data=b"b")
        self.client.post(f"/dashboard/settings/sound/{second.pk}/activate/")
        sound.refresh_from_db()
        second.refresh_from_db()
        self.assertFalse(sound.is_active)
        self.assertTrue(second.is_active)

        self.client.post(f"/dashboard/settings/sound/{sound.pk}/delete/")
        self.assertFalse(BackgroundSound.objects.filter(pk=sound.pk).exists())

    def test_rejects_non_audio(self):
        upload = SimpleUploadedFile("x.exe", b"MZ", content_type="application/octet-stream")
        response = self.client.post(
            "/dashboard/settings/sound/",
            {"action": "create", "title": "Bad", "volume": "0.5", "audio_file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(BackgroundSound.objects.exists())

    def test_toggle_and_privacy_pages(self):
        self.client.post("/dashboard/settings/sound/", {"action": "toggle"})
        self.assertFalse(SoundSettings.load().music_enabled)
        self.assertEqual(self.client.get("/dashboard/settings/sound/").status_code, 200)

        self.client.post("/dashboard/settings/privacy/", {"title": "Privacy", "content": "New text"})
        self.assertEqual(PrivacyPolicy.load().content, "New text")
        self.assertEqual(self.client.get("/dashboard/settings/privacy/").status_code, 200)


class ClientContractTests(TestCase):
    """Every public endpoint the web and Android apps call must answer JSON."""

    def test_public_endpoints_respond(self):
        from decimal import Decimal

        from products.models import Product, ProductCategory

        seller = User.objects.create_user(username="s", email="s@test.com", password="x")
        category = ProductCategory.objects.create(name="Shoes")
        product = Product.objects.create(
            seller=seller, category=category, name="Sneaker", price=Decimal("10.00"), quantity=3
        )
        client = APIClient()
        for url in [
            "/api/products/",
            f"/api/products/{product.pk}/",
            "/api/products/categories/",
            "/api/products/banners/",
            "/api/products/price-tiers/",
            "/api/products/promos/",
            "/api/products/merch-tiles/?placement=main",
            "/api/products/home-sections/?location=home",
            "/api/products/nav-links/",
            "/api/content/privacy/",
            "/api/content/background-music/",
        ]:
            with self.subTest(url=url):
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                response.json()
        listed = client.get("/api/products/").json()
        items = listed["results"] if isinstance(listed, dict) else listed
        self.assertEqual(items[0]["category"], "Shoes")
        self.assertEqual(items[0]["price"], "10.00")
