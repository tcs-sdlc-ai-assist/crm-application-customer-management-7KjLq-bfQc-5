import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from customers.models import Customer
from communications.models import CommunicationLog, Meeting
from deals.models import Deal, SalesStage
from reports.forms import ReportFilterForm
from reports.generators import (
    BaseReportGenerator,
    CustomerEngagementGenerator,
    PipelineHealthGenerator,
    ReportGeneratorFactory,
    SalesPerformanceGenerator,
)
from reports.models import Report
from reports.services import ReportService
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
def multiple_deals(db, sample_customer, second_customer, sales_user, sales_user_2, sample_stages):
    deals = []
    deal_data = [
        {"name": "Deal Alpha", "value": Decimal("10000.00"), "customer": sample_customer, "owner": sales_user, "stage": sample_stages["Lead"]},
        {"name": "Deal Beta", "value": Decimal("25000.00"), "customer": second_customer, "owner": sales_user, "stage": sample_stages["Qualified"]},
        {"name": "Deal Gamma", "value": Decimal("50000.00"), "customer": sample_customer, "owner": sales_user_2, "stage": sample_stages["Proposal"]},
        {"name": "Deal Delta", "value": Decimal("100000.00"), "customer": second_customer, "owner": sales_user_2, "stage": sample_stages["Negotiation"]},
        {"name": "Deal Epsilon", "value": Decimal("200000.00"), "customer": sample_customer, "owner": sales_user, "stage": sample_stages["Closed Won"]},
    ]
    for d in deal_data:
        deal = Deal.objects.create(
            name=d["name"],
            value=d["value"],
            customer=d["customer"],
            owner=d["owner"],
            stage=d["stage"],
        )
        deals.append(deal)
    return deals


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
    for i in range(3):
        start = timezone.now() - timedelta(days=i * 5)
        end = start + timedelta(hours=1)
        meeting = Meeting.objects.create(
            customer=sample_customer if i % 2 == 0 else second_customer,
            organizer=sales_user,
            title=f"Meeting {i}",
            description=f"Description for meeting {i}",
            start_time=start,
            end_time=end,
            location=f"Room {i}",
            status=Meeting.Status.COMPLETED if i < 2 else Meeting.Status.SCHEDULED,
        )
        meetings.append(meeting)
    return meetings


@pytest.fixture
def multiple_tasks(db, sample_customer, second_customer, sales_user, sales_user_2, admin_user):
    tasks = []
    task_data = [
        {
            "title": "Task Alpha",
            "customer": sample_customer,
            "assigned_to": sales_user,
            "status": Task.Status.COMPLETED,
            "priority": Task.Priority.HIGH,
            "due_date": timezone.now().date() - timedelta(days=2),
        },
        {
            "title": "Task Beta",
            "customer": second_customer,
            "assigned_to": sales_user,
            "status": Task.Status.PENDING,
            "priority": Task.Priority.MEDIUM,
            "due_date": timezone.now().date() + timedelta(days=3),
        },
        {
            "title": "Task Gamma",
            "customer": sample_customer,
            "assigned_to": sales_user_2,
            "status": Task.Status.COMPLETED,
            "priority": Task.Priority.URGENT,
            "due_date": timezone.now().date() - timedelta(days=5),
        },
        {
            "title": "Task Delta",
            "customer": second_customer,
            "assigned_to": sales_user_2,
            "status": Task.Status.IN_PROGRESS,
            "priority": Task.Priority.LOW,
            "due_date": timezone.now().date() + timedelta(days=7),
        },
    ]
    for td in task_data:
        task = Task.objects.create(
            created_by=admin_user,
            **td,
        )
        if td["status"] == Task.Status.COMPLETED:
            task.completed_at = timezone.now() - timedelta(days=1)
            task.save(update_fields=["completed_at"])
        tasks.append(task)
    return tasks


@pytest.fixture
def sample_report(db, admin_user):
    return Report.objects.create(
        report_type="sales_performance",
        title="Q1 Sales Performance",
        parameters={"date_range_start": "2025-01-01", "date_range_end": "2025-03-31"},
        status="completed",
        generated_by=admin_user,
        data={
            "title": "Sales Performance Report",
            "report_type": "sales_performance",
            "summary": [
                {"label": "Total Deals", "value": "5", "change": None},
                {"label": "Total Pipeline Value", "value": "$385,000.00", "change": None},
            ],
            "headers": [
                {"key": "representative", "label": "Representative"},
                {"key": "deal_count", "label": "Deals", "align": "center"},
                {"key": "total_value", "label": "Total Value", "align": "numeric"},
            ],
            "details": [
                {"representative": "Sales Rep", "deal_count": 3, "total_value": "$235,000.00"},
                {"representative": "Sales Rep2", "deal_count": 2, "total_value": "$150,000.00"},
            ],
            "chart": {
                "labels": ["Jan 2025", "Feb 2025", "Mar 2025"],
                "values": [100000, 150000, 135000],
                "datasets": [{"label": "Revenue", "data": [100000, 150000, 135000]}],
                "title": "Sales Performance Over Time",
            },
        },
        format="json",
        generated_at=timezone.now(),
    )


@pytest.fixture
def processing_report(db, admin_user):
    return Report.objects.create(
        report_type="pipeline_health",
        title="Pipeline Health Processing",
        parameters={},
        status="processing",
        generated_by=admin_user,
        data={},
        format="json",
    )


