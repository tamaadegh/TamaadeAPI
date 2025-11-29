from django.urls import include, path
from rest_framework.routers import DefaultRouter

from products.views import ProductCategoryViewSet, ProductViewSet, ProductImageViewSet, ProductVideoViewSet

app_name = "products"

router = DefaultRouter()
router.register(r"categories", ProductCategoryViewSet)
router.register(r"", ProductViewSet)
router.register(r"images", ProductImageViewSet)
router.register(r"videos", ProductVideoViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
