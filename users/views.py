from allauth.socialaccount.providers.google.views import GoogleOAuth2Adapter
from allauth.socialaccount.providers.oauth2.client import OAuth2Client
from dj_rest_auth.registration.views import RegisterView, SocialLoginView
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
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)

        response_data = ""

        email = request.data.get("email", None)
        phone_number = request.data.get("phone_number", None)

        if email and phone_number:
            res = SendOrResendSMSAPIView.as_view()(request._request, *args, **kwargs)

            if res.status_code == 200:
                response_data = {"detail": _("Verification e-mail and SMS sent.")}

        elif email and not phone_number:
            response_data = {"detail": _("Verification e-mail sent.")}

        else:
            res = SendOrResendSMSAPIView.as_view()(request._request, *args, **kwargs)

            if res.status_code == 200:
                response_data = {"detail": _("Verification SMS sent.")}

        return Response(response_data, status=status.HTTP_201_CREATED, headers=headers)


class UserLoginAPIView(LoginView):
    """
    Authenticate existing users using phone number or email and password.
    """

    serializer_class = UserLoginSerializer


class SendOrResendSMSAPIView(GenericAPIView):
    """
    Check if submitted phone number is a valid phone number and send OTP.
    """

    serializer_class = PhoneNumberSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)

        if serializer.is_valid():
            # Send OTP
            phone_number = str(serializer.validated_data["phone_number"])

            user = User.objects.filter(phone__phone_number=phone_number).first()

            sms_verification = PhoneNumber.objects.filter(
                user=user, is_verified=False
            ).first()
            if sms_verification is None:
                return Response(
                    {"detail": _("Phone number is already verified or not found.")},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            sms_verification.send_confirmation()

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
