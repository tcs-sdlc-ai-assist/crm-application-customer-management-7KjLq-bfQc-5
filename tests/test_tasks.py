import uuid
from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from customers.models import Customer
from deals.models import Deal, SalesStage
from tasks.forms import TaskForm
from tasks.models import Task
from tasks.services import TaskManagerService


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
def sales_user_2(db):
    return User.objects.create_user(
        email="sales2@example.com",
        password="testpass123",
        first_name="Sales",
        last_name="Rep2",
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
def sample_stages(db):
    stages_data = [
        {"name": "Lead", "order": 1, "is_active": True},
        {"name": "Qualified", "order": 2, "is_active": True},
        {"name": "Proposal", "order": 3, "is_active": True},
        {"name": "Negotiation", "order": 4, "is_active": True},
        {"name": "Closed Won", "order": 5, "is_active": True},
        {"name": "Closed Lost", "order": 6, "is_active": True},
    ]
    stages = {}
    for stage_data in stages_data:
        stage, _ = SalesStage.objects.get_or_create(
            name=stage_data["name"],
            defaults={
                "order": stage_data["order"],
                "is_active": stage_data["is_active"],
            },
        )
        stages[stage.name] = stage
    return stages


@pytest.fixture
def sample_deal(db, sample_customer, sales_user, sample_stages):
    return Deal.objects.create(
        name="Acme Enterprise License",
        value="150000.00",
        customer=sample_customer,
        owner=sales_user,
        stage=sample_stages["Lead"],
        expected_close_date="2025-06-30",
        description="Enterprise license deal for Acme Corporation.",
    )


@pytest.fixture
def sample_task(db, sample_customer, sample_deal, sales_user, admin_user):
    return Task.objects.create(
        title="Follow up with Acme",
        description="Send proposal document to Acme Corp.",
        customer=sample_customer,
        deal=sample_deal,
        assigned_to=sales_user,
        created_by=admin_user,
        status=Task.Status.PENDING,
        priority=Task.Priority.HIGH,
        due_date=timezone.now().date() + timedelta(days=3),
    )


@pytest.fixture
def overdue_task(db, sample_customer, sales_user, admin_user):
    return Task.objects.create(
        title="Overdue follow-up",
        description="This task is overdue.",
        customer=sample_customer,
        assigned_to=sales_user,
        created_by=admin_user,
        status=Task.Status.PENDING,
        priority=Task.Priority.URGENT,
        due_date=timezone.now().date() - timedelta(days=5),
    )


@pytest.fixture
def completed_task(db, sample_customer, sales_user, admin_user):
    return Task.objects.create(
        title="Completed task",
        description="This task is done.",
        customer=sample_customer,
        assigned_to=sales_user,
        created_by=admin_user,
        status=Task.Status.COMPLETED,
        priority=Task.Priority.MEDIUM,
        due_date=timezone.now().date() - timedelta(days=1),
        completed_at=timezone.now() - timedelta(days=1),
    )


@pytest.fixture
def cancelled_task(db, sample_customer, sales_user, admin_user):
    return Task.objects.create(
        title="Cancelled task",
        description="This task was cancelled.",
        customer=sample_customer,
        assigned_to=sales_user,
        created_by=admin_user,
        status=Task.Status.CANCELLED,
        priority=Task.Priority.LOW,
        due_date=timezone.now().date() + timedelta(days=10),
    )


@pytest.fixture
def in_progress_task(db, sample_customer, sample_deal, sales_user, admin_user):
    return Task.objects.create(
        title="In progress task",
        description="Currently working on this.",
        customer=sample_customer,
        deal=sample_deal,
        assigned_to=sales_user,
        created_by=admin_user,
        status=Task.Status.IN_PROGRESS,
        priority=Task.Priority.MEDIUM,
        due_date=timezone.now().date() + timedelta(days=7),
    )


@pytest.fixture
def multiple_tasks(
    db,
    sample_customer,
    second_customer,
    sample_deal,
    sales_user,
    sales_user_2,
    admin_user,
):
    tasks = []
    task_data = [
        {
            "title": "Task Alpha",
            "customer": sample_customer,
            "deal": sample_deal,
            "assigned_to": sales_user,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.HIGH,
            "due_date": timezone.now().date() + timedelta(days=1),
        },
        {
            "title": "Task Beta",
            "customer": second_customer,
            "deal": None,
            "assigned_to": sales_user,
            "status": Task.Status.IN_PROGRESS,
            "priority": Task.Priority.MEDIUM,
            "due_date": timezone.now().date() + timedelta(days=3),
        },
        {
            "title": "Task Gamma",
            "customer": sample_customer,
            "deal": sample_deal,
            "assigned_to": sales_user_2,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.URGENT,
            "due_date": timezone.now().date() - timedelta(days=2),
        },
        {
            "title": "Task Delta",
            "customer": second_customer,
            "deal": None,
            "assigned_to": sales_user_2,
            "status": Task.Status.COMPLETED,
            "priority": Task.Priority.LOW,
            "due_date": timezone.now().date() - timedelta(days=5),
            "completed_at": timezone.now() - timedelta(days=4),
        },
        {
            "title": "Task Epsilon",
            "customer": sample_customer,
            "deal": None,
            "assigned_to": sales_user,
            "status": Task.Status.CANCELLED,
            "priority": Task.Priority.MEDIUM,
            "due_date": timezone.now().date() + timedelta(days=10),
        },
    ]
    for td in task_data:
        completed_at = td.pop("completed_at", None)
        task = Task.objects.create(
            created_by=admin_user,
            **td,
        )
        if completed_at:
            task.completed_at = completed_at
            task.save(update_fields=["completed_at"])
        tasks.append(task)
    return tasks


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
# Task Model Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskModel:
    def test_task_creation_with_valid_data(self, sample_task):
        assert sample_task.pk is not None
        assert isinstance(sample_task.pk, uuid.UUID)
        assert sample_task.title == "Follow up with Acme"
        assert sample_task.status == Task.Status.PENDING
        assert sample_task.priority == Task.Priority.HIGH
        assert sample_task.customer is not None
        assert sample_task.deal is not None
        assert sample_task.assigned_to is not None
        assert sample_task.created_by is not None

    def test_task_str_representation(self, sample_task):
        result = str(sample_task)
        assert "Follow up with Acme" in result
        assert "Pending" in result

    def test_task_ordering_by_created_at_desc(self, multiple_tasks):
        tasks = list(Task.objects.all())
        for i in range(len(tasks) - 1):
            assert tasks[i].created_at >= tasks[i + 1].created_at

    def test_task_default_status_is_pending(self, sample_customer, admin_user):
        task = Task.objects.create(
            title="Default status task",
            customer=sample_customer,
            created_by=admin_user,
        )
        assert task.status == Task.Status.PENDING

    def test_task_default_priority_is_medium(self, sample_customer, admin_user):
        task = Task.objects.create(
            title="Default priority task",
            customer=sample_customer,
            created_by=admin_user,
        )
        assert task.priority == Task.Priority.MEDIUM

    def test_task_blank_optional_fields(self, admin_user):
        task = Task.objects.create(
            title="Minimal task",
            created_by=admin_user,
        )
        assert task.description == ""
        assert task.customer is None
        assert task.deal is None
        assert task.assigned_to is None
        assert task.due_date is None
        assert task.reminder_date is None
        assert task.completed_at is None

    def test_task_auto_timestamps(self, sample_task):
        assert sample_task.created_at is not None
        assert sample_task.updated_at is not None

    def test_task_customer_set_null_on_delete(self, sample_task, sample_customer):
        sample_customer.delete()
        sample_task.refresh_from_db()
        assert sample_task.customer is None

    def test_task_deal_set_null_on_delete(self, sample_task, sample_deal):
        sample_deal.delete()
        sample_task.refresh_from_db()
        assert sample_task.deal is None

    def test_task_assigned_to_set_null_on_delete(self, sample_task, sales_user):
        sales_user.delete()
        sample_task.refresh_from_db()
        assert sample_task.assigned_to is None

    def test_task_created_by_set_null_on_delete(self, sample_task, admin_user):
        admin_user.delete()
        sample_task.refresh_from_db()
        assert sample_task.created_by is None

    def test_task_is_overdue_true(self, overdue_task):
        assert overdue_task.is_overdue is True

    def test_task_is_overdue_false_future_date(self, sample_task):
        assert sample_task.is_overdue is False

    def test_task_is_overdue_false_no_due_date(self, admin_user):
        task = Task.objects.create(
            title="No due date task",
            created_by=admin_user,
            status=Task.Status.PENDING,
        )
        assert task.is_overdue is False

    def test_task_is_overdue_false_when_completed(self, admin_user):
        task = Task.objects.create(
            title="Completed overdue task",
            created_by=admin_user,
            status=Task.Status.COMPLETED,
            due_date=timezone.now().date() - timedelta(days=10),
            completed_at=timezone.now(),
        )
        assert task.is_overdue is False

    def test_task_is_overdue_false_when_cancelled(self, admin_user):
        task = Task.objects.create(
            title="Cancelled overdue task",
            created_by=admin_user,
            status=Task.Status.CANCELLED,
            due_date=timezone.now().date() - timedelta(days=10),
        )
        assert task.is_overdue is False

    def test_task_mark_completed(self, sample_task):
        assert sample_task.status == Task.Status.PENDING
        assert sample_task.completed_at is None
        sample_task.mark_completed()
        sample_task.refresh_from_db()
        assert sample_task.status == Task.Status.COMPLETED
        assert sample_task.completed_at is not None

    def test_task_status_choices(self):
        assert Task.Status.PENDING == "pending"
        assert Task.Status.IN_PROGRESS == "in_progress"
        assert Task.Status.COMPLETED == "completed"
        assert Task.Status.CANCELLED == "cancelled"

    def test_task_priority_choices(self):
        assert Task.Priority.LOW == "low"
        assert Task.Priority.MEDIUM == "medium"
        assert Task.Priority.HIGH == "high"
        assert Task.Priority.URGENT == "urgent"


# =============================================================================
# TaskForm Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskForm:
    def test_valid_form_with_all_fields(self, sample_customer, sample_deal, sales_user):
        data = {
            "title": "New Task",
            "description": "Task description",
            "customer": sample_customer.pk,
            "deal": sample_deal.pk,
            "assigned_to": sales_user.pk,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.HIGH,
            "due_date": (timezone.now().date() + timedelta(days=5)).isoformat(),
        }
        form = TaskForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_with_required_fields_only(self):
        data = {
            "title": "Minimal Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        form = TaskForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_title(self):
        data = {
            "title": "",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        form = TaskForm(data=data)
        assert not form.is_valid()
        assert "title" in form.errors

    def test_invalid_form_missing_status(self):
        data = {
            "title": "No Status Task",
            "status": "",
            "priority": Task.Priority.MEDIUM,
        }
        form = TaskForm(data=data)
        assert not form.is_valid()
        assert "status" in form.errors

    def test_invalid_form_missing_priority(self):
        data = {
            "title": "No Priority Task",
            "status": Task.Status.PENDING,
            "priority": "",
        }
        form = TaskForm(data=data)
        assert not form.is_valid()
        assert "priority" in form.errors

    def test_form_title_max_length_validation(self):
        data = {
            "title": "A" * 256,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        form = TaskForm(data=data)
        assert not form.is_valid()
        assert "title" in form.errors

    def test_form_due_date_in_past_invalid_for_new_task(self):
        data = {
            "title": "Past Due Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
            "due_date": (timezone.now().date() - timedelta(days=5)).isoformat(),
        }
        form = TaskForm(data=data)
        assert not form.is_valid()
        assert "due_date" in form.errors

    def test_form_due_date_in_future_valid(self):
        data = {
            "title": "Future Due Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
            "due_date": (timezone.now().date() + timedelta(days=10)).isoformat(),
        }
        form = TaskForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_form_due_date_today_valid(self):
        data = {
            "title": "Today Due Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
            "due_date": timezone.now().date().isoformat(),
        }
        form = TaskForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_edit_form_allows_same_past_due_date(self, overdue_task):
        data = {
            "title": overdue_task.title,
            "status": overdue_task.status,
            "priority": overdue_task.priority,
            "due_date": overdue_task.due_date.isoformat(),
        }
        form = TaskForm(data=data, instance=overdue_task)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_form_reminder_after_due_date_invalid(self):
        due = timezone.now().date() + timedelta(days=3)
        reminder = timezone.now() + timedelta(days=5)
        data = {
            "title": "Bad Reminder Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
            "due_date": due.isoformat(),
            "reminder_date": reminder.strftime("%Y-%m-%dT%H:%M"),
        }
        form = TaskForm(data=data)
        assert not form.is_valid()
        assert "reminder_date" in form.errors

    def test_form_customer_queryset_ordered_by_name(self):
        form = TaskForm()
        queryset = form.fields["customer"].queryset
        names = list(queryset.values_list("name", flat=True))
        assert names == sorted(names)

    def test_form_assigned_to_only_active_users(self, admin_user, sales_user):
        inactive_user = User.objects.create_user(
            email="inactive@example.com",
            password="testpass123",
            first_name="Inactive",
            last_name="User",
            role=User.Role.SALES,
            is_active=False,
        )
        form = TaskForm()
        queryset = form.fields["assigned_to"].queryset
        assert inactive_user not in queryset
        assert admin_user in queryset
        assert sales_user in queryset


# =============================================================================
# TaskManagerService Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskManagerService:
    def setup_method(self):
        self.service = TaskManagerService()

    def test_create_task_with_valid_data(self, sample_customer, sample_deal, sales_user, admin_user):
        data = {
            "title": "Service created task",
            "description": "Created via service layer.",
            "customer_id": sample_customer.pk,
            "deal_id": sample_deal.pk,
            "assigned_to_id": sales_user.pk,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.HIGH,
            "due_date": timezone.now().date() + timedelta(days=5),
        }
        task = self.service.create_task(data, user=admin_user)
        assert task.pk is not None
        assert task.title == "Service created task"
        assert task.customer == sample_customer
        assert task.deal == sample_deal
        assert task.assigned_to == sales_user
        assert task.created_by == admin_user
        assert task.status == Task.Status.PENDING
        assert task.priority == Task.Priority.HIGH

    def test_create_task_minimal_data(self, admin_user):
        data = {
            "title": "Minimal service task",
        }
        task = self.service.create_task(data, user=admin_user)
        assert task.pk is not None
        assert task.title == "Minimal service task"
        assert task.status == Task.Status.PENDING
        assert task.priority == Task.Priority.MEDIUM
        assert task.customer is None
        assert task.deal is None
        assert task.assigned_to is None

    def test_create_task_missing_title_raises_value_error(self, admin_user):
        data = {
            "title": "",
            "status": Task.Status.PENDING,
        }
        with pytest.raises(ValueError, match="Missing required field"):
            self.service.create_task(data, user=admin_user)

    def test_create_task_invalid_status_raises_value_error(self, admin_user):
        data = {
            "title": "Bad status task",
            "status": "invalid_status",
        }
        with pytest.raises(ValueError, match="Invalid status"):
            self.service.create_task(data, user=admin_user)

    def test_create_task_invalid_priority_raises_value_error(self, admin_user):
        data = {
            "title": "Bad priority task",
            "priority": "invalid_priority",
        }
        with pytest.raises(ValueError, match="Invalid priority"):
            self.service.create_task(data, user=admin_user)

    def test_create_task_nonexistent_customer_raises_value_error(self, admin_user):
        data = {
            "title": "Ghost customer task",
            "customer_id": uuid.uuid4(),
        }
        with pytest.raises(ValueError, match="not found"):
            self.service.create_task(data, user=admin_user)

    def test_create_task_nonexistent_deal_raises_value_error(self, admin_user):
        data = {
            "title": "Ghost deal task",
            "deal_id": uuid.uuid4(),
        }
        with pytest.raises(ValueError, match="not found"):
            self.service.create_task(data, user=admin_user)

    def test_create_task_nonexistent_assignee_raises_value_error(self, admin_user):
        data = {
            "title": "Ghost assignee task",
            "assigned_to_id": uuid.uuid4(),
        }
        with pytest.raises(ValueError, match="not found"):
            self.service.create_task(data, user=admin_user)

    def test_create_task_title_max_length_raises_value_error(self, admin_user):
        data = {
            "title": "A" * 256,
        }
        with pytest.raises(ValueError, match="exceeds maximum length"):
            self.service.create_task(data, user=admin_user)

    def test_get_task_existing(self, sample_task):
        task = self.service.get_task(sample_task.pk)
        assert task is not None
        assert task.pk == sample_task.pk

    def test_get_task_nonexistent(self):
        task = self.service.get_task(uuid.uuid4())
        assert task is None

    def test_list_tasks_no_filters(self, multiple_tasks):
        queryset = self.service.list_tasks()
        assert queryset.count() == 5

    def test_list_tasks_filter_by_status(self, multiple_tasks):
        queryset = self.service.list_tasks(filters={"status": Task.Status.PENDING})
        for task in queryset:
            assert task.status == Task.Status.PENDING

    def test_list_tasks_filter_by_priority(self, multiple_tasks):
        queryset = self.service.list_tasks(filters={"priority": Task.Priority.URGENT})
        for task in queryset:
            assert task.priority == Task.Priority.URGENT

    def test_list_tasks_filter_by_assigned_to(self, multiple_tasks, sales_user):
        queryset = self.service.list_tasks(filters={"assigned_to": sales_user.pk})
        for task in queryset:
            assert task.assigned_to_id == sales_user.pk

    def test_list_tasks_filter_by_customer(self, multiple_tasks, sample_customer):
        queryset = self.service.list_tasks(filters={"customer_id": sample_customer.pk})
        for task in queryset:
            assert task.customer_id == sample_customer.pk

    def test_list_tasks_filter_by_deal(self, multiple_tasks, sample_deal):
        queryset = self.service.list_tasks(filters={"deal_id": sample_deal.pk})
        for task in queryset:
            assert task.deal_id == sample_deal.pk

    def test_list_tasks_filter_by_search(self, multiple_tasks):
        queryset = self.service.list_tasks(filters={"search": "Alpha"})
        assert queryset.count() == 1
        assert queryset.first().title == "Task Alpha"

    def test_list_tasks_filter_overdue(self, multiple_tasks):
        queryset = self.service.list_tasks(filters={"is_overdue": True})
        today = timezone.now().date()
        for task in queryset:
            assert task.due_date < today
            assert task.status not in [Task.Status.COMPLETED, Task.Status.CANCELLED]

    def test_get_tasks_by_assignee(self, multiple_tasks, sales_user):
        queryset = self.service.get_tasks_by_assignee(sales_user.pk)
        for task in queryset:
            assert task.assigned_to_id == sales_user.pk

    def test_get_tasks_by_customer(self, multiple_tasks, sample_customer):
        queryset = self.service.get_tasks_by_customer(sample_customer.pk)
        for task in queryset:
            assert task.customer_id == sample_customer.pk

    def test_get_tasks_by_deal(self, multiple_tasks, sample_deal):
        queryset = self.service.get_tasks_by_deal(sample_deal.pk)
        for task in queryset:
            assert task.deal_id == sample_deal.pk

    def test_get_overdue_tasks(self, multiple_tasks):
        queryset = self.service.get_overdue_tasks()
        today = timezone.now().date()
        for task in queryset:
            assert task.due_date < today
            assert task.status not in [Task.Status.COMPLETED, Task.Status.CANCELLED]

    def test_get_overdue_tasks_by_user(self, multiple_tasks, sales_user_2):
        queryset = self.service.get_overdue_tasks(user_id=sales_user_2.pk)
        today = timezone.now().date()
        for task in queryset:
            assert task.due_date < today
            assert task.assigned_to_id == sales_user_2.pk

    def test_get_upcoming_tasks(self, multiple_tasks):
        queryset = self.service.get_upcoming_tasks()
        for task in queryset:
            assert task.status in [Task.Status.PENDING, Task.Status.IN_PROGRESS]
            assert task.due_date is not None

    def test_get_upcoming_tasks_by_user(self, multiple_tasks, sales_user):
        queryset = self.service.get_upcoming_tasks(user_id=sales_user.pk)
        for task in queryset:
            assert task.assigned_to_id == sales_user.pk

    def test_update_task_valid_data(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"title": "Updated task title"},
            user=admin_user,
        )
        assert updated is not None
        assert updated.title == "Updated task title"

    def test_update_task_status(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"status": Task.Status.IN_PROGRESS},
            user=admin_user,
        )
        assert updated is not None
        assert updated.status == Task.Status.IN_PROGRESS

    def test_update_task_priority(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"priority": Task.Priority.URGENT},
            user=admin_user,
        )
        assert updated is not None
        assert updated.priority == Task.Priority.URGENT

    def test_update_task_assignment(self, sample_task, sales_user_2, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"assigned_to_id": sales_user_2.pk},
            user=admin_user,
        )
        assert updated is not None
        assert updated.assigned_to == sales_user_2

    def test_update_task_nonexistent(self, admin_user):
        result = self.service.update_task(
            uuid.uuid4(),
            {"title": "Ghost"},
            user=admin_user,
        )
        assert result is None

    def test_update_task_no_changes(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"title": sample_task.title},
            user=admin_user,
        )
        assert updated is not None
        assert updated.title == sample_task.title

    def test_update_task_invalid_status_raises_value_error(self, sample_task, admin_user):
        with pytest.raises(ValueError, match="Invalid status"):
            self.service.update_task(
                sample_task.pk,
                {"status": "invalid_status"},
                user=admin_user,
            )

    def test_update_task_invalid_priority_raises_value_error(self, sample_task, admin_user):
        with pytest.raises(ValueError, match="Invalid priority"):
            self.service.update_task(
                sample_task.pk,
                {"priority": "invalid_priority"},
                user=admin_user,
            )

    def test_update_task_to_completed_sets_completed_at(self, sample_task, admin_user):
        assert sample_task.completed_at is None
        updated = self.service.update_task(
            sample_task.pk,
            {"status": Task.Status.COMPLETED},
            user=admin_user,
        )
        assert updated is not None
        assert updated.status == Task.Status.COMPLETED
        assert updated.completed_at is not None

    def test_complete_task(self, sample_task, admin_user):
        completed = self.service.complete_task(sample_task.pk, user=admin_user)
        assert completed is not None
        assert completed.status == Task.Status.COMPLETED
        assert completed.completed_at is not None

    def test_complete_task_already_completed(self, completed_task, admin_user):
        result = self.service.complete_task(completed_task.pk, user=admin_user)
        assert result is not None
        assert result.status == Task.Status.COMPLETED

    def test_complete_task_nonexistent(self, admin_user):
        result = self.service.complete_task(uuid.uuid4(), user=admin_user)
        assert result is None

    def test_delete_task_existing(self, sample_task, admin_user):
        pk = sample_task.pk
        result = self.service.delete_task(pk, user=admin_user)
        assert result is True
        assert not Task.objects.filter(pk=pk).exists()

    def test_delete_task_nonexistent(self, admin_user):
        result = self.service.delete_task(uuid.uuid4(), user=admin_user)
        assert result is False

    def test_search_tasks(self, multiple_tasks):
        queryset = self.service.search_tasks("Gamma")
        assert queryset.count() == 1
        assert queryset.first().title == "Task Gamma"

    def test_search_tasks_empty_query(self, multiple_tasks):
        queryset = self.service.search_tasks("")
        assert queryset.count() == 5

    def test_search_tasks_by_description(self, sample_task):
        queryset = self.service.search_tasks("proposal document")
        assert queryset.count() == 1


