from django.urls import path

from tasks.views import (
    task_complete_view,
    task_create_view,
    task_dashboard_view,
    task_delete_view,
    task_detail_view,
    task_edit_view,
    task_list_view,
)

urlpatterns = [
    path('', task_list_view, name='task-list'),
    path('create/', task_create_view, name='task-create'),
    path('dashboard/', task_dashboard_view, name='task-dashboard'),
    path('<uuid:pk>/', task_detail_view, name='task-detail'),
    path('<uuid:pk>/edit/', task_edit_view, name='task-update'),
    path('<uuid:pk>/delete/', task_delete_view, name='task-delete'),
    path('<uuid:pk>/complete/', task_complete_view, name='task-complete'),
]