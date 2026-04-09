import uuid
from django.conf import settings
from django.db import models


class IntegrationConfig(models.Model):
    SERVICE_TYPE_CHOICES = [
        ('gmail', 'Gmail'),
        ('google_calendar', 'Google Calendar'),
        ('slack', 'Slack'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='integration_configs',
    )
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
    )
    access_token = models.TextField(
        blank=True,
        default='',
        help_text='Encrypted access token for the integration service.',
    )
    refresh_token = models.TextField(
        blank=True,
        default='',
        help_text='Encrypted refresh token for the integration service.',
    )
    token_expiry = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Expiry datetime of the access token.',
    )
    webhook_url = models.URLField(
        max_length=512,
        blank=True,
        default='',
        help_text='Webhook URL for receiving events from the integration service.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Integration Configuration'
        verbose_name_plural = 'Integration Configurations'
        ordering = ['-created_at']
        unique_together = [['user', 'service_type']]

    def __str__(self):
        return f"{self.user} - {self.get_service_type_display()} ({'active' if self.is_active else 'inactive'})"