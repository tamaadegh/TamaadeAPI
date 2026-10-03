from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.utils.translation import gettext as _
from django_countries.serializers import CountryFieldMixin
from phonenumber_field.serializerfields import PhoneNumberField
from rest_framework import serializers

from .exceptions import (
    AccountDisabledException,
    AccountNotRegisteredException,
    InvalidCredentialsException,
)
from .models import Address, PhoneNumber, Profile

User = get_user_model()


class UserRegistrationSerializer(serializers.Serializer):
    """
    Sign-up with an e-mail and/or a Ghana phone number, plus a password.
    """

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value):
        value = (value or "").strip().lower()
        if value and User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError(_("A user is already registered with this e-mail address."))
        return value

    def validate_phone_number(self, value):
        from users.otp import is_valid_ghana_mobile, normalize_ghana_phone

        if not (value or "").strip():
            return ""
        if not is_valid_ghana_mobile(value):
            raise serializers.ValidationError(_("Enter a valid Ghana mobile number."))
        phone = normalize_ghana_phone(value)
        if PhoneNumber.objects.filter(phone_number=phone).exists():
            raise serializers.ValidationError(_("A user is already registered with this phone number."))
        return phone

    def validate(self, data):
        from django.contrib.auth.password_validation import validate_password
        from django.core.exceptions import ValidationError as DjangoValidationError

        data["first_name"] = data["first_name"].strip()
        data["last_name"] = data["last_name"].strip()
        if not data.get("email") and not data.get("phone_number"):
            raise serializers.ValidationError(_("Enter an email or a phone number."))
        candidate = User(first_name=data["first_name"], last_name=data["last_name"], email=data.get("email", ""))
        try:
            validate_password(data["password"], candidate)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"password": list(exc.messages)})
        return data

    def create(self, data):
        from django.db import transaction
        from django.utils.crypto import get_random_string

        phone = data.get("phone_number") or ""
        email = data.get("email") or ""
        username = f"tmd{phone.lstrip('+')}" if phone else email
        if User.objects.filter(username=username).exists():
            username = f"{username}-{get_random_string(6)}"
        with transaction.atomic():
            user = User(
                username=username[:150],
                first_name=data["first_name"],
                last_name=data["last_name"],
                email=email,
            )
            user.set_password(data["password"])
            user.save()
            if phone:
                # Not verified yet: the first SMS-code sign-in verifies it.
                PhoneNumber.objects.create(user=user, phone_number=phone, is_verified=False)
        return user


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

        if not email:
            phone = getattr(user, "phone", None)
            if phone is None or not phone.is_verified:
                raise serializers.ValidationError(_("Phone number is not verified."))

        validated_data["user"] = user
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


class OtpPhoneMixin:
    def validate_phone_number(self, value):
        from users.otp import is_valid_ghana_mobile, normalize_ghana_phone

        if not is_valid_ghana_mobile(value):
            raise serializers.ValidationError(_("Enter a valid Ghana mobile number."))
        return normalize_ghana_phone(value)


class OtpRequestSerializer(OtpPhoneMixin, serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)


class OtpVerifySerializer(OtpPhoneMixin, serializers.Serializer):
    phone_number = serializers.CharField(max_length=20)
    code = serializers.CharField(max_length=6)


class UserUpdateSerializer(serializers.Serializer):
    """
    PATCH /api/user/: names, e-mail and phone. Adding an e-mail enables
    e-mail + password sign-in, adding a phone enables SMS-code sign-in.
    An account must keep at least one of the two.
    """

    first_name = serializers.CharField(max_length=150, required=False)
    last_name = serializers.CharField(max_length=150, required=False)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True)

    def validate_email(self, value):
        value = (value or "").strip().lower()
        if value and User.objects.filter(email__iexact=value).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError(_("A user is already registered with this e-mail address."))
        return value

    def validate_phone_number(self, value):
        from users.otp import is_valid_ghana_mobile, normalize_ghana_phone

        if not (value or "").strip():
            return ""
        if not is_valid_ghana_mobile(value):
            raise serializers.ValidationError(_("Enter a valid Ghana mobile number."))
        phone = normalize_ghana_phone(value)
        if PhoneNumber.objects.filter(phone_number=phone).exclude(user=self.instance).exists():
            raise serializers.ValidationError(_("A user is already registered with this phone number."))
        return phone

    def validate(self, data):
        user = self.instance
        current_phone = getattr(getattr(user, "phone", None), "phone_number", None)
        email = data["email"] if "email" in data else user.email
        phone = data["phone_number"] if "phone_number" in data else (str(current_phone) if current_phone else "")
        if not email and not phone:
            raise serializers.ValidationError(_("Enter an email or a phone number."))
        for field in ("first_name", "last_name"):
            if field in data:
                data[field] = data[field].strip()
                if not data[field]:
                    raise serializers.ValidationError({field: _("This field is required.")})
        return data

    def update(self, user, data):
        from django.db import transaction

        with transaction.atomic():
            for field in ("first_name", "last_name", "email"):
                if field in data:
                    setattr(user, field, data[field])
            user.save()
            if "phone_number" in data:
                phone_record = PhoneNumber.objects.filter(user=user).first()
                new_phone = data["phone_number"]
                if not new_phone:
                    if phone_record:
                        phone_record.delete()
                elif phone_record is None:
                    PhoneNumber.objects.create(user=user, phone_number=new_phone, is_verified=False)
                elif phone_record.phone_number != new_phone:
                    # A new number is unverified until its first SMS-code sign-in.
                    phone_record.phone_number = new_phone
                    phone_record.is_verified = False
                    phone_record.save()
        user.refresh_from_db()
        return user
