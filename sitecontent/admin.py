from django.contrib import admin

from .models import BackgroundSound, PrivacyPolicy, SoundSettings


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ("title", "updated_at")


@admin.register(SoundSettings)
class SoundSettingsAdmin(admin.ModelAdmin):
    list_display = ("__str__", "music_enabled", "updated_at")


@admin.register(BackgroundSound)
class BackgroundSoundAdmin(admin.ModelAdmin):
    # Uploading/replacing audio happens in the custom dashboard (Sound page).
    list_display = ("title", "is_active", "volume", "size", "updated_at")
    readonly_fields = ("file_name", "content_type", "size")
