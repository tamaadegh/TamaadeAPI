from django.urls import path
from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.index, name="index"),
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
]
