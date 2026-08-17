from django.urls import include, path
from rest_framework.routers import DefaultRouter

from products.views import (
    HeroBannerViewSet,
    HomeSectionViewSet,
    MerchTileViewSet,
    NavLinkViewSet,
    PriceTierViewSet,
    ProductCategoryViewSet,
    ProductViewSet,
    ProductImageViewSet,
    ProductVideoViewSet,
    StorefrontPromoViewSet,
)

app_name = "products"

router = DefaultRouter()
router.register(r"categories", ProductCategoryViewSet)
router.register(r"banners", HeroBannerViewSet)
router.register(r"price-tiers", PriceTierViewSet)
router.register(r"promos", StorefrontPromoViewSet)
router.register(r"merch-tiles", MerchTileViewSet)
router.register(r"home-sections", HomeSectionViewSet)
router.register(r"nav-links", NavLinkViewSet)
router.register(r"images", ProductImageViewSet)
router.register(r"videos", ProductVideoViewSet)
router.register(r"", ProductViewSet)


urlpatterns = [
    path("", include(router.urls)),
]
