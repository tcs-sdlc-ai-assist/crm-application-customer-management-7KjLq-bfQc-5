import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class AuditLog(models.Model):
    class Action(models.TextChoices):
        CREATE = "create", "Create"
        UPDATE = "update", "Update"
        DELETE = "delete", "Delete"
        VIEW = "view", "View"
        EXPORT = "export", "Export"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    entity_type = models.CharField(max_length=255, db_index=True)
    entity_id = models.UUIDField(db_index=True)
    action = models.CharField(
        max_length=10,
        choices=Action.choices,
        db_index=True,
    )
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["entity_type", "entity_id"]),
            models.Index(fields=["user", "timestamp"]),
            models.Index(fields=["action", "timestamp"]),
        ]

    def __str__(self):
        user_display = self.user if self.user else "System"
        return f"[{self.timestamp:%Y-%m-%d %H:%M:%S}] {user_display} {self.action} {self.entity_type} ({self.entity_id})"

    @classmethod
    def create_entry(
        cls,
        entity_type,
        entity_id,
        action,
        user=None,
        changes=None,
        ip_address=None,
    ):
        if changes is None:
            changes = {}

        if action not in cls.Action.values:
            raise ValueError(
                f"Invalid action '{action}'. Must be one of: {', '.join(cls.Action.values)}"
            )

        try:
            entry = cls.objects.create(
                user=user,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                changes=changes,
                ip_address=ip_address,
            )
        except Exception as e:
            raise ValueError(f"Failed to create audit log entry: {e}") from e

        return entry