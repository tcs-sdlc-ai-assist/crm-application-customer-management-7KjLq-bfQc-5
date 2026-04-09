from django.urls import path

from audit_logs.views import audit_log_list_view

urlpatterns = [
    path('', audit_log_list_view, name='audit-log-list'),
]