from django.contrib import admin

from .models import Deal, SalesStage


@admin.register(SalesStage)
class SalesStageAdmin(admin.ModelAdmin):
    list_display = ("name", "order", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("order",)
    readonly_fields = ("id", "created_at")
    list_per_page = 25


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "customer",
        "owner",
        "stage",
        "value",
        "expected_close_date",
        "created_at",
    )
    list_filter = (
        "stage",
        "owner",
        "expected_close_date",
        "created_at",
    )
    search_fields = (
        "name",
        "description",
        "customer__name",
        "customer__email",
        "owner__email",
        "owner__first_name",
        "owner__last_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    list_per_page = 25
    list_select_related = ("customer", "owner", "stage")
    raw_id_fields = ("customer", "owner")