"""Phone-number OTP sign-in (ported from the UrbanAfrica/Trotro backend).

A 6-digit code is generated here, stored only as a keyed hash with a TTL, and
delivered by SMS through Hubtel. The SMS provider is just the channel, never
the source of truth for the code.

Every code is a paid SMS and the request endpoint is public, so sends are
throttled in layers (per phone + purpose, per phone per day, per IP, global
breaker) and wrong codes lock a phone out for a while. A blocked request never
sends anything nor invalidates the code the user is already waiting for.
"""

import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import timedelta

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

HUBTEL_SMS_SEND_URL = "https://sms.hubtel.com/v1/messages/send"

GHANA_E164_MOBILE_RE = re.compile(r"^\+233[235]\d{8}$")
OTP_CODE_RE = re.compile(r"^\d{6}$")

PURPOSE_LOGIN = "login"


class SmsNotConfiguredError(RuntimeError):
    """Server-side SMS is not set up (missing provider/credentials)."""


class SmsDeliveryError(RuntimeError):
    """The SMS provider refused or could not deliver the message."""


class OtpVerificationError(Exception):
    """User-safe message for any wrong/expired/exhausted code."""


class TooManyRequests(Exception):
    def __init__(self, retry_after, message):
        super().__init__(message)
        self.retry_after = max(1, int(retry_after + 0.999))


# ------------------------------------------------------------------ phones ---


def normalize_ghana_phone(phone):
    """'024 123 4567', '+233241234567', '00233…' -> '+233241234567' (or '')."""
    digits = re.sub(r"\D", "", str(phone or "").strip())
    if not digits:
        return ""
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("233"):
        return f"+{digits}"
    if digits.startswith("0"):
        digits = digits[1:]
    return f"+233{digits}"


def is_valid_ghana_mobile(phone):
    return bool(GHANA_E164_MOBILE_RE.match(normalize_ghana_phone(phone)))


def mask_phone(phone):
    return f"{phone[:6]}***{phone[-2:]}" if len(phone) > 8 else "***"


# --------------------------------------------------------------------- SMS ---


def send_sms(phone, message):
    """Send one SMS. Returns the provider name that handled it."""
    provider = (settings.OTP_SMS_PROVIDER or "").strip().lower()

    if provider == "log":
        # Sandbox only: refused when DEBUG is off (see request_otp).
        logger.warning("sms.sandbox_delivery phone=%s message=%s", phone, message)
        return "log"

    if provider == "hubtel":
        client_id = (settings.HUBTEL_SMS_CLIENT_ID or "").strip()
        client_secret = (settings.HUBTEL_SMS_CLIENT_SECRET or "").strip()
        if not client_id or not client_secret:
            raise SmsNotConfiguredError("HUBTEL_SMS_CLIENT_ID/HUBTEL_SMS_CLIENT_SECRET are not set")
        reference = f"tamaade-sms-{secrets.token_hex(8)}"
        # Hubtel's SMS v1 API takes the credentials as query params on a GET;
        # a POST with Basic Auth is rejected with HTTP 415.
        params = {
            "clientid": client_id,
            "clientsecret": client_secret,
            "from": settings.HUBTEL_SMS_SENDER_ID,
            "to": normalize_ghana_phone(phone).lstrip("+"),
            "content": message,
            "clientreference": reference,
        }
        try:
            response = requests.get(HUBTEL_SMS_SEND_URL, params=params, timeout=15)
        except requests.RequestException as exc:
            logger.error("sms.hubtel_request_failed phone=%s error=%s", mask_phone(phone), exc)
            raise SmsDeliveryError("Could not reach the SMS provider") from exc
        if response.status_code >= 400:
            logger.error(
                "sms.hubtel_send_failed phone=%s status=%s body=%s",
                mask_phone(phone), response.status_code, response.text[:300],
            )
            raise SmsDeliveryError("The SMS provider rejected the request")
        # A 2xx alone is not success: Hubtel answers status=0 when accepted and
        # a non-zero status for e.g. an unapproved sender ID or no balance.
        try:
            body = response.json()
        except ValueError:
            body = None
        if isinstance(body, dict) and body.get("status", 0) != 0:
            logger.error("sms.hubtel_send_rejected phone=%s body=%s", mask_phone(phone), response.text[:300])
            raise SmsDeliveryError("The SMS provider rejected the message")
        message_id = ((body or {}).get("data") or {}).get("messageId", "") if isinstance(body, dict) else ""
        logger.info(
            "sms.hubtel_send_queued phone=%s reference=%s message_id=%s",
            mask_phone(phone), reference, message_id or "unknown",
        )
        return "hubtel"

    raise SmsNotConfiguredError("No SMS provider configured (OTP_SMS_PROVIDER)")


