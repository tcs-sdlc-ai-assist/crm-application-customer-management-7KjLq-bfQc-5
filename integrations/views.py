import json
import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from integrations.models import IntegrationConfig
from integrations.services import (
    IntegrationError,
    IntegrationNotConfiguredError,
    SlackAdapter,
    get_adapter,
)

logger = logging.getLogger(__name__)


@login_required
@require_http_methods(["GET", "POST"])
def integration_settings_view(request):
    """
    GET: Display integration settings page with current config status.
    POST: Handle disconnect and webhook update actions.
    """
    if request.method == "POST":
        return _handle_integration_post(request)

    gmail_integration = IntegrationConfig.objects.filter(
        user=request.user,
        service_type="gmail",
    ).first()

    google_calendar_integration = IntegrationConfig.objects.filter(
        user=request.user,
        service_type="google_calendar",
    ).first()

    slack_integration = IntegrationConfig.objects.filter(
        user=request.user,
        service_type="slack",
    ).first()

    context = {
        "gmail_integration": gmail_integration,
        "google_calendar_integration": google_calendar_integration,
        "slack_integration": slack_integration,
        "integration_errors": [],
    }

    return render(request, "integrations/integration_settings.html", context)


def _handle_integration_post(request):
    """Route POST actions for integration settings."""
    action = request.POST.get("action", "")

    if "service_type" in request.POST and "webhook_url" in request.POST:
        return _handle_webhook_update(request)

    if "service_type" in request.POST:
        return _handle_disconnect(request)

    messages.error(request, "Invalid action.")
    return redirect("integration-settings")


@login_required
@require_POST
def integration_disconnect_view(request):
    """Disconnect an integration by deactivating its config."""
    service_type = request.POST.get("service_type", "").strip()

    if not service_type:
        messages.error(request, "Service type is required.")
        return redirect("integration-settings")

    valid_service_types = [choice[0] for choice in IntegrationConfig.SERVICE_TYPE_CHOICES]
    if service_type not in valid_service_types:
        messages.error(request, f"Invalid service type: {service_type}")
        return redirect("integration-settings")

    try:
        config = IntegrationConfig.objects.filter(
            user=request.user,
            service_type=service_type,
        ).first()

        if config is None:
            messages.warning(
                request,
                f"{dict(IntegrationConfig.SERVICE_TYPE_CHOICES).get(service_type, service_type)} "
                f"integration is not configured.",
            )
            return redirect("integration-settings")

        config.is_active = False
        config.access_token = ""
        config.refresh_token = ""
        config.token_expiry = None
        config.save(update_fields=[
            "is_active",
            "access_token",
            "refresh_token",
            "token_expiry",
            "updated_at",
        ])

        display_name = dict(IntegrationConfig.SERVICE_TYPE_CHOICES).get(
            service_type, service_type
        )
        messages.success(request, f"{display_name} integration disconnected successfully.")

        logger.info(
            "Integration disconnected: user=%s service=%s",
            request.user.email,
            service_type,
        )
    except Exception as e:
        logger.error(
            "Failed to disconnect integration: user=%s service=%s error=%s",
            request.user.email,
            service_type,
            str(e),
        )
        messages.error(request, "Failed to disconnect integration. Please try again.")

    return redirect("integration-settings")


@login_required
@require_POST
def integration_webhook_update_view(request):
    """Update or create a webhook-based integration (e.g., Slack)."""
    return _handle_webhook_update(request)


def _handle_webhook_update(request):
    """Handle webhook URL update for an integration."""
    service_type = request.POST.get("service_type", "").strip()
    webhook_url = request.POST.get("webhook_url", "").strip()

    if not service_type:
        messages.error(request, "Service type is required.")
        return redirect("integration-settings")

    if not webhook_url:
        messages.error(request, "Webhook URL is required.")
        return redirect("integration-settings")

    if not webhook_url.startswith("https://"):
        messages.error(request, "Webhook URL must use HTTPS.")
        return redirect("integration-settings")

    try:
        config, created = IntegrationConfig.objects.get_or_create(
            user=request.user,
            service_type=service_type,
            defaults={
                "webhook_url": webhook_url,
                "is_active": True,
            },
        )

        if not created:
            config.webhook_url = webhook_url
            config.is_active = True
            config.save(update_fields=["webhook_url", "is_active", "updated_at"])

        display_name = dict(IntegrationConfig.SERVICE_TYPE_CHOICES).get(
            service_type, service_type
        )

        if created:
            messages.success(request, f"{display_name} integration connected successfully.")
        else:
            messages.success(request, f"{display_name} webhook URL updated successfully.")

        logger.info(
            "Webhook updated: user=%s service=%s created=%s",
            request.user.email,
            service_type,
            created,
        )
    except Exception as e:
        logger.error(
            "Failed to update webhook: user=%s service=%s error=%s",
            request.user.email,
            service_type,
            str(e),
        )
        messages.error(request, "Failed to update webhook. Please try again.")

    return redirect("integration-settings")


