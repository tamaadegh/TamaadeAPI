from rest_framework import serializers
from django.core.exceptions import ObjectDoesNotExist

from orders.models import Order
from payment.models import Payment
from users.models import Address
from users.serializers import BillingAddressSerializer, ShippingAddressSerializer


class PaymentSerializer(serializers.ModelSerializer):
    """
    Serializer to CRUD payments for an order.
    """

    buyer = serializers.CharField(source="order.buyer.get_full_name", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "buyer",
            "status",
            "payment_option",
            "order",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status",)


class PaymentOptionSerializer(serializers.ModelSerializer):
    """
    Payment serializer for checkout. Order will be automatically set during checkout.
    """

    buyer = serializers.CharField(source="order.buyer.get_full_name", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "buyer",
            "status",
            "payment_option",
            "order",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("status", "order")


class CheckoutSerializer(serializers.ModelSerializer):
    """
    Serializer class to set or update shipping address, billing address and payment of an order.
    """

    shipping_address = ShippingAddressSerializer(required=False, allow_null=True)
    billing_address = BillingAddressSerializer(required=False, allow_null=True)
    payment = PaymentOptionSerializer(required=False, allow_null=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "payment",
            "shipping_address",
            "billing_address",
        )

    def update(self, instance, validated_data):
        # PATCH may send only one of shipping/billing/payment.
        shipping_address = validated_data.get("shipping_address")
        if shipping_address is not None:
            if not instance.shipping_address:
                order_shipping_address = Address(**shipping_address)
                order_shipping_address.save()
            else:
                address = Address.objects.filter(shipping_orders=instance.id)
                address.update(**shipping_address)
                order_shipping_address = address.first()
            instance.shipping_address = order_shipping_address

        billing_address = validated_data.get("billing_address")
        if billing_address is not None:
            if not instance.billing_address:
                order_billing_address = Address(**billing_address)
                order_billing_address.save()
            else:
                address = Address.objects.filter(billing_orders=instance.id)
                address.update(**billing_address)
                order_billing_address = address.first()
            instance.billing_address = order_billing_address

        payment = validated_data.get("payment")
        if payment is not None:
            try:
                existing_payment = instance.payment
            except ObjectDoesNotExist:
                existing_payment = None
            if not existing_payment:
                order_payment = Payment(**payment, order=instance)
                order_payment.save()
            else:
                p = Payment.objects.filter(order=instance)
                p.update(**payment)
                order_payment = p.first()
            instance.payment = order_payment

        instance.save()
        return instance
