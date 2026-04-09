import logging
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Type

from django.db import models
from django.db.models import Avg, Count, F, Q, Sum
from django.db.models.functions import TruncMonth, TruncWeek
from django.utils import timezone

logger = logging.getLogger(__name__)


class BaseReportGenerator:
    """
    Base class for all report generators.
    Subclasses must implement the generate() method.
    """

    report_type = None
    report_description = ""

    def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate report data based on the given parameters.

        Args:
            parameters: Dictionary of report parameters including
                date_range_start, date_range_end, user_id, stage_id, etc.

        Returns:
            A structured dictionary with keys: summary, details, headers, chart, title.
        """
        raise NotImplementedError("Subclasses must implement generate()")

    def _parse_date(self, value: Any, default: Optional[date] = None) -> Optional[date]:
        """Parse a date value from string or date object."""
        if value is None:
            return default
        if isinstance(value, date):
            return value
        if isinstance(value, str):
            try:
                parts = value.split("-")
                return date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                logger.warning("Failed to parse date: %s", value)
                return default
        return default

    def _get_date_range(self, parameters: Dict[str, Any]):
        """Extract start and end dates from parameters with defaults."""
        today = timezone.now().date()
        default_start = today - timedelta(days=90)
        default_end = today

        start_date = self._parse_date(
            parameters.get("date_range_start"),
            default=default_start,
        )
        end_date = self._parse_date(
            parameters.get("date_range_end"),
            default=default_end,
        )

        if start_date and end_date and start_date > end_date:
            start_date, end_date = end_date, start_date

        return start_date, end_date

    def _get_user_filter(self, parameters: Dict[str, Any]):
        """Extract user_id filter from parameters."""
        user_id = parameters.get("user_id")
        if user_id:
            try:
                return uuid.UUID(str(user_id))
            except (ValueError, AttributeError):
                return user_id
        return None

    def _get_stage_filter(self, parameters: Dict[str, Any]):
        """Extract stage_id filter from parameters."""
        stage_id = parameters.get("stage_id")
        if stage_id:
            try:
                return uuid.UUID(str(stage_id))
            except (ValueError, AttributeError):
                return stage_id
        return None

    def _format_currency(self, value) -> str:
        """Format a decimal value as currency string."""
        if value is None:
            return "$0.00"
        try:
            decimal_value = Decimal(str(value))
            return f"${decimal_value:,.2f}"
        except Exception:
            return "$0.00"

    def _format_percentage(self, value) -> str:
        """Format a numeric value as percentage string."""
        if value is None:
            return "0.0%"
        try:
            return f"{float(value):.1f}%"
        except Exception:
            return "0.0%"


class SalesPerformanceGenerator(BaseReportGenerator):
    """
    Generates sales performance reports.
    Aggregates deal values, win rates, and rep performance by time period.
    """

    report_type = "sales_performance"
    report_description = "Sales performance by representative, team, and time period"

    def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a sales performance report.

        Args:
            parameters: Dict with optional keys:
                - date_range_start: ISO date string
                - date_range_end: ISO date string
                - user_id: UUID of specific user to filter
                - stage_id: UUID of specific stage to filter

        Returns:
            Dict with summary, details, headers, chart, title keys.
        """
        from deals.models import Deal, SalesStage

        start_date, end_date = self._get_date_range(parameters)
        user_id = self._get_user_filter(parameters)
        stage_id = self._get_stage_filter(parameters)

        queryset = Deal.objects.select_related("customer", "owner", "stage").all()

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if user_id:
            queryset = queryset.filter(owner_id=user_id)
        if stage_id:
            queryset = queryset.filter(stage_id=stage_id)

        total_deals = queryset.count()
        total_value = queryset.aggregate(total=Sum("value"))["total"] or Decimal("0")

        won_stages = SalesStage.objects.filter(
            name__icontains="won",
            is_active=True,
        ).values_list("pk", flat=True)

        lost_stages = SalesStage.objects.filter(
            name__icontains="lost",
            is_active=True,
        ).values_list("pk", flat=True)

        won_deals = queryset.filter(stage_id__in=won_stages)
        lost_deals = queryset.filter(stage_id__in=lost_stages)

        won_count = won_deals.count()
        lost_count = lost_deals.count()
        won_value = won_deals.aggregate(total=Sum("value"))["total"] or Decimal("0")

        closed_count = won_count + lost_count
        win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0.0
        avg_deal_value = (total_value / total_deals) if total_deals > 0 else Decimal("0")

        summary = [
            {"label": "Total Deals", "value": str(total_deals), "change": None},
            {"label": "Total Pipeline Value", "value": self._format_currency(total_value), "change": None},
            {"label": "Won Revenue", "value": self._format_currency(won_value), "change": None},
            {"label": "Win Rate", "value": self._format_percentage(win_rate), "change": None},
            {"label": "Avg Deal Value", "value": self._format_currency(avg_deal_value), "change": None},
            {"label": "Deals Won", "value": str(won_count), "change": None},
            {"label": "Deals Lost", "value": str(lost_count), "change": None},
        ]

        rep_performance = (
            queryset
            .values(
                rep_email=F("owner__email"),
                rep_first=F("owner__first_name"),
                rep_last=F("owner__last_name"),
            )
            .annotate(
                deal_count=Count("id"),
                total_value=Sum("value"),
            )
            .order_by("-total_value")
        )

        headers = [
            {"key": "representative", "label": "Representative"},
            {"key": "deal_count", "label": "Deals", "align": "center"},
            {"key": "total_value", "label": "Total Value", "align": "numeric"},
        ]

        details = []
        for rep in rep_performance:
            rep_name = f"{rep['rep_first'] or ''} {rep['rep_last'] or ''}".strip()
            if not rep_name:
                rep_name = rep["rep_email"] or "Unassigned"
            details.append({
                "representative": rep_name,
                "deal_count": rep["deal_count"],
                "total_value": self._format_currency(rep["total_value"]),
            })

        if not details:
            details.append({
                "representative": "No data",
                "deal_count": 0,
                "total_value": self._format_currency(0),
            })

        monthly_data = (
            queryset
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(
                revenue=Sum("value"),
                count=Count("id"),
            )
            .order_by("month")
        )

        chart_labels = []
        chart_values = []
        for entry in monthly_data:
            if entry["month"]:
                chart_labels.append(entry["month"].strftime("%b %Y"))
                chart_values.append(float(entry["revenue"] or 0))

        chart = {
            "labels": chart_labels,
            "values": chart_values,
            "datasets": [
                {
                    "label": "Revenue",
                    "data": chart_values,
                },
            ],
            "title": "Sales Performance Over Time",
        }

        return {
            "title": "Sales Performance Report",
            "report_type": self.report_type,
            "summary": summary,
            "headers": headers,
            "details": details,
            "chart": chart,
            "date_range_start": str(start_date) if start_date else None,
            "date_range_end": str(end_date) if end_date else None,
        }


