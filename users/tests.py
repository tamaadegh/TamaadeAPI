from datetime import timedelta

from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

User = get_user_model()


class AuthApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="buyer",
            email="buyer@test.com",
            password="BuyerPass123!",
            first_name="Ama",
            last_name="Buyer",
        )
        EmailAddress.objects.create(
            user=self.user,
            email=self.user.email,
            verified=True,
            primary=True,
        )

    def test_login_with_email(self):
        response = self.client.post(
            "/api/user/login/",
            {"email": "buyer@test.com", "password": "BuyerPass123!"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        token = response.json().get("access") or response.json().get("access_token")
        self.assertTrue(token)

    def test_login_rejects_bad_password(self):
        response = self.client.post(
            "/api/user/login/",
            {"email": "buyer@test.com", "password": "wrong"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_current_user_requires_auth(self):
        response = self.client.get("/api/user/")
        self.assertIn(response.status_code, (401, 403))

    def test_current_user_after_login(self):
        login = self.client.post(
            "/api/user/login/",
            {"email": "buyer@test.com", "password": "BuyerPass123!"},
            format="json",
        )
        token = login.json().get("access") or login.json().get("access_token")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/user/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["email"], "buyer@test.com")
        self.assertIsNone(response.json()["phone_number"])

    def test_profile_get_recreates_missing_profile(self):
        self.user.profile.delete()
        login = self.client.post(
            "/api/user/login/",
            {"email": "buyer@test.com", "password": "BuyerPass123!"},
            format="json",
        )
        token = login.json().get("access") or login.json().get("access_token")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = self.client.get("/api/user/profile/")
        self.assertEqual(response.status_code, 200)

    def test_access_token_lasts_several_hours(self):
        response = self.client.post(
            "/api/user/login/",
            {"email": "buyer@test.com", "password": "BuyerPass123!"},
            format="json",
        )
        token = response.json().get("access") or response.json().get("access_token")
        remaining = AccessToken(token)["exp"] - timezone.now().timestamp()
        self.assertGreaterEqual(remaining, timedelta(hours=8).total_seconds())


class DeleteAccountTests(TestCase):
    def setUp(self):
        from allauth.account.models import EmailAddress
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.user = User.objects.create_user(
            username="del@test.com", email="del@test.com", password="DelPass123!",
            first_name="Ama", last_name="Mensah",
        )
        EmailAddress.objects.create(user=self.user, email=self.user.email, verified=True, primary=True)
        login = self.client.post("/api/user/login/", {"email": "del@test.com", "password": "DelPass123!"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json().get('access') or login.json().get('access_token')}")

    def test_requires_correct_password(self):
        response = self.client.post("/api/user/delete-account/", {"password": "wrong"}, format="json")
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_active)

    def test_anonymises_and_deactivates(self):
        from users.models import Profile

        response = self.client.post("/api/user/delete-account/", {"password": "DelPass123!"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_active)
        self.assertNotIn("del@test.com", self.user.email)
        self.assertEqual(self.user.first_name, "Deleted")
        self.assertFalse(Profile.objects.filter(user=self.user).exists())
        relogin = APIClient().post("/api/user/login/", {"email": "del@test.com", "password": "DelPass123!"}, format="json")
        self.assertIn(relogin.status_code, (400, 401))
