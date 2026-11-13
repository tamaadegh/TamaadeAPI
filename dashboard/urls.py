from django.urls import path
from . import account, storefront, views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
    path("insights/", views.insights, name="insights"),
    path("products/", views.products_list, name="products_list"),
    path("products/<int:product_id>/", views.product_detail, name="product_detail"),
    path("orders/", views.orders_list, name="orders_list"),
    path("users/", views.users_list, name="users_list"),
    path("products/create/", views.product_create, name="product_create"),
    path("products/<int:product_id>/update/", views.product_update, name="product_update"),
    path("products/<int:product_id>/delete/", views.product_delete, name="product_delete"),
    path("orders/<int:order_id>/status/", views.order_update_status, name="order_update_status"),
    path("settings/privacy/", views.privacy_settings, name="privacy_settings"),
    path("settings/sound/", views.sound_settings, name="sound_settings"),
    path("settings/sound/<int:sound_id>/update/", views.sound_update, name="sound_update"),
    path("settings/sound/<int:sound_id>/activate/", views.sound_activate, name="sound_activate"),
    path("settings/sound/<int:sound_id>/delete/", views.sound_delete, name="sound_delete"),
    path("account/password/", account.password_change, name="password_change"),
    # Storefront content: categories, banners, tiles (see storefront.RESOURCES).
    path("store/<slug:slug>/", storefront.resource_list, name="resource_list"),
    path("store/<slug:slug>/new/", storefront.resource_edit, name="resource_create"),
    path("store/<slug:slug>/<int:pk>/", storefront.resource_edit, name="resource_edit"),
    path("store/<slug:slug>/<int:pk>/delete/", storefront.resource_delete, name="resource_delete"),
]
