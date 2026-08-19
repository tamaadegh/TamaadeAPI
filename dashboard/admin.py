from django.contrib import admin

from dashboard.models import SystemEvent


@admin.register(SystemEvent)
class SystemEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "level", "category", "message", "reference", "user")
    list_filter = ("level", "category", "created_at")
    search_fields = ("message", "detail", "reference")
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # Operational history is written by the app, not edited by hand.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
