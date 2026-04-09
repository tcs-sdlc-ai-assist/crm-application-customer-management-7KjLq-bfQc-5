from django.urls import path

from integrations.views import (
    gmail_oauth_callback,
    google_calendar_oauth_callback,
    integration_disconnect_view,
    integration_oauth_connect_view,
    integration_settings_view,
    integration_status_view,
    integration_webhook_update_view,
    slack_webhook_view,
)

urlpatterns = [
    path('settings/', integration_settings_view, name='integration-settings'),
    path('disconnect/', integration_disconnect_view, name='integration-disconnect'),
    path('webhook-update/', integration_webhook_update_view, name='integration-webhook-update'),
    path('oauth/connect/<str:service_type>/', integration_oauth_connect_view, name='integration-oauth-connect'),
    path('gmail/callback/', gmail_oauth_callback, name='gmail-oauth-callback'),
    path('calendar/callback/', google_calendar_oauth_callback, name='google-calendar-oauth-callback'),
    path('slack/webhook/', slack_webhook_view, name='slack-webhook'),
    path('status/', integration_status_view, name='integration-status'),
]