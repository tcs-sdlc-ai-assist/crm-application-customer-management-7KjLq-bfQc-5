import uuid

from django.conf import settings
from django.db import models


class AutomationRule(models.Model):
    TRIGGER_TYPE_CHOICES = [
        ('meeting_completed', 'Meeting Completed'),
        ('call_completed', 'Call Completed'),
        ('demo_completed', 'Demo Completed'),
        ('new_lead', 'New Lead'),
    ]

    ACTION_TYPE_CHOICES = [
        ('send_email', 'Send Email'),
        ('assign_lead', 'Assign Lead'),
        ('create_task', 'Create Task'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    trigger_type = models.CharField(max_length=32, choices=TRIGGER_TYPE_CHOICES)
    action_type = models.CharField(max_length=32, choices=ACTION_TYPE_CHOICES)
    config = models.JSONField(default=dict, blank=True, help_text='Rule parameters and criteria configuration')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='automation_rules',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Automation Rule'
        verbose_name_plural = 'Automation Rules'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.name} ({self.get_trigger_type_display()} -> {self.get_action_type_display()})'


class AutomationLog(models.Model):
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('failed', 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    rule = models.ForeignKey(
        AutomationRule,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='automation_logs',
    )
    target_entity_type = models.CharField(max_length=64)
    target_entity_id = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES)
    result_message = models.TextField(blank=True, default='')
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Automation Log'
        verbose_name_plural = 'Automation Logs'
        ordering = ['-executed_at']

    def __str__(self):
        return f'Log {self.id} - Rule: {self.rule.name} - {self.get_status_display()}'