class CustomerEngagementGenerator(BaseReportGenerator):
    """
    Generates customer engagement reports.
    Aggregates communication counts, meeting frequency, and task completion
    rates per customer.
    """

    report_type = "customer_engagement"
    report_description = "Customer communication and activity analysis"

    def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a customer engagement report.

        Args:
            parameters: Dict with optional keys:
                - date_range_start: ISO date string
                - date_range_end: ISO date string
                - user_id: UUID of specific user to filter

        Returns:
            Dict with summary, details, headers, chart, title keys.
        """
        from communications.models import CommunicationLog, Meeting
        from customers.models import Customer
        from tasks.models import Task

        start_date, end_date = self._get_date_range(parameters)
        user_id = self._get_user_filter(parameters)

        comm_queryset = CommunicationLog.objects.select_related("customer", "user").all()
        if start_date:
            comm_queryset = comm_queryset.filter(logged_at__date__gte=start_date)
        if end_date:
            comm_queryset = comm_queryset.filter(logged_at__date__lte=end_date)
        if user_id:
            comm_queryset = comm_queryset.filter(user_id=user_id)

        meeting_queryset = Meeting.objects.select_related("customer", "organizer").all()
        if start_date:
            meeting_queryset = meeting_queryset.filter(start_time__date__gte=start_date)
        if end_date:
            meeting_queryset = meeting_queryset.filter(start_time__date__lte=end_date)
        if user_id:
            meeting_queryset = meeting_queryset.filter(organizer_id=user_id)

        task_queryset = Task.objects.select_related("customer", "assigned_to").all()
        if start_date:
            task_queryset = task_queryset.filter(created_at__date__gte=start_date)
        if end_date:
            task_queryset = task_queryset.filter(created_at__date__lte=end_date)
        if user_id:
            task_queryset = task_queryset.filter(assigned_to_id=user_id)

        total_communications = comm_queryset.count()
        total_meetings = meeting_queryset.count()
        total_tasks = task_queryset.count()
        completed_tasks = task_queryset.filter(status="completed").count()
        task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0.0

        call_count = comm_queryset.filter(communication_type="call").count()
        email_count = comm_queryset.filter(communication_type="email").count()
        meeting_comm_count = comm_queryset.filter(communication_type="meeting").count()

        completed_meetings = meeting_queryset.filter(status="completed").count()
        scheduled_meetings = meeting_queryset.filter(status="scheduled").count()

        summary = [
            {"label": "Total Communications", "value": str(total_communications), "change": None},
            {"label": "Total Meetings", "value": str(total_meetings), "change": None},
            {"label": "Total Tasks", "value": str(total_tasks), "change": None},
            {"label": "Task Completion Rate", "value": self._format_percentage(task_completion_rate), "change": None},
            {"label": "Calls", "value": str(call_count), "change": None},
            {"label": "Emails", "value": str(email_count), "change": None},
            {"label": "Completed Meetings", "value": str(completed_meetings), "change": None},
        ]

        customer_comms = (
            comm_queryset
            .values(
                customer_name=F("customer__name"),
                customer_id_val=F("customer__id"),
            )
            .annotate(
                comm_count=Count("id"),
            )
            .order_by("-comm_count")
        )

        customer_meetings = {}
        meeting_by_customer = (
            meeting_queryset
            .values(customer_id_val=F("customer__id"))
            .annotate(meeting_count=Count("id"))
        )
        for entry in meeting_by_customer:
            cid = entry["customer_id_val"]
            if cid:
                customer_meetings[str(cid)] = entry["meeting_count"]

        customer_tasks = {}
        customer_completed = {}
        task_by_customer = (
            task_queryset
            .filter(customer__isnull=False)
            .values(customer_id_val=F("customer__id"))
            .annotate(
                task_count=Count("id"),
                completed_count=Count("id", filter=Q(status="completed")),
            )
        )
        for entry in task_by_customer:
            cid = entry["customer_id_val"]
            if cid:
                customer_tasks[str(cid)] = entry["task_count"]
                customer_completed[str(cid)] = entry["completed_count"]

        headers = [
            {"key": "customer", "label": "Customer"},
            {"key": "communications", "label": "Communications", "align": "center"},
            {"key": "meetings", "label": "Meetings", "align": "center"},
            {"key": "tasks", "label": "Tasks", "align": "center"},
            {"key": "completion_rate", "label": "Task Completion", "align": "center"},
        ]

        details = []
        seen_customers = set()
        for entry in customer_comms:
            cid = str(entry["customer_id_val"]) if entry["customer_id_val"] else None
            cname = entry["customer_name"] or "Unknown"
            if cid and cid in seen_customers:
                continue
            if cid:
                seen_customers.add(cid)

            m_count = customer_meetings.get(cid, 0) if cid else 0
            t_count = customer_tasks.get(cid, 0) if cid else 0
            c_count = customer_completed.get(cid, 0) if cid else 0
            rate = (c_count / t_count * 100) if t_count > 0 else 0.0

            details.append({
                "customer": cname,
                "communications": entry["comm_count"],
                "meetings": m_count,
                "tasks": t_count,
                "completion_rate": self._format_percentage(rate),
            })

        if not details:
            details.append({
                "customer": "No data",
                "communications": 0,
                "meetings": 0,
                "tasks": 0,
                "completion_rate": "0.0%",
            })

        chart_labels = ["Calls", "Emails", "Meetings"]
        chart_values = [call_count, email_count, meeting_comm_count + total_meetings]

        chart = {
            "labels": chart_labels,
            "values": chart_values,
            "title": "Communication Channels Breakdown",
        }

        return {
            "title": "Customer Engagement Report",
            "report_type": self.report_type,
            "summary": summary,
            "headers": headers,
            "details": details,
            "chart": chart,
            "date_range_start": str(start_date) if start_date else None,
            "date_range_end": str(end_date) if end_date else None,
        }


class PipelineHealthGenerator(BaseReportGenerator):
    """
    Generates pipeline health reports.
    Aggregates deals by stage, conversion rates, and average time in stage.
    """

    report_type = "pipeline_health"
    report_description = "Deal progression and pipeline bottleneck visualization"

    def generate(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a pipeline health report.

        Args:
            parameters: Dict with optional keys:
                - date_range_start: ISO date string
                - date_range_end: ISO date string
                - user_id: UUID of specific user to filter
                - stage_id: UUID of specific stage to filter

        Returns:
            Dict with summary, details, headers, chart, title keys.
        """
        from deals.models import Deal, SalesStage

        start_date, end_date = self._get_date_range(parameters)
        user_id = self._get_user_filter(parameters)
        stage_id = self._get_stage_filter(parameters)

        queryset = Deal.objects.select_related("customer", "owner", "stage").all()

        if start_date:
            queryset = queryset.filter(created_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(created_at__date__lte=end_date)
        if user_id:
            queryset = queryset.filter(owner_id=user_id)
        if stage_id:
            queryset = queryset.filter(stage_id=stage_id)

        stages = SalesStage.objects.filter(is_active=True).order_by("order")

        total_deals = queryset.count()
        total_value = queryset.aggregate(total=Sum("value"))["total"] or Decimal("0")

        won_stages = SalesStage.objects.filter(
            name__icontains="won",
            is_active=True,
        ).values_list("pk", flat=True)

        lost_stages = SalesStage.objects.filter(
            name__icontains="lost",
            is_active=True,
        ).values_list("pk", flat=True)

        won_count = queryset.filter(stage_id__in=won_stages).count()
        lost_count = queryset.filter(stage_id__in=lost_stages).count()
        won_value = queryset.filter(stage_id__in=won_stages).aggregate(
            total=Sum("value")
        )["total"] or Decimal("0")

        closed_count = won_count + lost_count
        win_rate = (won_count / closed_count * 100) if closed_count > 0 else 0.0
        avg_deal_value = (total_value / total_deals) if total_deals > 0 else Decimal("0")

        stage_data = (
            queryset
            .values(
                stage_name=F("stage__name"),
                stage_order=F("stage__order"),
                stage_id_val=F("stage__id"),
            )
            .annotate(
                deal_count=Count("id"),
                stage_value=Sum("value"),
                avg_value=Avg("value"),
            )
            .order_by("stage_order")
        )

        now = timezone.now()
        stage_avg_days = {}
        for s in stages:
            stage_deals = queryset.filter(stage=s)
            if stage_deals.exists():
                total_days = Decimal("0")
                count = 0
                for deal in stage_deals:
                    days_in_stage = (now - deal.updated_at).days
                    total_days += days_in_stage
                    count += 1
                if count > 0:
                    stage_avg_days[str(s.pk)] = float(total_days / count)
                else:
                    stage_avg_days[str(s.pk)] = 0.0
            else:
                stage_avg_days[str(s.pk)] = 0.0

        summary = [
            {"label": "Total Deals in Pipeline", "value": str(total_deals), "change": None},
            {"label": "Total Pipeline Value", "value": self._format_currency(total_value), "change": None},
            {"label": "Won Revenue", "value": self._format_currency(won_value), "change": None},
            {"label": "Win Rate", "value": self._format_percentage(win_rate), "change": None},
            {"label": "Avg Deal Value", "value": self._format_currency(avg_deal_value), "change": None},
            {"label": "Active Stages", "value": str(stages.count()), "change": None},
        ]

        headers = [
            {"key": "stage", "label": "Stage"},
            {"key": "deal_count", "label": "Deals", "align": "center"},
            {"key": "stage_value", "label": "Total Value", "align": "numeric"},
            {"key": "avg_value", "label": "Avg Value", "align": "numeric"},
            {"key": "avg_days", "label": "Avg Days in Stage", "align": "center"},
            {"key": "percentage", "label": "% of Pipeline", "align": "center"},
        ]

        details = []
        chart_labels = []
        chart_values = []
        chart_amounts = []

        for entry in stage_data:
            stage_name = entry["stage_name"] or "Unknown"
            deal_count = entry["deal_count"] or 0
            stage_value = entry["stage_value"] or Decimal("0")
            avg_val = entry["avg_value"] or Decimal("0")
            sid = str(entry["stage_id_val"]) if entry["stage_id_val"] else ""
            avg_days = stage_avg_days.get(sid, 0.0)
            pct = (deal_count / total_deals * 100) if total_deals > 0 else 0.0

            details.append({
                "stage": stage_name,
                "deal_count": deal_count,
                "stage_value": self._format_currency(stage_value),
                "avg_value": self._format_currency(avg_val),
                "avg_days": f"{avg_days:.1f}",
                "percentage": self._format_percentage(pct),
            })

            chart_labels.append(stage_name)
            chart_values.append(deal_count)
            chart_amounts.append(float(stage_value))

        if not details:
            for s in stages:
                details.append({
                    "stage": s.name,
                    "deal_count": 0,
                    "stage_value": self._format_currency(0),
                    "avg_value": self._format_currency(0),
                    "avg_days": "0.0",
                    "percentage": "0.0%",
                })
                chart_labels.append(s.name)
                chart_values.append(0)
                chart_amounts.append(0.0)

        if not details:
            details.append({
                "stage": "No data",
                "deal_count": 0,
                "stage_value": self._format_currency(0),
                "avg_value": self._format_currency(0),
                "avg_days": "0.0",
                "percentage": "0.0%",
            })

        previous_count = total_deals
        conversion_details = []
        for i, entry in enumerate(stage_data):
            stage_name = entry["stage_name"] or "Unknown"
            deal_count = entry["deal_count"] or 0
            if i == 0:
                conversion_rate = 100.0
            else:
                conversion_rate = (deal_count / previous_count * 100) if previous_count > 0 else 0.0
            conversion_details.append({
                "stage": stage_name,
                "deals": deal_count,
                "conversion_rate": self._format_percentage(conversion_rate),
            })
            previous_count = deal_count if deal_count > 0 else previous_count

        chart = {
            "labels": chart_labels,
            "values": chart_values,
            "amounts": chart_amounts,
            "title": "Pipeline Health by Stage",
            "y_label": "Number of Deals",
        }

        table = {
            "title": "Stage Conversion Funnel",
            "headers": ["Stage", "Deals", "Conversion Rate"],
            "rows": [
                [c["stage"], c["deals"], c["conversion_rate"]]
                for c in conversion_details
            ],
        }

        return {
            "title": "Pipeline Health Report",
            "report_type": self.report_type,
            "summary": summary,
            "headers": headers,
            "details": details,
            "chart": chart,
            "table": table,
            "date_range_start": str(start_date) if start_date else None,
            "date_range_end": str(end_date) if end_date else None,
        }


class ReportGeneratorFactory:
    """
    Factory that returns the appropriate report generator based on report_type.
    """

    _registry: Dict[str, Type[BaseReportGenerator]] = {
        "sales_performance": SalesPerformanceGenerator,
        "customer_engagement": CustomerEngagementGenerator,
        "pipeline_health": PipelineHealthGenerator,
    }

    @classmethod
    def get_generator(cls, report_type: str) -> BaseReportGenerator:
        """
        Get the appropriate report generator for the given report type.

        Args:
            report_type: The type of report to generate.

        Returns:
            An instance of the appropriate report generator.

        Raises:
            ValueError: If the report type is not supported.
        """
        generator_class = cls._registry.get(report_type)
        if generator_class is None:
            supported = ", ".join(sorted(cls._registry.keys()))
            raise ValueError(
                f"Unsupported report type: '{report_type}'. "
                f"Supported types: {supported}"
            )
        return generator_class()

    @classmethod
    def get_available_types(cls) -> List[Dict[str, str]]:
        """
        List all available report types and their descriptions.

        Returns:
            A list of dicts with 'type' and 'description' keys.
        """
        result = []
        for report_type, generator_class in sorted(cls._registry.items()):
            result.append({
                "type": report_type,
                "description": generator_class.report_description,
            })
        return result

    @classmethod
    def register_generator(
        cls,
        report_type: str,
        generator_class: Type[BaseReportGenerator],
    ) -> None:
        """
        Register a new report generator type.

        Args:
            report_type: The report type identifier.
            generator_class: The generator class to register.
        """
        if not issubclass(generator_class, BaseReportGenerator):
            raise TypeError(
                f"Generator class must be a subclass of BaseReportGenerator, "
                f"got {generator_class.__name__}"
            )
        cls._registry[report_type] = generator_class
        logger.info("Registered report generator: %s -> %s", report_type, generator_class.__name__)