# ------------------------------------------------------------- rate limits ---


def _hits(key, window, now):
    return [t for t in cache.get(key, []) if now - t < window]


def _check_and_record(rules):
    """rules: [(key, limit, window_seconds, kind)]. All-or-nothing: if any rule
    is full nothing is recorded. Raises TooManyRequests."""
    now = time.time()
    worst, worst_kind = 0.0, ""
    current = {}
    for key, limit, window, kind in rules:
        hits = _hits(key, window, now)
        current[key] = hits
        if len(hits) >= limit:
            wait = hits[len(hits) - limit] + window - now
            if wait > worst:
                worst, worst_kind = wait, kind
    if worst > 0:
        raise TooManyRequests(worst, _send_limit_message(worst_kind, worst))
    for key, limit, window, kind in rules:
        cache.set(key, current[key] + [now], window)


def _human_wait(seconds):
    seconds = max(1, int(seconds + 0.999))
    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''}"
    minutes = (seconds + 59) // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours = (minutes + 59) // 60
    return f"{hours} hour{'s' if hours != 1 else ''}"


def _send_limit_message(kind, wait):
    when = _human_wait(wait)
    if kind == "cooldown":
        return f"Your code is on its way. Wait {when} before asking for another one."
    if kind == "global":
        return f"The service is busy. Please try again in {when}."
    return f"Too many code requests. Please try again in {when}."


def enforce_send_limits(phone, purpose, ip):
    if not settings.OTP_RATE_LIMIT_ENABLED:
        return
    day = 86_400
    rules = [
        (f"otp:cooldown:{purpose}:{phone}", 1, settings.OTP_RESEND_COOLDOWN_SECONDS, "cooldown"),
        (f"otp:phone-short:{purpose}:{phone}", settings.OTP_PHONE_SHORT_MAX, 900, "phone"),
        (f"otp:phone-day:{phone}", settings.OTP_PHONE_DAILY_MAX, day, "phone"),
    ]
    if ip:
        rules += [
            (f"otp:ip-hour:{ip}", settings.OTP_IP_HOURLY_MAX, 3600, "ip"),
            (f"otp:ip-day:{ip}", settings.OTP_IP_DAILY_MAX, day, "ip"),
        ]
    rules += [
        ("otp:global-hour", settings.OTP_GLOBAL_HOURLY_MAX, 3600, "global"),
        ("otp:global-day", settings.OTP_GLOBAL_DAILY_MAX, day, "global"),
    ]
    try:
        _check_and_record([r for r in rules if r[1] > 0])
    except TooManyRequests:
        logger.warning("otp.send_blocked phone=%s purpose=%s", mask_phone(phone), purpose)
        raise


def _verify_fail_key(phone):
    return f"otp:verify-fail:{phone}"


def enforce_verify_allowed(phone):
    if not settings.OTP_RATE_LIMIT_ENABLED:
        return
    window = settings.OTP_VERIFY_LOCKOUT_SECONDS
    hits = _hits(_verify_fail_key(phone), window, time.time())
    if len(hits) >= settings.OTP_VERIFY_FAIL_MAX:
        wait = hits[len(hits) - settings.OTP_VERIFY_FAIL_MAX] + window - time.time()
        raise TooManyRequests(
            wait, f"Too many wrong codes. Wait {_human_wait(wait)}, then request a new code."
        )


