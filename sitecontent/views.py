import re

from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_GET
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import BackgroundSound, PrivacyPolicy, SoundSettings
from .serializers import BackgroundSoundSerializer, PrivacyPolicySerializer


class PrivacyPolicyAPIView(APIView):
    """Public privacy page content, editable from the dashboard."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        return Response(PrivacyPolicySerializer(PrivacyPolicy.load()).data)


class BackgroundMusicAPIView(APIView):
    """Which background track web and mobile should play, if any."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, *args, **kwargs):
        sound_settings = SoundSettings.load()
        track = BackgroundSound.objects.filter(is_active=True).defer("audio_data").first()
        enabled = sound_settings.music_enabled and track is not None
        data = BackgroundSoundSerializer(track, context={"request": request}).data if enabled else None
        return Response({"enabled": enabled, "track": data})


_RANGE_RE = re.compile(r"bytes=(\d*)-(\d*)")


@require_GET
def sound_audio(request, sound_id):
    """Stream a stored sound. Supports Range requests, which Safari and the
    Android MediaPlayer use for streaming and looping."""
    sound = get_object_or_404(BackgroundSound, pk=sound_id)
    data = bytes(sound.audio_data or b"")
    if not data:
        raise Http404("No audio")
    total = len(data)

    match = _RANGE_RE.fullmatch(request.headers.get("Range", "").strip())
    if match and (match.group(1) or match.group(2)):
        start_s, end_s = match.groups()
        if start_s:
            start = int(start_s)
            end = min(int(end_s), total - 1) if end_s else total - 1
        else:
            start = max(0, total - int(end_s))
            end = total - 1
        if start > end:
            response = HttpResponse(status=416)
            response["Content-Range"] = f"bytes */{total}"
            return response
        response = HttpResponse(data[start : end + 1], status=206, content_type=sound.content_type)
        response["Content-Range"] = f"bytes {start}-{end}/{total}"
    else:
        response = HttpResponse(data, content_type=sound.content_type)

    response["Accept-Ranges"] = "bytes"
    response["Cache-Control"] = "public, max-age=86400"
    response["Access-Control-Allow-Origin"] = "*"
    return response
