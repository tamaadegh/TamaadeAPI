from django.contrib import admin
from payment.models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "order", "payment_option", "status", "client_reference", "created_at"]
    list_filter = ["status", "payment_option"]
    search_fields = ["client_reference", "checkout_id"]
    readonly_fields = ["created_at", "updated_at"]
