from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import SocialLoginView
from dj_rest_auth.views import LoginView
from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework import permissions, status
from rest_framework.generics import (
    GenericAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.response import Response
from rest_framework.viewsets import ReadOnlyModelViewSet

from users.models import Address, PhoneNumber, Profile
from users.permissions import IsUserAddressOwner, IsUserProfileOwner
from users.serializers import (
    AddressReadOnlySerializer,
    ProfileSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    OtpRequestSerializer,
    OtpVerifySerializer,
    UserSerializer,
    UserUpdateSerializer,
)

User = get_user_model()


class UserRegisterationAPIView(GenericAPIView):
    """
    Create an account and sign in straight away (no code). Needs an e-mail or
    a Ghana phone number (or both) and a password. E-mail accounts then sign
    in with their password, phone accounts with an SMS code.
    """

    authentication_classes = []
    permission_classes = (permissions.AllowAny,)
    serializer_class = UserRegistrationSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        user = serializer.save()
        return _signed_in_response(request, user, status.HTTP_201_CREATED)


class UserLoginAPIView(LoginView):
    """
    Authenticate existing users using phone number or email and password.
    """

    serializer_class = UserLoginSerializer


class GoogleLogin(SocialLoginView):
    """
    Social authentication with Google
    """

    adapter_class = GoogleOAuth2Adapter
    callback_url = "call_back_url"
    client_class = OAuth2Client


class ProfileAPIView(RetrieveUpdateAPIView):
    """
    Get, Update user profile
    """

    queryset = Profile.objects.all()
    serializer_class = ProfileSerializer
    permission_classes = (IsUserProfileOwner,)

    def get_object(self):
        profile, _ = Profile.objects.get_or_create(user=self.request.user)
        return profile


class UserAPIView(RetrieveUpdateAPIView):
    """
    Get the signed-in user, or PATCH names / e-mail / phone number.
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self):
        return self.request.user

    def patch(self, request, *args, **kwargs):
        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return _invalid(serializer)
        user = serializer.save()
        return Response(UserSerializer(User.objects.get(pk=user.pk)).data)


class AddressViewSet(ReadOnlyModelViewSet):
    """
    List and Retrieve user addresses
    """

    queryset = Address.objects.all()
    serializer_class = AddressReadOnlySerializer
    permission_classes = (IsUserAddressOwner,)

    def get_queryset(self):
        res = super().get_queryset()
        user = self.request.user
        return res.filter(user=user)


class DeleteAccountAPIView(GenericAPIView):
    """
    Delete the signed-in user's account (required by Google Play).

    Personal data (name, email, phone, addresses, profile, carts) is erased and
    the account is deactivated. Paid orders are kept, anonymised, for accounting.
    """

    permission_classes = (permissions.IsAuthenticated,)

    def post(self, request, *args, **kwargs):
        from allauth.account.models import EmailAddress
        from allauth.socialaccount.models import SocialAccount
        from django.db import transaction
        from rest_framework.authtoken.models import Token

        from orders.models import Order

        user = request.user
        password = request.data.get("password") or ""
        if user.has_usable_password() and not user.check_password(password):
            return Response(
                {"detail": _("Incorrect password.")}, status=status.HTTP_400_BAD_REQUEST
            )
        if user.is_staff or user.is_superuser:
            return Response(
                {"detail": _("Staff accounts must be removed by an administrator.")},
                status=status.HTTP_403_FORBIDDEN,
            )

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

        response = Response({"detail": _("Your account has been deleted.")})
        response.delete_cookie(settings.JWT_AUTH_COOKIE)
        response.delete_cookie(settings.JWT_AUTH_REFRESH_COOKIE)
        return response


def _client_ip(request):
    # Render appends the real client address as the LAST X-Forwarded-For entry;
    # earlier entries are client-supplied and can be spoofed.
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[-1].strip()
    return request.META.get("REMOTE_ADDR", "")


def _user_for_phone(phone):
    return (
        User.objects.filter(phone__phone_number=phone, is_active=True)
        .select_related("phone")
        .first()
    )


def _signed_in_response(request, user, status_code):
    """JWT pair + user, like the e-mail login, with the auth cookies set."""
    from dj_rest_auth.jwt_auth import set_jwt_cookies
    from dj_rest_auth.utils import jwt_encode

    access, refresh = jwt_encode(user)
    response = Response(
        {
            "access": str(access),
            "refresh": str(refresh),
            "user": UserSerializer(user).data,
        },
        status=status_code,
    )
    set_jwt_cookies(response, access, refresh)
    return response


def _invalid(serializer):
    """400 with a single readable `detail` plus the per-field `errors`."""
    errors = serializer.errors
    first = next(iter(errors.values()), [""])
    detail = first[0] if isinstance(first, list) and first else str(first)
    return Response({"detail": str(detail), "errors": errors}, status=status.HTTP_400_BAD_REQUEST)


def _too_many(exc):
    response = Response(
        {"detail": str(exc), "retry_after": exc.retry_after},
        status=status.HTTP_429_TOO_MANY_REQUESTS,
    )
    response["Retry-After"] = str(exc.retry_after)
    return response


class OtpRequestAPIView(GenericAPIView):
    """
    Send a 6-digit sign-in code by SMS to an existing account's number.
    """

    authentication_classes = []
    permission_classes = (permissions.AllowAny,)
    serializer_class = OtpRequestSerializer

    def post(self, request, *args, **kwargs):
        from users import otp

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        phone = serializer.validated_data["phone_number"]
        purpose = otp.PURPOSE_LOGIN

        if _user_for_phone(phone) is None:
            return Response(
                {
                    "detail": _("No account found with this number. Create an account first."),
                    "code": "not_registered",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            otp.enforce_send_limits(phone, purpose, _client_ip(request))
            otp.create_and_send_otp(phone, purpose)
        except otp.TooManyRequests as exc:
            return _too_many(exc)
        except (otp.SmsNotConfiguredError, otp.SmsDeliveryError):
            return Response(
                {"detail": _("We could not send the SMS right now. Please try again later.")},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                "detail": _("Code sent."),
                "phone_number": phone,
                "expires_in": settings.OTP_EXPIRE_MINUTES * 60,
                "resend_in": settings.OTP_RESEND_COOLDOWN_SECONDS,
            }
        )


class OtpVerifyAPIView(GenericAPIView):
    """
    Check the SMS code and sign the user in.
    """

    authentication_classes = []
    permission_classes = (permissions.AllowAny,)
    serializer_class = OtpVerifySerializer

    def post(self, request, *args, **kwargs):
        from users import otp

        serializer = self.get_serializer(data=request.data)
        if not serializer.is_valid():
            return _invalid(serializer)
        phone = serializer.validated_data["phone_number"]
        code = serializer.validated_data["code"]

        user = _user_for_phone(phone)
        if user is None:
            return Response(
                {"detail": _("No account found with this number. Create an account first."), "code": "not_registered"},
                status=status.HTTP_404_NOT_FOUND,
            )

        try:
            otp.verify_otp(phone, otp.PURPOSE_LOGIN, code)
        except otp.TooManyRequests as exc:
            return _too_many(exc)
        except otp.OtpVerificationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not user.phone.is_verified:
            # Receiving the code proves the number belongs to this user.
            user.phone.is_verified = True
            user.phone.save(update_fields=["is_verified", "updated_at"])
        return _signed_in_response(request, user, status.HTTP_200_OK)
