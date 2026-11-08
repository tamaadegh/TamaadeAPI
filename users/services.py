"""Account operations shared by the API and the public web pages."""

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction

User = get_user_model()


class StaffAccountError(Exception):
    """Staff and superuser accounts are never self-deleted."""


def delete_user_account(user):
    """
    Erase the user's personal data and deactivate the account (Google Play
    account-deletion requirement). Paid orders are kept, anonymised, for accounting.
    """
    from allauth.account.models import EmailAddress
    from allauth.socialaccount.models import SocialAccount
    from rest_framework.authtoken.models import Token

    from orders.models import Order
    from users.models import Address, PhoneNumber, Profile

    if user.is_staff or user.is_superuser:
        raise StaffAccountError()

    with transaction.atomic():
        Order.objects.filter(buyer=user, status=Order.PENDING).delete()
        Address.objects.filter(user=user).delete()
        PhoneNumber.objects.filter(user=user).delete()
        EmailAddress.objects.filter(user=user).delete()
        SocialAccount.objects.filter(user=user).delete()
        Token.objects.filter(user=user).delete()
        anon = f"deleted-{user.pk}"
        user.username = anon
        user.email = f"{anon}@deleted.tamaade.invalid"
        user.first_name = "Deleted"
        user.last_name = "User"
        user.is_active = False
        user.set_unusable_password()
        user.save()
        # After save: the post_save signal would recreate the profile.
        Profile.objects.filter(user=user).delete()


def authenticate_identifier(request, identifier, password):
    """Check an e-mail or Ghana phone number + password; returns the active user or None."""
    from users.otp import normalize_ghana_phone

    identifier = (identifier or "").strip()
    if not identifier or not password:
        return None
    username = identifier.lower() if "@" in identifier else normalize_ghana_phone(identifier)
    if not username:
        return None
    user = authenticate(request, username=username, password=password)
    if user is None or not user.is_active:
        return None
    return user
