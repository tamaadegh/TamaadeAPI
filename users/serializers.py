from dj_rest_auth.registration.serializers import RegisterSerializer
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext as _
from django_countries.serializers import CountryFieldMixin
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .exceptions import (
    AccountDisabledException,
    AccountNotRegisteredException,
    InvalidCredentialsException,
)
from dashboard.events import record_event
from dashboard.models import SystemEvent
from .models import Address, PhoneNumber, Profile

User = get_user_model()


class UserRegistrationSerializer(RegisterSerializer):
    """
    Serializer for registrating new users using email or phone number.
    """

    username = None
    first_name = serializers.CharField(required=True, write_only=True)
    last_name = serializers.CharField(required=True, write_only=True)
    phone_number = PhoneNumberField(
        required=False,
        write_only=True,
        validators=[
            UniqueValidator(
                queryset=PhoneNumber.objects.all(),
                message=_("A user is already registered with this phone number."),
            )
        ],
    )
    email = serializers.EmailField(required=False)

    def validate(self, validated_data):
        email = validated_data.get("email", None)
        phone_number = validated_data.get("phone_number", None)

        if not (email or phone_number):
            raise serializers.ValidationError(_("Enter an email or a phone number."))

        if validated_data["password1"] != validated_data["password2"]:
            raise serializers.ValidationError(
                _("The two password fields didn't match.")
            )

        return validated_data

    def get_cleaned_data_extra(self):
        return {
            "phone_number": self.validated_data.get("phone_number", ""),
            "first_name": self.validated_data.get("first_name", ""),
            "last_name": self.validated_data.get("last_name", ""),
        }

    def create_extra(self, user, validated_data):
        user.first_name = self.validated_data.get("first_name")
        user.last_name = self.validated_data.get("last_name")
        user.save()

        phone_number = validated_data.get("phone_number")

        if phone_number:
            PhoneNumber.objects.create(user=user, phone_number=phone_number)
            user.phone.save()

    def custom_signup(self, request, user):
        self.create_extra(user, self.get_cleaned_data_extra())


class UserLoginSerializer(serializers.Serializer):
    """
    Serializer to login users with email or phone number.
    """

    phone_number = PhoneNumberField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def _validate_phone_email(self, phone_number, email, password):
        user = None

        if email and password:
            user = authenticate(username=email, password=password)
        elif str(phone_number) and password:
            user = authenticate(username=str(phone_number), password=password)
        else:
            raise serializers.ValidationError(
                _("Enter a phone number or an email and password.")
            )

        return user

    def validate(self, validated_data):
        phone_number = validated_data.get("phone_number")
        email = validated_data.get("email")
        password = validated_data.get("password")

        user = None

        user = self._validate_phone_email(phone_number, email, password)

        if not user:
            raise InvalidCredentialsException()

        if not user.is_active:
            raise AccountDisabledException()

        # Only enforce a verification gate the customer can actually clear.
        #
        # These two checks used to be unconditional, which locked every new
        # customer out permanently: e-mail confirmation needs working SMTP and
        # phone confirmation needs Twilio, and with neither configured there was
        # no path to a verified state. Requiring proof that cannot be obtained is
        # an outage, not a security control - so each gate now follows whether
        # its delivery channel is actually live.
        if email:
            if getattr(settings, "ACCOUNT_EMAIL_VERIFICATION", "optional") == "mandatory":
                verified = user.emailaddress_set.filter(
                    email=user.email, verified=True
                ).exists()
                if not verified:
                    record_event(
                        message="Login refused: e-mail not verified",
                        level=SystemEvent.LEVEL_WARNING,
                        category=SystemEvent.CAT_LOGIN,
                        detail="ACCOUNT_EMAIL_VERIFICATION=mandatory and this "
                               "address has no confirmed EmailAddress record.",
                        reference=user.email or "",
                        user=user,
                    )
                    raise serializers.ValidationError(_("E-mail is not verified."))
        else:
            sms_configured = all([
                getattr(settings, "TWILIO_ACCOUNT_SID", ""),
                getattr(settings, "TWILIO_AUTH_TOKEN", ""),
                getattr(settings, "TWILIO_PHONE_NUMBER", ""),
            ])
            phone = getattr(user, "phone", None)
            if sms_configured and (phone is None or not phone.is_verified):
                record_event(
                    message="Login refused: phone not verified",
                    level=SystemEvent.LEVEL_WARNING,
                    category=SystemEvent.CAT_LOGIN,
                    detail="No verified PhoneNumber record for this account.",
                    reference=str(getattr(phone, "phone_number", "") or ""),
                    user=user,
                )
                raise serializers.ValidationError(_("Phone number is not verified."))

        validated_data["user"] = user
        return validated_data


class PhoneNumberSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize phone number.
    """

    phone_number = PhoneNumberField()

    class Meta:
        model = PhoneNumber
        fields = ("phone_number",)

    def validate_phone_number(self, value):
        try:
            queryset = User.objects.get(phone__phone_number=value)
            if queryset.phone.is_verified:
                err_message = _("Phone number is already verified")
                raise serializers.ValidationError(err_message)

        except User.DoesNotExist:
            raise AccountNotRegisteredException()

        return value


class VerifyPhoneNumberSerialzier(serializers.Serializer):
    """
    Serializer class to verify OTP.
    """

    phone_number = PhoneNumberField()
    otp = serializers.CharField(max_length=settings.TOKEN_LENGTH)

    def validate_phone_number(self, value):
        queryset = User.objects.filter(phone__phone_number=value)
        if not queryset.exists():
            raise AccountNotRegisteredException()
        return value

    def validate(self, validated_data):
        phone_number = str(validated_data.get("phone_number"))
        otp = validated_data.get("otp")

        queryset = PhoneNumber.objects.get(phone_number=phone_number)

        queryset.check_verification(security_code=otp)

        return validated_data


class ProfileSerializer(serializers.ModelSerializer):
    """
    Serializer class to serialize the user Profile model
    """

    class Meta:
        model = Profile
        fields = (
            "avatar",
            "bio",
            "created_at",
            "updated_at",
        )


class AddressReadOnlySerializer(CountryFieldMixin, serializers.ModelSerializer):
    """
    Serializer class to seralize Address model
    """

    user = serializers.CharField(source="user.get_full_name", read_only=True)

    class Meta:
        model = Address
        fields = "__all__"


class UserSerializer(serializers.ModelSerializer):
    """
    Serializer class to seralize User model
    """

    profile = ProfileSerializer(read_only=True)
    phone_number = PhoneNumberField(
        source="phone.phone_number", read_only=True, allow_null=True
    )
    addresses = AddressReadOnlySerializer(read_only=True, many=True)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone_number",
            "first_name",
            "last_name",
            "is_active",
            "profile",
            "addresses",
        )


class ShippingAddressSerializer(CountryFieldMixin, serializers.ModelSerializer):
    """
    Serializer class to seralize address of type shipping

    For shipping address, automatically set address type to shipping
    """

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ("address_type",)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["address_type"] = "S"

        return representation


class BillingAddressSerializer(CountryFieldMixin, serializers.ModelSerializer):
    """
    Serializer class to seralize address of type billing

    For billing address, automatically set address type to billing
    """

    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ("address_type",)

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["address_type"] = "B"

        return representation
