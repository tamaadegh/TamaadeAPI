from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response

from orders.models import Order, OrderItem
from orders.permissions import (
    IsOrderByBuyerOrAdmin,
    IsOrderItemByBuyerOrAdmin,
    IsOrderItemPending,
    IsOrderPending,
)
from orders.serializers import (
    OrderItemSerializer,
    OrderReadSerializer,
    OrderWriteSerializer,
)


class OrderItemViewSet(viewsets.ModelViewSet):
    """
    CRUD order items that are associated with the current order id.
    """

    queryset = OrderItem.objects.all()
    serializer_class = OrderItemSerializer
    permission_classes = [IsOrderItemByBuyerOrAdmin]

    def get_queryset(self):
        res = super().get_queryset()
        order_id = self.kwargs.get("order_id")
        return res.filter(order__id=order_id)

    def perform_create(self, serializer):
        order = get_object_or_404(Order, id=self.kwargs.get("order_id"))
        serializer.save(order=order)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            self.permission_classes += [IsOrderItemPending]

        return super().get_permissions()


class OrderViewSet(viewsets.ModelViewSet):
    """
    CRUD orders of a user
    """

    queryset = Order.objects.all()
    permission_classes = [IsOrderByBuyerOrAdmin]

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return OrderWriteSerializer

        return OrderReadSerializer

    def _read_response(self, instance, status_code):
        """Always answer with the read shape, whatever the write used.

        OrderWriteSerializer omits total_cost (and buyer/payment). The storefront
        stores the create response directly as its cart state and then renders
        formatPrice(order.total_cost), so replying with the write shape took the
        whole cart page down with "Cannot read properties of undefined (reading
        'toFixed')" the moment a customer added their first item. Reads and writes
        now return the same object.
        """
        read = OrderReadSerializer(instance, context=self.get_serializer_context())
        return Response(read.data, status=status_code)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return self._read_response(serializer.instance, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return self._read_response(serializer.instance, status.HTTP_200_OK)

    def get_queryset(self):
        res = super().get_queryset()
        user = self.request.user
        return res.filter(buyer=user)

    def get_permissions(self):
        if self.action in ("update", "partial_update", "destroy"):
            self.permission_classes += [IsOrderPending]

        return super().get_permissions()
