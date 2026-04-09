from django.contrib import admin

from .models import AutomationLog, AutomationRule


@admin.register(AutomationRule)
class AutomationRuleAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "trigger_type",
        "action_type",
        "is_active",
        "created_by",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "trigger_type",
        "action_type",
        "is_active",
        "created_at",
    )
    search_fields = (
        "name",
        "created_by__email",
        "created_by__first_name",
        "created_by__last_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    raw_id_fields = ("created_by",)


@admin.register(AutomationLog)
class AutomationLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "rule",
        "triggered_by",
        "target_entity_type",
        "target_entity_id",
        "status",
        "executed_at",
    )
    list_filter = (
        "status",
        "target_entity_type",
        "executed_at",
    )
    search_fields = (
        "rule__name",
        "triggered_by__email",
        "target_entity_type",
        "target_entity_id",
        "result_message",
    )
    readonly_fields = ("id", "executed_at")
    ordering = ("-executed_at",)
    raw_id_fields = ("rule", "triggered_by")