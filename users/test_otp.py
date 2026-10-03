from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APIClient

from users import otp
from users.models import OtpCode, PhoneNumber

User = get_user_model()

PASSWORD = "Tamaade-Pass-2026"

OTP_SETTINGS = dict(
    OTP_SMS_PROVIDER="hubtel",
    HUBTEL_SMS_CLIENT_ID="cid",
    HUBTEL_SMS_CLIENT_SECRET="secret",
    HUBTEL_SMS_SENDER_ID="Tamaade",
    OTP_REVIEW_PHONE="",
    OTP_REVIEW_CODE="",
)


class PhoneHelperTests(SimpleTestCase):
    def test_normalize_ghana_phone(self):
        for raw in ("0241234567", "024 123 4567", "+233241234567", "233241234567", "00233241234567"):
            self.assertEqual(otp.normalize_ghana_phone(raw), "+233241234567")

    def test_valid_mobile(self):
        self.assertTrue(otp.is_valid_ghana_mobile("0551234567"))
        self.assertFalse(otp.is_valid_ghana_mobile("0141234567"))
        self.assertFalse(otp.is_valid_ghana_mobile("02412345"))
        self.assertFalse(otp.is_valid_ghana_mobile(""))


def _password_login(email, password=PASSWORD):
    return APIClient().post("/api/user/login/", {"email": email, "password": password}, format="json")


class RegisterTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def _register(self, **fields):
        body = {"first_name": "Kofi", "last_name": "Mensah", "password": PASSWORD, **fields}
        return self.client.post("/api/user/register/", body, format="json")

    def test_register_with_phone_only_signs_in_without_code(self):
        with patch("users.otp.send_sms") as send:
            response = self._register(phone_number="024 123 4567")
        send.assert_not_called()
        self.assertEqual(response.status_code, 201, response.json())
        data = response.json()
        self.assertTrue(data["access"])
        self.assertEqual(data["user"]["phone_number"], "+233241234567")
        me = self.client.get("/api/user/", HTTP_AUTHORIZATION=f"Bearer {data['access']}")
        self.assertEqual(me.status_code, 200)
        user = User.objects.get(phone__phone_number="+233241234567")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertEqual(user.email, "")

    def test_register_with_email_only_then_login_with_password(self):
        response = self._register(email="Kofi@Test.com")
        self.assertEqual(response.status_code, 201, response.json())
        self.assertEqual(response.json()["user"]["phone_number"], None)
        self.assertEqual(_password_login("kofi@test.com").status_code, 200)
        self.assertIn(_password_login("kofi@test.com", "wrong").status_code, (400, 401))

    def test_register_with_both(self):
        response = self._register(email="k@test.com", phone_number="0551234567")
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(email="k@test.com")
        self.assertEqual(user.phone.phone_number.as_e164, "+233551234567")

    def test_requires_email_or_phone(self):
        response = self._register(email="", phone_number="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email or a phone", response.json()["detail"])

    def test_rejects_weak_password_invalid_phone_and_duplicates(self):
        weak = self._register(email="a@test.com", password="123")
        self.assertIn("password", weak.json()["errors"])
        bad_phone = self._register(phone_number="12345")
        self.assertIn("phone_number", bad_phone.json()["errors"])
        self._register(email="dup@test.com", phone_number="0241234567")
        dup_email = self._register(email="DUP@test.com")
        self.assertIn("email", dup_email.json()["errors"])
        dup_phone = self._register(phone_number="+233241234567")
        self.assertIn("phone_number", dup_phone.json()["errors"])
        self.assertEqual(User.objects.count(), 1)