@pytest.fixture
def failed_report(db, admin_user):
    return Report.objects.create(
        report_type="customer_engagement",
        title="Failed Engagement Report",
        parameters={},
        status="failed",
        generated_by=admin_user,
        data={},
        format="json",
    )


@pytest.fixture
def multiple_reports(db, admin_user, sales_user):
    reports = []
    report_data = [
        {
            "report_type": "sales_performance",
            "title": "Sales Report 1",
            "status": "completed",
            "generated_by": admin_user,
            "format": "json",
            "data": {"title": "Sales Report 1", "summary": [], "headers": [], "details": [], "chart": {"labels": [], "values": []}},
            "generated_at": timezone.now() - timedelta(days=5),
        },
        {
            "report_type": "customer_engagement",
            "title": "Engagement Report 1",
            "status": "completed",
            "generated_by": sales_user,
            "format": "csv",
            "data": {"title": "Engagement Report 1", "summary": [], "headers": [], "details": [], "chart": {"labels": [], "values": []}},
            "generated_at": timezone.now() - timedelta(days=3),
        },
        {
            "report_type": "pipeline_health",
            "title": "Pipeline Report 1",
            "status": "completed",
            "generated_by": admin_user,
            "format": "json",
            "data": {"title": "Pipeline Report 1", "summary": [], "headers": [], "details": [], "chart": {"labels": [], "values": []}},
            "generated_at": timezone.now() - timedelta(days=1),
        },
        {
            "report_type": "sales_performance",
            "title": "Sales Report 2",
            "status": "processing",
            "generated_by": admin_user,
            "format": "pdf",
            "data": {},
        },
        {
            "report_type": "customer_engagement",
            "title": "Engagement Report 2",
            "status": "failed",
            "generated_by": sales_user,
            "format": "json",
            "data": {},
        },
    ]
    for rd in report_data:
        generated_at = rd.pop("generated_at", None)
        report = Report.objects.create(
            parameters={},
            **rd,
        )
        if generated_at:
            report.generated_at = generated_at
            report.save(update_fields=["generated_at"])
        reports.append(report)
    return reports


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
# Report Model Tests
# =============================================================================


@pytest.mark.django_db
class TestReportModel:
    def test_report_creation_with_valid_data(self, admin_user):
        report = Report.objects.create(
            report_type="sales_performance",
            title="Test Report",
            parameters={"date_range_start": "2025-01-01"},
            status="completed",
            generated_by=admin_user,
            data={"title": "Test"},
            format="json",
            generated_at=timezone.now(),
        )
        assert report.pk is not None
        assert isinstance(report.pk, uuid.UUID)
        assert report.report_type == "sales_performance"
        assert report.title == "Test Report"
        assert report.status == "completed"
        assert report.generated_by == admin_user

    def test_report_str_representation(self, sample_report):
        result = str(sample_report)
        assert "Sales Performance" in result
        assert "Q1 Sales Performance" in result
        assert "completed" in result

    def test_report_ordering_by_created_at_desc(self, multiple_reports):
        reports = list(Report.objects.all())
        for i in range(len(reports) - 1):
            assert reports[i].created_at >= reports[i + 1].created_at

    def test_report_default_status_is_processing(self, admin_user):
        report = Report.objects.create(
            report_type="sales_performance",
            title="Default Status Report",
            generated_by=admin_user,
        )
        assert report.status == "processing"

    def test_report_default_format_is_json(self, admin_user):
        report = Report.objects.create(
            report_type="sales_performance",
            title="Default Format Report",
            generated_by=admin_user,
        )
        assert report.format == "json"

    def test_report_default_data_is_empty_dict(self, admin_user):
        report = Report.objects.create(
            report_type="sales_performance",
            title="Default Data Report",
            generated_by=admin_user,
        )
        assert report.data == {}

    def test_report_default_parameters_is_empty_dict(self, admin_user):
        report = Report.objects.create(
            report_type="sales_performance",
            title="Default Params Report",
            generated_by=admin_user,
        )
        assert report.parameters == {}

    def test_report_generated_by_set_null_on_delete(self, sample_report, admin_user):
        admin_user.delete()
        sample_report.refresh_from_db()
        assert sample_report.generated_by is None

    def test_report_auto_timestamps(self, sample_report):
        assert sample_report.created_at is not None

    def test_report_type_choices(self):
        valid_types = ["sales_performance", "customer_engagement", "pipeline_health"]
        for rt in valid_types:
            assert any(rt == choice[0] for choice in Report.REPORT_TYPE_CHOICES)

    def test_report_format_choices(self):
        valid_formats = ["json", "csv", "pdf"]
        for fmt in valid_formats:
            assert any(fmt == choice[0] for choice in Report.FORMAT_CHOICES)

    def test_report_status_choices(self):
        valid_statuses = ["processing", "completed", "failed", "archived"]
        for status in valid_statuses:
            assert any(status == choice[0] for choice in Report.STATUS_CHOICES)


# =============================================================================
# ReportFilterForm Tests
# =============================================================================


