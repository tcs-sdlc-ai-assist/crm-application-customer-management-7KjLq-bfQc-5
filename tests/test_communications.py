import uuid
from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from communications.forms import CommunicationLogForm, MeetingForm
from communications.models import CommunicationLog, Meeting
from communications.services import CommunicationLogService, SchedulerService
from customers.models import Customer


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def admin_user(db):
    return User.objects.create_user(
        email="admin@example.com",
        password="testpass123",
        first_name="Admin",
        last_name="User",
        role=User.Role.ADMIN,
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def sales_user(db):
    return User.objects.create_user(
        email="sales@example.com",
        password="testpass123",
        first_name="Sales",
        last_name="Rep",
        role=User.Role.SALES,
    )


@pytest.fixture
def support_user(db):
    return User.objects.create_user(
        email="support@example.com",
        password="testpass123",
        first_name="Support",
        last_name="Agent",
        role=User.Role.SUPPORT,
    )


@pytest.fixture
def sample_customer(db, admin_user):
    return Customer.objects.create(
        name="Acme Corp",
        email="contact@acme.com",
        phone="+1-555-0100",
        industry="Technology",
        company="Acme Corporation",
        address="123 Main St, Springfield",
        notes="Important client",
        created_by=admin_user,
    )


@pytest.fixture
def second_customer(db, admin_user):
    return Customer.objects.create(
        name="Globex Industries",
        email="info@globex.com",
        phone="+1-555-0200",
        industry="Manufacturing",
        company="Globex Industries",
        created_by=admin_user,
    )


@pytest.fixture
def sample_communication(db, sample_customer, sales_user):
    return CommunicationLog.objects.create(
        customer=sample_customer,
        user=sales_user,
        communication_type=CommunicationLog.CommunicationType.CALL,
        subject="Initial outreach call",
        body="Discussed product features and pricing.",
        direction=CommunicationLog.Direction.OUTBOUND,
        logged_at=timezone.now(),
    )


@pytest.fixture
def sample_meeting(db, sample_customer, sales_user):
    start = timezone.now() + timedelta(days=1)
    end = start + timedelta(hours=1)
    return Meeting.objects.create(
        customer=sample_customer,
        organizer=sales_user,
        title="Quarterly Review",
        description="Review Q4 performance and plan Q1.",
        start_time=start,
        end_time=end,
        location="Conference Room A",
        status=Meeting.Status.SCHEDULED,
    )


@pytest.fixture
def multiple_communications(db, sample_customer, second_customer, sales_user):
    comms = []
    types = [
        CommunicationLog.CommunicationType.CALL,
        CommunicationLog.CommunicationType.EMAIL,
        CommunicationLog.CommunicationType.MEETING,
        CommunicationLog.CommunicationType.CALL,
        CommunicationLog.CommunicationType.EMAIL,
    ]
    directions = [
        CommunicationLog.Direction.OUTBOUND,
        CommunicationLog.Direction.INBOUND,
        CommunicationLog.Direction.OUTBOUND,
        CommunicationLog.Direction.INBOUND,
        CommunicationLog.Direction.OUTBOUND,
    ]
    customers = [sample_customer, sample_customer, second_customer, second_customer, sample_customer]
    for i in range(5):
        comm = CommunicationLog.objects.create(
            customer=customers[i],
            user=sales_user,
            communication_type=types[i],
            subject=f"Communication {i}",
            body=f"Body of communication {i}",
            direction=directions[i],
            logged_at=timezone.now() - timedelta(days=i),
        )
        comms.append(comm)
    return comms


@pytest.fixture
def multiple_meetings(db, sample_customer, second_customer, sales_user):
    meetings = []
    for i in range(4):
        start = timezone.now() + timedelta(days=i + 1)
        end = start + timedelta(hours=1)
        meeting = Meeting.objects.create(
            customer=sample_customer if i % 2 == 0 else second_customer,
            organizer=sales_user,
            title=f"Meeting {i}",
            description=f"Description for meeting {i}",
            start_time=start,
            end_time=end,
            location=f"Room {i}",
            status=Meeting.Status.SCHEDULED,
        )
        meetings.append(meeting)
    return meetings


@pytest.fixture
def past_meeting(db, sample_customer, sales_user):
    start = timezone.now() - timedelta(days=3)
    end = start + timedelta(hours=1)
    return Meeting.objects.create(
        customer=sample_customer,
        organizer=sales_user,
        title="Past Meeting",
        description="This meeting already happened.",
        start_time=start,
        end_time=end,
        location="Old Room",
        status=Meeting.Status.COMPLETED,
    )


@pytest.fixture
def authenticated_client(admin_user):
    client = Client()
    client.login(email="admin@example.com", password="testpass123")
    return client


@pytest.fixture
def sales_client(sales_user):
    client = Client()
    client.login(email="sales@example.com", password="testpass123")
    return client


@pytest.fixture
def support_client(support_user):
    client = Client()
    client.login(email="support@example.com", password="testpass123")
    return client


@pytest.fixture
def anonymous_client():
    return Client()


# =============================================================================
# CommunicationLog Model Tests
# =============================================================================


@pytest.mark.django_db
class TestCommunicationLogModel:
    def test_communication_creation_with_valid_data(self, sample_customer, sales_user):
        comm = CommunicationLog.objects.create(
            customer=sample_customer,
            user=sales_user,
            communication_type=CommunicationLog.CommunicationType.EMAIL,
            subject="Follow-up email",
            body="Sending proposal as discussed.",
            direction=CommunicationLog.Direction.OUTBOUND,
            logged_at=timezone.now(),
        )
        assert comm.pk is not None
        assert isinstance(comm.pk, uuid.UUID)
        assert comm.customer == sample_customer
        assert comm.user == sales_user
        assert comm.communication_type == "email"
        assert comm.direction == "outbound"

    def test_communication_str_representation(self, sample_communication):
        result = str(sample_communication)
        assert "Call" in result
        assert "Initial outreach call" in result

    def test_communication_ordering_by_logged_at_desc(self, multiple_communications):
        comms = list(CommunicationLog.objects.all())
        for i in range(len(comms) - 1):
            assert comms[i].logged_at >= comms[i + 1].logged_at

    def test_communication_blank_optional_fields(self, sample_customer, sales_user):
        comm = CommunicationLog.objects.create(
            customer=sample_customer,
            user=sales_user,
            communication_type=CommunicationLog.CommunicationType.CALL,
        )
        assert comm.subject == ""
        assert comm.body == ""
        assert comm.direction == ""

    def test_communication_customer_cascade_delete(self, sample_communication, sample_customer):
        comm_pk = sample_communication.pk
        sample_customer.delete()
        assert not CommunicationLog.objects.filter(pk=comm_pk).exists()

    def test_communication_user_set_null_on_delete(self, sample_communication, sales_user):
        sales_user.delete()
        sample_communication.refresh_from_db()
        assert sample_communication.user is None

    def test_communication_auto_timestamps(self, sample_communication):
        assert sample_communication.created_at is not None
        assert sample_communication.logged_at is not None


# =============================================================================
# Meeting Model Tests
# =============================================================================


@pytest.mark.django_db
class TestMeetingModel:
    def test_meeting_creation_with_valid_data(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=2)
        end = start + timedelta(hours=1)
        meeting = Meeting.objects.create(
            customer=sample_customer,
            organizer=sales_user,
            title="Product Demo",
            description="Demo of new features.",
            start_time=start,
            end_time=end,
            location="Zoom",
            status=Meeting.Status.SCHEDULED,
        )
        assert meeting.pk is not None
        assert isinstance(meeting.pk, uuid.UUID)
        assert meeting.customer == sample_customer
        assert meeting.organizer == sales_user
        assert meeting.status == "scheduled"

    def test_meeting_str_representation(self, sample_meeting):
        result = str(sample_meeting)
        assert "Quarterly Review" in result

    def test_meeting_ordering_by_start_time_desc(self, multiple_meetings):
        meetings = list(Meeting.objects.all())
        for i in range(len(meetings) - 1):
            assert meetings[i].start_time >= meetings[i + 1].start_time

    def test_meeting_default_status_is_scheduled(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=5)
        end = start + timedelta(hours=1)
        meeting = Meeting.objects.create(
            customer=sample_customer,
            organizer=sales_user,
            title="Default Status Meeting",
            start_time=start,
            end_time=end,
        )
        assert meeting.status == Meeting.Status.SCHEDULED

    def test_meeting_blank_optional_fields(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=5)
        end = start + timedelta(hours=1)
        meeting = Meeting.objects.create(
            customer=sample_customer,
            organizer=sales_user,
            title="Minimal Meeting",
            start_time=start,
            end_time=end,
        )
        assert meeting.description == ""
        assert meeting.location == ""
        assert meeting.google_calendar_event_id == ""

    def test_meeting_customer_cascade_delete(self, sample_meeting, sample_customer):
        meeting_pk = sample_meeting.pk
        sample_customer.delete()
        assert not Meeting.objects.filter(pk=meeting_pk).exists()

    def test_meeting_organizer_set_null_on_delete(self, sample_meeting, sales_user):
        sales_user.delete()
        sample_meeting.refresh_from_db()
        assert sample_meeting.organizer is None

    def test_meeting_auto_timestamps(self, sample_meeting):
        assert sample_meeting.created_at is not None
        assert sample_meeting.updated_at is not None

    def test_meeting_status_choices(self):
        assert Meeting.Status.SCHEDULED == "scheduled"
        assert Meeting.Status.COMPLETED == "completed"
        assert Meeting.Status.CANCELLED == "cancelled"


# =============================================================================
# CommunicationLogForm Tests
# =============================================================================


@pytest.mark.django_db
class TestCommunicationLogForm:
    def test_valid_form_with_all_fields(self, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "communication_type": "call",
            "subject": "Test call",
            "body": "Discussed pricing.",
            "direction": "outbound",
        }
        form = CommunicationLogForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_without_optional_body(self, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "communication_type": "email",
            "subject": "Quick email",
            "direction": "inbound",
        }
        form = CommunicationLogForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_customer(self):
        data = {
            "communication_type": "call",
            "subject": "No customer",
            "direction": "outbound",
        }
        form = CommunicationLogForm(data=data)
        assert not form.is_valid()
        assert "customer" in form.errors

    def test_invalid_form_missing_communication_type(self, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "subject": "No type",
            "direction": "outbound",
        }
        form = CommunicationLogForm(data=data)
        assert not form.is_valid()
        assert "communication_type" in form.errors

    def test_invalid_form_missing_subject(self, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "communication_type": "call",
            "subject": "",
            "direction": "outbound",
        }
        form = CommunicationLogForm(data=data)
        assert not form.is_valid()
        assert "subject" in form.errors

    def test_invalid_form_missing_direction(self, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "communication_type": "call",
            "subject": "Test",
        }
        form = CommunicationLogForm(data=data)
        assert not form.is_valid()
        assert "direction" in form.errors

    def test_form_subject_max_length(self, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "communication_type": "call",
            "subject": "A" * 256,
            "direction": "outbound",
        }
        form = CommunicationLogForm(data=data)
        assert not form.is_valid()
        assert "subject" in form.errors


# =============================================================================
# MeetingForm Tests
# =============================================================================


@pytest.mark.django_db
class TestMeetingForm:
    def test_valid_form_with_all_fields(self, sample_customer):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "Team Sync",
            "description": "Weekly sync meeting.",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
            "location": "Room 101",
        }
        form = MeetingForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_without_optional_fields(self, sample_customer):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "Quick Chat",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_customer(self):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        data = {
            "title": "No Customer",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "customer" in form.errors

    def test_invalid_form_missing_title(self, sample_customer):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "title" in form.errors

    def test_invalid_form_missing_start_time(self, sample_customer):
        end = timezone.now() + timedelta(days=1, hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "No Start",
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "start_time" in form.errors

    def test_invalid_form_missing_end_time(self, sample_customer):
        start = timezone.now() + timedelta(days=1)
        data = {
            "customer": sample_customer.pk,
            "title": "No End",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "end_time" in form.errors

    def test_invalid_form_end_before_start(self, sample_customer):
        start = timezone.now() + timedelta(days=2)
        end = start - timedelta(hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "Bad Times",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "end_time" in form.errors

    def test_invalid_form_end_equals_start(self, sample_customer):
        start = timezone.now() + timedelta(days=2)
        data = {
            "customer": sample_customer.pk,
            "title": "Same Times",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": start.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "end_time" in form.errors

    def test_form_title_max_length(self, sample_customer):
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "A" * 256,
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
        }
        form = MeetingForm(data=data)
        assert not form.is_valid()
        assert "title" in form.errors


# =============================================================================
# CommunicationLogService Tests
# =============================================================================


@pytest.mark.django_db
class TestCommunicationLogService:
    def setup_method(self):
        self.service = CommunicationLogService()

    def test_log_communication_with_valid_data(self, sample_customer, sales_user):
        data = {
            "customer_id": sample_customer.pk,
            "communication_type": "email",
            "subject": "Service test email",
            "body": "Testing the service layer.",
            "direction": "outbound",
        }
        comm = self.service.log_communication(data, user=sales_user)
        assert comm.pk is not None
        assert comm.customer == sample_customer
        assert comm.user == sales_user
        assert comm.communication_type == "email"
        assert comm.subject == "Service test email"

    def test_log_communication_missing_customer_id_raises_value_error(self, sales_user):
        data = {
            "communication_type": "call",
            "subject": "No customer",
        }
        with pytest.raises(ValueError, match="Missing required field"):
            self.service.log_communication(data, user=sales_user)

    def test_log_communication_missing_type_raises_value_error(self, sample_customer, sales_user):
        data = {
            "customer_id": sample_customer.pk,
            "subject": "No type",
        }
        with pytest.raises(ValueError, match="Missing required field"):
            self.service.log_communication(data, user=sales_user)

    def test_log_communication_invalid_type_raises_value_error(self, sample_customer, sales_user):
        data = {
            "customer_id": sample_customer.pk,
            "communication_type": "invalid_type",
            "subject": "Bad type",
        }
        with pytest.raises(ValueError, match="Invalid communication type"):
            self.service.log_communication(data, user=sales_user)

    def test_log_communication_invalid_direction_raises_value_error(self, sample_customer, sales_user):
        data = {
            "customer_id": sample_customer.pk,
            "communication_type": "call",
            "subject": "Bad direction",
            "direction": "sideways",
        }
        with pytest.raises(ValueError, match="Invalid direction"):
            self.service.log_communication(data, user=sales_user)

    def test_log_communication_nonexistent_customer_raises_value_error(self, sales_user):
        data = {
            "customer_id": uuid.uuid4(),
            "communication_type": "call",
            "subject": "Ghost customer",
        }
        with pytest.raises(ValueError, match="does not exist"):
            self.service.log_communication(data, user=sales_user)

    def test_get_communication_existing(self, sample_communication):
        comm = self.service.get_communication(sample_communication.pk)
        assert comm is not None
        assert comm.pk == sample_communication.pk

    def test_get_communication_nonexistent(self):
        comm = self.service.get_communication(uuid.uuid4())
        assert comm is None

    def test_get_communications_by_customer(self, sample_customer, multiple_communications):
        comms = self.service.get_communications_by_customer(sample_customer.pk)
        for comm in comms:
            assert comm.customer_id == sample_customer.pk

    def test_get_communications_by_customer_with_type_filter(self, sample_customer, multiple_communications):
        comms = self.service.get_communications_by_customer(
            sample_customer.pk,
            filters={"communication_type": "call"},
        )
        for comm in comms:
            assert comm.communication_type == "call"

    def test_list_communications_no_filters(self, multiple_communications):
        comms = self.service.list_communications()
        assert comms.count() == 5

    def test_list_communications_filter_by_type(self, multiple_communications):
        comms = self.service.list_communications(filters={"communication_type": "email"})
        for comm in comms:
            assert comm.communication_type == "email"

    def test_list_communications_filter_by_direction(self, multiple_communications):
        comms = self.service.list_communications(filters={"direction": "inbound"})
        for comm in comms:
            assert comm.direction == "inbound"

    def test_list_communications_search(self, multiple_communications):
        comms = self.service.list_communications(filters={"search": "Communication 2"})
        assert comms.count() >= 1

    def test_update_communication_valid_data(self, sample_communication, sales_user):
        updated = self.service.update_communication(
            sample_communication.pk,
            {"subject": "Updated subject"},
            user=sales_user,
        )
        assert updated is not None
        assert updated.subject == "Updated subject"

    def test_update_communication_nonexistent(self, sales_user):
        result = self.service.update_communication(
            uuid.uuid4(),
            {"subject": "Ghost"},
            user=sales_user,
        )
        assert result is None

    def test_update_communication_no_changes(self, sample_communication, sales_user):
        updated = self.service.update_communication(
            sample_communication.pk,
            {"subject": sample_communication.subject},
            user=sales_user,
        )
        assert updated is not None
        assert updated.subject == sample_communication.subject

    def test_delete_communication_existing(self, sample_communication, sales_user):
        pk = sample_communication.pk
        result = self.service.delete_communication(pk, user=sales_user)
        assert result is True
        assert not CommunicationLog.objects.filter(pk=pk).exists()

    def test_delete_communication_nonexistent(self, sales_user):
        result = self.service.delete_communication(uuid.uuid4(), user=sales_user)
        assert result is False


# =============================================================================
# SchedulerService Tests
# =============================================================================


@pytest.mark.django_db
class TestSchedulerService:
    def setup_method(self):
        self.service = SchedulerService()

    def test_schedule_meeting_with_valid_data(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=3)
        end = start + timedelta(hours=1)
        data = {
            "customer_id": sample_customer.pk,
            "title": "Service scheduled meeting",
            "start_time": start,
            "end_time": end,
            "description": "Testing scheduler service.",
            "location": "Zoom",
        }
        meeting = self.service.schedule_meeting(data, user=sales_user)
        assert meeting.pk is not None
        assert meeting.customer == sample_customer
        assert meeting.organizer == sales_user
        assert meeting.title == "Service scheduled meeting"
        assert meeting.status == Meeting.Status.SCHEDULED

    def test_schedule_meeting_creates_communication_log(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=3)
        end = start + timedelta(hours=1)
        data = {
            "customer_id": sample_customer.pk,
            "title": "Meeting with comm log",
            "start_time": start,
            "end_time": end,
        }
        meeting = self.service.schedule_meeting(data, user=sales_user)
        assert meeting.communication_log is not None
        assert meeting.communication_log.communication_type == CommunicationLog.CommunicationType.MEETING

    def test_schedule_meeting_missing_required_field_raises_value_error(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=3)
        end = start + timedelta(hours=1)
        data = {
            "customer_id": sample_customer.pk,
            "title": "",
            "start_time": start,
            "end_time": end,
        }
        with pytest.raises(ValueError):
            self.service.schedule_meeting(data, user=sales_user)

    def test_schedule_meeting_end_before_start_raises_value_error(self, sample_customer, sales_user):
        start = timezone.now() + timedelta(days=3)
        end = start - timedelta(hours=1)
        data = {
            "customer_id": sample_customer.pk,
            "title": "Bad meeting",
            "start_time": start,
            "end_time": end,
        }
        with pytest.raises(ValueError, match="end_time must be after start_time"):
            self.service.schedule_meeting(data, user=sales_user)

    def test_schedule_meeting_nonexistent_customer_raises_value_error(self, sales_user):
        start = timezone.now() + timedelta(days=3)
        end = start + timedelta(hours=1)
        data = {
            "customer_id": uuid.uuid4(),
            "title": "Ghost customer meeting",
            "start_time": start,
            "end_time": end,
        }
        with pytest.raises(ValueError, match="does not exist"):
            self.service.schedule_meeting(data, user=sales_user)

    def test_get_meeting_existing(self, sample_meeting):
        meeting = self.service.get_meeting(sample_meeting.pk)
        assert meeting is not None
        assert meeting.pk == sample_meeting.pk

    def test_get_meeting_nonexistent(self):
        meeting = self.service.get_meeting(uuid.uuid4())
        assert meeting is None

    def test_get_meetings_no_filters(self, multiple_meetings):
        meetings = self.service.get_meetings()
        assert meetings.count() == 4

    def test_get_meetings_filter_by_customer(self, sample_customer, multiple_meetings):
        meetings = self.service.get_meetings(filters={"customer_id": sample_customer.pk})
        for meeting in meetings:
            assert meeting.customer_id == sample_customer.pk

    def test_get_meetings_filter_by_status(self, multiple_meetings):
        meetings = self.service.get_meetings(filters={"status": "scheduled"})
        for meeting in meetings:
            assert meeting.status == "scheduled"

    def test_get_meetings_search(self, multiple_meetings):
        meetings = self.service.get_meetings(filters={"search": "Meeting 1"})
        assert meetings.count() >= 1

    def test_get_upcoming_meetings(self, multiple_meetings, past_meeting, sales_user):
        upcoming = self.service.get_upcoming_meetings(user=sales_user)
        for meeting in upcoming:
            assert meeting.start_time >= timezone.now()
            assert meeting.status == Meeting.Status.SCHEDULED

    def test_get_past_meetings(self, past_meeting, multiple_meetings, sales_user):
        past = self.service.get_past_meetings(user=sales_user)
        for meeting in past:
            assert meeting.start_time < timezone.now()

    def test_update_meeting_valid_data(self, sample_meeting, sales_user):
        updated = self.service.update_meeting(
            sample_meeting.pk,
            {"title": "Updated Quarterly Review"},
            user=sales_user,
        )
        assert updated is not None
        assert updated.title == "Updated Quarterly Review"

    def test_update_meeting_nonexistent(self, sales_user):
        result = self.service.update_meeting(
            uuid.uuid4(),
            {"title": "Ghost"},
            user=sales_user,
        )
        assert result is None

    def test_update_meeting_no_changes(self, sample_meeting, sales_user):
        updated = self.service.update_meeting(
            sample_meeting.pk,
            {"title": sample_meeting.title},
            user=sales_user,
        )
        assert updated is not None
        assert updated.title == sample_meeting.title

    def test_update_meeting_invalid_status_raises_value_error(self, sample_meeting, sales_user):
        with pytest.raises(ValueError, match="Invalid status"):
            self.service.update_meeting(
                sample_meeting.pk,
                {"status": "invalid_status"},
                user=sales_user,
            )

    def test_cancel_meeting(self, sample_meeting, sales_user):
        cancelled = self.service.cancel_meeting(sample_meeting.pk, user=sales_user)
        assert cancelled is not None
        assert cancelled.status == Meeting.Status.CANCELLED

    def test_complete_meeting(self, sample_meeting, sales_user):
        completed = self.service.complete_meeting(sample_meeting.pk, user=sales_user)
        assert completed is not None
        assert completed.status == Meeting.Status.COMPLETED

    def test_delete_meeting_existing(self, sample_meeting, sales_user):
        pk = sample_meeting.pk
        result = self.service.delete_meeting(pk, user=sales_user)
        assert result is True
        assert not Meeting.objects.filter(pk=pk).exists()

    def test_delete_meeting_nonexistent(self, sales_user):
        result = self.service.delete_meeting(uuid.uuid4(), user=sales_user)
        assert result is False


# =============================================================================
# Communication View Tests
# =============================================================================


@pytest.mark.django_db
class TestCommunicationListView:
    def test_communication_list_authenticated(self, authenticated_client, multiple_communications):
        response = authenticated_client.get(reverse("communication-list"))
        assert response.status_code == 200

    def test_communication_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("communication-list"))
        assert response.status_code in (302, 403)

    def test_communication_list_contains_communications(self, authenticated_client, multiple_communications):
        response = authenticated_client.get(reverse("communication-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for comm in multiple_communications:
            assert comm.subject in content


@pytest.mark.django_db
class TestCommunicationDetailView:
    def test_communication_detail_authenticated(self, authenticated_client, sample_communication):
        response = authenticated_client.get(
            reverse("communication-detail", kwargs={"pk": sample_communication.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_communication.subject in content

    def test_communication_detail_unauthenticated_redirects(self, anonymous_client, sample_communication):
        response = anonymous_client.get(
            reverse("communication-detail", kwargs={"pk": sample_communication.pk})
        )
        assert response.status_code in (302, 403)

    def test_communication_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("communication-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestCommunicationCreateView:
    def test_communication_create_get_form(self, authenticated_client):
        response = authenticated_client.get(reverse("communication-create"))
        assert response.status_code == 200

    def test_communication_create_post_valid_data(self, authenticated_client, sample_customer):
        data = {
            "customer": sample_customer.pk,
            "communication_type": "email",
            "subject": "New via view",
            "body": "Created through the view.",
            "direction": "outbound",
        }
        response = authenticated_client.post(reverse("communication-create"), data)
        assert response.status_code in (200, 301, 302)
        assert CommunicationLog.objects.filter(subject="New via view").exists()

    def test_communication_create_post_invalid_data(self, authenticated_client):
        data = {
            "customer": "",
            "communication_type": "",
            "subject": "",
            "direction": "",
        }
        response = authenticated_client.post(reverse("communication-create"), data)
        assert response.status_code == 200
        assert CommunicationLog.objects.count() == 0

    def test_communication_create_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("communication-create"))
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestCommunicationDeleteView:
    def test_communication_delete_authenticated(self, authenticated_client, sample_communication):
        pk = sample_communication.pk
        response = authenticated_client.post(
            reverse("communication-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not CommunicationLog.objects.filter(pk=pk).exists()

    def test_communication_delete_unauthenticated_redirects(self, anonymous_client, sample_communication):
        response = anonymous_client.post(
            reverse("communication-delete", kwargs={"pk": sample_communication.pk})
        )
        assert response.status_code in (302, 403)
        assert CommunicationLog.objects.filter(pk=sample_communication.pk).exists()


# =============================================================================
# Meeting View Tests
# =============================================================================


@pytest.mark.django_db
class TestMeetingListView:
    def test_meeting_list_authenticated(self, authenticated_client, multiple_meetings):
        response = authenticated_client.get(reverse("meeting-list"))
        assert response.status_code == 200

    def test_meeting_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("meeting-list"))
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestMeetingDetailView:
    def test_meeting_detail_authenticated(self, authenticated_client, sample_meeting):
        response = authenticated_client.get(
            reverse("meeting-detail", kwargs={"pk": sample_meeting.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_meeting.title in content

    def test_meeting_detail_unauthenticated_redirects(self, anonymous_client, sample_meeting):
        response = anonymous_client.get(
            reverse("meeting-detail", kwargs={"pk": sample_meeting.pk})
        )
        assert response.status_code in (302, 403)

    def test_meeting_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("meeting-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


@pytest.mark.django_db
class TestMeetingCreateView:
    def test_meeting_create_get_form(self, authenticated_client):
        response = authenticated_client.get(reverse("meeting-create"))
        assert response.status_code == 200

    def test_meeting_create_post_valid_data(self, authenticated_client, sample_customer):
        start = timezone.now() + timedelta(days=5)
        end = start + timedelta(hours=1)
        data = {
            "customer": sample_customer.pk,
            "title": "New Meeting via View",
            "description": "Created through the view.",
            "start_time": start.strftime("%Y-%m-%dT%H:%M"),
            "end_time": end.strftime("%Y-%m-%dT%H:%M"),
            "location": "Room 42",
        }
        response = authenticated_client.post(reverse("meeting-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Meeting.objects.filter(title="New Meeting via View").exists()

    def test_meeting_create_post_invalid_data(self, authenticated_client):
        data = {
            "customer": "",
            "title": "",
            "start_time": "",
            "end_time": "",
        }
        response = authenticated_client.post(reverse("meeting-create"), data)
        assert response.status_code == 200
        assert Meeting.objects.count() == 0

    def test_meeting_create_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("meeting-create"))
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestMeetingDeleteView:
    def test_meeting_delete_authenticated(self, authenticated_client, sample_meeting):
        pk = sample_meeting.pk
        response = authenticated_client.post(
            reverse("meeting-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Meeting.objects.filter(pk=pk).exists()

    def test_meeting_delete_