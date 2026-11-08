"""Public HTML pages for the Google Play listing.

Play asks for a privacy policy URL and an account-deletion URL: deleting an
account must also be possible outside the app.
"""

import re

from django.core.cache import cache
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .models import PrivacyPolicy

DELETE_ATTEMPTS_PER_HOUR = 10


def policy_blocks(content):
    """Dashboard plain text -> blocks: blank line = paragraph, "## " = heading, "- " = bullet."""
    blocks = []
    paragraph = []
    bullets = []

    def flush_paragraph():
        if paragraph:
            blocks.append({"kind": "p", "text": " ".join(paragraph)})
            paragraph.clear()

    def flush_bullets():
        if bullets:
            blocks.append({"kind": "ul", "items": list(bullets)})
            bullets.clear()

    for chunk in re.split(r"\n\s*\n", (content or "").strip()):
        for line in (line.strip() for line in chunk.splitlines()):
            if not line:
                continue
            if line.startswith("## "):
                flush_paragraph()
                flush_bullets()
                blocks.append({"kind": "h2", "text": line[3:].strip()})
            elif line.startswith("- "):
                flush_paragraph()
                bullets.append(line[2:].strip())
            else:
                flush_bullets()
                paragraph.append(line)
        flush_paragraph()
        flush_bullets()
    return blocks


@require_GET
def privacy_page(request):
    policy = PrivacyPolicy.load()
    return render(
        request,
        "sitecontent/privacy.html",
        {"policy": policy, "blocks": policy_blocks(policy.content)},
    )


@csrf_protect
@require_http_methods(["GET", "HEAD", "POST"])
def account_deletion_page(request):
    """Sign in with e-mail or phone + password and delete the account."""
    from users.services import StaffAccountError, authenticate_identifier, delete_user_account
    from users.views import _client_ip

    context = {"deleted": False, "error": None, "identifier": ""}
    if request.method == "POST":
        identifier = (request.POST.get("identifier") or "").strip()
        password = request.POST.get("password") or ""
        context["identifier"] = identifier
        key = f"web-delete:{_client_ip(request)}"
        attempts = cache.get(key, 0)
        if attempts >= DELETE_ATTEMPTS_PER_HOUR:
            context["error"] = "Too many attempts. Please try again in an hour."
        elif request.POST.get("confirm") != "yes":
            context["error"] = "Tick the box to confirm you want to delete your account."
        else:
            user = authenticate_identifier(request, identifier, password)
            if user is None:
                cache.set(key, attempts + 1, 3600)
                context["error"] = "Incorrect e-mail/phone number or password."
            else:
                try:
                    delete_user_account(user)
                    context = {"deleted": True, "error": None, "identifier": ""}
                except StaffAccountError:
                    context["error"] = "Staff accounts must be removed by an administrator."
    return render(request, "sitecontent/account_deletion.html", context)
