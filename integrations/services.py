import logging
import json
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class IntegrationError(Exception):
    """Base exception for integration errors."""
    pass


class TokenExpiredError(IntegrationError):
    """Raised when an OAuth token has expired and cannot be refreshed."""
    pass


class IntegrationNotConfiguredError(IntegrationError):
    """Raised when an integration is not configured for a user."""
    pass


class BaseAdapter:
    """
    Base adapter class for all external integrations.
    Handles common OAuth token management and configuration loading.
    """

    service_type = None

    def __init__(self, user=None, config=None):
        self.user = user
        self.config = config
        self._access_token = None
        self._refresh_token = None
        self._token_expiry = None

        if config is not None:
            self._access_token = config.access_token
            self._refresh_token = config.refresh_token
            self._token_expiry = config.token_expiry
        elif user is not None:
            self._load_config_from_user(user)

    def _load_config_from_user(self, user):
        """Load integration configuration from the database for the given user."""
        try:
            from integrations.models import IntegrationConfig
            config = IntegrationConfig.objects.filter(
                user=user,
                service_type=self.service_type,
                is_active=True,
            ).first()
            if config is None:
                raise IntegrationNotConfiguredError(
                    f"{self.service_type} integration is not configured for user {user}."
                )
            self.config = config
            self._access_token = config.access_token
            self._refresh_token = config.refresh_token
            self._token_expiry = config.token_expiry
        except IntegrationNotConfiguredError:
            raise
        except Exception as e:
            logger.error(
                "Failed to load integration config for user=%s service=%s: %s",
                user,
                self.service_type,
                str(e),
            )
            raise IntegrationError(
                f"Failed to load {self.service_type} integration configuration."
            ) from e

    def _is_token_expired(self):
        """Check if the current access token has expired."""
        if self._token_expiry is None:
            return False
        now = timezone.now()
        buffer = timedelta(minutes=5)
        return now >= (self._token_expiry - buffer)

    def _refresh_access_token(self):
        """
        Refresh the OAuth access token using the refresh token.
        In a production environment, this would make an HTTP call to the
        OAuth provider's token endpoint.
        """
        if not self._refresh_token:
            raise TokenExpiredError(
                f"No refresh token available for {self.service_type}. "
                "User must re-authenticate."
            )

        try:
            logger.info(
                "Refreshing access token for user=%s service=%s",
                self.user,
                self.service_type,
            )
            new_access_token = self._perform_token_refresh(self._refresh_token)
            self._access_token = new_access_token
            self._token_expiry = timezone.now() + timedelta(hours=1)

            if self.config is not None:
                self.config.access_token = self._access_token
                self.config.token_expiry = self._token_expiry
                self.config.save(update_fields=["access_token", "token_expiry", "updated_at"])

            logger.info(
                "Successfully refreshed access token for user=%s service=%s",
                self.user,
                self.service_type,
            )
        except Exception as e:
            logger.error(
                "Failed to refresh access token for user=%s service=%s: %s",
                self.user,
                self.service_type,
                str(e),
            )
            raise TokenExpiredError(
                f"Failed to refresh {self.service_type} access token. "
                "User must re-authenticate."
            ) from e

    def _perform_token_refresh(self, refresh_token):
        """
        Perform the actual token refresh HTTP call.
        Subclasses can override this for provider-specific refresh logic.
        Returns the new access token string.
        """
        logger.warning(
            "Token refresh not implemented for %s. "
            "Override _perform_token_refresh in subclass.",
            self.service_type,
        )
        return self._access_token

    def _ensure_valid_token(self):
        """Ensure the access token is valid, refreshing if necessary."""
        if self._is_token_expired():
            self._refresh_access_token()

    def _get_headers(self):
        """Return authorization headers for API requests."""
        self._ensure_valid_token()
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }


