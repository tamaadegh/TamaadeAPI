from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from .models import Address, PhoneNumber, Profile

User = get_user_model()


class AddressInline(admin.StackedInline):
    model = Address
    extra = 0
    can_delete = True


class PhoneNumberInline(admin.TabularInline):
    model = PhoneNumber
    extra = 0


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'bio_preview', 'created_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'bio']
    readonly_fields = ['created_at', 'updated_at']
    list_per_page = 25
    
    def bio_preview(self, obj):
        if obj.bio:
            return obj.bio[:50] + '...' if len(obj.bio) > 50 else obj.bio
        return format_html('<span style="color: #999;">No bio</span>')
    bio_preview.short_description = 'Bio'


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_address', 'city', 'country', 'address_type_display', 'default']
    list_filter = ['country', 'address_type', 'default']
    search_fields = ['user__email', 'street_address', 'city', 'country']
    list_per_page = 25
    
    def full_address(self, obj):
        return f"{obj.street_address}, {obj.apartment_address}"
    full_address.short_description = 'Address'
    
    def address_type_display(self, obj):
        colors = {'B': '#007bff', 'S': '#28a745'}
        color = colors.get(obj.address_type, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color, obj.get_address_type_display()
        )
    address_type_display.short_description = 'Type'


@admin.register(PhoneNumber)
class PhoneNumberAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone_number', 'verification_status', 'created_at']
    list_filter = ['is_verified', 'created_at']
    search_fields = ['user__email', 'phone_number']
    readonly_fields = ['created_at', 'updated_at', 'security_code', 'sent']
    list_per_page = 25
    
    def verification_status(self, obj):
        if obj.is_verified:
            return format_html('<span style="color: #28a745;">✓ Verified</span>')
        return format_html('<span style="color: #dc3545;">✗ Not Verified</span>')
    verification_status.short_description = 'Status'


# Customize the User admin to include inlines
class CustomUserAdmin(BaseUserAdmin):
    inlines = [ProfileInline, PhoneNumberInline, AddressInline]

# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)
