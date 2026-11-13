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


# ---------------------------------------------------------------------------
# Storefront content managed from the dashboard (categories, hero banners, home tiles).
# Uploaded images go to Cloudinary when the model is saved (see products.models).
# ---------------------------------------------------------------------------
from products.models import HeroBanner, MerchTile, ProductCategory  # noqa: E402

_TEXT = {"class": "form-control"}
_IMAGE = {"class": "form-control", "accept": "image/*"}
_SWITCH = {"class": "form-check-input", "role": "switch"}


class _ImageRequiredMixin:
    """A row needs a picture: an uploaded file, the existing one, or (where offered) an image URL."""

    image_field = "image"
    url_field = "image_url"
    image_message = "Add an image."

    def clean(self):
        data = super().clean()
        uploaded = data.get(self.image_field)
        url = (data.get(self.url_field) or "").strip()
        # instance still holds the saved values here (the form copies the new ones after clean()).
        kept_file = bool(self.instance.pk and getattr(self.instance, self.image_field))
        if not (uploaded or url or kept_file):
            self.add_error(self.image_field, self.image_message)
        return data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ["name", "icon"]
        widgets = {
            "name": forms.TextInput(attrs={**_TEXT, "placeholder": "e.g. Office chairs"}),
            "icon": forms.FileInput(attrs=_IMAGE),
        }
        labels = {"name": "Name", "icon": "Image"}
        help_texts = {"icon": "Square picture, shown in a circle in the apps. JPG or PNG."}

    def clean(self):
        data = super().clean()
        # New categories need an image; older ones without one can be saved and get one later.
        if not self.instance.pk and not data.get("icon"):
            self.add_error("icon", "A new category needs an image.")
        return data


class HeroBannerForm(_ImageRequiredMixin, forms.ModelForm):
    image_message = "Upload an image or paste an image URL."

    class Meta:
        model = HeroBanner
        fields = ["title", "image", "image_url", "link", "order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={**_TEXT, "placeholder": "e.g. Black Friday deals"}),
            "image": forms.FileInput(attrs=_IMAGE),
            "image_url": forms.URLInput(attrs={**_TEXT, "placeholder": "https://…"}),
            "link": forms.TextInput(attrs={**_TEXT, "placeholder": "/deals"}),
            "order": forms.NumberInput(attrs={**_TEXT, "min": 0}),
            "is_active": forms.CheckboxInput(attrs=_SWITCH),
        }
        labels = {"image": "Image", "image_url": "…or image URL", "link": "Opens", "order": "Position", "is_active": "Show on the store"}
        help_texts = {
            "image": "Wide picture, about 3:1 (e.g. 1500×500).",
            "link": "Page opened on tap, e.g. /deals or /products?category=FURNITURE.",
            "order": "Lower numbers come first.",
        }


class MerchTileForm(_ImageRequiredMixin, forms.ModelForm):
    image_message = "Upload an image or paste an image URL."

    class Meta:
        model = MerchTile
        fields = ["title", "placement", "image", "image_url", "link", "badge", "highlight", "order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={**_TEXT, "placeholder": "e.g. Furniture"}),
            "placement": forms.Select(attrs={"class": "form-select"}),
            "image": forms.FileInput(attrs=_IMAGE),
            "image_url": forms.URLInput(attrs={**_TEXT, "placeholder": "https://…"}),
            "link": forms.TextInput(attrs={**_TEXT, "placeholder": "/products?category=FURNITURE"}),
            "badge": forms.TextInput(attrs={**_TEXT, "placeholder": "e.g. NEW"}),
            "order": forms.NumberInput(attrs={**_TEXT, "min": 0}),
            "highlight": forms.CheckboxInput(attrs=_SWITCH),
            "is_active": forms.CheckboxInput(attrs=_SWITCH),
        }
        labels = {
            "placement": "Where", "image": "Image", "image_url": "…or image URL", "link": "Opens",
            "badge": "Badge", "highlight": "Highlight (green circle)", "order": "Position", "is_active": "Show on the store",
        }
        help_texts = {
            "image": "Square picture, shown in a circle.",
            "badge": "Short label on the circle. Leave empty for none.",
            "order": "Lower numbers come first.",
        }


class StyledModelForm(forms.ModelForm):
    """Gives every widget the dashboard classes, so simple forms need no widget list."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            w = field.widget
            if isinstance(w, forms.CheckboxInput):
                w.attrs.update(_SWITCH)
            elif isinstance(w, forms.Select):
                w.attrs.setdefault("class", "form-select")
            else:
                w.attrs.setdefault("class", "form-control")


from products.models import HomeSection, NavLink, PriceTier, StorefrontPromo  # noqa: E402


class HomeSectionForm(StyledModelForm):
    class Meta:
        model = HomeSection
        fields = ["title", "subtitle", "location", "product_source", "cta_label", "link", "key", "order", "is_active"]
        labels = {
            "location": "Page", "product_source": "Products shown", "cta_label": "Button text",
            "link": "Button opens", "key": "Key", "order": "Position", "is_active": "Show on the store",
        }
        help_texts = {
            "key": "Short unique id used by the website, e.g. new-arrivals.",
            "order": "Lower numbers come first.",
        }


class StorefrontPromoForm(StyledModelForm):
    class Meta:
        model = StorefrontPromo
        fields = ["title", "subtitle", "highlight", "cta_label", "link", "key", "order", "is_active"]
        labels = {
            "highlight": "Highlighted text", "cta_label": "Button text", "link": "Opens",
            "key": "Key", "order": "Position", "is_active": "Show on the store",
        }
        help_texts = {
            "key": "Where it shows: top_strip (home page strip) or deals_header (Deals page).",
            "highlight": "Short bold part, e.g. UP TO 50% OFF.",
        }


class PriceTierForm(StyledModelForm):
    class Meta:
        model = PriceTier
        fields = ["amount", "order", "is_active"]
        labels = {"amount": "Amount (GH₵)", "order": "Position", "is_active": "Show on the store"}
        help_texts = {"amount": "Shown as “Under GH₵…” and opens products up to that price."}


class NavLinkForm(StyledModelForm):
    class Meta:
        model = NavLink
        fields = ["label", "link", "has_dropdown", "order", "is_active"]
        labels = {"has_dropdown": "Has a dropdown", "order": "Position", "is_active": "Show on the website"}
        help_texts = {"link": "e.g. /products?category=FURNITURE"}
