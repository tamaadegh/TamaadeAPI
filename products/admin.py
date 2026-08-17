from django.contrib import admin
from django.utils.html import format_html
from products.models import (
    HeroBanner,
    HomeSection,
    MerchTile,
    NavLink,
    PriceTier,
    Product,
    ProductCategory,
    ProductImage,
    ProductVideo,
    StorefrontPromo,
)


@admin.register(HeroBanner)
class HeroBannerAdmin(admin.ModelAdmin):
    list_display = ["preview", "title", "order", "is_active", "link", "updated_at"]
    list_editable = ["order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["title", "link"]
    ordering = ["order", "id"]

    def preview(self, obj):
        url = obj.resolved_image
        if url:
            return format_html(
                '<img src="{}" width="120" height="40" style="object-fit: cover; border-radius: 4px;" />',
                url,
            )
        return format_html('<span style="color: #999;">No image</span>')

    preview.short_description = "Banner"


@admin.register(PriceTier)
class PriceTierAdmin(admin.ModelAdmin):
    list_display = ["amount", "order", "is_active"]
    list_editable = ["order", "is_active"]
    ordering = ["order", "amount"]


@admin.register(StorefrontPromo)
class StorefrontPromoAdmin(admin.ModelAdmin):
    list_display = ["key", "title", "highlight", "cta_label", "is_active", "order"]
    list_editable = ["is_active", "order"]
    search_fields = ["key", "title"]


@admin.register(MerchTile)
class MerchTileAdmin(admin.ModelAdmin):
    list_display = ["preview", "title", "placement", "badge", "highlight", "order", "is_active"]
    list_editable = ["order", "is_active"]
    list_filter = ["placement", "is_active", "highlight"]
    search_fields = ["title", "link"]

    def preview(self, obj):
        url = obj.resolved_image
        if url:
            return format_html(
                '<img src="{}" width="40" height="40" style="object-fit: cover; border-radius: 50%;" />',
                url,
            )
        return format_html('<span style="color: #999;">—</span>')

    preview.short_description = "Image"


@admin.register(HomeSection)
class HomeSectionAdmin(admin.ModelAdmin):
    list_display = ["title", "location", "key", "product_source", "order", "is_active"]
    list_editable = ["order", "is_active"]
    list_filter = ["location", "is_active"]
    search_fields = ["title", "key"]


@admin.register(NavLink)
class NavLinkAdmin(admin.ModelAdmin):
    list_display = ["label", "link", "has_dropdown", "order", "is_active"]
    list_editable = ["order", "is_active", "has_dropdown"]


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'product_count', 'created_at']
    search_fields = ['name']
    list_per_page = 25
    
    def product_count(self, obj):
        count = obj.product_list.count()
        return format_html('<span style="font-weight: bold;">{}</span>', count)
    product_count.short_description = 'Products'


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['thumbnail_preview', 'name', 'category', 'price', 'promo_label', 'quantity', 'stock_status', 'has_video', 'created_at']
    list_filter = ['category', 'is_new', 'is_express', 'created_at', 'updated_at']
    search_fields = ['name', 'desc', 'category__name']
    list_editable = ['price', 'quantity']
    list_per_page = 25
    readonly_fields = ['thumbnail_display', 'video_preview', 'seller', 'created_at', 'updated_at']
    inlines = []
    
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'brand', 'category', 'desc', 'seller')
        }),
        ('Media', {
            'fields': ('image', 'thumbnail_display', 'video', 'video_preview')
        }),
        ('Pricing & Inventory', {
            'fields': ('price', 'compare_at_price', 'quantity')
        }),
        ('Promotion', {
            'fields': ('promo_label', 'is_new', 'is_express', 'sale_ends_at')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Automatically set the seller to the current user if not set"""
        if not obj.seller_id:
            obj.seller = request.user
        super().save_model(request, obj, form, change)
    
    def thumbnail_preview(self, obj):
        # Prefer the first ProductImage if present
        image = None
        try:
            image = obj.images.first()
        except Exception:
            image = None

        if image and image.url:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                image.url
            )
        if obj.image:
            return format_html(
                '<img src="{}" width="50" height="50" style="object-fit: cover; border-radius: 5px;" />',
                obj.image.url
            )
        return format_html('<span style="color: #999;">No image</span>')
    thumbnail_preview.short_description = 'Image'
    
    def thumbnail_display(self, obj):
        image = None
        try:
            image = obj.images.first()
        except Exception:
            image = None

        if image and image.url:
            return format_html(
                '<img src="{}" width="300" style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                image.url
            )
        if obj.image:
            return format_html(
                '<img src="{}" width="300" style="border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1);" />',
                obj.image.url
            )
        return format_html('<span style="color: #999;">No image uploaded</span>')
    thumbnail_display.short_description = 'Product Image'
    
    def video_preview(self, obj):
        video = None
        try:
            video = obj.videos.first()
        except Exception:
            video = None

        if video and video.url:
            return format_html(
                '<video width="300" controls><source src="{}">Your browser does not support the video tag.</video>',
                video.url
            )

        if obj.video:
            return format_html(
                '<video width="300" controls><source src="{}" type="video/mp4">Your browser does not support the video tag.</video>',
                obj.video.url
            )
        return format_html('<span style="color: #999;">No video uploaded</span>')
    video_preview.short_description = 'Product Video'
    
    def stock_status(self, obj):
        if obj.quantity > 20:
            color = '#28a745'
            status = 'In Stock'
        elif obj.quantity > 0:
            color = '#ffc107'
            status = 'Low Stock'
        else:
            color = '#dc3545'
            status = 'Out of Stock'
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, status
        )
    stock_status.short_description = 'Status'
    
    def has_video(self, obj):
        if obj.video:
            return format_html('<span style="color: #28a745;">✓ Yes</span>')
        return format_html('<span style="color: #999;">✗ No</span>')
    has_video.short_description = 'Video'


# Customize the admin site header and title
admin.site.site_header = 'Tamaade Administration'
admin.site.site_title = 'Tamaade Admin Portal'
admin.site.index_title = 'Welcome to Tamaade Admin Dashboard'


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ('file_local', 'preview', 'url', 'is_primary', 'order')
    readonly_fields = ('preview',)

    def preview(self, obj):
        if obj and obj.url:
            return format_html('<img src="{}" style="max-width: 150px;" />', obj.url)
        return '(no image)'


class ProductVideoInline(admin.TabularInline):
    model = ProductVideo
    extra = 1
    fields = ('file_local', 'preview', 'url', 'is_primary', 'order')
    readonly_fields = ('preview',)

    def preview(self, obj):
        if obj and obj.url:
            return format_html('<video width="200" controls><source src="{}">Your browser does not support the video tag.</video>', obj.url)
        return '(no video)'


# Hook up the inlines to the ProductAdmin
ProductAdmin.inlines = [ProductImageInline, ProductVideoInline]