# =============================================================================
# Task Assignment Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskAssignment:
    def setup_method(self):
        self.service = TaskManagerService()

    def test_assign_task_to_user(self, sample_task, sales_user_2, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"assigned_to_id": sales_user_2.pk},
            user=admin_user,
        )
        assert updated is not None
        assert updated.assigned_to == sales_user_2

    def test_reassign_task_to_different_user(self, sample_task, sales_user, sales_user_2, admin_user):
        assert sample_task.assigned_to == sales_user
        updated = self.service.update_task(
            sample_task.pk,
            {"assigned_to_id": sales_user_2.pk},
            user=admin_user,
        )
        assert updated.assigned_to == sales_user_2

        updated = self.service.update_task(
            sample_task.pk,
            {"assigned_to_id": sales_user.pk},
            user=admin_user,
        )
        assert updated.assigned_to == sales_user

    def test_unassign_task(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"assigned_to_id": ""},
            user=admin_user,
        )
        assert updated is not None
        assert updated.assigned_to is None

    def test_assign_task_preserves_other_fields(self, sample_task, sales_user_2, admin_user):
        original_title = sample_task.title
        original_status = sample_task.status
        original_priority = sample_task.priority

        updated = self.service.update_task(
            sample_task.pk,
            {"assigned_to_id": sales_user_2.pk},
            user=admin_user,
        )
        assert updated.title == original_title
        assert updated.status == original_status
        assert updated.priority == original_priority

    def test_create_task_with_assignment(self, sample_customer, sales_user, admin_user):
        data = {
            "title": "Assigned on creation",
            "customer_id": sample_customer.pk,
            "assigned_to_id": sales_user.pk,
        }
        task = self.service.create_task(data, user=admin_user)
        assert task.assigned_to == sales_user


