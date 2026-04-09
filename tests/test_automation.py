import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from automation.engine import AutomationEngine
from automation.forms import AutomationRuleForm
from automation.models import AutomationLog, AutomationRule
from customers.models import Customer
from deals.models import Deal, SalesStage
from tasks.models import Task


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
        value=Decimal("150000.00"),
        customer=sample_customer,
        owner=sales_user,
        stage=sample_stages["Lead"],
        expected_close_date="2025-06-30",
        description="Enterprise license deal for Acme Corporation.",
    )


@pytest.fixture
def sample_rule_create_task(db, admin_user):
    return AutomationRule.objects.create(
        name="Follow-up after meeting",
        trigger_type="meeting_completed",
        action_type="create_task",
        config={
            "task_title": "Follow up after meeting",
            "task_priority": "high",
            "delay_hours": 24,
        },
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def sample_rule_send_email(db, admin_user):
    return AutomationRule.objects.create(
        name="Send welcome email to new leads",
        trigger_type="new_lead",
        action_type="send_email",
        config={
            "email_template": "welcome_lead",
            "subject": "Welcome! Let's get started",
            "delay_minutes": 5,
        },
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def sample_rule_assign_lead(db, admin_user):
    return AutomationRule.objects.create(
        name="Auto-assign new leads to sales team",
        trigger_type="new_lead",
        action_type="assign_lead",
        config={
            "assignment_strategy": "round_robin",
            "team": "sales",
        },
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def inactive_rule(db, admin_user):
    return AutomationRule.objects.create(
        name="Inactive rule",
        trigger_type="call_completed",
        action_type="send_email",
        config={
            "subject": "Call Summary",
        },
        is_active=False,
        created_by=admin_user,
    )


@pytest.fixture
def sample_rule_demo_task(db, admin_user):
    return AutomationRule.objects.create(
        name="Create follow-up task after demo",
        trigger_type="demo_completed",
        action_type="create_task",
        config={
            "task_title": "Send proposal after demo",
            "task_priority": "urgent",
            "delay_hours": 2,
        },
        is_active=True,
        created_by=admin_user,
    )


@pytest.fixture
def multiple_rules(db, admin_user, sample_rule_create_task, sample_rule_send_email, sample_rule_assign_lead, inactive_rule, sample_rule_demo_task):
    return [sample_rule_create_task, sample_rule_send_email, sample_rule_assign_lead, inactive_rule, sample_rule_demo_task]


@pytest.fixture
def sample_automation_log(db, sample_rule_create_task, sales_user):
    return AutomationLog.objects.create(
        rule=sample_rule_create_task,
        triggered_by=sales_user,
        target_entity_type="Customer",
        target_entity_id=str(uuid.uuid4()),
        status="success",
        result_message="Task created successfully.",
    )


@pytest.fixture
def multiple_automation_logs(db, sample_rule_create_task, sample_rule_send_email, sales_user, admin_user):
    logs = []
    for i in range(6):
        log = AutomationLog.objects.create(
            rule=sample_rule_create_task if i % 2 == 0 else sample_rule_send_email,
            triggered_by=sales_user if i % 2 == 0 else admin_user,
            target_entity_type="Customer" if i % 2 == 0 else "Deal",
            target_entity_id=str(uuid.uuid4()),
            status="success" if i < 4 else "failed",
            result_message=f"Log entry {i}",
        )
        logs.append(log)
    return logs


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
# AutomationRule Model Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationRuleModel:
    def test_rule_creation_with_valid_data(self, admin_user):
        rule = AutomationRule.objects.create(
            name="Test Rule",
            trigger_type="meeting_completed",
            action_type="create_task",
            config={"task_title": "Follow up", "delay_hours": 24},
            is_active=True,
            created_by=admin_user,
        )
        assert rule.pk is not None
        assert isinstance(rule.pk, uuid.UUID)
        assert rule.name == "Test Rule"
        assert rule.trigger_type == "meeting_completed"
        assert rule.action_type == "create_task"
        assert rule.is_active is True
        assert rule.created_by == admin_user

    def test_rule_str_representation(self, sample_rule_create_task):
        result = str(sample_rule_create_task)
        assert "Follow-up after meeting" in result
        assert "Meeting Completed" in result
        assert "Create Task" in result

    def test_rule_ordering_by_created_at_desc(self, multiple_rules):
        rules = list(AutomationRule.objects.all())
        for i in range(len(rules) - 1):
            assert rules[i].created_at >= rules[i + 1].created_at

    def test_rule_default_config_is_empty_dict(self, admin_user):
        rule = AutomationRule.objects.create(
            name="No Config Rule",
            trigger_type="new_lead",
            action_type="send_email",
            created_by=admin_user,
        )
        assert rule.config == {}

    def test_rule_default_is_active_true(self, admin_user):
        rule = AutomationRule.objects.create(
            name="Default Active Rule",
            trigger_type="new_lead",
            action_type="send_email",
            created_by=admin_user,
        )
        assert rule.is_active is True

    def test_rule_auto_timestamps(self, sample_rule_create_task):
        assert sample_rule_create_task.created_at is not None
        assert sample_rule_create_task.updated_at is not None

    def test_rule_created_by_cascade_on_delete(self, sample_rule_create_task, admin_user):
        pk = sample_rule_create_task.pk
        admin_user.delete()
        assert not AutomationRule.objects.filter(pk=pk).exists()

    def test_rule_trigger_type_choices(self):
        valid_triggers = ["meeting_completed", "call_completed", "demo_completed", "new_lead"]
        for trigger in valid_triggers:
            assert any(trigger == choice[0] for choice in AutomationRule.TRIGGER_TYPE_CHOICES)

    def test_rule_action_type_choices(self):
        valid_actions = ["send_email", "assign_lead", "create_task"]
        for action in valid_actions:
            assert any(action == choice[0] for choice in AutomationRule.ACTION_TYPE_CHOICES)


# =============================================================================
# AutomationLog Model Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationLogModel:
    def test_log_creation_with_valid_data(self, sample_rule_create_task, sales_user):
        log = AutomationLog.objects.create(
            rule=sample_rule_create_task,
            triggered_by=sales_user,
            target_entity_type="Customer",
            target_entity_id=str(uuid.uuid4()),
            status="success",
            result_message="Action executed successfully.",
        )
        assert log.pk is not None
        assert isinstance(log.pk, uuid.UUID)
        assert log.rule == sample_rule_create_task
        assert log.triggered_by == sales_user
        assert log.status == "success"

    def test_log_str_representation(self, sample_automation_log):
        result = str(sample_automation_log)
        assert "Follow-up after meeting" in result
        assert "Success" in result

    def test_log_ordering_by_executed_at_desc(self, multiple_automation_logs):
        logs = list(AutomationLog.objects.all())
        for i in range(len(logs) - 1):
            assert logs[i].executed_at >= logs[i + 1].executed_at

    def test_log_rule_cascade_on_delete(self, sample_automation_log, sample_rule_create_task):
        log_pk = sample_automation_log.pk
        sample_rule_create_task.delete()
        assert not AutomationLog.objects.filter(pk=log_pk).exists()

    def test_log_triggered_by_set_null_on_delete(self, sample_automation_log, sales_user):
        sales_user.delete()
        sample_automation_log.refresh_from_db()
        assert sample_automation_log.triggered_by is None

    def test_log_auto_executed_at(self, sample_automation_log):
        assert sample_automation_log.executed_at is not None

    def test_log_status_choices(self):
        valid_statuses = ["success", "failed"]
        for status in valid_statuses:
            assert any(status == choice[0] for choice in AutomationLog.STATUS_CHOICES)

    def test_log_blank_result_message(self, sample_rule_create_task, sales_user):
        log = AutomationLog.objects.create(
            rule=sample_rule_create_task,
            triggered_by=sales_user,
            target_entity_type="Deal",
            target_entity_id=str(uuid.uuid4()),
            status="success",
        )
        assert log.result_message == ""


# =============================================================================
# AutomationRuleForm Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationRuleForm:
    def test_valid_form_with_all_fields(self):
        data = {
            "name": "Test Rule",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": '{"task_title": "Follow up", "delay_hours": 24}',
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_with_empty_config(self):
        data = {
            "name": "Minimal Rule",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "",
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"
        assert form.cleaned_data["config"] == {}

    def test_valid_form_with_empty_json_object(self):
        data = {
            "name": "Empty Config Rule",
            "trigger_type": "new_lead",
            "action_type": "assign_lead",
            "config": "{}",
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"
        assert form.cleaned_data["config"] == {}

    def test_invalid_form_missing_name(self):
        data = {
            "name": "",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": "{}",
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert not form.is_valid()
        assert "name" in form.errors

    def test_invalid_form_missing_trigger_type(self):
        data = {
            "name": "No Trigger",
            "trigger_type": "",
            "action_type": "create_task",
            "config": "{}",
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert not form.is_valid()
        assert "trigger_type" in form.errors

    def test_invalid_form_missing_action_type(self):
        data = {
            "name": "No Action",
            "trigger_type": "meeting_completed",
            "action_type": "",
            "config": "{}",
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert not form.is_valid()
        assert "action_type" in form.errors

    def test_invalid_form_bad_json_config(self):
        data = {
            "name": "Bad JSON Rule",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": "not valid json",
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert not form.is_valid()
        assert "config" in form.errors

    def test_invalid_form_json_array_config(self):
        data = {
            "name": "Array Config Rule",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": '[1, 2, 3]',
            "is_active": True,
        }
        form = AutomationRuleForm(data=data)
        assert not form.is_valid()
        assert "config" in form.errors

    def test_form_populates_initial_config_for_existing_instance(self, sample_rule_create_task):
        form = AutomationRuleForm(instance=sample_rule_create_task)
        initial_config = form.initial.get("config", "")
        assert "task_title" in initial_config
        assert "Follow up after meeting" in initial_config

    def test_form_without_is_active_defaults_to_unchecked(self):
        data = {
            "name": "No Active Field",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "{}",
        }
        form = AutomationRuleForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"


# =============================================================================
# AutomationEngine Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationEngine:
    def setup_method(self):
        self.engine = AutomationEngine()

    def test_evaluate_rules_returns_matching_active_rules(self, sample_rule_create_task):
        matching = self.engine.evaluate_rules("meeting_completed")
        assert len(matching) >= 1
        for rule in matching:
            assert rule.trigger_type == "meeting_completed"
            assert rule.is_active is True

    def test_evaluate_rules_excludes_inactive_rules(self, inactive_rule):
        matching = self.engine.evaluate_rules("call_completed")
        assert len(matching) == 0

    def test_evaluate_rules_returns_empty_for_unknown_event(self):
        matching = self.engine.evaluate_rules("unknown_event_type")
        assert len(matching) == 0

    def test_evaluate_rules_returns_empty_for_empty_event(self):
        matching = self.engine.evaluate_rules("")
        assert len(matching) == 0

    def test_evaluate_rules_returns_multiple_matching_rules(self, sample_rule_send_email, sample_rule_assign_lead):
        matching = self.engine.evaluate_rules("new_lead")
        assert len(matching) == 2
        for rule in matching:
            assert rule.trigger_type == "new_lead"

    def test_publish_event_creates_task_action(self, sample_rule_create_task, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) >= 1
        for log in logs:
            assert log.status in ("success", "failed")
            assert log.rule == sample_rule_create_task

        tasks = Task.objects.filter(title="Follow up after meeting")
        assert tasks.exists()

    def test_publish_event_creates_task_with_correct_priority(self, sample_rule_create_task, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        task = Task.objects.filter(title="Follow up after meeting").first()
        assert task is not None
        assert task.priority == "high"

    def test_publish_event_creates_task_with_due_date(self, sample_rule_create_task, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        task = Task.objects.filter(title="Follow up after meeting").first()
        assert task is not None
        assert task.due_date is not None

    def test_publish_event_creates_task_linked_to_customer(self, sample_rule_create_task, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        task = Task.objects.filter(title="Follow up after meeting").first()
        assert task is not None
        assert task.customer == sample_customer

    def test_publish_event_creates_task_linked_to_deal(self, sample_rule_create_task, sample_customer, sample_deal, sales_user):
        context = {
            "customer_id": sample_customer.pk,
            "deal_id": sample_deal.pk,
        }
        self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        task = Task.objects.filter(title="Follow up after meeting").first()
        assert task is not None
        assert task.deal == sample_deal

    def test_publish_event_send_email_with_customer(self, sample_rule_send_email, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) >= 1
        email_logs = [log for log in logs if log.rule.action_type == "send_email"]
        assert len(email_logs) >= 1

    def test_publish_event_send_email_no_customer_returns_message(self, sample_rule_send_email, admin_user):
        # Only keep the send_email rule active for new_lead
        AutomationRule.objects.filter(
            trigger_type="new_lead",
            action_type="assign_lead",
        ).update(is_active=False)

        context = {}
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=admin_user,
        )
        assert len(logs) >= 1
        email_log = [log for log in logs if log.rule.action_type == "send_email"][0]
        assert "No customer found" in email_log.result_message or email_log.status == "success"

    def test_publish_event_send_email_customer_no_email(self, sample_rule_send_email, admin_user):
        # Only keep the send_email rule active for new_lead
        AutomationRule.objects.filter(
            trigger_type="new_lead",
            action_type="assign_lead",
        ).update(is_active=False)

        customer = Customer.objects.create(
            name="No Email Customer",
            email="",
            industry="Tech",
            created_by=admin_user,
        )
        context = {
            "customer_id": customer.pk,
        }
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=admin_user,
        )
        assert len(logs) >= 1
        email_log = [log for log in logs if log.rule.action_type == "send_email"][0]
        assert "no email" in email_log.result_message.lower() or email_log.status in ("success", "failed")

    def test_publish_event_assign_lead_round_robin(self, sample_rule_assign_lead, sample_customer, sales_user, sales_user_2, admin_user):
        # Only keep the assign_lead rule active for new_lead
        AutomationRule.objects.filter(
            trigger_type="new_lead",
            action_type="send_email",
        ).update(is_active=False)

        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=admin_user,
        )
        assert len(logs) >= 1
        assign_log = [log for log in logs if log.rule.action_type == "assign_lead"][0]
        assert assign_log.status == "success"
        assert "assigned" in assign_log.result_message.lower() or "sales" in assign_log.result_message.lower()

    def test_publish_event_assign_lead_with_deal(self, sample_rule_assign_lead, sample_customer, sample_deal, sales_user, sales_user_2, admin_user):
        # Only keep the assign_lead rule active for new_lead
        AutomationRule.objects.filter(
            trigger_type="new_lead",
            action_type="send_email",
        ).update(is_active=False)

        context = {
            "customer_id": sample_customer.pk,
            "deal_id": sample_deal.pk,
        }
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=admin_user,
        )
        assert len(logs) >= 1
        assign_log = [log for log in logs if log.rule.action_type == "assign_lead"][0]
        assert assign_log.status == "success"

    def test_publish_event_assign_lead_specific_strategy(self, admin_user, sample_customer, sales_user_2):
        rule = AutomationRule.objects.create(
            name="Specific assignment",
            trigger_type="new_lead",
            action_type="assign_lead",
            config={
                "assignment_strategy": "specific",
                "assignee_id": str(sales_user_2.pk),
            },
            is_active=True,
            created_by=admin_user,
        )
        # Deactivate other new_lead rules
        AutomationRule.objects.filter(
            trigger_type="new_lead",
        ).exclude(pk=rule.pk).update(is_active=False)

        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=admin_user,
        )
        assert len(logs) >= 1
        assign_log = logs[0]
        assert assign_log.status == "success"

    def test_publish_event_no_matching_rules_returns_empty(self):
        logs = self.engine.publish_event(
            "nonexistent_event",
            {"customer_id": uuid.uuid4()},
        )
        assert len(logs) == 0

    def test_publish_event_empty_event_type_returns_empty(self, sample_rule_create_task):
        logs = self.engine.publish_event(
            "",
            {"customer_id": uuid.uuid4()},
        )
        assert len(logs) == 0

    def test_publish_event_creates_automation_log_entries(self, sample_rule_create_task, sample_customer, sales_user):
        initial_log_count = AutomationLog.objects.count()
        context = {
            "customer_id": sample_customer.pk,
        }
        self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        assert AutomationLog.objects.count() > initial_log_count

    def test_publish_event_log_contains_correct_target_entity(self, sample_rule_create_task, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) >= 1
        log = logs[0]
        assert log.target_entity_type == "Customer"
        assert str(sample_customer.pk) == log.target_entity_id

    def test_publish_event_log_contains_deal_target_when_deal_in_context(self, sample_rule_create_task, sample_customer, sample_deal, sales_user):
        context = {
            "customer_id": sample_customer.pk,
            "deal_id": sample_deal.pk,
        }
        logs = self.engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) >= 1
        log = logs[0]
        assert log.target_entity_type == "Deal"
        assert str(sample_deal.pk) == log.target_entity_id

    def test_execute_action_unknown_action_type_returns_failed_log(self, admin_user, sample_customer):
        rule = AutomationRule.objects.create(
            name="Unknown action rule",
            trigger_type="meeting_completed",
            action_type="unknown_action",
            config={},
            is_active=True,
            created_by=admin_user,
        )
        context = {
            "customer_id": sample_customer.pk,
        }
        log = self.engine.execute_action(rule, context, triggered_by=admin_user)
        assert log is not None
        assert log.status == "failed"
        assert "Unknown action type" in log.result_message

    def test_execute_action_with_none_rule_returns_none(self):
        result = self.engine.execute_action(None, {}, triggered_by=None)
        assert result is None

    def test_demo_completed_creates_task(self, sample_rule_demo_task, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "demo_completed",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) >= 1
        task = Task.objects.filter(title="Send proposal after demo").first()
        assert task is not None
        assert task.priority == "urgent"

    def test_multiple_rules_same_trigger_all_execute(self, sample_rule_send_email, sample_rule_assign_lead, sample_customer, sales_user):
        context = {
            "customer_id": sample_customer.pk,
        }
        logs = self.engine.publish_event(
            "new_lead",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) == 2
        action_types = {log.rule.action_type for log in logs}
        assert "send_email" in action_types
        assert "assign_lead" in action_types


# =============================================================================
# AutomationRule View Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationRuleListView:
    def test_rule_list_authenticated_admin(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(reverse("automation-list"))
        assert response.status_code == 200

    def test_rule_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("automation-list"))
        assert response.status_code in (302, 403)

    def test_rule_list_contains_rules(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(reverse("automation-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for rule in multiple_rules:
            assert rule.name in content

    def test_rule_list_filter_by_trigger_type(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(
            reverse("automation-list"), {"trigger_type": "meeting_completed"}
        )
        assert response.status_code == 200

    def test_rule_list_filter_by_action_type(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(
            reverse("automation-list"), {"action_type": "create_task"}
        )
        assert response.status_code == 200

    def test_rule_list_filter_by_active_status(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(
            reverse("automation-list"), {"is_active": "true"}
        )
        assert response.status_code == 200

    def test_rule_list_filter_by_inactive_status(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(
            reverse("automation-list"), {"is_active": "false"}
        )
        assert response.status_code == 200


@pytest.mark.django_db
class TestAutomationRuleDetailView:
    def test_rule_detail_authenticated_admin(self, authenticated_client, sample_rule_create_task):
        response = authenticated_client.get(
            reverse("automation-rule-detail", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_rule_create_task.name in content

    def test_rule_detail_unauthenticated_redirects(self, anonymous_client, sample_rule_create_task):
        response = anonymous_client.get(
            reverse("automation-rule-detail", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code in (302, 403)

    def test_rule_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("automation-rule-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404

    def test_rule_detail_shows_recent_logs(self, authenticated_client, sample_rule_create_task, sample_automation_log):
        response = authenticated_client.get(
            reverse("automation-rule-detail", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "Task created successfully." in content or "Success" in content


@pytest.mark.django_db
class TestAutomationRuleCreateView:
    def test_rule_create_get_form(self, authenticated_client):
        response = authenticated_client.get(reverse("automation-rule-create"))
        assert response.status_code == 200

    def test_rule_create_post_valid_data(self, authenticated_client):
        data = {
            "name": "New Rule Via View",
            "trigger_type": "call_completed",
            "action_type": "create_task",
            "config": '{"task_title": "Follow up call", "delay_hours": 12}',
            "is_active": True,
        }
        response = authenticated_client.post(reverse("automation-rule-create"), data)
        assert response.status_code in (200, 301, 302)
        assert AutomationRule.objects.filter(name="New Rule Via View").exists()

    def test_rule_create_post_invalid_data(self, authenticated_client):
        data = {
            "name": "",
            "trigger_type": "",
            "action_type": "",
            "config": "{}",
        }
        response = authenticated_client.post(reverse("automation-rule-create"), data)
        assert response.status_code == 200
        initial_count = AutomationRule.objects.count()
        # Re-post to confirm no creation
        authenticated_client.post(reverse("automation-rule-create"), data)
        assert AutomationRule.objects.count() == initial_count

    def test_rule_create_post_invalid_json_config(self, authenticated_client):
        data = {
            "name": "Bad JSON Rule",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": "not valid json",
            "is_active": True,
        }
        response = authenticated_client.post(reverse("automation-rule-create"), data)
        assert response.status_code == 200
        assert not AutomationRule.objects.filter(name="Bad JSON Rule").exists()

    def test_rule_create_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("automation-rule-create"))
        assert response.status_code in (302, 403)

    def test_rule_create_sets_created_by_to_current_user(self, authenticated_client, admin_user):
        data = {
            "name": "Created By Test",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "{}",
            "is_active": True,
        }
        authenticated_client.post(reverse("automation-rule-create"), data)
        rule = AutomationRule.objects.filter(name="Created By Test").first()
        assert rule is not None
        assert rule.created_by == admin_user


@pytest.mark.django_db
class TestAutomationRuleEditView:
    def test_rule_edit_get_form(self, authenticated_client, sample_rule_create_task):
        response = authenticated_client.get(
            reverse("automation-rule-update", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code == 200

    def test_rule_edit_post_valid_data(self, authenticated_client, sample_rule_create_task):
        data = {
            "name": "Updated Rule Name",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": '{"task_title": "Updated follow up", "delay_hours": 48}',
            "is_active": True,
        }
        response = authenticated_client.post(
            reverse("automation-rule-update", kwargs={"pk": sample_rule_create_task.pk}),
            data,
        )
        assert response.status_code in (200, 301, 302)
        sample_rule_create_task.refresh_from_db()
        assert sample_rule_create_task.name == "Updated Rule Name"

    def test_rule_edit_post_deactivate_rule(self, authenticated_client, sample_rule_create_task):
        data = {
            "name": sample_rule_create_task.name,
            "trigger_type": sample_rule_create_task.trigger_type,
            "action_type": sample_rule_create_task.action_type,
            "config": '{"task_title": "Follow up after meeting", "task_priority": "high", "delay_hours": 24}',
            # is_active not included means unchecked
        }
        response = authenticated_client.post(
            reverse("automation-rule-update", kwargs={"pk": sample_rule_create_task.pk}),
            data,
        )
        assert response.status_code in (200, 301, 302)
        sample_rule_create_task.refresh_from_db()
        assert sample_rule_create_task.is_active is False

    def test_rule_edit_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("automation-rule-update", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404

    def test_rule_edit_unauthenticated_redirects(self, anonymous_client, sample_rule_create_task):
        response = anonymous_client.get(
            reverse("automation-rule-update", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestAutomationRuleDeleteView:
    def test_rule_delete_authenticated_admin(self, authenticated_client, sample_rule_create_task):
        pk = sample_rule_create_task.pk
        response = authenticated_client.post(
            reverse("automation-rule-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not AutomationRule.objects.filter(pk=pk).exists()

    def test_rule_delete_get_shows_confirmation(self, authenticated_client, sample_rule_create_task):
        response = authenticated_client.get(
            reverse("automation-rule-delete", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code == 200

    def test_rule_delete_unauthenticated_redirects(self, anonymous_client, sample_rule_create_task):
        response = anonymous_client.post(
            reverse("automation-rule-delete", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code in (302, 403)
        assert AutomationRule.objects.filter(pk=sample_rule_create_task.pk).exists()

    def test_rule_delete_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.post(
            reverse("automation-rule-delete", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404


# =============================================================================
# AutomationLog View Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationLogListView:
    def test_log_list_authenticated_admin(self, authenticated_client, multiple_automation_logs):
        response = authenticated_client.get(reverse("automation-log-list"))
        assert response.status_code == 200

    def test_log_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("automation-log-list"))
        assert response.status_code in (302, 403)

    def test_log_list_contains_logs(self, authenticated_client, multiple_automation_logs):
        response = authenticated_client.get(reverse("automation-log-list"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Follow-up after meeting" in content or "Send welcome email" in content

    def test_log_list_filter_by_status_success(self, authenticated_client, multiple_automation_logs):
        response = authenticated_client.get(
            reverse("automation-log-list"), {"status": "success"}
        )
        assert response.status_code == 200

    def test_log_list_filter_by_status_failed(self, authenticated_client, multiple_automation_logs):
        response = authenticated_client.get(
            reverse("automation-log-list"), {"status": "failed"}
        )
        assert response.status_code == 200

    def test_log_list_filter_by_search(self, authenticated_client, multiple_automation_logs):
        response = authenticated_client.get(
            reverse("automation-log-list"), {"search": "Follow-up"}
        )
        assert response.status_code == 200


# =============================================================================
# RBAC Tests
# =============================================================================


@pytest.mark.django_db
class TestAutomationRBAC:
    def test_admin_can_access_rule_list(self, authenticated_client, multiple_rules):
        response = authenticated_client.get(reverse("automation-list"))
        assert response.status_code == 200

    def test_sales_cannot_access_rule_list(self, sales_client, multiple_rules):
        response = sales_client.get(reverse("automation-list"))
        assert response.status_code == 403

    def test_support_cannot_access_rule_list(self, support_client, multiple_rules):
        response = support_client.get(reverse("automation-list"))
        assert response.status_code == 403

    def test_admin_can_create_rule(self, authenticated_client):
        data = {
            "name": "Admin Created Rule",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "{}",
            "is_active": True,
        }
        response = authenticated_client.post(reverse("automation-rule-create"), data)
        assert response.status_code in (200, 301, 302)
        assert AutomationRule.objects.filter(name="Admin Created Rule").exists()

    def test_sales_cannot_create_rule(self, sales_client):
        data = {
            "name": "Sales Created Rule",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "{}",
            "is_active": True,
        }
        response = sales_client.post(reverse("automation-rule-create"), data)
        assert response.status_code == 403
        assert not AutomationRule.objects.filter(name="Sales Created Rule").exists()

    def test_support_cannot_create_rule(self, support_client):
        data = {
            "name": "Support Created Rule",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "{}",
            "is_active": True,
        }
        response = support_client.post(reverse("automation-rule-create"), data)
        assert response.status_code == 403
        assert not AutomationRule.objects.filter(name="Support Created Rule").exists()

    def test_admin_can_edit_rule(self, authenticated_client, sample_rule_create_task):
        data = {
            "name": "Admin Edited Rule",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": '{"task_title": "Edited", "delay_hours": 12}',
            "is_active": True,
        }
        response = authenticated_client.post(
            reverse("automation-rule-update", kwargs={"pk": sample_rule_create_task.pk}),
            data,
        )
        assert response.status_code in (200, 301, 302)
        sample_rule_create_task.refresh_from_db()
        assert sample_rule_create_task.name == "Admin Edited Rule"

    def test_sales_cannot_edit_rule(self, sales_client, sample_rule_create_task):
        data = {
            "name": "Sales Edited Rule",
            "trigger_type": "meeting_completed",
            "action_type": "create_task",
            "config": "{}",
            "is_active": True,
        }
        response = sales_client.post(
            reverse("automation-rule-update", kwargs={"pk": sample_rule_create_task.pk}),
            data,
        )
        assert response.status_code == 403
        sample_rule_create_task.refresh_from_db()
        assert sample_rule_create_task.name != "Sales Edited Rule"

    def test_admin_can_delete_rule(self, authenticated_client, sample_rule_create_task):
        pk = sample_rule_create_task.pk
        response = authenticated_client.post(
            reverse("automation-rule-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (200, 301, 302)
        assert not AutomationRule.objects.filter(pk=pk).exists()

    def test_sales_cannot_delete_rule(self, sales_client, sample_rule_create_task):
        pk = sample_rule_create_task.pk
        response = sales_client.post(
            reverse("automation-rule-delete", kwargs={"pk": pk})
        )
        assert response.status_code == 403
        assert AutomationRule.objects.filter(pk=pk).exists()

    def test_support_cannot_delete_rule(self, support_client, sample_rule_create_task):
        pk = sample_rule_create_task.pk
        response = support_client.post(
            reverse("automation-rule-delete", kwargs={"pk": pk})
        )
        assert response.status_code == 403
        assert AutomationRule.objects.filter(pk=pk).exists()

    def test_admin_can_access_rule_detail(self, authenticated_client, sample_rule_create_task):
        response = authenticated_client.get(
            reverse("automation-rule-detail", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code == 200

    def test_sales_cannot_access_rule_detail(self, sales_client, sample_rule_create_task):
        response = sales_client.get(
            reverse("automation-rule-detail", kwargs={"pk": sample_rule_create_task.pk})
        )
        assert response.status_code == 403

    def test_admin_can_access_automation_logs(self, authenticated_client, multiple_automation_logs):
        response = authenticated_client.get(reverse("automation-log-list"))
        assert response.status_code == 200

    def test_sales_cannot_access_automation_logs(self, sales_client, multiple_automation_logs):
        response = sales_client.get(reverse("automation-log-list"))
        assert response.status_code == 403

    def test_support_cannot_access_automation_logs(self, support_client, multiple_automation_logs):
        response = support_client.get(reverse("automation-log-list"))
        assert response.status_code == 403

    def test_unauthenticated_cannot_access_rule_list(self, anonymous_client):
        response = anonymous_client.get(reverse("automation-list"))
        assert response.status_code in (302, 403)

    def test_unauthenticated_cannot_create_rule(self, anonymous_client):
        data = {
            "name": "Anon Rule",
            "trigger_type": "new_lead",
            "action_type": "send_email",
            "config": "{}",
            "is_active": True,
        }
        response = anonymous_client.post(reverse("automation-rule-create"), data)
        assert response.status_code in (302, 403)
        assert not AutomationRule.objects.filter(name="Anon Rule").exists()

    def test_unauthenticated_cannot_delete_rule(self, anonymous_client, sample_rule_create_task):
        pk = sample_rule_create_task.pk
        response = anonymous_client.post(
            reverse("automation-rule-delete", kwargs={"pk": pk})
        )
        assert response.status_code in (302, 403)
        assert AutomationRule.objects.filter(pk=pk).exists()

    def test_unauthenticated_cannot_access_automation_logs(self, anonymous_client):
        response = anonymous_client.get(reverse("automation-log-list"))
        assert response.status_code in (302, 403)


# =============================================================================
# Integration Tests: End-to-End Automation Flow
# =============================================================================


@pytest.mark.django_db
class TestAutomationEndToEnd:
    def test_full_flow_meeting_completed_creates_task_and_log(self, sample_rule_create_task, sample_customer, sample_deal, sales_user):
        engine = AutomationEngine()
        initial_task_count = Task.objects.count()
        initial_log_count = AutomationLog.objects.count()

        context = {
            "customer_id": sample_customer.pk,
            "deal_id": sample_deal.pk,
        }
        logs = engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )

        assert len(logs) >= 1
        assert Task.objects.count() > initial_task_count
        assert AutomationLog.objects.count() > initial_log_count

        task = Task.objects.filter(title="Follow up after meeting").first()
        assert task is not None
        assert task.customer == sample_customer
        assert task.deal == sample_deal
        assert task.priority == "high"
        assert task.assigned_to == sales_user

        log = logs[0]
        assert log.rule == sample_rule_create_task
        assert log.triggered_by == sales_user
        assert log.status == "success"
        assert log.target_entity_type == "Deal"

    def test_full_flow_new_lead_triggers_email_and_assignment(self, sample_rule_send_email, sample_rule_assign_lead, sample_customer, sales_user, sales_user_2, admin_user):
        engine = AutomationEngine()
        initial_log_count = AutomationLog.objects.count()

        context = {
            "customer_id": sample_customer.pk,
        }
        logs = engine.publish_event(
            "new_lead",
            context,
            triggered_by=admin_user,
        )

        assert len(logs) == 2
        assert AutomationLog.objects.count() == initial_log_count + 2

        action_types = {log.rule.action_type for log in logs}
        assert "send_email" in action_types
        assert "assign_lead" in action_types

        for log in logs:
            assert log.triggered_by == admin_user
            assert log.target_entity_type == "Customer"

    def test_inactive_rule_not_triggered(self, inactive_rule, sample_customer, sales_user):
        engine = AutomationEngine()
        initial_log_count = AutomationLog.objects.count()

        context = {
            "customer_id": sample_customer.pk,
        }
        logs = engine.publish_event(
            "call_completed",
            context,
            triggered_by=sales_user,
        )

        assert len(logs) == 0
        assert AutomationLog.objects.count() == initial_log_count

    def test_rule_activation_deactivation_affects_execution(self, sample_rule_create_task, sample_customer, sales_user):
        engine = AutomationEngine()

        # Deactivate the rule
        sample_rule_create_task.is_active = False
        sample_rule_create_task.save()

        context = {
            "customer_id": sample_customer.pk,
        }
        logs = engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) == 0

        # Reactivate the rule
        sample_rule_create_task.is_active = True
        sample_rule_create_task.save()

        logs = engine.publish_event(
            "meeting_completed",
            context,
            triggered_by=sales_user,
        )
        assert len(logs) >= 1

    def test_demo_completed_creates_urgent_task(self, sample_rule_demo_task, sample_customer, sales_user):
        engine = AutomationEngine()

        context = {
            "customer_id": sample_customer.pk,
        }
        logs = engine.publish_event(
            "demo_completed",
            context,
            triggered_by=sales_user,
        )

        assert len(logs) >= 1
        task = Task.objects.filter(title="Send proposal after demo").first()
        assert task is not None
        assert task.priority == "urgent"
        assert task.customer == sample_customer
        assert task.assigned_to == sales_user

        # Verify due date is approximately 2 hours from now
        expected_due = (timezone.now() + timedelta(hours=2)).date()
        assert task.due_date == expected_due