from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    AddressViewSet,
    DeleteAccountAPIView,
    OtpRequestAPIView,
    OtpVerifyAPIView,
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
    path("", UserAPIView.as_view(), name="user_detail"),
    path("profile/", ProfileAPIView.as_view(), name="profile_detail"),
    path("delete-account/", DeleteAccountAPIView.as_view(), name="delete_account"),
    path("profile/address/", include(router.urls)),
]