# =============================================================================
# Task Status Update Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskStatusUpdates:
    def setup_method(self):
        self.service = TaskManagerService()

    def test_pending_to_in_progress(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"status": Task.Status.IN_PROGRESS},
            user=admin_user,
        )
        assert updated.status == Task.Status.IN_PROGRESS

    def test_in_progress_to_completed(self, in_progress_task, admin_user):
        updated = self.service.update_task(
            in_progress_task.pk,
            {"status": Task.Status.COMPLETED},
            user=admin_user,
        )
        assert updated.status == Task.Status.COMPLETED
        assert updated.completed_at is not None

    def test_pending_to_cancelled(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"status": Task.Status.CANCELLED},
            user=admin_user,
        )
        assert updated.status == Task.Status.CANCELLED

    def test_pending_to_completed(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"status": Task.Status.COMPLETED},
            user=admin_user,
        )
        assert updated.status == Task.Status.COMPLETED
        assert updated.completed_at is not None

    def test_complete_task_method(self, sample_task, admin_user):
        completed = self.service.complete_task(sample_task.pk, user=admin_user)
        assert completed.status == Task.Status.COMPLETED
        assert completed.completed_at is not None

    def test_status_update_with_priority_change(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {
                "status": Task.Status.IN_PROGRESS,
                "priority": Task.Priority.URGENT,
            },
            user=admin_user,
        )
        assert updated.status == Task.Status.IN_PROGRESS
        assert updated.priority == Task.Priority.URGENT

    def test_full_lifecycle_pending_to_completed(self, sample_task, admin_user):
        updated = self.service.update_task(
            sample_task.pk,
            {"status": Task.Status.IN_PROGRESS},
            user=admin_user,
        )
        assert updated.status == Task.Status.IN_PROGRESS

        completed = self.service.complete_task(sample_task.pk, user=admin_user)
        assert completed.status == Task.Status.COMPLETED
        assert completed.completed_at is not None


