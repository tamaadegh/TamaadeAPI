from django.db import models
from django.utils.translation import gettext_lazy as _

DEFAULT_PRIVACY_TITLE = "Privacy Policy"
DEFAULT_PRIVACY_CONTENT = """Tamaade respects your privacy. We only collect your personal data when you shop with us.

## What we collect
- Your name, email address and phone number when you create an account or sign in.
- The products in your cart and your orders.
- Delivery and billing details you provide at checkout.
- The payment status returned by our payment provider (Hubtel). We never see or store your card details or mobile money PIN.

## How we use it
- To manage your cart, process your orders and deliver them.
- To confirm payments and send you order updates.

We do not sell your data and we do not use it for anything other than your shopping on Tamaade.

## Deleting your account
You can delete your account at any time from your profile, on the website or in the mobile app. Your name, email, phone number, addresses and cart are erased. Paid orders are kept without your personal details, for accounting.

## Contact
If you have questions about your data, contact our support team."""

# Audio is stored in the database: the Render disk is wiped on every deploy, so
# files saved under MEDIA_ROOT would disappear.
MAX_SOUND_BYTES = 10 * 1024 * 1024
ALLOWED_SOUND_TYPES = {
    "audio/mpeg",
    "audio/mp3",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/wave",
    "audio/webm",
    "audio/aac",
    "audio/mp4",
    "audio/x-m4a",
}


class SingletonMixin:
    @classmethod
    def load(cls):
        obj = cls.objects.order_by("pk").first()
        if obj is None:
            obj = cls.objects.create()
        return obj


class PrivacyPolicy(SingletonMixin, models.Model):
    """Single row holding the privacy page shown on web and mobile."""

    title = models.CharField(max_length=200, default=DEFAULT_PRIVACY_TITLE)
    content = models.TextField(
        default=DEFAULT_PRIVACY_CONTENT,
        help_text='Plain text. Blank line = new paragraph, "## " = heading, "- " = bullet.',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Privacy Policy")
        verbose_name_plural = _("Privacy Policy")

    def __str__(self):
        return self.title


class SoundSettings(SingletonMixin, models.Model):
    """Single row: global switch for background music on web and mobile."""

    music_enabled = models.BooleanField(
        default=True,
        help_text="Turn background music off for every user.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Sound Settings")
        verbose_name_plural = _("Sound Settings")

    def __str__(self):
        return "Sound settings"


class BackgroundSound(models.Model):
    title = models.CharField(max_length=150)
    audio_data = models.BinaryField(editable=False)
    content_type = models.CharField(max_length=50, default="audio/mpeg")
    file_name = models.CharField(max_length=255, blank=True)
    size = models.PositiveIntegerField(default=0)
    volume = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.4,
        help_text="Playback volume between 0 and 1.",
    )
    is_active = models.BooleanField(
        default=False,
        help_text="Only one sound plays in the apps; activating one deactivates the others.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_active", "-created_at")
        verbose_name = _("Background Sound")
        verbose_name_plural = _("Background Sounds")

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.is_active:
            BackgroundSound.objects.exclude(pk=self.pk).filter(is_active=True).update(is_active=False)

    @property
    def version(self):
        return int(self.updated_at.timestamp()) if self.updated_at else 0