@override_settings(**OTP_SETTINGS)
class OtpLoginTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.sent = []
        patcher = patch("users.otp.send_sms", side_effect=lambda phone, msg: self.sent.append((phone, msg)) or "hubtel")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _code(self):
        return self.sent[-1][1].split("code is ")[1][:6]

    def _request(self, phone="0241234567"):
        return self.client.post("/api/user/otp/request/", {"phone_number": phone}, format="json")

    def _verify(self, code, phone="0241234567"):
        return self.client.post("/api/user/otp/verify/", {"phone_number": phone, "code": code}, format="json")

    def _user(self, phone="+233241234567"):
        user = User.objects.create_user(username="ama", email="ama@test.com", password=PASSWORD, first_name="Ama")
        PhoneNumber.objects.create(user=user, phone_number=phone, is_verified=False)
        return user

    def test_login_with_code(self):
        user = self._user()
        response = self._request()
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["phone_number"], "+233241234567")
        self.assertEqual(self.sent[0][0], "+233241234567")
        self.assertNotIn(self._code(), OtpCode.objects.get().code_hash)

        response = self._verify(self._code())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["id"], user.id)
        self.assertTrue(response.json()["access"])
        user.phone.refresh_from_db()
        self.assertTrue(user.phone.is_verified)

    def test_registered_phone_account_can_login_with_code(self):
        reg = self.client.post(
            "/api/user/register/",
            {"first_name": "Kofi", "last_name": "M", "password": PASSWORD, "phone_number": "0241234567"},
            format="json",
        )
        self.assertEqual(reg.status_code, 201)
        self.assertEqual(self.sent, [])
        self._request()
        self.assertEqual(self._verify(self._code()).status_code, 200)

    def test_unknown_number(self):
        response = self._request()
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["code"], "not_registered")
        self.assertEqual(self.sent, [])

    def test_invalid_phone(self):
        response = self._request(phone="12345")
        self.assertEqual(response.status_code, 400)
        self.assertIn("Ghana", response.json()["detail"])

    def test_wrong_code_then_too_many_attempts(self):
        self._user()
        self._request()
        good = self._code()
        wrong = "000000" if good != "000000" else "111111"
        for _ in range(4):
            self.assertEqual(self._verify(wrong).status_code, 400)
        self.assertIn("Too many attempts", self._verify(wrong).json()["detail"])
        self.assertEqual(self._verify(good).status_code, 400)
        self.assertEqual(OtpCode.objects.get().attempts, 5)

    def test_code_is_single_use_and_new_request_invalidates_old(self):
        self._user()
        self._request()
        first = self._code()
        cache.clear()  # skip the resend cooldown
        self._request()
        second = self._code()
        if first != second:
            self.assertEqual(self._verify(first).status_code, 400)
        self.assertEqual(self._verify(second).status_code, 200)
        self.assertEqual(self._verify(second).status_code, 400)

    def test_expired_code(self):
        self._user()
        self._request()
        OtpCode.objects.update(expires_at="2000-01-01T00:00:00Z")
        response = self._verify(self._code())
        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", response.json()["detail"])

    def test_resend_cooldown(self):
        self._user()
        self.assertEqual(self._request().status_code, 200)
        response = self._request()
        self.assertEqual(response.status_code, 429)
        self.assertGreater(response.json()["retry_after"], 0)
        self.assertEqual(len(self.sent), 1)

    @override_settings(OTP_VERIFY_FAIL_MAX=3)
    def test_verify_lockout(self):
        self._user()
        self._request()
        for _ in range(3):
            self._verify("999999" if self._code() != "999999" else "888888")
        self.assertEqual(self._verify(self._code()).status_code, 429)

    @override_settings(OTP_REVIEW_PHONE="0200000000", OTP_REVIEW_CODE="123456")
    def test_play_review_number_uses_fixed_code_without_sms(self):
        self._user(phone="+233200000000")
        self.assertEqual(self._request(phone="0200000000").status_code, 200)
        self.assertEqual(self.sent, [])
        self.assertEqual(self._verify("123456", phone="0200000000").status_code, 200)

    def test_sms_failure_returns_503(self):
        self._user()
        with patch("users.otp.send_sms", side_effect=otp.SmsDeliveryError("rejected")):
            response = self._request()
        self.assertEqual(response.status_code, 503)

    def test_delete_account_requires_password(self):
        self._user()
        self._request()
        access = self._verify(self._code()).json()["access"]
        auth = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
        self.assertEqual(self.client.post("/api/user/delete-account/", {}, format="json", **auth).status_code, 400)
        ok = self.client.post("/api/user/delete-account/", {"password": PASSWORD}, format="json", **auth)
        self.assertEqual(ok.status_code, 200)