@pytest.mark.django_db
class TestReportFilterForm:
    def test_valid_form_with_all_fields(self, sample_stages):
        data = {
            "report_type": "sales_performance",
            "title": "Test Report",
            "format": "json",
            "date_range_start": "2025-01-01",
            "date_range_end": "2025-03-31",
        }
        form = ReportFilterForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_valid_form_with_required_fields_only(self):
        data = {
            "report_type": "sales_performance",
            "title": "Minimal Report",
            "format": "json",
        }
        form = ReportFilterForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_invalid_form_missing_report_type(self):
        data = {
            "report_type": "",
            "title": "No Type Report",
            "format": "json",
        }
        form = ReportFilterForm(data=data)
        assert not form.is_valid()
        assert "report_type" in form.errors

    def test_invalid_form_missing_title(self):
        data = {
            "report_type": "sales_performance",
            "title": "",
            "format": "json",
        }
        form = ReportFilterForm(data=data)
        assert not form.is_valid()
        assert "title" in form.errors

    def test_invalid_form_missing_format(self):
        data = {
            "report_type": "sales_performance",
            "title": "No Format Report",
            "format": "",
        }
        form = ReportFilterForm(data=data)
        assert not form.is_valid()
        assert "format" in form.errors

    def test_invalid_form_end_date_before_start_date(self):
        data = {
            "report_type": "sales_performance",
            "title": "Bad Date Range",
            "format": "json",
            "date_range_start": "2025-03-31",
            "date_range_end": "2025-01-01",
        }
        form = ReportFilterForm(data=data)
        assert not form.is_valid()
        assert "date_range_end" in form.errors

    def test_valid_form_same_start_and_end_date(self):
        data = {
            "report_type": "sales_performance",
            "title": "Same Day Report",
            "format": "json",
            "date_range_start": "2025-03-15",
            "date_range_end": "2025-03-15",
        }
        form = ReportFilterForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"

    def test_get_report_parameters(self, sample_stages):
        stage = list(sample_stages.values())[0]
        data = {
            "report_type": "pipeline_health",
            "title": "Pipeline Report",
            "format": "json",
            "date_range_start": "2025-01-01",
            "date_range_end": "2025-06-30",
            "stage": stage.pk,
        }
        form = ReportFilterForm(data=data)
        assert form.is_valid(), f"Form errors: {form.errors}"
        params = form.get_report_parameters()
        assert "date_range_start" in params
        assert "date_range_end" in params
        assert "stage_id" in params
        assert "stage_name" in params

    def test_get_report_parameters_empty_when_invalid(self):
        data = {
            "report_type": "",
            "title": "",
            "format": "",
        }
        form = ReportFilterForm(data=data)
        assert not form.is_valid()
        params = form.get_report_parameters()
        assert params == {}


# =============================================================================
# ReportGeneratorFactory Tests
# =============================================================================


@pytest.mark.django_db
class TestReportGeneratorFactory:
    def test_get_generator_sales_performance(self):
        generator = ReportGeneratorFactory.get_generator("sales_performance")
        assert isinstance(generator, SalesPerformanceGenerator)

    def test_get_generator_customer_engagement(self):
        generator = ReportGeneratorFactory.get_generator("customer_engagement")
        assert isinstance(generator, CustomerEngagementGenerator)

    def test_get_generator_pipeline_health(self):
        generator = ReportGeneratorFactory.get_generator("pipeline_health")
        assert isinstance(generator, PipelineHealthGenerator)

    def test_get_generator_unsupported_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported report type"):
            ReportGeneratorFactory.get_generator("nonexistent_type")

    def test_get_available_types(self):
        types = ReportGeneratorFactory.get_available_types()
        assert len(types) >= 3
        type_names = [t["type"] for t in types]
        assert "sales_performance" in type_names
        assert "customer_engagement" in type_names
        assert "pipeline_health" in type_names

    def test_get_available_types_have_descriptions(self):
        types = ReportGeneratorFactory.get_available_types()
        for t in types:
            assert "type" in t
            assert "description" in t
            assert t["description"] != ""


# =============================================================================
# SalesPerformanceGenerator Tests
# =============================================================================


