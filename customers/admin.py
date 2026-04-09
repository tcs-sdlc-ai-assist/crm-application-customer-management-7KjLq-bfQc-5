from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "industry", "company", "created_by", "created_at")
    search_fields = ("name", "email", "company", "industry")
    list_filter = ("industry", "created_at")
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-created_at",)
    raw_id_fields = ("created_by",)