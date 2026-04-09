from django.urls import path

from automation.views import (
    automation_log_list_view,
    automation_rule_create_view,
    automation_rule_delete_view,
    automation_rule_detail_view,
    automation_rule_edit_view,
    automation_rule_list_view,
)

urlpatterns = [
    path('', automation_rule_list_view, name='automation-list'),
    path('create/', automation_rule_create_view, name='automation-rule-create'),
    path('<uuid:pk>/', automation_rule_detail_view, name='automation-rule-detail'),
    path('<uuid:pk>/edit/', automation_rule_edit_view, name='automation-rule-update'),
    path('<uuid:pk>/delete/', automation_rule_delete_view, name='automation-rule-delete'),
    path('logs/', automation_log_list_view, name='automation-log-list'),
]