def _handle_disconnect(request):
    """Handle disconnect action from the settings form."""
    service_type = request.POST.get("service_type", "").strip()

    if not service_type:
        messages.error(request, "Service type is required.")
        return redirect("integration-settings")

    try:
        config = IntegrationConfig.objects.filter(
            user=request.user,
            service_type=service_type,
        ).first()

        if config is None:
            messages.warning(request, "Integration is not configured.")
            return redirect("integration-settings")

        config.is_active = False
        config.access_token = ""
        config.refresh_token = ""
        config.token_expiry = None
        config.save(update_fields=[
            "is_active",
            "access_token",
            "refresh_token",
            "token_expiry",
            "updated_at",
        ])

        display_name = dict(IntegrationConfig.SERVICE_TYPE_CHOICES).get(
            service_type, service_type
        )
        messages.success(request, f"{display_name} integration disconnected successfully.")

        logger.info(
            "Integration disconnected via settings: user=%s service=%s",
            request.user.email,
            service_type,
        )
    except Exception as e:
        logger.error(
            "Failed to disconnect integration via settings: user=%s service=%s error=%s",
            request.user.email,
            service_type,
            str(e),
        )
        messages.error(request, "Failed to disconnect integration. Please try again.")

    return redirect("integration-settings")


@login_required
def integration_oauth_connect_view(request, service_type):
    """
    Initiate OAuth flow for Gmail or Google Calendar.
    In production, this would redirect to Google's OAuth consent screen.
    For now, it simulates the OAuth initiation.
    """
    valid_oauth_services = ["gmail", "google_calendar"]

    if service_type not in valid_oauth_services:
        messages.error(request, f"OAuth is not supported for service: {service_type}")
        return redirect("integration-settings")

    google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
    if not google_client_id:
        google_client_id = __import__("os").environ.get("GOOGLE_CLIENT_ID", "")

    if not google_client_id:
        messages.error(
            request,
            "Google OAuth is not configured. Please contact your administrator.",
        )
        logger.error(
            "Google OAuth not configured: GOOGLE_CLIENT_ID is missing. user=%s service=%s",
            request.user.email,
            service_type,
        )
        return redirect("integration-settings")

    if service_type == "gmail":
        scope = "https://www.googleapis.com/auth/gmail.modify"
        callback_path = "gmail-oauth-callback"
    else:
        scope = "https://www.googleapis.com/auth/calendar"
        callback_path = "google-calendar-oauth-callback"

    site_url = getattr(settings, "SITE_URL", "") or ""
    if not site_url:
        site_url = __import__("os").environ.get("SITE_URL", "http://localhost:8000")

    from django.urls import reverse
    redirect_uri = f"{site_url.rstrip('/')}{reverse(callback_path)}"

    import urllib.parse
    oauth_params = urllib.parse.urlencode({
        "client_id": google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": service_type,
    })

    oauth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{oauth_params}"

    logger.info(
        "Initiating OAuth flow: user=%s service=%s",
        request.user.email,
        service_type,
    )

    return redirect(oauth_url)


