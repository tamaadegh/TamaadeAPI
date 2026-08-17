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

    def test_phone_security_code_expired_without_sent(self):
        from users.models import PhoneNumber

        phone = PhoneNumber(sent=None)
        self.assertTrue(phone.is_security_code_expired())

    def test_access_token_lasts_several_hours(self):
        response = self.client.post(
            "/api/user/login/",
            {"email": "buyer@test.com", "password": "BuyerPass123!"},
            format="json",
        )
        token = response.json().get("access") or response.json().get("access_token")
        remaining = AccessToken(token)["exp"] - timezone.now().timestamp()
        self.assertGreaterEqual(remaining, timedelta(hours=8).total_seconds())
