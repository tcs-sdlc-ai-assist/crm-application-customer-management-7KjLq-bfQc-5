from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("title", "report_type", "status", "format", "generated_by", "generated_at", "created_at")
    list_filter = ("report_type", "status", "format", "created_at", "generated_at")
    search_fields = ("title", "generated_by__email", "generated_by__first_name", "generated_by__last_name")
    readonly_fields = ("id", "created_at", "generated_at")
    list_select_related = ("generated_by",)
    ordering = ("-created_at",)
    list_per_page = 25
    raw_id_fields = ("generated_by",)