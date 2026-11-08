from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client, SimpleTestCase, TestCase

from sitecontent.models import PrivacyPolicy
from sitecontent.pages import policy_blocks
from users.models import PhoneNumber

User = get_user_model()

PASSWORD = "Tamaade-Pass-2026"


class PolicyBlocksTests(SimpleTestCase):
    def test_headings_bullets_paragraphs(self):
        blocks = policy_blocks("Intro line\nsecond line\n\n## Data\n- Name\n- Phone\n\nEnd.")
        self.assertEqual(
            blocks,
            [
                {"kind": "p", "text": "Intro line second line"},
                {"kind": "h2", "text": "Data"},
                {"kind": "ul", "items": ["Name", "Phone"]},
                {"kind": "p", "text": "End."},
            ],
        )


class PrivacyPageTests(TestCase):
    def test_renders_policy_escaped(self):
        policy = PrivacyPolicy.load()
        policy.title = "Our Privacy"
        policy.content = "## Who we are\n<script>x</script>"
        policy.save()
        response = Client().get("/privacy/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "<h2>Who we are</h2>", html=True)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>x</script>")


class AccountDeletionPageTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(username="ama", email="ama@test.com", password=PASSWORD)
        PhoneNumber.objects.create(user=self.user, phone_number="+233241234567", is_verified=True)

    def _post(self, **data):
        page = self.client.get("/account/delete/")
        self.assertEqual(page.status_code, 200)
        token = page.cookies["csrftoken"].value if "csrftoken" in page.cookies else page.context["csrf_token"]
        return self.client.post("/account/delete/", {"csrfmiddlewaretoken": str(token), **data})

    def test_delete_with_phone_and_password(self):
        response = self._post(identifier="024 123 4567", password=PASSWORD, confirm="yes")
        self.assertContains(response, "has been deleted")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertFalse(PhoneNumber.objects.exists())

    def test_delete_with_email(self):
        self._post(identifier="AMA@test.com", password=PASSWORD, confirm="yes")
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)

    def test_wrong_password_and_missing_confirmation(self):
        self.assertContains(self._post(identifier="ama@test.com", password="bad", confirm="yes"), "Incorrect")
        self.assertContains(self._post(identifier="ama@test.com", password=PASSWORD), "Tick the box")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_attempts_are_throttled(self):
        for _ in range(10):
            self._post(identifier="ama@test.com", password="bad", confirm="yes")
        response = self._post(identifier="ama@test.com", password=PASSWORD, confirm="yes")
        self.assertContains(response, "Too many attempts")
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_post_without_csrf_is_rejected(self):
        response = self.client.post("/account/delete/", {"identifier": "ama@test.com", "password": PASSWORD, "confirm": "yes"})
        self.assertEqual(response.status_code, 403)
