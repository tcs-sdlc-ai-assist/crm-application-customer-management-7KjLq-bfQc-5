from django.contrib import admin
from django.urls import include, path
from django.shortcuts import redirect

from core.dashboard_views import dashboard_view


def home_redirect(request):
    if request.user.is_authenticated:
        return redirect("home")
    return redirect("login")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", dashboard_view, name="home"),
    path("accounts/", include("accounts.urls")),
    path("customers/", include("customers.urls")),
    path("deals/", include("deals.urls")),
    path("communications/", include("communications.urls")),
    path("tasks/", include("tasks.urls")),
    path("automation/", include("automation.urls")),
    path("reports/", include("reports.urls")),
    path("integrations/", include("integrations.urls")),
    path("audit-logs/", include("audit_logs.urls")),
]