@override_settings(**OTP_SETTINGS)
class UpdateContactTests(TestCase):
    """Adding an e-mail or phone later enables that sign-in method too."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.sent = []
        patcher = patch("users.otp.send_sms", side_effect=lambda phone, msg: self.sent.append((phone, msg)) or "hubtel")
        patcher.start()
        self.addCleanup(patcher.stop)

    def _register(self, **fields):
        body = {"first_name": "Kofi", "last_name": "Mensah", "password": PASSWORD, **fields}
        data = self.client.post("/api/user/register/", body, format="json").json()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {data['access']}")

    def _patch(self, **fields):
        return self.client.patch("/api/user/", fields, format="json")

    def _otp_login(self, phone):
        anon = APIClient()
        self.assertEqual(anon.post("/api/user/otp/request/", {"phone_number": phone}, format="json").status_code, 200)
        code = self.sent[-1][1].split("code is ")[1][:6]
        return anon.post("/api/user/otp/verify/", {"phone_number": phone, "code": code}, format="json")

    def test_email_account_adds_phone_then_logs_in_both_ways(self):
        self._register(email="kofi@test.com")
        response = self._patch(phone_number="0241234567")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["phone_number"], "+233241234567")
        self.assertEqual(self._otp_login("0241234567").status_code, 200)
        self.assertEqual(_password_login("kofi@test.com").status_code, 200)

    def test_phone_account_adds_email_then_logs_in_both_ways(self):
        self._register(phone_number="0241234567")
        response = self._patch(email="Kofi@Test.com", first_name="Kwame")
        self.assertEqual(response.status_code, 200, response.json())
        self.assertEqual(response.json()["email"], "kofi@test.com")
        self.assertEqual(response.json()["first_name"], "Kwame")
        self.assertEqual(_password_login("kofi@test.com").status_code, 200)
        self.assertEqual(self._otp_login("0241234567").status_code, 200)

    def test_changing_phone_moves_otp_login_to_new_number(self):
        self._register(email="kofi@test.com", phone_number="0241234567")
        self._patch(phone_number="0551234567")
        self.assertEqual(APIClient().post("/api/user/otp/request/", {"phone_number": "0241234567"}, format="json").status_code, 404)
        self.assertEqual(self._otp_login("0551234567").status_code, 200)

    def test_cannot_remove_both_or_take_someone_elses(self):
        other = User.objects.create_user(username="o", email="taken@test.com", password="x")
        PhoneNumber.objects.create(user=other, phone_number="+233201234567")
        self._register(email="kofi@test.com")
        self.assertIn("email", self._patch(email="TAKEN@test.com").json()["errors"])
        self.assertIn("phone_number", self._patch(phone_number="0201234567").json()["errors"])
        self.assertIn("phone_number", self._patch(phone_number="123").json()["errors"])
        response = self._patch(email="")
        self.assertEqual(response.status_code, 400)
        self.assertIn("email or a phone", response.json()["detail"])

    def test_removing_phone_when_email_exists(self):
        self._register(email="kofi@test.com", phone_number="0241234567")
        response = self._patch(phone_number="")
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["phone_number"])
        self.assertFalse(PhoneNumber.objects.exists())


@override_settings(**OTP_SETTINGS)
class HubtelSmsTests(SimpleTestCase):
    @patch("users.otp.requests.get")
    def test_sends_get_with_query_credentials(self, mock_get):
        mock_get.return_value = Mock(status_code=201, json=lambda: {"status": 0, "data": {"messageId": "m1"}})
        self.assertEqual(otp.send_sms("0241234567", "hello"), "hubtel")
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["to"], "233241234567")
        self.assertEqual(params["from"], "Tamaade")
        self.assertEqual(params["clientid"], "cid")

    @patch("users.otp.requests.get")
    def test_rejected_status_raises(self, mock_get):
        mock_get.return_value = Mock(status_code=200, json=lambda: {"status": 1, "message": "Invalid sender"}, text="x")
        with self.assertRaises(otp.SmsDeliveryError):
            otp.send_sms("0241234567", "hello")

    @override_settings(HUBTEL_SMS_CLIENT_ID="")
    def test_missing_credentials(self):
        with self.assertRaises(otp.SmsNotConfiguredError):
            otp.send_sms("0241234567", "hello")