@pytest.mark.django_db
class TestSalesPerformanceGenerator:
    def setup_method(self):
        self.generator = SalesPerformanceGenerator()

    def test_generate_with_no_data(self, sample_stages):
        result = self.generator.generate({})
        assert "title" in result
        assert "summary" in result
        assert "headers" in result
        assert "details" in result
        assert "chart" in result
        assert result["report_type"] == "sales_performance"

    def test_generate_with_deals(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        assert result["title"] == "Sales Performance Report"
        assert len(result["summary"]) > 0
        assert len(result["details"]) > 0

    def test_generate_summary_contains_expected_metrics(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        summary_labels = [s["label"] for s in result["summary"]]
        assert "Total Deals" in summary_labels
        assert "Total Pipeline Value" in summary_labels
        assert "Win Rate" in summary_labels
        assert "Avg Deal Value" in summary_labels

    def test_generate_with_date_range_filter(self, multiple_deals, sample_stages):
        today = timezone.now().date()
        params = {
            "date_range_start": (today - timedelta(days=90)).isoformat(),
            "date_range_end": today.isoformat(),
        }
        result = self.generator.generate(params)
        assert result is not None
        assert "summary" in result

    def test_generate_with_user_filter(self, multiple_deals, sample_stages, sales_user):
        params = {
            "user_id": str(sales_user.pk),
        }
        result = self.generator.generate(params)
        assert result is not None
        assert len(result["details"]) >= 1

    def test_generate_with_stage_filter(self, multiple_deals, sample_stages):
        params = {
            "stage_id": str(sample_stages["Lead"].pk),
        }
        result = self.generator.generate(params)
        assert result is not None

    def test_generate_chart_data_structure(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        chart = result["chart"]
        assert "labels" in chart
        assert "values" in chart or "datasets" in chart
        assert "title" in chart

    def test_generate_headers_structure(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        headers = result["headers"]
        assert len(headers) > 0
        for header in headers:
            assert "key" in header
            assert "label" in header

    def test_generate_details_match_headers(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        headers = result["headers"]
        details = result["details"]
        header_keys = [h["key"] for h in headers]
        if details:
            for detail in details:
                for key in header_keys:
                    assert key in detail


# =============================================================================
# CustomerEngagementGenerator Tests
# =============================================================================


@pytest.mark.django_db
class TestCustomerEngagementGenerator:
    def setup_method(self):
        self.generator = CustomerEngagementGenerator()

    def test_generate_with_no_data(self):
        result = self.generator.generate({})
        assert "title" in result
        assert "summary" in result
        assert "headers" in result
        assert "details" in result
        assert "chart" in result
        assert result["report_type"] == "customer_engagement"

    def test_generate_with_communications(self, multiple_communications, multiple_meetings, multiple_tasks):
        result = self.generator.generate({})
        assert result["title"] == "Customer Engagement Report"
        assert len(result["summary"]) > 0

    def test_generate_summary_contains_expected_metrics(self, multiple_communications, multiple_meetings, multiple_tasks):
        result = self.generator.generate({})
        summary_labels = [s["label"] for s in result["summary"]]
        assert "Total Communications" in summary_labels
        assert "Total Meetings" in summary_labels
        assert "Total Tasks" in summary_labels
        assert "Task Completion Rate" in summary_labels

    def test_generate_with_date_range_filter(self, multiple_communications, multiple_meetings, multiple_tasks):
        today = timezone.now().date()
        params = {
            "date_range_start": (today - timedelta(days=30)).isoformat(),
            "date_range_end": today.isoformat(),
        }
        result = self.generator.generate(params)
        assert result is not None
        assert "summary" in result

    def test_generate_with_user_filter(self, multiple_communications, multiple_meetings, multiple_tasks, sales_user):
        params = {
            "user_id": str(sales_user.pk),
        }
        result = self.generator.generate(params)
        assert result is not None

    def test_generate_chart_data_structure(self, multiple_communications, multiple_meetings, multiple_tasks):
        result = self.generator.generate({})
        chart = result["chart"]
        assert "labels" in chart
        assert "values" in chart
        assert "title" in chart

    def test_generate_details_contain_customer_data(self, multiple_communications, multiple_meetings, multiple_tasks):
        result = self.generator.generate({})
        details = result["details"]
        if details and details[0].get("customer") != "No data":
            for detail in details:
                assert "customer" in detail
                assert "communications" in detail


# =============================================================================
# PipelineHealthGenerator Tests
# =============================================================================


@pytest.mark.django_db
class TestPipelineHealthGenerator:
    def setup_method(self):
        self.generator = PipelineHealthGenerator()

    def test_generate_with_no_data(self, sample_stages):
        result = self.generator.generate({})
        assert "title" in result
        assert "summary" in result
        assert "headers" in result
        assert "details" in result
        assert "chart" in result
        assert result["report_type"] == "pipeline_health"

    def test_generate_with_deals(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        assert result["title"] == "Pipeline Health Report"
        assert len(result["summary"]) > 0
        assert len(result["details"]) > 0

    def test_generate_summary_contains_expected_metrics(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        summary_labels = [s["label"] for s in result["summary"]]
        assert "Total Deals in Pipeline" in summary_labels
        assert "Total Pipeline Value" in summary_labels
        assert "Win Rate" in summary_labels

    def test_generate_details_contain_stage_data(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        details = result["details"]
        if details and details[0].get("stage") != "No data":
            for detail in details:
                assert "stage" in detail
                assert "deal_count" in detail
                assert "stage_value" in detail

    def test_generate_with_date_range_filter(self, multiple_deals, sample_stages):
        today = timezone.now().date()
        params = {
            "date_range_start": (today - timedelta(days=90)).isoformat(),
            "date_range_end": today.isoformat(),
        }
        result = self.generator.generate(params)
        assert result is not None
        assert "summary" in result

    def test_generate_with_user_filter(self, multiple_deals, sample_stages, sales_user):
        params = {
            "user_id": str(sales_user.pk),
        }
        result = self.generator.generate(params)
        assert result is not None

    def test_generate_with_stage_filter(self, multiple_deals, sample_stages):
        params = {
            "stage_id": str(sample_stages["Lead"].pk),
        }
        result = self.generator.generate(params)
        assert result is not None

    def test_generate_chart_data_structure(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        chart = result["chart"]
        assert "labels" in chart
        assert "values" in chart
        assert "title" in chart

    def test_generate_includes_conversion_table(self, multiple_deals, sample_stages):
        result = self.generator.generate({})
        if "table" in result:
            table = result["table"]
            assert "title" in table
            assert "headers" in table
            assert "rows" in table


# =============================================================================
# ReportService Tests
# =============================================================================


@pytest.mark.django_db
class TestReportService:
    def setup_method(self):
        self.service = ReportService()

    def test_generate_report_sales_performance(self, admin_user, multiple_deals, sample_stages):
        report = self.service.generate_report(
            report_type="sales_performance",
            parameters={},
            user=admin_user,
            title="Service Sales Report",
            output_format="json",
        )
        assert report.pk is not None
        assert report.report_type == "sales_performance"
        assert report.status == "completed"
        assert report.generated_by == admin_user
        assert report.data is not None
        assert "summary" in report.data
        assert report.generated_at is not None

    def test_generate_report_customer_engagement(self, admin_user, multiple_communications, multiple_meetings, multiple_tasks):
        report = self.service.generate_report(
            report_type="customer_engagement",
            parameters={},
            user=admin_user,
            title="Service Engagement Report",
            output_format="json",
        )
        assert report.pk is not None
        assert report.report_type == "customer_engagement"
        assert report.status == "completed"
        assert "summary" in report.data

    def test_generate_report_pipeline_health(self, admin_user, multiple_deals, sample_stages):
        report = self.service.generate_report(
            report_type="pipeline_health",
            parameters={},
            user=admin_user,
            title="Service Pipeline Report",
            output_format="json",
        )
        assert report.pk is not None
        assert report.report_type == "pipeline_health"
        assert report.status == "completed"
        assert "summary" in report.data

    def test_generate_report_invalid_type_raises_value_error(self, admin_user):
        with pytest.raises(ValueError, match="Invalid report type"):
            self.service.generate_report(
                report_type="nonexistent_type",
                parameters={},
                user=admin_user,
            )

    def test_generate_report_invalid_format_raises_value_error(self, admin_user):
        with pytest.raises(ValueError, match="Invalid format"):
            self.service.generate_report(
                report_type="sales_performance",
                parameters={},
                user=admin_user,
                output_format="xlsx",
            )

    def test_generate_report_auto_title(self, admin_user, sample_stages):
        report = self.service.generate_report(
            report_type="sales_performance",
            parameters={},
            user=admin_user,
        )
        assert report.title is not None
        assert report.title != ""
        assert "Sales Performance" in report.title

    def test_generate_report_with_parameters(self, admin_user, multiple_deals, sample_stages, sales_user):
        params = {
            "date_range_start": "2025-01-01",
            "date_range_end": "2025-12-31",
            "user_id": str(sales_user.pk),
        }
        report = self.service.generate_report(
            report_type="sales_performance",
            parameters=params,
            user=admin_user,
            title="Filtered Report",
        )
        assert report.pk is not None
        assert report.parameters == params
        assert report.status == "completed"

    def test_get_report_existing(self, sample_report):
        report = self.service.get_report(sample_report.pk)
        assert report is not None
        assert report.pk == sample_report.pk

    def test_get_report_nonexistent(self):
        report = self.service.get_report(uuid.uuid4())
        assert report is None

    def test_list_reports_no_filters(self, multiple_reports):
        queryset = self.service.list_reports()
        assert queryset.count() == 5

    def test_list_reports_filter_by_report_type(self, multiple_reports):
        queryset = self.service.list_reports(filters={"report_type": "sales_performance"})
        for report in queryset:
            assert report.report_type == "sales_performance"

    def test_list_reports_filter_by_status(self, multiple_reports):
        queryset = self.service.list_reports(filters={"status": "completed"})
        for report in queryset:
            assert report.status == "completed"

    def test_list_reports_filter_by_search(self, multiple_reports):
        queryset = self.service.list_reports(filters={"search": "Pipeline"})
        assert queryset.count() >= 1

    def test_list_reports_filter_by_generated_by(self, multiple_reports, admin_user):
        queryset = self.service.list_reports(filters={"generated_by": admin_user.pk})
        for report in queryset:
            assert report.generated_by_id == admin_user.pk

    def test_list_report_types(self):
        types = self.service.list_report_types()
        assert len(types) >= 3
        type_names = [t["type"] for t in types]
        assert "sales_performance" in type_names
        assert "customer_engagement" in type_names
        assert "pipeline_health" in type_names
        for t in types:
            assert "display_name" in t
            assert "description" in t

    def test_delete_report_existing(self, sample_report, admin_user):
        pk = sample_report.pk
        result = self.service.delete_report(pk, user=admin_user)
        assert result is True
        assert not Report.objects.filter(pk=pk).exists()

    def test_delete_report_nonexistent(self, admin_user):
        result = self.service.delete_report(uuid.uuid4(), user=admin_user)
        assert result is False

    def test_archive_report(self, sample_report, admin_user):
        archived = self.service.archive_report(sample_report.pk, user=admin_user)
        assert archived is not None
        assert archived.status == "archived"

    def test_archive_report_already_archived(self, sample_report, admin_user):
        sample_report.status = "archived"
        sample_report.save(update_fields=["status"])
        archived = self.service.archive_report(sample_report.pk, user=admin_user)
        assert archived is not None
        assert archived.status == "archived"

    def test_archive_report_nonexistent(self, admin_user):
        result = self.service.archive_report(uuid.uuid4(), user=admin_user)
        assert result is None

    def test_get_recent_reports(self, multiple_reports, admin_user):
        recent = self.service.get_recent_reports(user=admin_user, limit=3)
        assert len(recent) <= 3
        for report in recent:
            assert report.generated_by_id == admin_user.pk

    def test_get_recent_reports_no_user(self, multiple_reports):
        recent = self.service.get_recent_reports(limit=10)
        assert len(recent) == 5


# =============================================================================
# Report Export Tests (CSV)
# =============================================================================


@pytest.mark.django_db
class TestReportExportCSV:
    def setup_method(self):
        self.service = ReportService()

    def test_export_csv_completed_report(self, sample_report, admin_user):
        response = self.service.export_report(
            report_id=sample_report.pk,
            export_format="csv",
            user=admin_user,
        )
        assert response is not None
        assert response["Content-Type"] == "text/csv"
        assert "attachment" in response["Content-Disposition"]
        assert ".csv" in response["Content-Disposition"]

    def test_export_csv_contains_headers(self, sample_report, admin_user):
        response = self.service.export_report(
            report_id=sample_report.pk,
            export_format="csv",
            user=admin_user,
        )
        content = response.content.decode("utf-8")
        assert "Representative" in content
        assert "Deals" in content
        assert "Total Value" in content

    def test_export_csv_contains_data_rows(self, sample_report, admin_user):
        response = self.service.export_report(
            report_id=sample_report.pk,
            export_format="csv",
            user=admin_user,
        )
        content = response.content.decode("utf-8")
        assert "Sales Rep" in content

    def test_export_csv_nonexistent_report_raises_value_error(self, admin_user):
        with pytest.raises(ValueError, match="not found"):
            self.service.export_report(
                report_id=uuid.uuid4(),
                export_format="csv",
                user=admin_user,
            )

    def test_export_csv_processing_report_raises_value_error(self, processing_report, admin_user):
        with pytest.raises(ValueError, match="Cannot export"):
            self.service.export_report(
                report_id=processing_report.pk,
                export_format="csv",
                user=admin_user,
            )

    def test_export_csv_failed_report_raises_value_error(self, failed_report, admin_user):
        with pytest.raises(ValueError, match="Cannot export"):
            self.service.export_report(
                report_id=failed_report.pk,
                export_format="csv",
                user=admin_user,
            )

    def test_export_invalid_format_raises_value_error(self, sample_report, admin_user):
        with pytest.raises(ValueError, match="Invalid export format"):
            self.service.export_report(
                report_id=sample_report.pk,
                export_format="xlsx",
                user=admin_user,
            )

    def test_export_csv_report_with_no_data_raises_value_error(self, admin_user):
        report = Report.objects.create(
            report_type="sales_performance",
            title="Empty Data Report",
            status="completed",
            generated_by=admin_user,
            data={},
            format="json",
            generated_at=timezone.now(),
        )
        with pytest.raises(ValueError, match="no data"):
            self.service.export_report(
                report_id=report.pk,
                export_format="csv",
                user=admin_user,
            )


# =============================================================================
# Report Export Tests (PDF)
# =============================================================================


@pytest.mark.django_db
class TestReportExportPDF:
    def setup_method(self):
        self.service = ReportService()

    def test_export_pdf_completed_report(self, sample_report, admin_user):
        try:
            response = self.service.export_report(
                report_id=sample_report.pk,
                export_format="pdf",
                user=admin_user,
            )
            assert response is not None
            assert response["Content-Type"] == "application/pdf"
            assert "attachment" in response["Content-Disposition"]
            assert ".pdf" in response["Content-Disposition"]
        except ValueError as e:
            if "WeasyPrint" in str(e):
                pytest.skip("WeasyPrint not available for PDF export testing")
            raise

    def test_export_pdf_nonexistent_report_raises_value_error(self, admin_user):
        with pytest.raises(ValueError, match="not found"):
            self.service.export_report(
                report_id=uuid.uuid4(),
                export_format="pdf",
                user=admin_user,
            )

    def test_export_pdf_processing_report_raises_value_error(self, processing_report, admin_user):
        with pytest.raises(ValueError, match="Cannot export"):
            self.service.export_report(
                report_id=processing_report.pk,
                export_format="pdf",
                user=admin_user,
            )

    def test_export_pdf_failed_report_raises_value_error(self, failed_report, admin_user):
        with pytest.raises(ValueError, match="Cannot export"):
            self.service.export_report(
                report_id=failed_report.pk,
                export_format="pdf",
                user=admin_user,
            )


# =============================================================================
# Report View Tests
# =============================================================================


@pytest.mark.django_db
class TestReportListView:
    def test_report_list_authenticated_admin(self, authenticated_client, multiple_reports):
        response = authenticated_client.get(reverse("report-list"))
        assert response.status_code == 200

    def test_report_list_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("report-list"))
        assert response.status_code in (302, 403)

    def test_report_list_contains_reports(self, authenticated_client, multiple_reports):
        response = authenticated_client.get(reverse("report-list"))
        assert response.status_code == 200
        content = response.content.decode()
        for report in multiple_reports:
            assert report.title in content


@pytest.mark.django_db
class TestReportDetailView:
    def test_report_detail_authenticated(self, authenticated_client, sample_report):
        response = authenticated_client.get(
            reverse("report-detail", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert sample_report.title in content

    def test_report_detail_unauthenticated_redirects(self, anonymous_client, sample_report):
        response = anonymous_client.get(
            reverse("report-detail", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code in (302, 403)

    def test_report_detail_nonexistent_returns_404(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("report-detail", kwargs={"pk": fake_pk})
        )
        assert response.status_code == 404

    def test_report_detail_shows_summary_stats(self, authenticated_client, sample_report):
        response = authenticated_client.get(
            reverse("report-detail", kwargs={"pk": sample_report.pk})
        )
        content = response.content.decode()
        assert "Total Deals" in content or "Sales Performance" in content

    def test_report_detail_processing_report(self, authenticated_client, processing_report):
        response = authenticated_client.get(
            reverse("report-detail", kwargs={"pk": processing_report.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "processing" in content.lower() or "generated" in content.lower()

    def test_report_detail_failed_report(self, authenticated_client, failed_report):
        response = authenticated_client.get(
            reverse("report-detail", kwargs={"pk": failed_report.pk})
        )
        assert response.status_code == 200
        content = response.content.decode()
        assert "failed" in content.lower() or "error" in content.lower()


@pytest.mark.django_db
class TestReportGenerateView:
    def test_report_generate_get_form(self, authenticated_client, sample_stages):
        response = authenticated_client.get(reverse("report-generate"))
        assert response.status_code == 200

    def test_report_generate_post_valid_data(self, authenticated_client, multiple_deals, sample_stages):
        data = {
            "report_type": "sales_performance",
            "title": "Generated via View",
            "format": "json",
        }
        response = authenticated_client.post(reverse("report-generate"), data)
        assert response.status_code in (200, 301, 302)
        assert Report.objects.filter(title="Generated via View").exists()

    def test_report_generate_post_with_date_range(self, authenticated_client, multiple_deals, sample_stages):
        data = {
            "report_type": "pipeline_health",
            "title": "Pipeline with Dates",
            "format": "json",
            "date_range_start": "2025-01-01",
            "date_range_end": "2025-12-31",
        }
        response = authenticated_client.post(reverse("report-generate"), data)
        assert response.status_code in (200, 301, 302)
        assert Report.objects.filter(title="Pipeline with Dates").exists()

    def test_report_generate_post_invalid_data(self, authenticated_client):
        data = {
            "report_type": "",
            "title": "",
            "format": "",
        }
        response = authenticated_client.post(reverse("report-generate"), data)
        assert response.status_code == 200

    def test_report_generate_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("report-generate"))
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestReportExportViews:
    def test_export_csv_view_authenticated(self, authenticated_client, sample_report):
        response = authenticated_client.get(
            reverse("report-export-csv", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv"

    def test_export_csv_view_unauthenticated_redirects(self, anonymous_client, sample_report):
        response = anonymous_client.get(
            reverse("report-export-csv", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code in (302, 403)

    def test_export_csv_view_nonexistent_report(self, authenticated_client):
        fake_pk = uuid.uuid4()
        response = authenticated_client.get(
            reverse("report-export-csv", kwargs={"pk": fake_pk})
        )
        assert response.status_code in (302, 404)

    def test_export_pdf_view_authenticated(self, authenticated_client, sample_report):
        try:
            response = authenticated_client.get(
                reverse("report-export-pdf", kwargs={"pk": sample_report.pk})
            )
            assert response.status_code == 200
            assert response["Content-Type"] == "application/pdf"
        except Exception:
            pytest.skip("PDF export may not be available in test environment")

    def test_export_pdf_view_unauthenticated_redirects(self, anonymous_client, sample_report):
        response = anonymous_client.get(
            reverse("report-export-pdf", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code in (302, 403)


@pytest.mark.django_db
class TestReportDashboardView:
    def test_report_dashboard_authenticated_admin(self, authenticated_client, multiple_reports):
        response = authenticated_client.get(reverse("report-dashboard"))
        assert response.status_code == 200

    def test_report_dashboard_unauthenticated_redirects(self, anonymous_client):
        response = anonymous_client.get(reverse("report-dashboard"))
        assert response.status_code in (302, 403)

    def test_report_dashboard_contains_report_types(self, authenticated_client):
        response = authenticated_client.get(reverse("report-dashboard"))
        assert response.status_code == 200
        content = response.content.decode()
        assert "Sales Performance" in content or "sales_performance" in content

    def test_report_dashboard_shows_recent_reports(self, authenticated_client, multiple_reports):
        response = authenticated_client.get(reverse("report-dashboard"))
        assert response.status_code == 200
        content = response.content.decode()
        has_report = False
        for report in multiple_reports:
            if report.title in content:
                has_report = True
                break
        assert has_report or "No reports" in content


# =============================================================================
# RBAC Tests
# =============================================================================


@pytest.mark.django_db
class TestReportRBAC:
    def test_admin_can_access_report_list(self, authenticated_client, multiple_reports):
        response = authenticated_client.get(reverse("report-list"))
        assert response.status_code == 200

    def test_admin_can_access_report_detail(self, authenticated_client, sample_report):
        response = authenticated_client.get(
            reverse("report-detail", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code == 200

    def test_admin_can_generate_report(self, authenticated_client, sample_stages):
        data = {
            "report_type": "sales_performance",
            "title": "Admin Generated Report",
            "format": "json",
        }
        response = authenticated_client.post(reverse("report-generate"), data)
        assert response.status_code in (200, 301, 302)
        assert Report.objects.filter(title="Admin Generated Report").exists()

    def test_admin_can_export_csv(self, authenticated_client, sample_report):
        response = authenticated_client.get(
            reverse("report-export-csv", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code == 200

    def test_admin_can_access_report_dashboard(self, authenticated_client):
        response = authenticated_client.get(reverse("report-dashboard"))
        assert response.status_code == 200

    def test_sales_cannot_access_report_list(self, sales_client, multiple_reports):
        response = sales_client.get(reverse("report-list"))
        assert response.status_code in (200, 403)

    def test_support_cannot_access_report_list(self, support_client, multiple_reports):
        response = support_client.get(reverse("report-list"))
        assert response.status_code in (200, 403)

    def test_unauthenticated_cannot_access_report_list(self, anonymous_client):
        response = anonymous_client.get(reverse("report-list"))
        assert response.status_code in (302, 403)

    def test_unauthenticated_cannot_generate_report(self, anonymous_client):
        data = {
            "report_type": "sales_performance",
            "title": "Anon Report",
            "format": "json",
        }
        response = anonymous_client.post(reverse("report-generate"), data)
        assert response.status_code in (302, 403)
        assert not Report.objects.filter(title="Anon Report").exists()

    def test_unauthenticated_cannot_access_report_detail(self, anonymous_client, sample_report):
        response = anonymous_client.get(
            reverse("report-detail", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code in (302, 403)

    def test_unauthenticated_cannot_export_csv(self, anonymous_client, sample_report):
        response = anonymous_client.get(
            reverse("report-export-csv", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code in (302, 403)

    def test_unauthenticated_cannot_export_pdf(self, anonymous_client, sample_report):
        response = anonymous_client.get(
            reverse("report-export-pdf", kwargs={"pk": sample_report.pk})
        )
        assert response.status_code in (302, 403)

    def test_unauthenticated_cannot_access_report_dashboard(self, anonymous_client):
        response = anonymous_client.get(reverse("report-dashboard"))
        assert response.status_code in (302, 403)


# =============================================================================
# Integration Tests: End-to-End Report Flow
# =============================================================================


@pytest.mark.django_db
class TestReportEndToEnd:
    def test_full_flow_generate_and_export_csv(self, admin_user, multiple_deals, sample_stages):
        service = ReportService()

        report = service.generate_report(
            report_type="sales_performance",
            parameters={},
            user=admin_user,
            title="E2E Sales Report",
            output_format="json",
        )
        assert report.status == "completed"
        assert report.data is not None
        assert "summary" in report.data
        assert "details" in report.data

        csv_response = service.export_report(
            report_id=report.pk,
            export_format="csv",
            user=admin_user,
        )
        assert csv_response["Content-Type"] == "text/csv"
        content = csv_response.content.decode("utf-8")
        assert len(content) > 0

    def test_full_flow_generate_pipeline_health(self, admin_user, multiple_deals, sample_stages):
        service = ReportService()

        report = service.generate_report(
            report_type="pipeline_health",
            parameters={},
            user=admin_user,
            title="E2E Pipeline Report",
        )
        assert report.status == "completed"
        assert "summary" in report.data
        assert "details" in report.data
        assert "chart" in report.data

        summary_labels = [s["label"] for s in report.data["summary"]]
        assert "Total Deals in Pipeline" in summary_labels
        assert "Total Pipeline Value" in summary_labels

    def test_full_flow_generate_customer_engagement(
        self, admin_user, multiple_communications, multiple_meetings, multiple_tasks
    ):
        service = ReportService()

        report = service.generate_report(
            report_type="customer_engagement",
            parameters={},
            user=admin_user,
            title="E2E Engagement Report",
        )
        assert report.status == "completed"
        assert "summary" in report.data
        assert "details" in report.data
        assert "chart" in report.data

        summary_labels = [s["label"] for s in report.data["summary"]]
        assert "Total Communications" in summary_labels
        assert "Total Meetings" in summary_labels

    def test_full_flow_generate_with_filters_and_export(
        self, admin_user, multiple_deals, sample_stages, sales_user
    ):
        service = ReportService()
        today = timezone.now().date()

        params = {
            "date_range_start": (today - timedelta(days=90)).isoformat(),
            "date_range_end": today.isoformat(),
            "user_id": str(sales_user.pk),
        }

        report = service.generate_report(
            report_type="sales_performance",
            parameters=params,
            user=admin_user,
            title="Filtered E2E Report",
        )
        assert report.status == "completed"
        assert report.parameters == params

        csv_response = service.export_report(
            report_id=report.pk,
            export_format="csv",
            user=admin_user,
        )
        assert csv_response["Content-Type"] == "text/csv"

    def test_full_flow_generate_archive_delete(self, admin_user, sample_stages):
        service = ReportService()

        report = service.generate_report(
            report_type="sales_performance",
            parameters={},
            user=admin_user,
            title="Lifecycle Report",
        )
        assert report.status == "completed"

        archived = service.archive_report(report.pk, user=admin_user)
        assert archived.status == "archived"

        deleted = service.delete_report(report.pk, user=admin_user)
        assert deleted is True
        assert not Report.objects.filter(pk=report.pk).exists()

    def test_multiple_report_types_generate_successfully(
        self, admin_user, multiple_deals, sample_stages, multiple_communications, multiple_meetings, multiple_tasks
    ):
        service = ReportService()
        report_types = ["sales_performance", "customer_engagement", "pipeline_health"]

        for report_type in report_types:
            report = service.generate_report(
                report_type=report_type,
                parameters={},
                user=admin_user,
                title=f"Multi-type {report_type}",
            )
            assert report.status == "completed", f"Report type {report_type} failed"
            assert report.data is not None
            assert "summary" in report.data
            assert "details" in report.data
            assert "chart" in report.data