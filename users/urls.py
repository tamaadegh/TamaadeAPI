from dj_rest_auth.jwt_auth import get_refresh_view
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AddressViewSet,
    DeleteAccountAPIView,
    OtpRequestAPIView,
    OtpVerifyAPIView,
    PasswordResetOtpConfirmAPIView,
    PasswordResetOtpRequestAPIView,
    ProfileAPIView,
    UserAPIView,
    UserLoginAPIView,
    UserRegisterationAPIView,
)

app_name = "users"

router = DefaultRouter()
router.register(r"", AddressViewSet)

urlpatterns = [
    path("register/", UserRegisterationAPIView.as_view(), name="user_register"),
    path("login/", UserLoginAPIView.as_view(), name="user_login"),
    path("otp/request/", OtpRequestAPIView.as_view(), name="otp_request"),
    path("otp/verify/", OtpVerifyAPIView.as_view(), name="otp_verify"),
    # Mobile: trade the refresh token for a new access token (body {"refresh": "..."}).
    path("token/refresh/", get_refresh_view().as_view(), name="token_refresh"),
    path(
        "password/reset/otp/request/",
        PasswordResetOtpRequestAPIView.as_view(),
        name="password_reset_otp_request",
    ),
    path(
        "password/reset/otp/confirm/",
        PasswordResetOtpConfirmAPIView.as_view(),
        name="password_reset_otp_confirm",
    ),
    path("", UserAPIView.as_view(), name="user_detail"),
    path("profile/", ProfileAPIView.as_view(), name="profile_detail"),
    path("delete-account/", DeleteAccountAPIView.as_view(), name="delete_account"),
    path("profile/address/", include(router.urls)),
]
