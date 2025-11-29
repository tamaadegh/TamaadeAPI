from django import forms
from django.core.exceptions import ValidationError
from products.models import Product
from orders.models import Order


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
            'price': 'Price ($)',
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
