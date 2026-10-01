from django.urls import reverse
from rest_framework import serializers

from .models import BackgroundSound, PrivacyPolicy


class PrivacyPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyPolicy
        fields = ("title", "content", "updated_at")


class BackgroundSoundSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()
    volume = serializers.FloatField()

    class Meta:
        model = BackgroundSound
        fields = ("id", "title", "url", "volume")

    def get_url(self, obj):
        # The version busts browser/app caches when the admin replaces the file.
        path = f"{reverse('sitecontent:sound_audio', args=[obj.pk])}?v={obj.version}"
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path
