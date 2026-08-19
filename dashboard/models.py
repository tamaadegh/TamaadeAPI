"""Operational event log surfaced to staff on the dashboard.

Storefront problems used to be invisible: a signup could fail, a Hubtel
checkout could be rejected, or a verification e-mail could bounce, and the only
trace was a container log nobody reads. `SystemEvent` records those moments so
the dashboard can show what is actually going wrong in production.

This is deliberately a coarse operational log, not an audit trail or an
analytics pipeline: a bounded number of rows, written on notable events only,
and safe to prune.
"""

from django.conf import settings
from django.db import models


class SystemEvent(models.Model):
    LEVEL_INFO = "info"
    LEVEL_WARNING = "warning"
    LEVEL_ERROR = "error"
    LEVEL_CHOICES = (
        (LEVEL_INFO, "Info"),
        (LEVEL_WARNING, "Warning"),
        (LEVEL_ERROR, "Error"),
    )

    CAT_SIGNUP = "signup"
    CAT_LOGIN = "login"
    CAT_PAYMENT = "payment"
    CAT_CART = "cart"
    CAT_EMAIL = "email"
    CAT_SMS = "sms"
    CAT_INTEGRATION = "integration"
    CAT_OTHER = "other"
    CATEGORY_CHOICES = (
        (CAT_SIGNUP, "Signup"),
        (CAT_LOGIN, "Login"),
        (CAT_PAYMENT, "Payment"),
        (CAT_CART, "Cart"),
        (CAT_EMAIL, "E-mail"),
        (CAT_SMS, "SMS"),
        (CAT_INTEGRATION, "Integration"),
        (CAT_OTHER, "Other"),
    )

    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default=LEVEL_INFO)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default=CAT_OTHER)
    message = models.CharField(max_length=300)
    detail = models.TextField(blank=True, help_text="Extra context: payload, exception text, etc.")
    # Free-text handle for whatever identifies the subject - a Hubtel
    # clientReference, an order id, an e-mail address.
    reference = models.CharField(max_length=120, blank=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        related_name="system_events",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "System event"
        verbose_name_plural = "System events"
        indexes = [
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["level", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.level}] {self.category}: {self.message}"

    @property
    def is_bad(self):
        return self.level in (self.LEVEL_WARNING, self.LEVEL_ERROR)
