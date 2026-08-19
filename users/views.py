from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import RegisterView, SocialLoginView
from dj_rest_auth.views import LoginView
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

from dashboard.events import record_event
from dashboard.models import SystemEvent
from users.models import Address, PhoneNumber, Profile
from users.permissions import IsUserAddressOwner, IsUserProfileOwner
from users.serializers import (
    AddressReadOnlySerializer,
    PhoneNumberSerializer,
    ProfileSerializer,
    UserLoginSerializer,
    UserRegistrationSerializer,
    UserSerializer,
    VerifyPhoneNumberSerialzier,
)

User = get_user_model()


class UserRegisterationAPIView(RegisterView):
    """
    Register new users using phone number or email and password.
    """

    serializer_class = UserRegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as exc:
            # Surface why real customers cannot sign up. Never log credentials.
            record_event(
                message="Signup rejected",
                level=SystemEvent.LEVEL_WARNING,
                category=SystemEvent.CAT_SIGNUP,
                detail=str(getattr(serializer, "errors", exc))[:2000],
                reference=str(request.data.get("email") or request.data.get("phone_number") or ""),
            )
            raise

        # dj_rest_auth's perform_create returns the created user; the
        # serializer does not expose it as `.instance`.
        user = self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        email = request.data.get("email", None)
        phone_number = request.data.get("phone_number", None)

        # Previously this re-dispatched SendOrResendSMSAPIView with
        # request._request. DRF had already consumed the request body to build
        # `serializer`, so the second view's access to request.body raised
        # RawPostDataException and every phone signup returned 500 - with the
        # account already created. Call the OTP helper directly instead.
        #
        # Read the number back off the saved record rather than reusing the raw
        # input: PhoneNumberField stores normalised E.164 (+233...), so looking
        # up the "0244..." the customer typed would not match.
        sms_sent = False
        phone_record = getattr(user, "phone", None) if user is not None else None
        if phone_record is not None:
            sms_sent = send_phone_verification(str(phone_record.phone_number))

        if email and sms_sent:
            detail = _("Verification e-mail and SMS sent.")
        elif email:
            detail = _("Account created. Check your e-mail to verify your address.")
        elif sms_sent:
            detail = _("Verification SMS sent.")
        else:
            detail = _("Account created.")

        record_event(
            message="New customer signed up",
            level=SystemEvent.LEVEL_INFO,
            category=SystemEvent.CAT_SIGNUP,
            detail=f"email={email or '-'} phone={phone_number or '-'} sms_sent={sms_sent}",
            reference=str(email or phone_number or ""),
            user=user,
        )

        return Response(
            {"detail": detail}, status=status.HTTP_201_CREATED, headers=headers
        )


class UserLoginAPIView(LoginView):
    """
    Authenticate existing users using phone number or email and password.
    """

    serializer_class = UserLoginSerializer


def send_phone_verification(phone_number):
    """Send an OTP to an unverified number. Returns True only if one went out.

    Shared by registration and the resend endpoint so neither has to re-dispatch
    the other as a view. Never raises: SMS is a notification, and a Twilio
    outage must not fail the request that triggered it.
    """
    try:
        sms_verification = PhoneNumber.objects.filter(
            phone_number=phone_number, is_verified=False
        ).first()
        if sms_verification is None:
            return False
        sent = bool(sms_verification.send_confirmation())
        if not sent:
            record_event(
                message="Verification SMS not sent",
                level=SystemEvent.LEVEL_WARNING,
                category=SystemEvent.CAT_SMS,
                detail="send_confirmation() returned no confirmation - Twilio "
                       "credentials are probably unset.",
                reference=str(phone_number),
            )
        return sent
    except Exception as exc:
        record_event(
            message="Verification SMS failed",
            level=SystemEvent.LEVEL_ERROR,
            category=SystemEvent.CAT_SMS,
            detail=f"{type(exc).__name__}: {exc}",
            reference=str(phone_number),
        )
        return False


class SendOrResendSMSAPIView(GenericAPIView):
    """
    Check if submitted phone number is a valid phone number and send OTP.
    """

    serializer_class = PhoneNumberSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            phone_number = str(serializer.validated_data["phone_number"])
            if not PhoneNumber.objects.filter(
                phone_number=phone_number, is_verified=False
            ).exists():
                return Response(
                    {"detail": _("Phone number is already verified or not found.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            send_phone_verification(phone_number)
            return Response(status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyPhoneNumberAPIView(GenericAPIView):
    """
    Check if submitted phone number and OTP matches and verify the user.
    """

    serializer_class = VerifyPhoneNumberSerialzier

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            message = {"detail": _("Phone number successfully verified.")}
            return Response(message, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


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


class UserAPIView(RetrieveAPIView):
    """
    Get user details
    """

    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = (permissions.IsAuthenticated,)

    def get_object(self):
        return self.request.user


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