@login_required
def gmail_oauth_callback(request):
    """
    Handle Gmail OAuth redirect callback.
    Exchanges the authorization code for access/refresh tokens.
    """
    error = request.GET.get("error", "")
    if error:
        logger.warning(
            "Gmail OAuth error: user=%s error=%s",
            request.user.email,
            error,
        )
        messages.error(request, f"Gmail authorization failed: {error}")
        return redirect("integration-settings")

    code = request.GET.get("code", "").strip()
    if not code:
        messages.error(request, "Authorization code not received from Google.")
        return redirect("integration-settings")

    try:
        tokens = _exchange_oauth_code(code, "gmail", request)

        config, created = IntegrationConfig.objects.get_or_create(
            user=request.user,
            service_type="gmail",
            defaults={
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "token_expiry": tokens.get("token_expiry"),
                "is_active": True,
            },
        )

        if not created:
            config.access_token = tokens.get("access_token", "")
            config.refresh_token = tokens.get("refresh_token", config.refresh_token)
            config.token_expiry = tokens.get("token_expiry")
            config.is_active = True
            config.save(update_fields=[
                "access_token",
                "refresh_token",
                "token_expiry",
                "is_active",
                "updated_at",
            ])

        messages.success(request, "Gmail integration connected successfully.")
        logger.info(
            "Gmail OAuth completed: user=%s created=%s",
            request.user.email,
            created,
        )
    except Exception as e:
        logger.error(
            "Gmail OAuth callback failed: user=%s error=%s",
            request.user.email,
            str(e),
        )
        messages.error(
            request,
            "Failed to connect Gmail. Please try again.",
        )

    return redirect("integration-settings")


@login_required
def google_calendar_oauth_callback(request):
    """
    Handle Google Calendar OAuth redirect callback.
    Exchanges the authorization code for access/refresh tokens.
    """
    error = request.GET.get("error", "")
    if error:
        logger.warning(
            "Google Calendar OAuth error: user=%s error=%s",
            request.user.email,
            error,
        )
        messages.error(request, f"Google Calendar authorization failed: {error}")
        return redirect("integration-settings")

    code = request.GET.get("code", "").strip()
    if not code:
        messages.error(request, "Authorization code not received from Google.")
        return redirect("integration-settings")

    try:
        tokens = _exchange_oauth_code(code, "google_calendar", request)

        config, created = IntegrationConfig.objects.get_or_create(
            user=request.user,
            service_type="google_calendar",
            defaults={
                "access_token": tokens.get("access_token", ""),
                "refresh_token": tokens.get("refresh_token", ""),
                "token_expiry": tokens.get("token_expiry"),
                "is_active": True,
            },
        )

        if not created:
            config.access_token = tokens.get("access_token", "")
            config.refresh_token = tokens.get("refresh_token", config.refresh_token)
            config.token_expiry = tokens.get("token_expiry")
            config.is_active = True
            config.save(update_fields=[
                "access_token",
                "refresh_token",
                "token_expiry",
                "is_active",
                "updated_at",
            ])

        messages.success(request, "Google Calendar integration connected successfully.")
        logger.info(
            "Google Calendar OAuth completed: user=%s created=%s",
            request.user.email,
            created,
        )
    except Exception as e:
        logger.error(
            "Google Calendar OAuth callback failed: user=%s error=%s",
            request.user.email,
            str(e),
        )
        messages.error(
            request,
            "Failed to connect Google Calendar. Please try again.",
        )

    return redirect("integration-settings")


def _exchange_oauth_code(code, service_type, request):
    """
    Exchange an OAuth authorization code for access and refresh tokens.
    In production, this would make an HTTP POST to Google's token endpoint.
    Returns a dict with access_token, refresh_token, and token_expiry.
    """
    import os
    from datetime import timedelta

    google_client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or os.environ.get(
        "GOOGLE_CLIENT_ID", ""
    )
    google_client_secret = getattr(settings, "GOOGLE_CLIENT_SECRET", "") or os.environ.get(
        "GOOGLE_CLIENT_SECRET", ""
    )
    site_url = getattr(settings, "SITE_URL", "") or os.environ.get(
        "SITE_URL", "http://localhost:8000"
    )

    if service_type == "gmail":
        callback_name = "gmail-oauth-callback"
    else:
        callback_name = "google-calendar-oauth-callback"

    from django.urls import reverse
    redirect_uri = f"{site_url.rstrip('/')}{reverse(callback_name)}"

    token_data = {
        "code": code,
        "client_id": google_client_id,
        "client_secret": google_client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }

    try:
        import httpx

        response = httpx.post(
            "https://oauth2.googleapis.com/token",
            data=token_data,
            timeout=30.0,
        )

        if response.status_code >= 400:
            logger.error(
                "OAuth token exchange failed: service=%s status=%d body=%s",
                service_type,
                response.status_code,
                response.text,
            )
            raise IntegrationError(
                f"Token exchange failed with status {response.status_code}"
            )

        data = response.json()
        expires_in = data.get("expires_in", 3600)
        token_expiry = timezone.now() + timedelta(seconds=expires_in)

        return {
            "access_token": data.get("access_token", ""),
            "refresh_token": data.get("refresh_token", ""),
            "token_expiry": token_expiry,
        }
    except ImportError:
        logger.warning(
            "httpx not available, simulating OAuth token exchange for service=%s",
            service_type,
        )
        token_expiry = timezone.now() + timedelta(hours=1)
        return {
            "access_token": f"simulated_access_token_{service_type}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
            "refresh_token": f"simulated_refresh_token_{service_type}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
            "token_expiry": token_expiry,
        }
    except IntegrationError:
        raise
    except Exception as e:
        logger.error(
            "OAuth token exchange error: service=%s error=%s",
            service_type,
            str(e),
        )
        raise IntegrationError(f"OAuth token exchange failed: {str(e)}") from e


