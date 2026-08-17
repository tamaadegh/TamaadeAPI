import base64
import re
from decimal import Decimal, ROUND_HALF_UP

import requests
from django.conf import settings


class HubtelError(Exception):
    def __init__(self, message, status_code=None, body=None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def hubtel_is_configured():
    return bool(
        getattr(settings, "HUBTEL_API_ID", "")
        and getattr(settings, "HUBTEL_API_KEY", "")
        and getattr(settings, "HUBTEL_COLLECTION_ACCOUNT_NUMBER", "")
    )


def _auth_header():
    if not hubtel_is_configured():
        raise HubtelError("Hubtel is not configured")
    token = base64.b64encode(
        f"{settings.HUBTEL_API_ID}:{settings.HUBTEL_API_KEY}".encode()
    ).decode()
    return f"Basic {token}"


def sanitize_description(description):
    cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", description or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return (cleaned or "Tamaade order")[:100]


def hubtel_data(payload):
    if not isinstance(payload, dict):
        return {}
    data = payload.get("data") or payload.get("Data") or {}
    return data if isinstance(data, dict) else {}


def hubtel_response_code(payload):
    if not isinstance(payload, dict):
        return ""
    data = hubtel_data(payload)
    return str(
        payload.get("responseCode")
        or payload.get("ResponseCode")
        or data.get("responseCode")
        or data.get("ResponseCode")
        or ""
    )


def hubtel_error_detail(status_code, body):
    if isinstance(body, dict):
        data = body.get("data") if "data" in body else body.get("Data")
        if isinstance(data, list):
            messages = [
                item.get("errorMessage") or item.get("ErrorMessage")
                for item in data
                if isinstance(item, dict)
            ]
            messages = [str(msg) for msg in messages if msg]
            if messages:
                return "; ".join(messages)
        message = body.get("message") or body.get("Message")
        if message:
            return str(message)
    return f"Hubtel checkout failed ({status_code})"


def initiate_checkout(
    *,
    total_amount,
    description,
    callback_url,
    return_url,
    cancellation_url,
    client_reference,
    payee_name=None,
    payee_mobile_number=None,
    payee_email=None,
):
    collection = settings.HUBTEL_COLLECTION_ACCOUNT_NUMBER
    url = f"{settings.HUBTEL_CHECKOUT_BASE.rstrip('/')}/items/initiate"
    amount = float(Decimal(str(total_amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    payload = {
        "totalAmount": amount,
        "description": sanitize_description(description),
        "callbackUrl": callback_url,
        "returnUrl": return_url,
        "merchantAccountNumber": collection,
        "cancellationUrl": cancellation_url,
        "clientReference": (client_reference or "")[:32],
    }
    if payee_name:
        payload["payeeName"] = payee_name
    if payee_mobile_number:
        payload["payeeMobileNumber"] = payee_mobile_number
    if payee_email:
        payload["payeeEmail"] = payee_email

    try:
        response = requests.post(
            url,
            json=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": _auth_header(),
                "Cache-Control": "no-cache",
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise HubtelError(str(exc)) from exc

    try:
        body = response.json()
    except ValueError:
        body = {"raw_text": response.text[:2000]}

    if response.status_code >= 400:
        raise HubtelError(
            hubtel_error_detail(response.status_code, body),
            status_code=response.status_code,
            body=body,
        )
    return body
