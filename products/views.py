from rest_framework import permissions, viewsets, status

from products.models import Product, ProductCategory, ProductImage, ProductVideo
from products.permissions import IsSellerOrAdmin
from products.serializers import (
    ProductCategoryReadSerializer,
    ProductReadSerializer,
    ProductWriteSerializer,
    ProductImageSerializer,
    ProductVideoSerializer,
    ProductImageCreateSerializer,
    ProductVideoCreateSerializer,
)


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
        instance = serializer.save()
        # If asynchronous upload is enabled the task will pick it up
        return instance
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
        instance = serializer.save()
        return instance
    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes = (IsSellerOrAdmin,)
        else:
            self.permission_classes = (permissions.AllowAny,)
        return super().get_permissions()
