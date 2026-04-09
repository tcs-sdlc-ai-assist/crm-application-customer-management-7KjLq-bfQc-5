import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class CommunicationLog(models.Model):
    class CommunicationType(models.TextChoices):
        CALL = "call", "Call"
        EMAIL = "email", "Email"
        MEETING = "meeting", "Meeting"

    class Direction(models.TextChoices):
        INBOUND = "inbound", "Inbound"
        OUTBOUND = "outbound", "Outbound"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="communication_logs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="communication_logs",
    )
    communication_type = models.CharField(
        max_length=16,
        choices=CommunicationType.choices,
        db_index=True,
    )
    subject = models.CharField(max_length=255, blank=True, default="")
    body = models.TextField(blank=True, default="")
    direction = models.CharField(
        max_length=8,
        choices=Direction.choices,
        blank=True,
        default="",
    )
    logged_at = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Communication Log"
        verbose_name_plural = "Communication Logs"
        ordering = ["-logged_at"]
        indexes = [
            models.Index(fields=["customer", "logged_at"]),
            models.Index(fields=["user", "logged_at"]),
            models.Index(fields=["communication_type", "logged_at"]),
        ]

    def __str__(self):
        return f"{self.get_communication_type_display()} - {self.subject or 'No Subject'} ({self.logged_at:%Y-%m-%d %H:%M})"


class Meeting(models.Model):
    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer = models.ForeignKey(
        "customers.Customer",
        on_delete=models.CASCADE,
        related_name="meetings",
    )
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_meetings",
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    start_time = models.DateTimeField(db_index=True)
    end_time = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True, default="")
    google_calendar_event_id = models.CharField(
        max_length=128,
        blank=True,
        default="",
        help_text="Google Calendar event ID for calendar sync.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.SCHEDULED,
        db_index=True,
    )
    communication_log = models.ForeignKey(
        CommunicationLog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="meetings",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Meeting"
        verbose_name_plural = "Meetings"
        ordering = ["-start_time"]
        indexes = [
            models.Index(fields=["customer", "start_time"]),
            models.Index(fields=["organizer", "start_time"]),
            models.Index(fields=["status", "start_time"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.start_time:%Y-%m-%d %H:%M})"