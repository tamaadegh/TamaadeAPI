from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission

from orders.models import Order
from payment.models import Payment


class IsOrderPending(BasePermission):
    """
    Check the status of order is pending or completed before updating/deleting instance
    """

    message = _("Updating or deleting closed order is not allowed.")

    def has_object_permission(self, request, view, obj):
        if view.action in ("retrieve",):
            return True
        return obj.status == "P"


class IsOrderItemByBuyerOrAdmin(BasePermission):
    """
    Check if order item is owned by appropriate buyer or admin
    """

    def has_permission(self, request, view):
        order_id = view.kwargs.get("order_id")
        order = get_object_or_404(Order, id=order_id)
        return order.buyer == request.user or request.user.is_staff

    def has_object_permission(self, request, view, obj):
        return obj.order.buyer == request.user or request.user.is_staff


class IsOrderByBuyerOrAdmin(BasePermission):
    """
    Check if order is owned by appropriate buyer or admin
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated is True

    def has_object_permission(self, request, view, obj):
        return obj.buyer == request.user or request.user.is_staff


class IsOrderItemPending(BasePermission):
    """
    Check the status of order is pending or completed before creating, updating and deleting order items
    """

    message = _(
        "Creating, updating or deleting order items for a closed order is not allowed."
    )

    def has_permission(self, request, view):
        order_id = view.kwargs.get("order_id")
        order = get_object_or_404(Order, id=order_id)

        if view.action in ("list", "retrieve"):
            return True

        self._ensure_order_editable(order)
        return True

    def has_object_permission(self, request, view, obj):
        if view.action in ("retrieve",):
            return True
        self._ensure_order_editable(obj.order)
        return True

    def _ensure_order_editable(self, order):
        try:
            payment = order.payment
        except ObjectDoesNotExist:
            payment = None

        already_paid = order.status != Order.PENDING or (
            payment is not None and payment.status == Payment.COMPLETED
        )
        if already_paid:
            raise ValidationError(
                {
                    "detail": _(
                        "This order is already paid and cannot be modified."
                    )
                }
            )
