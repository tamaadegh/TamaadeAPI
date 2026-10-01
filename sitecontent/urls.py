from django.urls import path

from .views import BackgroundMusicAPIView, PrivacyPolicyAPIView, sound_audio

app_name = "sitecontent"

urlpatterns = [
    path("privacy/", PrivacyPolicyAPIView.as_view(), name="privacy"),
    path("background-music/", BackgroundMusicAPIView.as_view(), name="background_music"),
    path("sounds/<int:sound_id>/audio/", sound_audio, name="sound_audio"),
]