def record_verify_failure(phone):
    if not settings.OTP_RATE_LIMIT_ENABLED:
        return
    window = settings.OTP_VERIFY_LOCKOUT_SECONDS
    key = _verify_fail_key(phone)
    cache.set(key, _hits(key, window, time.time()) + [time.time()], window)


# ------------------------------------------------------------------- codes ---


def _hash_code(phone, code):
    """Keyed hash so codes are never stored in plaintext."""
    payload = f"{normalize_ghana_phone(phone)}:{code}".encode()
    return hmac.new(settings.SECRET_KEY.encode(), payload, hashlib.sha256).hexdigest()


def review_fixed_code(phone, purpose):
    """Fixed code for the one Google Play review number (login only), else None.

    Play reviewers need a working sign-in but cannot receive a Ghana SMS.
    """
    configured_phone = (settings.OTP_REVIEW_PHONE or "").strip()
    configured_code = (settings.OTP_REVIEW_CODE or "").strip()
    if purpose != PURPOSE_LOGIN or not configured_phone or not OTP_CODE_RE.match(configured_code):
        return None
    if normalize_ghana_phone(configured_phone) != phone:
        return None
    return configured_code


def create_and_send_otp(phone, purpose):
    """Store a fresh hashed code (invalidating older ones) and SMS it."""
    from users.models import OtpCode

    provider = (settings.OTP_SMS_PROVIDER or "").strip().lower()
    if provider == "log" and not settings.DEBUG:
        raise SmsNotConfiguredError("The 'log' SMS provider is only allowed with DEBUG=True")

    fixed = review_fixed_code(phone, purpose)
    code = fixed or f"{secrets.randbelow(1_000_000):06d}"
    with transaction.atomic():
        OtpCode.objects.filter(phone=phone, purpose=purpose, consumed=False).delete()
        OtpCode.objects.create(
            phone=phone,
            purpose=purpose,
            code_hash=_hash_code(phone, code),
            expires_at=timezone.now() + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
        )
    if fixed:
        # The reviewers already hold the code; nothing is sent.
        logger.info("otp.review_challenge_created phone=%s", mask_phone(phone))
        return
    message = (
        f"Your Tamaade code is {code}. It expires in {settings.OTP_EXPIRE_MINUTES} minutes. "
        "Do not share it with anyone."
    )
    send_sms(phone, message)
    logger.info("otp.sent phone=%s purpose=%s provider=%s", mask_phone(phone), purpose, provider)


def verify_otp(phone, purpose, code):
    """Raise OtpVerificationError/TooManyRequests, or consume the code."""
    enforce_verify_allowed(phone)
    try:
        _verify(phone, purpose, code)
    except OtpVerificationError:
        record_verify_failure(phone)
        raise
    cache.delete(_verify_fail_key(phone))


def _verify(phone, purpose, code):
    from users.models import OtpCode

    if not OTP_CODE_RE.match(code or ""):
        raise OtpVerificationError("Enter the 6-digit code we sent you.")
    # The error is raised after the transaction commits: raising inside it
    # would roll back the attempts counter.
    error = None
    with transaction.atomic():
        challenge = (
            OtpCode.objects.select_for_update()
            .filter(phone=phone, purpose=purpose, consumed=False)
            .order_by("-created_at")
            .first()
        )
        if challenge is None:
            error = "No pending code for this number. Request a new one."
        elif timezone.now() > challenge.expires_at:
            error = "This code has expired. Request a new one."
        elif challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
            error = "Too many attempts. Request a new code."
        else:
            challenge.attempts += 1
            if hmac.compare_digest(_hash_code(phone, code), challenge.code_hash):
                challenge.consumed = True
            elif challenge.attempts >= settings.OTP_MAX_ATTEMPTS:
                error = "Too many attempts. Request a new code."
            else:
                error = "Incorrect code. Check the SMS or tap Resend."
            challenge.save(update_fields=["attempts", "consumed"])
    if error:
        raise OtpVerificationError(error)
