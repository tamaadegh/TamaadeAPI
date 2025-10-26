from django.contrib import admin
from django.utils.html import format_html
from orders.models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['product', 'quantity', 'item_cost']
    can_delete = False
    
    def item_cost(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.cost)
    item_cost.short_description = 'Cost'


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['id', 'buyer', 'status_badge', 'total_cost_display', 'item_count', 'created_at']
    list_filter = ['status', 'created_at', 'updated_at']
    search_fields = ['id', 'buyer__email', 'buyer__first_name', 'buyer__last_name']
    readonly_fields = ['created_at', 'updated_at', 'total_cost_display']
    list_per_page = 25
    inlines = [OrderItemInline]
    
    fieldsets = (
        ('Order Information', {
            'fields': ('buyer', 'status', 'shipping_address', 'billing_address')
        }),
        ('Order Summary', {
            'fields': ('total_cost_display',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        status_colors = {
            'P': '#ffc107',  # Pending
            'C': '#28a745',   # Completed
        }
        color = status_colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def item_count(self, obj):
        count = obj.order_items.count()
        return format_html('<strong>{}</strong> items', count)
    item_count.short_description = 'Items'
    
    def total_cost_display(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.total_cost)
    total_cost_display.short_description = 'Total Cost'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['id', 'order', 'product', 'quantity', 'product_price', 'item_cost']
    list_filter = ['order__status', 'order__created_at']
    search_fields = ['order__id', 'product__name']
    readonly_fields = ['item_cost']
    list_per_page = 25
    
    def product_price(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.product.price)
    product_price.short_description = 'Unit Price'
    
    def item_cost(self, obj):
        return format_html('<strong>${:.2f}</strong>', obj.cost)
    item_cost.short_description = 'Total Cost'