# =============================================================================
# Task List View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskListView:
    def test_task_list_authenticated(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(reverse("task-list"))
        assert response.status_code == 200

    def test_task_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("task-list"))
        assert response.status_code in (302, 403)

    def test_task_list_contains_tasks(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(reverse("task-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for task in multiple_tasks:
            assert task.title in content

    def test_task_list_filter_by_status(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(
            reverse("task-list"), {"status": "pending"}
        )
        assert response.status_code == 200

    def test_task_list_filter_by_priority(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(
            reverse("task-list"), {"priority": "urgent"}
        )
        assert response.status_code == 200

    def test_task_list_search(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(
            reverse("task-list"), {"search": "Alpha"}
        )
        assert response.status_code == 200


# =============================================================================
# Task Detail View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskDetailView:
    def test_task_detail_authenticated(self, authenticated_client, sample_task):
        response = authenticated_client.get(
            reverse("task-detail", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_task.title in content

    def test_task_detail_unauthenticated_redirects(self, anonymous_client, sample_task):
        response = anonymous_client.get(
            reverse("task-detail", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (302, 403)

    def test_task_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("task-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404

    def test_task_detail_shows_customer_link(self, authenticated_client, sample_task):
        response = authenticated_client.get(
            reverse("task-detail", kwargs={"pk": sample_task.pk})
        )
        content = response.content.decode()
        assert sample_task.customer.name in content

    def test_task_detail_shows_deal_link(self, authenticated_client, sample_task):
        response = authenticated_client.get(
            reverse("task-detail", kwargs={"pk": sample_task.pk})
        )
        content = response.content.decode()
        assert sample_task.deal.name in content

    def test_task_detail_shows_assignee(self, authenticated_client, sample_task):
        response = authenticated_client.get(
            reverse("task-detail", kwargs={"pk": sample_task.pk})
        )
        content = response.content.decode()
        assert sample_task.assigned_to.first_name in content


# =============================================================================
# Task Create View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskCreateView:
    def test_task_create_get_form(self, authenticated_client):
        response = authenticated_client.get(reverse("task-create"))
        assert response.status_code == 200

    def test_task_create_post_valid_data(
        self, authenticated_client, sample_customer, sample_deal, sales_user
    ):
        data = {
            "title": "New Task Via View",
            "description": "Created through the view.",
            "customer": sample_customer.pk,
            "deal": sample_deal.pk,
            "assigned_to": sales_user.pk,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.HIGH,
            "due_date": (timezone.now().date() + timedelta(days=7)).isoformat(),
        }
        response = authenticated_client.post(reverse("task-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Task.objects.filter(title="New Task Via View").exists()

    def test_task_create_post_minimal_data(self, authenticated_client):
        data = {
            "title": "Minimal View Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        response = authenticated_client.post(reverse("task-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Task.objects.filter(title="Minimal View Task").exists()

    def test_task_create_post_invalid_data(self, authenticated_client):
        data = {
            "title": "",
            "status": "",
            "priority": "",
        }
        response = authenticated_client.post(reverse("task-create"), data)
        assert response.status_code == 200
        initial_count = Task.objects.count()
        assert initial_count == 0

    def test_task_create_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("task-create"))
        assert response.status_code in (302, 403)


# =============================================================================
# Task Update View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskUpdateView:
    def test_task_update_get_form(self, authenticated_client, sample_task):
        response = authenticated_client.get(
            reverse("task-update", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code == 200

    def test_task_update_post_valid_data(self, authenticated_client, sample_task):
        data = {
            "title": "Updated Task Title",
            "description": sample_task.description,
            "status": Task.Status.IN_PROGRESS,
            "priority": Task.Priority.URGENT,
            "due_date": (timezone.now().date() + timedelta(days=10)).isoformat(),
        }
        if sample_task.customer:
            data["customer"] = sample_task.customer.pk
        if sample_task.deal:
            data["deal"] = sample_task.deal.pk
        if sample_task.assigned_to:
            data["assigned_to"] = sample_task.assigned_to.pk
        response = authenticated_client.post(
            reverse("task-update", kwargs={"pk": sample_task.pk}), data
        )
        assert response.status_code in (200, 301, 302)
        sample_task.refresh_from_db()
        assert sample_task.title == "Updated Task Title"
        assert sample_task.status == Task.Status.IN_PROGRESS

    def test_task_update_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("task-update", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


# =============================================================================
# Task Delete View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskDeleteView:
    def test_task_delete_authenticated(self, authenticated_client, sample_task):
        pk = sample_task.pk
        response = authenticated_client.post(
            reverse("task-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Task.objects.filter(pk=pk).exists()

    def test_task_delete_unauthenticated_redirects(self, anonymous_client, sample_task):
        response = anonymous_client.post(
            reverse("task-delete", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (302, 403)
        assert Task.objects.filter(pk=sample_task.pk).exists()

    def test_task_delete_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.post(
            reverse("task-delete", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


# =============================================================================
# Task Complete View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskCompleteView:
    def test_task_complete_via_post(self, authenticated_client, sample_task):
        response = authenticated_client.post(
            reverse("task-complete", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (200, 301, 302)
        sample_task.refresh_from_db()
        assert sample_task.status == Task.Status.COMPLETED
        assert sample_task.completed_at is not None

    def test_task_complete_unauthenticated_redirects(self, anonymous_client, sample_task):
        response = anonymous_client.post(
            reverse("task-complete", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (302, 403)
        sample_task.refresh_from_db()
        assert sample_task.status == Task.Status.PENDING

    def test_task_complete_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.post(
            reverse("task-complete", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


# =============================================================================
# Task Dashboard View Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskDashboardView:
    def test_task_dashboard_authenticated(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(reverse("task-dashboard"))
        assert response.status_code == 200

    def test_task_dashboard_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("task-dashboard"))
        assert response.status_code in (302, 403)

    def test_task_dashboard_shows_overdue_tasks(
        self, authenticated_client, overdue_task, sample_task
    ):
        response = authenticated_client.get(reverse("task-dashboard"))
        assert response.status_code == 200
        content = response.content.decode()
        assert overdue_task.title in content

    def test_task_dashboard_shows_pending_tasks(
        self, authenticated_client, sample_task, completed_task
    ):
        response = authenticated_client.get(reverse("task-dashboard"))
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_task.title in content

    def test_task_dashboard_shows_completed_tasks(
        self, authenticated_client, completed_task
    ):
        response = authenticated_client.get(reverse("task-dashboard"))
        assert response.status_code == 200
        content = response.content.decode()
        assert completed_task.title in content

    def test_task_dashboard_shows_in_progress_tasks(
        self, authenticated_client, in_progress_task
    ):
        response = authenticated_client.get(reverse("task-dashboard"))
        assert response.status_code == 200
        content = response.content.decode()
        assert in_progress_task.title in content


# =============================================================================
# RBAC Tests
# =============================================================================


@pytest.mark.django_db
class TestTaskRBAC:
    def test_admin_can_access_task_list(self, authenticated_client, multiple_tasks):
        response = authenticated_client.get(reverse("task-list"))
        assert response.status_code == 200

    def test_sales_can_access_task_list(self, sales_client, multiple_tasks):
        response = sales_client.get(reverse("task-list"))
        assert response.status_code == 200

    def test_support_can_access_task_list(self, support_client, multiple_tasks):
        response = support_client.get(reverse("task-list"))
        assert response.status_code == 200

    def test_admin_can_create_task(self, authenticated_client):
        data = {
            "title": "Admin Created Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.HIGH,
        }
        response = authenticated_client.post(reverse("task-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Task.objects.filter(title="Admin Created Task").exists()

    def test_sales_can_create_task(self, sales_client):
        data = {
            "title": "Sales Created Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        response = sales_client.post(reverse("task-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Task.objects.filter(title="Sales Created Task").exists()

    def test_support_can_create_task(self, support_client):
        data = {
            "title": "Support Created Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.LOW,
        }
        response = support_client.post(reverse("task-create"), data)
        assert response.status_code in (200, 301, 302)
        assert Task.objects.filter(title="Support Created Task").exists()

    def test_admin_can_delete_task(self, authenticated_client, sample_task):
        pk = sample_task.pk
        response = authenticated_client.post(
            reverse("task-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Task.objects.filter(pk=pk).exists()

    def test_sales_can_delete_task(self, sales_client, sample_task):
        pk = sample_task.pk
        response = sales_client.post(
            reverse("task-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not Task.objects.filter(pk=pk).exists()

    def test_admin_can_update_task(self, authenticated_client, sample_task):
        data = {
            "title": "Admin Updated Task",
            "status": sample_task.status,
            "priority": sample_task.priority,
        }
        if sample_task.customer:
            data["customer"] = sample_task.customer.pk
        if sample_task.deal:
            data["deal"] = sample_task.deal.pk
        if sample_task.assigned_to:
            data["assigned_to"] = sample_task.assigned_to.pk
        if sample_task.due_date:
            data["due_date"] = sample_task.due_date.isoformat()
        response = authenticated_client.post(
            reverse("task-update", kwargs={"pk": sample_task.pk}), data
        )
        assert response.status_code in (200, 301, 302)
        sample_task.refresh_from_db()
        assert sample_task.title == "Admin Updated Task"

    def test_admin_can_complete_task(self, authenticated_client, sample_task):
        response = authenticated_client.post(
            reverse("task-complete", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (200, 301, 302)
        sample_task.refresh_from_db()
        assert sample_task.status == Task.Status.COMPLETED

    def test_sales_can_complete_task(self, sales_client, sample_task):
        response = sales_client.post(
            reverse("task-complete", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (200, 301, 302)
        sample_task.refresh_from_db()
        assert sample_task.status == Task.Status.COMPLETED

    def test_unauthenticated_cannot_create_task(self, anonymous_client):
        data = {
            "title": "Anon Task",
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
        }
        response = anonymous_client.post(reverse("task-create"), data)
        assert response.status_code in (302, 403)
        assert not Task.objects.filter(title="Anon Task").exists()

    def test_unauthenticated_cannot_delete_task(self, anonymous_client, sample_task):
        pk = sample_task.pk
        response = anonymous_client.post(
            reverse("task-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (302, 403)
        assert Task.objects.filter(pk=pk).exists()

    def test_unauthenticated_cannot_complete_task(self, anonymous_client, sample_task):
        response = anonymous_client.post(
            reverse("task-complete", kwargs={"pk": sample_task.pk})
        )
        assert response.status_code in (302, 403)
        sample_task.refresh_from_db()
        assert sample_task.status == Task.Status.PENDING

    def test_task_detail_accessible_by_all_authenticated_roles(
        self, authenticated_client, sales_client, support_client, sample_task
    ):
        url = reverse("task-detail", kwargs={"pk": sample_task.pk})
        for client in [authenticated_client, sales_client, support_client]:
            response = client.get(url)
            assert response.status_code == 200

    def test_task_dashboard_accessible_by_all_authenticated_roles(
        self, authenticated_client, sales_client, support_client, multiple_tasks
    ):
        url = reverse("task-dashboard")
        for client in [authenticated_client, sales_client, support_client]:
            response = client.get(url)
            assert response.status_code == 200

    def test_unauthenticated_cannot_access_task_dashboard(self, anonymous_client):
        response = anonymous_client.get(reverse("task-dashboard"))
        assert response.status_code in (302, 403)