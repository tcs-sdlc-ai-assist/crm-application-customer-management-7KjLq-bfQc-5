from django.urls import path

from communications.views import (
    communication_delete_view,
    communication_detail_view,
    communication_edit_view,
    communication_list_view,
    communication_log_view,
    meeting_cancel_view,
    meeting_complete_view,
    meeting_delete_view,
    meeting_detail_view,
    meeting_list_view,
    meeting_schedule_view,
    meeting_update_view,
)

urlpatterns = [
    path('', communication_list_view, name='communication-list'),
    path('log/', communication_log_view, name='communication-create'),
    path('<uuid:pk>/', communication_detail_view, name='communication-detail'),
    path('<uuid:pk>/edit/', communication_edit_view, name='communication-update'),
    path('<uuid:pk>/delete/', communication_delete_view, name='communication-delete'),
    path('meetings/', meeting_list_view, name='meeting-list'),
    path('meetings/schedule/', meeting_schedule_view, name='meeting-create'),
    path('meetings/<uuid:pk>/', meeting_detail_view, name='meeting-detail'),
    path('meetings/<uuid:pk>/edit/', meeting_update_view, name='meeting-update'),
    path('meetings/<uuid:pk>/delete/', meeting_delete_view, name='meeting-delete'),
    path('meetings/<uuid:pk>/cancel/', meeting_cancel_view, name='meeting-cancel'),
    path('meetings/<uuid:pk>/complete/', meeting_complete_view, name='meeting-complete'),
]