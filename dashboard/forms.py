from django import forms
from django.core.exceptions import ValidationError
from products.models import Product
from orders.models import Order
from sitecontent.models import (
    ALLOWED_SOUND_TYPES,
    MAX_SOUND_BYTES,
    BackgroundSound,
    PrivacyPolicy,
    SoundSettings,
)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # Keep legacy `image` and `video` while adding multiple-upload inputs
        fields = [
            "name",
            "category",
            "desc",
            "image",
            "video",
            "price",
            "quantity",
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter product name',
                'required': True
            }),
            'category': forms.Select(attrs={
                'class': 'form-select',
                'required': True
            }),
            'desc': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter detailed product description...'
            }),
            'image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'video': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'video/mp4,video/webm,video/ogg'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'placeholder': '0.00',
                'required': True
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'placeholder': '0',
                'required': True
            }),
        }
        labels = {
            'name': 'Product Name',
            'category': 'Category',
            'desc': 'Description',
            'image': 'Product Image',
            'video': 'Product Video (MP4/WebM/Ogg)',
            'price': 'Price (GH₵)',
            'quantity': 'Stock Quantity',
        }

    def clean_video(self):
        video = self.cleaned_data.get("video")
        if not video:
            return video
        allowed = {"video/mp4", "video/webm", "video/ogg"}
        content_type = getattr(video, "content_type", None)
        if content_type and content_type not in allowed:
            raise ValidationError("Unsupported video format. Allowed: MP4, WebM, Ogg")
        # Basic size guard: 50MB default
        max_mb = 50
        if hasattr(video, "size") and video.size > max_mb * 1024 * 1024:
            raise ValidationError(f"Video file too large (>{max_mb}MB)")
        return video

    # Add optional form fields for multiple uploads (not model fields):
    image_files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"multiple": True, "accept": "image/*", "class": "form-control"}),
        required=False,
    )
    video_files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={"multiple": True, "accept": "video/mp4,video/webm,video/ogg", "class": "form-control"}),
        required=False,
    )


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["status"]


class PrivacyPolicyForm(forms.ModelForm):
    class Meta:
        model = PrivacyPolicy
        fields = ["title", "content"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control"}),
            "content": forms.Textarea(attrs={"class": "form-control font-monospace", "rows": 22}),
        }


class SoundSettingsForm(forms.ModelForm):
    class Meta:
        model = SoundSettings
        fields = ["music_enabled"]
        widgets = {"music_enabled": forms.CheckboxInput(attrs={"class": "form-check-input", "role": "switch"})}
        labels = {"music_enabled": "Play background music on web and mobile"}


class BackgroundSoundForm(forms.ModelForm):
    audio_file = forms.FileField(
        required=False,
        label="Audio file (MP3, OGG, WAV, M4A – max 10 MB)",
        widget=forms.ClearableFileInput(attrs={"class": "form-control", "accept": "audio/*"}),
    )

    class Meta:
        model = BackgroundSound
        fields = ["title", "volume", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Chill shopping vibes"}),
            "volume": forms.NumberInput(attrs={"class": "form-control", "step": "0.05", "min": "0", "max": "1"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {"is_active": "Use this sound in the apps"}

    def clean_volume(self):
        volume = self.cleaned_data.get("volume")
        if volume is not None and not (0 <= volume <= 1):
            raise ValidationError("Volume must be between 0 and 1.")
        return volume

    def clean_audio_file(self):
        audio = self.cleaned_data.get("audio_file")
        if not audio:
            if not (self.instance and self.instance.pk):
                raise ValidationError("Please choose an audio file.")
            return audio
        content_type = (getattr(audio, "content_type", "") or "").lower()
        if content_type not in ALLOWED_SOUND_TYPES:
            raise ValidationError("Unsupported audio format. Use MP3, OGG, WAV or M4A.")
        if audio.size > MAX_SOUND_BYTES:
            raise ValidationError(f"Audio file too large (max {MAX_SOUND_BYTES // (1024 * 1024)} MB).")
        return audio

    def save(self, commit=True):
        sound = super().save(commit=False)
        audio = self.cleaned_data.get("audio_file")
        if audio:
            sound.audio_data = audio.read()
            sound.content_type = audio.content_type
            sound.file_name = audio.name[:255]
            sound.size = audio.size
        if commit:
            sound.save()
        return sound
