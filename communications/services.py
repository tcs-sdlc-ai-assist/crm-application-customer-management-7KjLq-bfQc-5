import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.db import IntegrityError, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from audit_logs.models import AuditLog
from communications.models import CommunicationLog, Meeting
from customers.models import Customer

logger = logging.getLogger(__name__)


class CommunicationLogService:
    """
    Business logic service for communication logging operations.
    Wraps repository operations with validation and audit logging.
    """

    def log_communication(
        self,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> CommunicationLog:
        """
        Log a new communication (call, email, or meeting).

        Args:
            data: Dictionary containing communication fields:
                - customer_id: UUID of the customer (required)
                - communication_type: 'call', 'email', or 'meeting' (required)
                - subject: Subject line (optional)
                - body: Communication body/notes (optional)
                - direction: 'inbound' or 'outbound' (optional)
                - logged_at: Datetime of the communication (optional, defaults to now)
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The newly created CommunicationLog instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
            Customer.DoesNotExist: If the customer does not exist.
        """
        self._validate_required_fields(data, ["customer_id", "communication_type"])
        self._validate_communication_type(data["communication_type"])

        if "direction" in data and data["direction"]:
            self._validate_direction(data["direction"])

        customer = self._get_customer(data["customer_id"])

        with transaction.atomic():
            comm_data = {
                "customer": customer,
                "communication_type": data["communication_type"],
                "subject": data.get("subject", "").strip() if data.get("subject") else "",
                "body": data.get("body", "").strip() if data.get("body") else "",
                "direction": data.get("direction", "").strip() if data.get("direction") else "",
            }

            if data.get("logged_at"):
                comm_data["logged_at"] = data["logged_at"]
            else:
                comm_data["logged_at"] = timezone.now()

            if user is not None and hasattr(user, "pk"):
                comm_data["user"] = user

            communication = CommunicationLog.objects.create(**comm_data)

            self._log_audit(
                entity_type="CommunicationLog",
                entity_id=communication.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={
                    "created": {
                        "customer_id": str(customer.pk),
                        "communication_type": comm_data["communication_type"],
                        "subject": comm_data["subject"],
                        "direction": comm_data["direction"],
                    }
                },
                ip_address=ip_address,
            )

        logger.info(
            "Communication logged: id=%s type=%s customer=%s user=%s",
            communication.pk,
            communication.communication_type,
            customer.pk,
            user,
        )

        return communication

    def get_communication(self, communication_id: uuid.UUID) -> Optional[CommunicationLog]:
        """
        Retrieve a single communication log by ID.

        Args:
            communication_id: The UUID of the communication log.

        Returns:
            The CommunicationLog instance or None if not found.
        """
        try:
            return CommunicationLog.objects.select_related("customer", "user").get(
                pk=communication_id
            )
        except CommunicationLog.DoesNotExist:
            return None

    def get_communications_by_customer(
        self,
        customer_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
    ) -> QuerySet:
        """
        List communications for a specific customer.

        Args:
            customer_id: The UUID of the customer.
            filters: Optional dictionary of filter parameters:
                - communication_type: Filter by type ('call', 'email', 'meeting')
                - direction: Filter by direction ('inbound', 'outbound')
                - date_from: Filter communications from this date
                - date_to: Filter communications up to this date

        Returns:
            A QuerySet of CommunicationLog instances.
        """
        queryset = CommunicationLog.objects.select_related("customer", "user").filter(
            customer_id=customer_id
        )

        if filters:
            queryset = self._apply_communication_filters(queryset, filters)

        return queryset

    def get_communications_by_deal(
        self,
        deal_id: uuid.UUID,
        filters: Optional[Dict[str, Any]] = None,
    ) -> QuerySet:
        """
        List communications related to a specific deal's customer.

        Args:
            deal_id: The UUID of the deal.
            filters: Optional dictionary of filter parameters.

        Returns:
            A QuerySet of CommunicationLog instances.
        """
        try:
            from deals.models import Deal

            deal = Deal.objects.get(pk=deal_id)
        except Exception:
            return CommunicationLog.objects.none()

        queryset = CommunicationLog.objects.select_related("customer", "user").filter(
            customer=deal.customer
        )

        if filters:
            queryset = self._apply_communication_filters(queryset, filters)

        return queryset

    def list_communications(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> QuerySet:
        """
        List all communications with optional filtering.

        Args:
            filters: Optional dictionary of filter parameters:
                - communication_type: Filter by type
                - direction: Filter by direction
                - customer_id: Filter by customer
                - user_id: Filter by user
                - search: Search by subject or customer name
                - date_from: Filter from date
                - date_to: Filter to date

        Returns:
            A QuerySet of CommunicationLog instances.
        """
        queryset = CommunicationLog.objects.select_related("customer", "user").all()

        if not filters:
            return queryset

        if filters.get("customer_id"):
            queryset = queryset.filter(customer_id=filters["customer_id"])

        if filters.get("user_id"):
            queryset = queryset.filter(user_id=filters["user_id"])

        if filters.get("search"):
            search_term = filters["search"].strip()
            if search_term:
                queryset = queryset.filter(
                    Q(subject__icontains=search_term)
                    | Q(customer__name__icontains=search_term)
                    | Q(body__icontains=search_term)
                )

        queryset = self._apply_communication_filters(queryset, filters)

        return queryset

    def update_communication(
        self,
        communication_id: uuid.UUID,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[CommunicationLog]:
        """
        Update an existing communication log.

        Args:
            communication_id: The UUID of the communication to update.
            data: Dictionary containing fields to update.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated CommunicationLog instance, or None if not found.
        """
        communication = self.get_communication(communication_id)
        if communication is None:
            return None

        if "communication_type" in data and data["communication_type"]:
            self._validate_communication_type(data["communication_type"])

        if "direction" in data and data["direction"]:
            self._validate_direction(data["direction"])

        updatable_fields = [
            "communication_type",
            "subject",
            "body",
            "direction",
            "logged_at",
        ]

        changes = {}

        with transaction.atomic():
            for field in updatable_fields:
                if field in data:
                    new_value = data[field]
                    if isinstance(new_value, str):
                        new_value = new_value.strip()
                    old_value = getattr(communication, field, None)
                    if old_value != new_value:
                        changes[field] = {
                            "old": str(old_value) if old_value is not None else None,
                            "new": str(new_value) if new_value is not None else None,
                        }
                        setattr(communication, field, new_value)

            if not changes:
                return communication

            communication.save()

            self._log_audit(
                entity_type="CommunicationLog",
                entity_id=communication.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        logger.info(
            "Communication updated: id=%s fields=%s user=%s",
            communication.pk,
            list(changes.keys()),
            user,
        )

        return communication

    def delete_communication(
        self,
        communication_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a communication log by ID.

        Args:
            communication_id: The UUID of the communication to delete.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            True if deleted, False if not found.
        """
        communication = self.get_communication(communication_id)
        if communication is None:
            return False

        comm_repr = str(communication)
        comm_pk = communication.pk

        with transaction.atomic():
            communication.delete()

            self._log_audit(
                entity_type="CommunicationLog",
                entity_id=comm_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={"deleted": comm_repr},
                ip_address=ip_address,
            )

        logger.info(
            "Communication deleted: id=%s user=%s",
            comm_pk,
            user,
        )

        return True

    def _apply_communication_filters(
        self, queryset: QuerySet, filters: Dict[str, Any]
    ) -> QuerySet:
        """Apply common communication filters to a queryset."""
        communication_type = filters.get("communication_type", "").strip() if filters.get("communication_type") else ""
        if communication_type and communication_type in CommunicationLog.CommunicationType.values:
            queryset = queryset.filter(communication_type=communication_type)

        direction = filters.get("direction", "").strip() if filters.get("direction") else ""
        if direction and direction in CommunicationLog.Direction.values:
            queryset = queryset.filter(direction=direction)

        date_from = filters.get("date_from")
        if date_from:
            if isinstance(date_from, str):
                queryset = queryset.filter(logged_at__date__gte=date_from)
            else:
                queryset = queryset.filter(logged_at__gte=date_from)

        date_to = filters.get("date_to")
        if date_to:
            if isinstance(date_to, str):
                queryset = queryset.filter(logged_at__date__lte=date_to)
            else:
                queryset = queryset.filter(logged_at__lte=date_to)

        return queryset

    def _validate_required_fields(
        self, data: Dict[str, Any], required_fields: List[str]
    ) -> None:
        """Validate that all required fields are present and non-empty."""
        for field in required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                raise ValueError(f"Missing required field: {field}")

    def _validate_communication_type(self, communication_type: str) -> None:
        """Validate that the communication type is valid."""
        valid_types = CommunicationLog.CommunicationType.values
        if communication_type not in valid_types:
            raise ValueError(
                f"Invalid communication type '{communication_type}'. "
                f"Must be one of: {', '.join(valid_types)}"
            )

    def _validate_direction(self, direction: str) -> None:
        """Validate that the direction is valid."""
        valid_directions = CommunicationLog.Direction.values
        if direction not in valid_directions:
            raise ValueError(
                f"Invalid direction '{direction}'. "
                f"Must be one of: {', '.join(valid_directions)}"
            )

    def _get_customer(self, customer_id) -> Customer:
        """Retrieve a customer by ID, raising DoesNotExist if not found."""
        try:
            return Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise ValueError(f"Customer with ID '{customer_id}' does not exist.")

    def _log_audit(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        user=None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Create an audit log entry. Failures are silently ignored."""
        try:
            audit_user = user if user is not None and hasattr(user, "pk") else None
            AuditLog.create_entry(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user=audit_user,
                changes=changes or {},
                ip_address=ip_address,
            )
        except Exception:
            logger.warning(
                "Failed to create audit log entry for %s %s",
                entity_type,
                entity_id,
                exc_info=True,
            )


class SchedulerService:
    """
    Business logic service for meeting scheduling operations.
    Wraps repository operations with validation, audit logging,
    and optional Google Calendar sync.
    """

    def schedule_meeting(
        self,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Meeting:
        """
        Schedule a new meeting.

        Args:
            data: Dictionary containing meeting fields:
                - customer_id: UUID of the customer (required)
                - title: Meeting title (required)
                - start_time: Meeting start datetime (required)
                - end_time: Meeting end datetime (required)
                - description: Meeting description (optional)
                - location: Meeting location (optional)
                - calendar_sync: Whether to sync with Google Calendar (optional)
            user: The user performing the action (organizer).
            ip_address: Optional IP address for audit logging.

        Returns:
            The newly created Meeting instance.

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        self._validate_required_fields(data, ["customer_id", "title", "start_time", "end_time"])

        customer = self._get_customer(data["customer_id"])

        start_time = data["start_time"]
        end_time = data["end_time"]

        if isinstance(start_time, str):
            start_time = datetime.fromisoformat(start_time)
        if isinstance(end_time, str):
            end_time = datetime.fromisoformat(end_time)

        if end_time <= start_time:
            raise ValueError("Meeting end_time must be after start_time.")

        title = data["title"].strip() if isinstance(data["title"], str) else data["title"]
        if not title:
            raise ValueError("Meeting title is required.")
        if len(title) > 255:
            raise ValueError("Meeting title must be 255 characters or fewer.")

        with transaction.atomic():
            meeting_data = {
                "customer": customer,
                "title": title,
                "start_time": start_time,
                "end_time": end_time,
                "description": data.get("description", "").strip() if data.get("description") else "",
                "location": data.get("location", "").strip() if data.get("location") else "",
                "status": Meeting.Status.SCHEDULED,
            }

            if user is not None and hasattr(user, "pk"):
                meeting_data["organizer"] = user

            meeting = Meeting.objects.create(**meeting_data)

            # Create a corresponding communication log entry for the meeting
            comm_log = self._create_meeting_communication_log(meeting, user)
            if comm_log:
                meeting.communication_log = comm_log
                meeting.save(update_fields=["communication_log"])

            self._log_audit(
                entity_type="Meeting",
                entity_id=meeting.pk,
                action=AuditLog.Action.CREATE,
                user=user,
                changes={
                    "created": {
                        "customer_id": str(customer.pk),
                        "title": meeting_data["title"],
                        "start_time": str(start_time),
                        "end_time": str(end_time),
                        "location": meeting_data["location"],
                    }
                },
                ip_address=ip_address,
            )

        logger.info(
            "Meeting scheduled: id=%s title=%s customer=%s user=%s",
            meeting.pk,
            meeting.title,
            customer.pk,
            user,
        )

        # Optionally sync with Google Calendar
        if data.get("calendar_sync") and user is not None:
            try:
                self.sync_with_google_calendar(meeting.pk, user)
            except Exception:
                logger.warning(
                    "Failed to sync meeting %s with Google Calendar",
                    meeting.pk,
                    exc_info=True,
                )

        return meeting

    def get_meeting(self, meeting_id: uuid.UUID) -> Optional[Meeting]:
        """
        Retrieve a single meeting by ID.

        Args:
            meeting_id: The UUID of the meeting.

        Returns:
            The Meeting instance or None if not found.
        """
        try:
            return Meeting.objects.select_related(
                "customer", "organizer", "communication_log"
            ).get(pk=meeting_id)
        except Meeting.DoesNotExist:
            return None

    def get_meetings(
        self,
        filters: Optional[Dict[str, Any]] = None,
    ) -> QuerySet:
        """
        List meetings with optional filtering.

        Args:
            filters: Optional dictionary of filter parameters:
                - customer_id: Filter by customer
                - organizer_id: Filter by organizer (user)
                - status: Filter by status ('scheduled', 'completed', 'cancelled')
                - date_from: Filter meetings starting from this date
                - date_to: Filter meetings starting up to this date
                - search: Search by title or customer name
                - upcoming: If True, only return future meetings

        Returns:
            A QuerySet of Meeting instances.
        """
        queryset = Meeting.objects.select_related(
            "customer", "organizer", "communication_log"
        ).all()

        if not filters:
            return queryset

        if filters.get("customer_id"):
            queryset = queryset.filter(customer_id=filters["customer_id"])

        if filters.get("organizer_id"):
            queryset = queryset.filter(organizer_id=filters["organizer_id"])

        status = filters.get("status", "").strip() if filters.get("status") else ""
        if status and status in Meeting.Status.values:
            queryset = queryset.filter(status=status)

        if filters.get("search"):
            search_term = filters["search"].strip()
            if search_term:
                queryset = queryset.filter(
                    Q(title__icontains=search_term)
                    | Q(customer__name__icontains=search_term)
                    | Q(description__icontains=search_term)
                    | Q(location__icontains=search_term)
                )

        date_from = filters.get("date_from")
        if date_from:
            if isinstance(date_from, str):
                queryset = queryset.filter(start_time__date__gte=date_from)
            else:
                queryset = queryset.filter(start_time__gte=date_from)

        date_to = filters.get("date_to")
        if date_to:
            if isinstance(date_to, str):
                queryset = queryset.filter(start_time__date__lte=date_to)
            else:
                queryset = queryset.filter(start_time__lte=date_to)

        if filters.get("upcoming"):
            queryset = queryset.filter(start_time__gte=timezone.now())

        return queryset

    def get_upcoming_meetings(self, user=None, limit: int = 10) -> QuerySet:
        """
        Get upcoming meetings, optionally filtered by organizer.

        Args:
            user: Optional user to filter by organizer.
            limit: Maximum number of meetings to return.

        Returns:
            A QuerySet of upcoming Meeting instances.
        """
        queryset = Meeting.objects.select_related(
            "customer", "organizer"
        ).filter(
            start_time__gte=timezone.now(),
            status=Meeting.Status.SCHEDULED,
        ).order_by("start_time")

        if user is not None and hasattr(user, "pk"):
            queryset = queryset.filter(organizer=user)

        return queryset[:limit]

    def get_past_meetings(self, user=None, limit: int = 10) -> QuerySet:
        """
        Get past meetings, optionally filtered by organizer.

        Args:
            user: Optional user to filter by organizer.
            limit: Maximum number of meetings to return.

        Returns:
            A QuerySet of past Meeting instances.
        """
        queryset = Meeting.objects.select_related(
            "customer", "organizer"
        ).filter(
            start_time__lt=timezone.now(),
        ).order_by("-start_time")

        if user is not None and hasattr(user, "pk"):
            queryset = queryset.filter(organizer=user)

        return queryset[:limit]

    def update_meeting(
        self,
        meeting_id: uuid.UUID,
        data: Dict[str, Any],
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Meeting]:
        """
        Update an existing meeting.

        Args:
            meeting_id: The UUID of the meeting to update.
            data: Dictionary containing fields to update.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The updated Meeting instance, or None if not found.
        """
        meeting = self.get_meeting(meeting_id)
        if meeting is None:
            return None

        if "start_time" in data and "end_time" in data:
            start_time = data["start_time"]
            end_time = data["end_time"]
            if isinstance(start_time, str):
                start_time = datetime.fromisoformat(start_time)
            if isinstance(end_time, str):
                end_time = datetime.fromisoformat(end_time)
            if end_time <= start_time:
                raise ValueError("Meeting end_time must be after start_time.")

        if "status" in data and data["status"]:
            valid_statuses = Meeting.Status.values
            if data["status"] not in valid_statuses:
                raise ValueError(
                    f"Invalid status '{data['status']}'. "
                    f"Must be one of: {', '.join(valid_statuses)}"
                )

        updatable_fields = [
            "title",
            "description",
            "start_time",
            "end_time",
            "location",
            "status",
        ]

        changes = {}

        with transaction.atomic():
            for field in updatable_fields:
                if field in data:
                    new_value = data[field]
                    if isinstance(new_value, str) and field not in ("start_time", "end_time"):
                        new_value = new_value.strip()
                    elif isinstance(new_value, str) and field in ("start_time", "end_time"):
                        new_value = datetime.fromisoformat(new_value)
                    old_value = getattr(meeting, field, None)
                    if old_value != new_value:
                        changes[field] = {
                            "old": str(old_value) if old_value is not None else None,
                            "new": str(new_value) if new_value is not None else None,
                        }
                        setattr(meeting, field, new_value)

            if not changes:
                return meeting

            meeting.save()

            self._log_audit(
                entity_type="Meeting",
                entity_id=meeting.pk,
                action=AuditLog.Action.UPDATE,
                user=user,
                changes=changes,
                ip_address=ip_address,
            )

        logger.info(
            "Meeting updated: id=%s fields=%s user=%s",
            meeting.pk,
            list(changes.keys()),
            user,
        )

        # Sync changes with Google Calendar if the meeting has a calendar event
        if meeting.google_calendar_event_id and user is not None:
            try:
                self._update_google_calendar_event(meeting, user)
            except Exception:
                logger.warning(
                    "Failed to update Google Calendar event for meeting %s",
                    meeting.pk,
                    exc_info=True,
                )

        return meeting

    def cancel_meeting(
        self,
        meeting_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Meeting]:
        """
        Cancel a scheduled meeting.

        Args:
            meeting_id: The UUID of the meeting to cancel.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The cancelled Meeting instance, or None if not found.
        """
        return self.update_meeting(
            meeting_id=meeting_id,
            data={"status": Meeting.Status.CANCELLED},
            user=user,
            ip_address=ip_address,
        )

    def complete_meeting(
        self,
        meeting_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> Optional[Meeting]:
        """
        Mark a meeting as completed.

        Args:
            meeting_id: The UUID of the meeting to complete.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            The completed Meeting instance, or None if not found.
        """
        return self.update_meeting(
            meeting_id=meeting_id,
            data={"status": Meeting.Status.COMPLETED},
            user=user,
            ip_address=ip_address,
        )

    def delete_meeting(
        self,
        meeting_id: uuid.UUID,
        user=None,
        ip_address: Optional[str] = None,
    ) -> bool:
        """
        Delete a meeting by ID.

        Args:
            meeting_id: The UUID of the meeting to delete.
            user: The user performing the action.
            ip_address: Optional IP address for audit logging.

        Returns:
            True if deleted, False if not found.
        """
        meeting = self.get_meeting(meeting_id)
        if meeting is None:
            return False

        meeting_repr = str(meeting)
        meeting_pk = meeting.pk
        calendar_event_id = meeting.google_calendar_event_id

        with transaction.atomic():
            meeting.delete()

            self._log_audit(
                entity_type="Meeting",
                entity_id=meeting_pk,
                action=AuditLog.Action.DELETE,
                user=user,
                changes={"deleted": meeting_repr},
                ip_address=ip_address,
            )

        logger.info(
            "Meeting deleted: id=%s user=%s",
            meeting_pk,
            user,
        )

        # Delete the Google Calendar event if one exists
        if calendar_event_id and user is not None:
            try:
                self._delete_google_calendar_event(calendar_event_id, user)
            except Exception:
                logger.warning(
                    "Failed to delete Google Calendar event %s for meeting %s",
                    calendar_event_id,
                    meeting_pk,
                    exc_info=True,
                )

        return True

    def sync_with_google_calendar(
        self,
        meeting_id: uuid.UUID,
        user=None,
    ) -> Optional[Dict[str, Any]]:
        """
        Sync a meeting with Google Calendar by creating a calendar event.

        Args:
            meeting_id: The UUID of the meeting to sync.
            user: The user whose Google Calendar to sync with.

        Returns:
            Dictionary with event details, or None if sync failed.
        """
        meeting = self.get_meeting(meeting_id)
        if meeting is None:
            logger.warning("Cannot sync meeting %s: not found", meeting_id)
            return None

        if meeting.google_calendar_event_id:
            logger.info(
                "Meeting %s already synced with Google Calendar event %s",
                meeting_id,
                meeting.google_calendar_event_id,
            )
            return {
                "event_id": meeting.google_calendar_event_id,
                "status": "already_synced",
            }

        try:
            from integrations.services import GoogleCalendarAdapter

            adapter = GoogleCalendarAdapter(user=user)

            attendees = []
            if meeting.customer and meeting.customer.email:
                attendees.append(meeting.customer.email)

            result = adapter.create_event(
                title=meeting.title,
                start_time=meeting.start_time,
                end_time=meeting.end_time,
                description=meeting.description,
                location=meeting.location,
                attendees=attendees if attendees else None,
            )

            event_id = result.get("event_id", "")
            if event_id:
                meeting.google_calendar_event_id = event_id
                meeting.save(update_fields=["google_calendar_event_id", "updated_at"])

            logger.info(
                "Meeting %s synced with Google Calendar: event_id=%s",
                meeting_id,
                event_id,
            )

            return result

        except ImportError:
            logger.warning(
                "Google Calendar integration not available for meeting %s",
                meeting_id,
            )
            return None
        except Exception as e:
            logger.error(
                "Failed to sync meeting %s with Google Calendar: %s",
                meeting_id,
                str(e),
                exc_info=True,
            )
            return None

    def _update_google_calendar_event(self, meeting: Meeting, user=None) -> Optional[Dict[str, Any]]:
        """Update an existing Google Calendar event for a meeting."""
        if not meeting.google_calendar_event_id:
            return None

        try:
            from integrations.services import GoogleCalendarAdapter

            adapter = GoogleCalendarAdapter(user=user)

            result = adapter.update_event(
                event_id=meeting.google_calendar_event_id,
                title=meeting.title,
                start_time=meeting.start_time,
                end_time=meeting.end_time,
                description=meeting.description,
                location=meeting.location,
            )

            logger.info(
                "Google Calendar event updated for meeting %s: event_id=%s",
                meeting.pk,
                meeting.google_calendar_event_id,
            )

            return result

        except ImportError:
            logger.warning("Google Calendar integration not available")
            return None
        except Exception as e:
            logger.error(
                "Failed to update Google Calendar event for meeting %s: %s",
                meeting.pk,
                str(e),
                exc_info=True,
            )
            return None

    def _delete_google_calendar_event(self, event_id: str, user=None) -> Optional[Dict[str, Any]]:
        """Delete a Google Calendar event."""
        try:
            from integrations.services import GoogleCalendarAdapter

            adapter = GoogleCalendarAdapter(user=user)
            result = adapter.delete_event(event_id=event_id)

            logger.info("Google Calendar event deleted: event_id=%s", event_id)

            return result

        except ImportError:
            logger.warning("Google Calendar integration not available")
            return None
        except Exception as e:
            logger.error(
                "Failed to delete Google Calendar event %s: %s",
                event_id,
                str(e),
                exc_info=True,
            )
            return None

    def _create_meeting_communication_log(
        self, meeting: Meeting, user=None
    ) -> Optional[CommunicationLog]:
        """Create a communication log entry for a meeting."""
        try:
            comm_data = {
                "customer": meeting.customer,
                "communication_type": CommunicationLog.CommunicationType.MEETING,
                "subject": meeting.title,
                "body": meeting.description,
                "direction": CommunicationLog.Direction.OUTBOUND,
                "logged_at": meeting.start_time,
            }

            if user is not None and hasattr(user, "pk"):
                comm_data["user"] = user

            return CommunicationLog.objects.create(**comm_data)
        except Exception:
            logger.warning(
                "Failed to create communication log for meeting %s",
                meeting.pk,
                exc_info=True,
            )
            return None

    def _validate_required_fields(
        self, data: Dict[str, Any], required_fields: List[str]
    ) -> None:
        """Validate that all required fields are present and non-empty."""
        for field in required_fields:
            value = data.get(field)
            if value is None or (isinstance(value, str) and value.strip() == ""):
                raise ValueError(f"Missing required field: {field}")

    def _get_customer(self, customer_id) -> Customer:
        """Retrieve a customer by ID, raising ValueError if not found."""
        try:
            return Customer.objects.get(pk=customer_id)
        except Customer.DoesNotExist:
            raise ValueError(f"Customer with ID '{customer_id}' does not exist.")

    def _log_audit(
        self,
        entity_type: str,
        entity_id: uuid.UUID,
        action: str,
        user=None,
        changes: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Create an audit log entry. Failures are silently ignored."""
        try:
            audit_user = user if user is not None and hasattr(user, "pk") else None
            AuditLog.create_entry(
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                user=audit_user,
                changes=changes or {},
                ip_address=ip_address,
            )
        except Exception:
            logger.warning(
                "Failed to create audit log entry for %s %s",
                entity_type,
                entity_id,
                exc_info=True,
            )