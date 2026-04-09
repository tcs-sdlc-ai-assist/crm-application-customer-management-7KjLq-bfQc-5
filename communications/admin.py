from django.contrib import admin

from .models import CommunicationLog, Meeting


@admin.register(CommunicationLog)
class CommunicationLogAdmin(admin.ModelAdmin):
    list_display = (
        "subject",
        "customer",
        "user",
        "communication_type",
        "direction",
        "logged_at",
        "created_at",
    )
    list_filter = (
        "communication_type",
        "direction",
        "logged_at",
        "created_at",
    )
    search_fields = (
        "subject",
        "body",
        "customer__name",
        "customer__email",
        "user__email",
        "user__first_name",
        "user__last_name",
    )
    readonly_fields = ("id", "created_at")
    ordering = ("-logged_at",)
    list_per_page = 25
    list_select_related = ("customer", "user")
    raw_id_fields = ("customer", "user")


@admin.register(Meeting)
class MeetingAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "customer",
        "organizer",
        "start_time",
        "end_time",
        "status",
        "location",
        "created_at",
    )
    list_filter = (
        "status",
        "start_time",
        "created_at",
    )
    search_fields = (
        "title",
        "description",
        "location",
        "customer__name",
        "customer__email",
        "organizer__email",
        "organizer__first_name",
        "organizer__last_name",
    )
    readonly_fields = ("id", "created_at", "updated_at")
    ordering = ("-start_time",)
    list_per_page = 25
    list_select_related = ("customer", "organizer", "communication_log")
    raw_id_fields = ("customer", "organizer", "communication_log")