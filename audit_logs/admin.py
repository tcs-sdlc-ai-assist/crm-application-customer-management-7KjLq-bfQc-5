from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("user", "entity_type", "action", "entity_id", "timestamp")
    list_filter = ("action", "entity_type", "timestamp")
    search_fields = (
        "entity_type",
        "entity_id",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    readonly_fields = (
        "id",
        "user",
        "entity_type",
        "entity_id",
        "action",
        "changes",
        "ip_address",
        "timestamp",
    )
    ordering = ("-timestamp",)
    list_per_page = 50
    list_select_related = ("user",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False