import uuid

from django.conf import settings
from django.db import models


class Report(models.Model):
    REPORT_TYPE_CHOICES = [
        ("sales_performance", "Sales Performance"),
        ("customer_engagement", "Customer Engagement"),
        ("pipeline_health", "Pipeline Health"),
    ]

    FORMAT_CHOICES = [
        ("json", "JSON"),
        ("csv", "CSV"),
        ("pdf", "PDF"),
    ]

    STATUS_CHOICES = [
        ("processing", "Processing"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report_type = models.CharField(
        max_length=64,
        choices=REPORT_TYPE_CHOICES,
        db_index=True,
    )
    title = models.CharField(max_length=255)
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text="Filters such as user_id, date_range, stage.",
    )
    status = models.CharField(
        max_length=32,
        choices=STATUS_CHOICES,
        default="processing",
        db_index=True,
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reports",
    )
    data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Cached report results.",
    )
    format = models.CharField(
        max_length=16,
        choices=FORMAT_CHOICES,
        default="json",
    )
    file_path = models.FileField(
        upload_to="reports/files/",
        null=True,
        blank=True,
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["generated_by", "created_at"],
                name="idx_report_user_created",
            ),
            models.Index(
                fields=["report_type", "status"],
                name="idx_report_type_status",
            ),
        ]

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.title} ({self.status})"