import uuid

from django.conf import settings
from django.db import models


class SalesStage(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=64, unique=True)
    order = models.IntegerField(default=0, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Sales Stage"
        verbose_name_plural = "Sales Stages"
        ordering = ["order"]
        indexes = [
            models.Index(fields=["order"], name="idx_sales_stages_order"),
        ]

    def __str__(self):
        return f"{self.name} (Order: {self.order})"


class Deal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=128)
    value = models.DecimalField(max_digits=12, decimal_places=2)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="deals",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_deals",
    )
    stage = models.ForeignKey(
        SalesStage,
        on_delete=models.PROTECT,
        related_name="deals",
    )
    expected_close_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Deal"
        verbose_name_plural = "Deals"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["customer"], name="idx_deals_customer_id"),
            models.Index(fields=["owner"], name="idx_deals_owner_id"),
            models.Index(fields=["stage"], name="idx_deals_stage_id"),
        ]

    def __str__(self):
        return f"{self.name} - {self.value}"