@csrf_exempt
@require_POST
def slack_webhook_view(request):
    """
    POST endpoint for receiving Slack incoming webhooks.
    Handles Slack URL verification challenges and event callbacks.
    """
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        logger.warning("Slack webhook received invalid JSON payload.")
        return JsonResponse(
            {"error": "Invalid JSON payload"},
            status=400,
        )

    event_type = body.get("type", "")

    if event_type == "url_verification":
        challenge = body.get("challenge", "")
        logger.info("Slack URL verification challenge received.")
        return JsonResponse({"challenge": challenge})

    if event_type == "event_callback":
        event = body.get("event", {})
        event_subtype = event.get("type", "")

        logger.info(
            "Slack event received: type=%s subtype=%s",
            event_type,
            event_subtype,
        )

        try:
            _process_slack_event(event)
        except Exception as e:
            logger.error(
                "Failed to process Slack event: type=%s error=%s",
                event_subtype,
                str(e),
            )

        return JsonResponse({"status": "ok"})

    logger.info("Slack webhook received unknown type: %s", event_type)
    return JsonResponse({"status": "ok"})


def _process_slack_event(event):
    """
    Process a Slack event callback.
    Handles message events and other Slack interactions.
    """
    event_type = event.get("type", "")
    channel = event.get("channel", "")
    user = event.get("user", "")
    text = event.get("text", "")

    logger.info(
        "Processing Slack event: type=%s channel=%s user=%s text_preview=%s",
        event_type,
        channel,
        user,
        text[:100] if text else "",
    )


@login_required
@require_GET
def integration_status_view(request):
    """
    GET endpoint returning the status of all integrations for the current user.
    Returns JSON with status of each integration service.
    """
    integrations = IntegrationConfig.objects.filter(user=request.user)

    status_map = {}
    for choice_value, choice_label in IntegrationConfig.SERVICE_TYPE_CHOICES:
        status_map[choice_value] = {
            "service_type": choice_value,
            "display_name": choice_label,
            "is_active": False,
            "is_configured": False,
            "token_expiry": None,
            "webhook_url": "",
            "created_at": None,
            "updated_at": None,
        }

    for config in integrations:
        token_expiry_str = None
        if config.token_expiry:
            token_expiry_str = config.token_expiry.isoformat()

        is_token_valid = True
        if config.token_expiry and config.token_expiry < timezone.now():
            is_token_valid = False

        created_at_str = None
        if config.created_at:
            created_at_str = config.created_at.isoformat()

        updated_at_str = None
        if config.updated_at:
            updated_at_str = config.updated_at.isoformat()

        status_map[config.service_type] = {
            "service_type": config.service_type,
            "display_name": config.get_service_type_display(),
            "is_active": config.is_active,
            "is_configured": True,
            "is_token_valid": is_token_valid,
            "token_expiry": token_expiry_str,
            "webhook_url": bool(config.webhook_url),
            "created_at": created_at_str,
            "updated_at": updated_at_str,
        }

    return JsonResponse({
        "integrations": list(status_map.values()),
        "user": str(request.user.pk),
    })