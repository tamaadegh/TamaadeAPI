from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from users.models import PhoneNumber
from users.test_otp import OTP_SETTINGS, PASSWORD

User = get_user_model()

NEW_PASSWORD = "Fresh-Tamaade-2027"


@override_settings(**OTP_SETTINGS)
class PasswordResetOtpTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.sent = []
        patcher = patch("users.otp.send_sms", side_effect=lambda phone, msg: self.sent.append((phone, msg)) or "hubtel")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = User.objects.create_user(username="ama", email="ama@test.com", password=PASSWORD)
        PhoneNumber.objects.create(user=self.user, phone_number="+233241234567", is_verified=True)

    def _code(self):
        return self.sent[-1][1].split("code is ")[1][:6]

    def _request(self, phone="0241234567"):
        return self.client.post("/api/user/password/reset/otp/request/", {"phone_number": phone}, format="json")

    def _confirm(self, code, password=NEW_PASSWORD, phone="0241234567"):
        return self.client.post(
            "/api/user/password/reset/otp/confirm/",
            {"phone_number": phone, "code": code, "new_password": password},
            format="json",
        )

    def test_reset_sets_password_and_signs_in(self):
        self.assertEqual(self._request().status_code, 200)
        response = self._confirm(self._code())
        self.assertEqual(response.status_code, 200, response.json())
        self.assertTrue(response.json()["access"])
        self.assertTrue(response.json()["refresh"])
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(NEW_PASSWORD))

    def test_login_code_cannot_reset_password(self):
        self.client.post("/api/user/otp/request/", {"phone_number": "0241234567"}, format="json")
        response = self._confirm(self._code())
        self.assertEqual(response.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(PASSWORD))

    def test_weak_password_keeps_the_code(self):
        self._request()
        code = self._code()
        weak = self._confirm(code, password="123")
        self.assertEqual(weak.status_code, 400)
        self.assertIn("new_password", weak.json()["errors"])
        self.assertEqual(self._confirm(code).status_code, 200)

    def test_unknown_number(self):
        response = self._request(phone="0551234567")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_registered")
        self.assertEqual(self.sent, [])


class TokenRefreshTests(TestCase):
    def test_refresh_returns_new_access_token(self):
        User.objects.create_user(username="kofi", email="kofi@test.com", password=PASSWORD)
        client = APIClient()
        login = client.post("/api/user/login/", {"email": "kofi@test.com", "password": PASSWORD}, format="json")
        self.assertEqual(login.status_code, 200)
        refresh = login.json()["refresh_token"]
        self.assertTrue(refresh)

        response = APIClient().post("/api/user/token/refresh/", {"refresh": refresh}, format="json")
        self.assertEqual(response.status_code, 200, response.content)
        access = response.json()["access"]
        me = APIClient()
        me.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        self.assertEqual(me.get("/api/user/").status_code, 200)

    def test_bad_refresh_token(self):
        response = APIClient().post("/api/user/token/refresh/", {"refresh": "nope"}, format="json")
        self.assertEqual(response.status_code, 401)