class GmailAdapter(BaseAdapter):
    """
    Adapter for Gmail integration.
    Handles sending emails, fetching emails, and logging email communications.
    """

    service_type = "gmail"

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        cc: Optional[List[str]] = None,
        bcc: Optional[List[str]] = None,
        html_body: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send an email via Gmail API.

        Args:
            to: Recipient email address.
            subject: Email subject line.
            body: Plain text email body.
            cc: Optional list of CC recipients.
            bcc: Optional list of BCC recipients.
            html_body: Optional HTML email body.

        Returns:
            Dictionary with email_id and status.
        """
        if not to:
            raise IntegrationError("Recipient email address is required.")
        if not subject:
            raise IntegrationError("Email subject is required.")

        try:
            self._ensure_valid_token()

            email_payload = {
                "to": to,
                "subject": subject,
                "body": body,
            }
            if cc:
                email_payload["cc"] = cc
            if bcc:
                email_payload["bcc"] = bcc
            if html_body:
                email_payload["html_body"] = html_body

            logger.info(
                "Sending email via Gmail: to=%s subject=%s user=%s",
                to,
                subject,
                self.user,
            )

            email_id = self._send_gmail_message(email_payload)

            logger.info(
                "Email sent successfully via Gmail: email_id=%s to=%s user=%s",
                email_id,
                to,
                self.user,
            )

            return {
                "email_id": email_id,
                "status": "sent",
                "to": to,
                "subject": subject,
            }
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to send email via Gmail: to=%s subject=%s user=%s error=%s",
                to,
                subject,
                self.user,
                str(e),
            )
            raise IntegrationError(f"Failed to send email via Gmail: {str(e)}") from e

    def _send_gmail_message(self, email_payload: Dict[str, Any]) -> str:
        """
        Perform the actual Gmail API call to send a message.
        In production, this would use the Gmail API client.
        Returns the message ID.
        """
        try:
            import httpx

            headers = self._get_headers()
            response = httpx.post(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers=headers,
                json=email_payload,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TokenExpiredError("Gmail access token is invalid or expired.")
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Gmail API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            return data.get("id", "")
        except (TokenExpiredError, IntegrationError):
            raise
        except ImportError:
            logger.warning("httpx not available, simulating Gmail send.")
            return f"gmail_msg_{timezone.now().strftime('%Y%m%d%H%M%S')}"
        except Exception as e:
            raise IntegrationError(f"Gmail API call failed: {str(e)}") from e

    def fetch_emails(
        self,
        max_results: int = 20,
        query: Optional[str] = None,
        after_date: Optional[datetime] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch emails from Gmail.

        Args:
            max_results: Maximum number of emails to fetch.
            query: Optional Gmail search query string.
            after_date: Optional date to fetch emails after.

        Returns:
            List of email dictionaries with id, subject, from, date, snippet.
        """
        try:
            self._ensure_valid_token()

            params = {"maxResults": min(max_results, 100)}
            if query:
                params["q"] = query
            if after_date:
                timestamp = int(after_date.timestamp())
                q_part = f"after:{timestamp}"
                params["q"] = f"{params.get('q', '')} {q_part}".strip()

            logger.info(
                "Fetching emails from Gmail: user=%s max_results=%d query=%s",
                self.user,
                max_results,
                params.get("q"),
            )

            emails = self._fetch_gmail_messages(params)

            logger.info(
                "Fetched %d emails from Gmail for user=%s",
                len(emails),
                self.user,
            )

            return emails
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to fetch emails from Gmail: user=%s error=%s",
                self.user,
                str(e),
            )
            raise IntegrationError(f"Failed to fetch emails from Gmail: {str(e)}") from e

    def _fetch_gmail_messages(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Perform the actual Gmail API call to list/fetch messages.
        Returns a list of email dictionaries.
        """
        try:
            import httpx

            headers = self._get_headers()
            response = httpx.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers=headers,
                params=params,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TokenExpiredError("Gmail access token is invalid or expired.")
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Gmail API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            messages = data.get("messages", [])
            return [
                {
                    "id": msg.get("id", ""),
                    "thread_id": msg.get("threadId", ""),
                }
                for msg in messages
            ]
        except (TokenExpiredError, IntegrationError):
            raise
        except ImportError:
            logger.warning("httpx not available, returning empty email list.")
            return []
        except Exception as e:
            raise IntegrationError(f"Gmail API call failed: {str(e)}") from e

    def log_email(
        self,
        customer_id: str,
        subject: str,
        direction: str = "outbound",
        notes: str = "",
        external_id: str = "",
        deal_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Log an email communication in the CRM system.

        Args:
            customer_id: The customer UUID.
            subject: Email subject.
            direction: 'inbound' or 'outbound'.
            notes: Additional notes about the email.
            external_id: External email ID (e.g., Gmail message ID).
            deal_id: Optional related deal UUID.

        Returns:
            Dictionary with the logged communication details.
        """
        if not customer_id:
            raise IntegrationError("customer_id is required to log an email.")
        if direction not in ("inbound", "outbound"):
            raise IntegrationError("direction must be 'inbound' or 'outbound'.")

        try:
            from communications.models import Communication

            comm_data = {
                "customer_id": customer_id,
                "comm_type": "email",
                "direction": direction,
                "subject": subject,
                "notes": notes,
                "external_id": external_id,
            }
            if deal_id:
                comm_data["deal_id"] = deal_id
            if self.user:
                comm_data["created_by"] = self.user

            communication = Communication.objects.create(**comm_data)

            logger.info(
                "Logged email communication: id=%s customer=%s subject=%s user=%s",
                communication.id,
                customer_id,
                subject,
                self.user,
            )

            return {
                "communication_id": str(communication.id),
                "status": "logged",
                "comm_type": "email",
                "subject": subject,
            }
        except IntegrationError:
            raise
        except Exception as e:
            logger.warning(
                "Failed to log email communication via model, returning dict: %s",
                str(e),
            )
            return {
                "communication_id": None,
                "status": "logged_locally",
                "comm_type": "email",
                "subject": subject,
                "customer_id": customer_id,
                "direction": direction,
                "notes": notes,
                "external_id": external_id,
            }


class GoogleCalendarAdapter(BaseAdapter):
    """
    Adapter for Google Calendar integration.
    Handles creating, updating, deleting, and syncing calendar events.
    """

    service_type = "google_calendar"

    CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"

    def create_event(
        self,
        title: str,
        start_time: datetime,
        end_time: datetime,
        description: str = "",
        location: str = "",
        attendees: Optional[List[str]] = None,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Create a calendar event via Google Calendar API.

        Args:
            title: Event title/summary.
            start_time: Event start datetime.
            end_time: Event end datetime.
            description: Event description.
            location: Event location.
            attendees: List of attendee email addresses.
            calendar_id: Google Calendar ID (default: 'primary').

        Returns:
            Dictionary with event_id, status, and link.
        """
        if not title:
            raise IntegrationError("Event title is required.")
        if not start_time or not end_time:
            raise IntegrationError("Event start_time and end_time are required.")
        if end_time <= start_time:
            raise IntegrationError("Event end_time must be after start_time.")

        try:
            self._ensure_valid_token()

            event_payload = {
                "summary": title,
                "description": description,
                "location": location,
                "start": {
                    "dateTime": start_time.isoformat(),
                    "timeZone": str(settings.TIME_ZONE),
                },
                "end": {
                    "dateTime": end_time.isoformat(),
                    "timeZone": str(settings.TIME_ZONE),
                },
            }
            if attendees:
                event_payload["attendees"] = [
                    {"email": email} for email in attendees
                ]

            logger.info(
                "Creating calendar event: title=%s start=%s end=%s user=%s",
                title,
                start_time.isoformat(),
                end_time.isoformat(),
                self.user,
            )

            result = self._create_calendar_event(calendar_id, event_payload)

            logger.info(
                "Calendar event created: event_id=%s title=%s user=%s",
                result.get("event_id"),
                title,
                self.user,
            )

            return result
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to create calendar event: title=%s user=%s error=%s",
                title,
                self.user,
                str(e),
            )
            raise IntegrationError(
                f"Failed to create calendar event: {str(e)}"
            ) from e

    def _create_calendar_event(
        self, calendar_id: str, event_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform the actual Google Calendar API call to create an event."""
        try:
            import httpx

            headers = self._get_headers()
            url = f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events"
            response = httpx.post(
                url,
                headers=headers,
                json=event_payload,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TokenExpiredError(
                    "Google Calendar access token is invalid or expired."
                )
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Google Calendar API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            return {
                "event_id": data.get("id", ""),
                "status": "created",
                "link": data.get("htmlLink", ""),
            }
        except (TokenExpiredError, IntegrationError):
            raise
        except ImportError:
            logger.warning("httpx not available, simulating calendar event creation.")
            return {
                "event_id": f"gcal_evt_{timezone.now().strftime('%Y%m%d%H%M%S')}",
                "status": "created",
                "link": "",
            }
        except Exception as e:
            raise IntegrationError(
                f"Google Calendar API call failed: {str(e)}"
            ) from e

    def update_event(
        self,
        event_id: str,
        title: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        description: Optional[str] = None,
        location: Optional[str] = None,
        attendees: Optional[List[str]] = None,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Update an existing calendar event.

        Args:
            event_id: The Google Calendar event ID.
            title: Updated event title.
            start_time: Updated start datetime.
            end_time: Updated end datetime.
            description: Updated description.
            location: Updated location.
            attendees: Updated list of attendee emails.
            calendar_id: Google Calendar ID.

        Returns:
            Dictionary with event_id and status.
        """
        if not event_id:
            raise IntegrationError("event_id is required to update an event.")

        if start_time and end_time and end_time <= start_time:
            raise IntegrationError("Event end_time must be after start_time.")

        try:
            self._ensure_valid_token()

            patch_payload = {}
            if title is not None:
                patch_payload["summary"] = title
            if description is not None:
                patch_payload["description"] = description
            if location is not None:
                patch_payload["location"] = location
            if start_time is not None:
                patch_payload["start"] = {
                    "dateTime": start_time.isoformat(),
                    "timeZone": str(settings.TIME_ZONE),
                }
            if end_time is not None:
                patch_payload["end"] = {
                    "dateTime": end_time.isoformat(),
                    "timeZone": str(settings.TIME_ZONE),
                }
            if attendees is not None:
                patch_payload["attendees"] = [
                    {"email": email} for email in attendees
                ]

            if not patch_payload:
                return {"event_id": event_id, "status": "no_changes"}

            logger.info(
                "Updating calendar event: event_id=%s user=%s",
                event_id,
                self.user,
            )

            result = self._update_calendar_event(calendar_id, event_id, patch_payload)

            logger.info(
                "Calendar event updated: event_id=%s user=%s",
                event_id,
                self.user,
            )

            return result
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to update calendar event: event_id=%s user=%s error=%s",
                event_id,
                self.user,
                str(e),
            )
            raise IntegrationError(
                f"Failed to update calendar event: {str(e)}"
            ) from e

    def _update_calendar_event(
        self, calendar_id: str, event_id: str, patch_payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Perform the actual Google Calendar API call to update an event."""
        try:
            import httpx

            headers = self._get_headers()
            url = f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}"
            response = httpx.patch(
                url,
                headers=headers,
                json=patch_payload,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TokenExpiredError(
                    "Google Calendar access token is invalid or expired."
                )
            if response.status_code == 404:
                raise IntegrationError(
                    f"Calendar event not found: {event_id}"
                )
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Google Calendar API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            return {
                "event_id": data.get("id", event_id),
                "status": "updated",
                "link": data.get("htmlLink", ""),
            }
        except (TokenExpiredError, IntegrationError):
            raise
        except ImportError:
            logger.warning("httpx not available, simulating calendar event update.")
            return {
                "event_id": event_id,
                "status": "updated",
                "link": "",
            }
        except Exception as e:
            raise IntegrationError(
                f"Google Calendar API call failed: {str(e)}"
            ) from e

    def delete_event(
        self,
        event_id: str,
        calendar_id: str = "primary",
    ) -> Dict[str, Any]:
        """
        Delete a calendar event.

        Args:
            event_id: The Google Calendar event ID.
            calendar_id: Google Calendar ID.

        Returns:
            Dictionary with event_id and status.
        """
        if not event_id:
            raise IntegrationError("event_id is required to delete an event.")

        try:
            self._ensure_valid_token()

            logger.info(
                "Deleting calendar event: event_id=%s user=%s",
                event_id,
                self.user,
            )

            result = self._delete_calendar_event(calendar_id, event_id)

            logger.info(
                "Calendar event deleted: event_id=%s user=%s",
                event_id,
                self.user,
            )

            return result
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to delete calendar event: event_id=%s user=%s error=%s",
                event_id,
                self.user,
                str(e),
            )
            raise IntegrationError(
                f"Failed to delete calendar event: {str(e)}"
            ) from e

    def _delete_calendar_event(
        self, calendar_id: str, event_id: str
    ) -> Dict[str, Any]:
        """Perform the actual Google Calendar API call to delete an event."""
        try:
            import httpx

            headers = self._get_headers()
            url = f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events/{event_id}"
            response = httpx.delete(
                url,
                headers=headers,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TokenExpiredError(
                    "Google Calendar access token is invalid or expired."
                )
            if response.status_code == 404:
                raise IntegrationError(
                    f"Calendar event not found: {event_id}"
                )
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Google Calendar API returned status {response.status_code}: {response.text}"
                )
            return {
                "event_id": event_id,
                "status": "deleted",
            }
        except (TokenExpiredError, IntegrationError):
            raise
        except ImportError:
            logger.warning("httpx not available, simulating calendar event deletion.")
            return {
                "event_id": event_id,
                "status": "deleted",
            }
        except Exception as e:
            raise IntegrationError(
                f"Google Calendar API call failed: {str(e)}"
            ) from e

    def sync_events(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        calendar_id: str = "primary",
    ) -> List[Dict[str, Any]]:
        """
        Sync calendar events from Google Calendar.

        Args:
            start_date: Start of the sync window.
            end_date: End of the sync window.
            calendar_id: Google Calendar ID.

        Returns:
            List of event dictionaries.
        """
        try:
            self._ensure_valid_token()

            if start_date is None:
                start_date = timezone.now()
            if end_date is None:
                end_date = start_date + timedelta(days=30)

            params = {
                "timeMin": start_date.isoformat(),
                "timeMax": end_date.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 250,
            }

            logger.info(
                "Syncing calendar events: start=%s end=%s user=%s",
                start_date.isoformat(),
                end_date.isoformat(),
                self.user,
            )

            events = self._list_calendar_events(calendar_id, params)

            logger.info(
                "Synced %d calendar events for user=%s",
                len(events),
                self.user,
            )

            return events
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to sync calendar events: user=%s error=%s",
                self.user,
                str(e),
            )
            raise IntegrationError(
                f"Failed to sync calendar events: {str(e)}"
            ) from e

    def _list_calendar_events(
        self, calendar_id: str, params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Perform the actual Google Calendar API call to list events."""
        try:
            import httpx

            headers = self._get_headers()
            url = f"{self.CALENDAR_API_BASE}/calendars/{calendar_id}/events"
            response = httpx.get(
                url,
                headers=headers,
                params=params,
                timeout=30.0,
            )
            if response.status_code == 401:
                raise TokenExpiredError(
                    "Google Calendar access token is invalid or expired."
                )
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Google Calendar API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            items = data.get("items", [])
            return [
                {
                    "event_id": item.get("id", ""),
                    "title": item.get("summary", ""),
                    "description": item.get("description", ""),
                    "location": item.get("location", ""),
                    "start_time": item.get("start", {}).get("dateTime", ""),
                    "end_time": item.get("end", {}).get("dateTime", ""),
                    "status": item.get("status", ""),
                    "link": item.get("htmlLink", ""),
                    "attendees": [
                        a.get("email", "")
                        for a in item.get("attendees", [])
                    ],
                }
                for item in items
            ]
        except (TokenExpiredError, IntegrationError):
            raise
        except ImportError:
            logger.warning("httpx not available, returning empty event list.")
            return []
        except Exception as e:
            raise IntegrationError(
                f"Google Calendar API call failed: {str(e)}"
            ) from e


class SlackAdapter(BaseAdapter):
    """
    Adapter for Slack integration.
    Handles sending notifications and channel messages via Slack webhooks and API.
    """

    service_type = "slack"

    def send_notification(
        self,
        message: str,
        channel: Optional[str] = None,
        username: str = "CRM Bot",
        icon_emoji: str = ":robot_face:",
    ) -> Dict[str, Any]:
        """
        Send a notification to Slack via webhook.

        Args:
            message: The notification message text.
            channel: Optional Slack channel override.
            username: Display name for the bot.
            icon_emoji: Emoji icon for the bot.

        Returns:
            Dictionary with status.
        """
        if not message:
            raise IntegrationError("Notification message is required.")

        try:
            webhook_url = self._get_webhook_url()

            payload = {
                "text": message,
                "username": username,
                "icon_emoji": icon_emoji,
            }
            if channel:
                payload["channel"] = channel

            logger.info(
                "Sending Slack notification: channel=%s user=%s",
                channel or "default",
                self.user,
            )

            result = self._post_webhook(webhook_url, payload)

            logger.info(
                "Slack notification sent: channel=%s user=%s",
                channel or "default",
                self.user,
            )

            return result
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to send Slack notification: user=%s error=%s",
                self.user,
                str(e),
            )
            raise IntegrationError(
                f"Failed to send Slack notification: {str(e)}"
            ) from e

    def send_channel_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None,
        thread_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a message to a Slack channel via the Slack API.

        Args:
            channel: Slack channel ID or name.
            text: Message text (used as fallback for blocks).
            blocks: Optional Slack Block Kit blocks.
            thread_ts: Optional thread timestamp for threaded replies.

        Returns:
            Dictionary with message_ts and status.
        """
        if not channel:
            raise IntegrationError("Slack channel is required.")
        if not text:
            raise IntegrationError("Message text is required.")

        try:
            self._ensure_valid_token()

            payload = {
                "channel": channel,
                "text": text,
            }
            if blocks:
                payload["blocks"] = blocks
            if thread_ts:
                payload["thread_ts"] = thread_ts

            logger.info(
                "Sending Slack channel message: channel=%s user=%s",
                channel,
                self.user,
            )

            result = self._post_slack_message(payload)

            logger.info(
                "Slack channel message sent: channel=%s ts=%s user=%s",
                channel,
                result.get("message_ts"),
                self.user,
            )

            return result
        except IntegrationError:
            raise
        except Exception as e:
            logger.error(
                "Failed to send Slack channel message: channel=%s user=%s error=%s",
                channel,
                self.user,
                str(e),
            )
            raise IntegrationError(
                f"Failed to send Slack channel message: {str(e)}"
            ) from e

    def _get_webhook_url(self) -> str:
        """Get the Slack webhook URL from config or settings."""
        if self.config and self.config.webhook_url:
            return self.config.webhook_url

        webhook_url = getattr(settings, "SLACK_WEBHOOK_URL", "")
        if not webhook_url:
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL", "")

        if not webhook_url:
            raise IntegrationNotConfiguredError(
                "Slack webhook URL is not configured. "
                "Set SLACK_WEBHOOK_URL in settings or configure the integration."
            )

        return webhook_url

    def _post_webhook(
        self, webhook_url: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post a message to a Slack webhook URL."""
        try:
            import httpx

            response = httpx.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0,
            )
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Slack webhook returned status {response.status_code}: {response.text}"
                )
            return {"status": "sent"}
        except IntegrationError:
            raise
        except ImportError:
            logger.warning("httpx not available, simulating Slack webhook post.")
            return {"status": "sent"}
        except Exception as e:
            raise IntegrationError(
                f"Slack webhook call failed: {str(e)}"
            ) from e

    def _post_slack_message(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Post a message via the Slack chat.postMessage API."""
        try:
            import httpx

            headers = self._get_headers()
            response = httpx.post(
                "https://slack.com/api/chat.postMessage",
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            if response.status_code >= 400:
                raise IntegrationError(
                    f"Slack API returned status {response.status_code}: {response.text}"
                )
            data = response.json()
            if not data.get("ok", False):
                error_msg = data.get("error", "Unknown Slack API error")
                raise IntegrationError(f"Slack API error: {error_msg}")
            return {
                "message_ts": data.get("ts", ""),
                "channel": data.get("channel", payload.get("channel", "")),
                "status": "sent",
            }
        except IntegrationError:
            raise
        except ImportError:
            logger.warning("httpx not available, simulating Slack message post.")
            return {
                "message_ts": f"slack_ts_{timezone.now().strftime('%Y%m%d%H%M%S')}",
                "channel": payload.get("channel", ""),
                "status": "sent",
            }
        except Exception as e:
            raise IntegrationError(
                f"Slack API call failed: {str(e)}"
            ) from e


# Import os at module level for SlackAdapter._get_webhook_url
import os


_ADAPTER_REGISTRY = {
    "gmail": GmailAdapter,
    "google_calendar": GoogleCalendarAdapter,
    "slack": SlackAdapter,
}


def get_adapter(service_type: str, user=None, config=None) -> BaseAdapter:
    """
    Factory method to get the appropriate integration adapter.

    Args:
        service_type: The type of integration ('gmail', 'google_calendar', 'slack').
        user: Optional user instance for loading configuration.
        config: Optional IntegrationConfig instance.

    Returns:
        An instance of the appropriate adapter class.

    Raises:
        IntegrationError: If the service_type is not supported.
    """
    adapter_class = _ADAPTER_REGISTRY.get(service_type)
    if adapter_class is None:
        supported = ", ".join(sorted(_ADAPTER_REGISTRY.keys()))
        raise IntegrationError(
            f"Unsupported integration service type: '{service_type}'. "
            f"Supported types: {supported}"
        )

    return adapter_class(user=user, config=config)