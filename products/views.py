from rest_framework import permissions, viewsets, status

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
from products.permissions import IsSellerOrAdmin
from products.serializers import (
    HeroBannerSerializer,
    HomeSectionSerializer,
    MerchTileSerializer,
    NavLinkSerializer,
    PriceTierSerializer,
    ProductCategoryReadSerializer,
    ProductReadSerializer,
    ProductWriteSerializer,
    ProductImageSerializer,
    ProductVideoSerializer,
    ProductImageCreateSerializer,
    ProductVideoCreateSerializer,
    StorefrontPromoSerializer,
)


class PublicListAdminWriteViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action in ("list", "retrieve") and not getattr(
            self.request.user, "is_staff", False
        ):
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (permissions.IsAdminUser,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()


class HeroBannerViewSet(viewsets.ModelViewSet):
    """Public list of active homepage banners. Writes are admin-only."""

    serializer_class = HeroBannerSerializer
    queryset = HeroBanner.objects.all()

    def get_queryset(self):
        queryset = HeroBanner.objects.all()
        if self.action in ("list", "retrieve") and not getattr(
            self.request.user, "is_staff", False
        ):
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (permissions.IsAdminUser,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()


class PriceTierViewSet(viewsets.ModelViewSet):
    serializer_class = PriceTierSerializer
    queryset = PriceTier.objects.all()

    def get_queryset(self):
        queryset = PriceTier.objects.all()
        if self.action in ("list", "retrieve") and not getattr(
            self.request.user, "is_staff", False
        ):
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (permissions.IsAdminUser,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()


class StorefrontPromoViewSet(viewsets.ModelViewSet):
    serializer_class = StorefrontPromoSerializer
    queryset = StorefrontPromo.objects.all()

    def get_queryset(self):
        queryset = StorefrontPromo.objects.all()
        if self.action in ("list", "retrieve") and not getattr(
            self.request.user, "is_staff", False
        ):
            queryset = queryset.filter(is_active=True)
        return queryset

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (permissions.IsAdminUser,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()


class MerchTileViewSet(PublicListAdminWriteViewSet):
    serializer_class = MerchTileSerializer
    queryset = MerchTile.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        placement = self.request.query_params.get("placement")
        if placement:
            queryset = queryset.filter(placement=placement)
        return queryset


class HomeSectionViewSet(PublicListAdminWriteViewSet):
    serializer_class = HomeSectionSerializer
    queryset = HomeSection.objects.all()

    def get_queryset(self):
        queryset = super().get_queryset()
        location = self.request.query_params.get("location")
        if location:
            queryset = queryset.filter(location=location)
        return queryset


class NavLinkViewSet(PublicListAdminWriteViewSet):
    serializer_class = NavLinkSerializer
    queryset = NavLink.objects.all()


class ProductCategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    List and Retrieve product categories
    """

    queryset = ProductCategory.objects.all()
    serializer_class = ProductCategoryReadSerializer
    permission_classes = (permissions.AllowAny,)


class ProductViewSet(viewsets.ModelViewSet):
    """
    CRUD products
    """

    queryset = Product.objects.all()

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return ProductWriteSerializer

        return ProductReadSerializer

    def get_permissions(self):
        if self.action in ("create",):
            self.permission_classes = (permissions.IsAuthenticated,)
        elif self.action in ("update", "partial_update", "destroy"):
            self.permission_classes = (IsSellerOrAdmin,)
        else:
            self.permission_classes = (permissions.AllowAny,)

        return super().get_permissions()


class ProductImageViewSet(viewsets.ModelViewSet):
    queryset = ProductImage.objects.all()
    permission_classes = (permissions.AllowAny,)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductImageCreateSerializer
        return ProductImageSerializer

    def perform_create(self, serializer):
        product = serializer.validated_data.get("product")
        user = self.request.user
        if (
            product is not None
            and product.seller != user
            and not user.is_staff
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied()
        serializer.save()
    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (IsSellerOrAdmin,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()


class ProductVideoViewSet(viewsets.ModelViewSet):
    queryset = ProductVideo.objects.all()
    permission_classes = (permissions.AllowAny,)

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductVideoCreateSerializer
        return ProductVideoSerializer

    def perform_create(self, serializer):
        product = serializer.validated_data.get("product")
        user = self.request.user
        if (
            product is not None
            and product.seller != user
            and not user.is_staff
        ):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied()
        serializer.save()
    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (IsSellerOrAdmin,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()
