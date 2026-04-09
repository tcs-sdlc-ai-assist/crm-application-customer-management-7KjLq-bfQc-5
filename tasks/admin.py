from django.contrib import admin

from .models import Task


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "assigned_to",
        "status",
        "priority",
        "due_date",
        "customer",
        "deal",
        "created_by",
        "created_at",
    )
    list_filter = (
        "status",
        "priority",
        "due_date",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "customer__name",
        "customer__email",
        "deal__name",
        "assigned_to__email",
        "assigned_to__first_name",
        "assigned_to__last_name",
        "created_by__email",
        "created_by__first_name",
        "created_by__last_name",
    )
    readonly_fields = ("id", "created_at", "updated_at", "completed_at")
    ordering = ("-created_at",)
    list_per_page = 25
    list_select_related = ("assigned_to", "created_by", "customer", "deal")
    raw_id_fields = ("assigned_to", "created_by", "customer", "deal")