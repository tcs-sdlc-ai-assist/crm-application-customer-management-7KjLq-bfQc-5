from django.contrib import admin

from .models import IntegrationConfig


@admin.register(IntegrationConfig)
class IntegrationConfigAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "service_type",
        "is_active",
        "token_expiry",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "service_type",
        "is_active",
        "created_at",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "service_type",
    )
    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )
    list_select_related = ("user",)
    ordering = ("-created_at",)