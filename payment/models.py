from django.db import models
from django.utils.translation import gettext_lazy as _

from orders.models import Order


class Payment(models.Model):
    PENDING = "P"
    COMPLETED = "C"
    FAILED = "F"

    STATUS_CHOICES = (
        (PENDING, _("pending")),
        (COMPLETED, _("completed")),
        (FAILED, _("failed")),
    )

    # Payment options
    PAYPAL = "P"
    STRIPE = "S"
    HUBTEL = "H"

    PAYMENT_CHOICES = (
        (PAYPAL, _("paypal")),
        (STRIPE, _("stripe")),
        (HUBTEL, _("hubtel")),
    )

    status = models.CharField(max_length=1, choices=STATUS_CHOICES, default=PENDING)
    payment_option = models.CharField(max_length=1, choices=PAYMENT_CHOICES, default=HUBTEL)
    order = models.OneToOneField(
        Order, related_name="payment", on_delete=models.CASCADE
    )
    client_reference = models.CharField(max_length=32, blank=True, null=True, unique=True)
    checkout_id = models.CharField(max_length=80, blank=True)
    checkout_url = models.URLField(max_length=1000, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.order.buyer.get_full_name()
