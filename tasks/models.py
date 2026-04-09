import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Task(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        IN_PROGRESS = "in_progress", "In Progress"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        URGENT = "urgent", "Urgent"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    deal = models.ForeignKey(
        "deals.Deal",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tasks",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_tasks",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    priority = models.CharField(
        max_length=8,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        db_index=True,
    )
    due_date = models.DateField(null=True, blank=True)
    reminder_date = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Task"
        verbose_name_plural = "Tasks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["assigned_to", "status"], name="idx_task_assignee_status"),
            models.Index(fields=["customer", "status"], name="idx_task_customer_status"),
            models.Index(fields=["deal", "status"], name="idx_task_deal_status"),
            models.Index(fields=["due_date", "status"], name="idx_task_due_date_status"),
            models.Index(fields=["priority", "status"], name="idx_task_priority_status"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def is_overdue(self):
        if self.due_date is None:
            return False
        if self.status in (self.Status.COMPLETED, self.Status.CANCELLED):
            return False
        return self.due_date < timezone.now().date()

    def mark_completed(self):
        self.status = self.Status.COMPLETED
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at", "updated_at"])