import json
import logging
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import render
from django.utils import timezone

logger = logging.getLogger(__name__)


@login_required
def dashboard_view(request):
    """
    Main CRM dashboard view.
    Renders summary widgets with total customers, active deals by stage,
    upcoming tasks, recent communications, pipeline value, and chart data.
    """
    user = request.user

    # Total customers
    total_customers = 0
    customers_change = None
    try:
        from customers.models import Customer

        total_customers = Customer.objects.count()
    except Exception:
        logger.warning("Failed to fetch customer count for dashboard", exc_info=True)

    # Active deals and pipeline value
    active_deals = 0
    pipeline_value = Decimal("0.00")
    deals_change = None
    pipeline_change = None
    recent_deals = []
    stage_choices = []
    pipeline_chart_data = {
        "labels": [],
        "values": [],
        "amounts": [],
        "title": "Deals by Pipeline Stage",
    }
    try:
        from deals.models import Deal, SalesStage

        active_stages = SalesStage.objects.filter(is_active=True).order_by("order")

        stage_labels = []
        stage_deal_counts = []
        stage_deal_amounts = []

        for stage in active_stages:
            stage_deals = Deal.objects.filter(stage=stage)
            deal_count = stage_deals.count()
            deal_value = stage_deals.aggregate(total=Sum("value"))["total"] or Decimal("0.00")

            stage_labels.append(stage.name)
            stage_deal_counts.append(deal_count)
            stage_deal_amounts.append(float(deal_value))

        pipeline_chart_data = {
            "labels": stage_labels,
            "values": stage_deal_counts,
            "amounts": stage_deal_amounts,
            "title": "Deals by Pipeline Stage",
        }

        active_deals = Deal.objects.count()
        pipeline_agg = Deal.objects.aggregate(total=Sum("value"))
        pipeline_value = pipeline_agg["total"] or Decimal("0.00")

        recent_deals = (
            Deal.objects.select_related("customer", "owner", "stage")
            .order_by("-created_at")[:5]
        )

        stage_choices = [
            (str(s.pk), s.name)
            for s in active_stages
        ]
    except Exception:
        logger.warning("Failed to fetch deal data for dashboard", exc_info=True)

    # Pending and overdue tasks
    pending_tasks = 0
    overdue_tasks = 0
    upcoming_tasks = []
    try:
        from tasks.models import Task

        today = timezone.now().date()

        pending_tasks = Task.objects.exclude(
            status=Task.Status.COMPLETED,
        ).exclude(
            status=Task.Status.CANCELLED,
        ).count()

        overdue_tasks = Task.objects.exclude(
            status=Task.Status.COMPLETED,
        ).exclude(
            status=Task.Status.CANCELLED,
        ).filter(
            due_date__lt=today,
            due_date__isnull=False,
        ).count()

        upcoming_tasks = (
            Task.objects.select_related("assigned_to", "customer", "deal")
            .exclude(status=Task.Status.COMPLETED)
            .exclude(status=Task.Status.CANCELLED)
            .order_by("due_date", "-priority", "-created_at")[:5]
        )
    except Exception:
        logger.warning("Failed to fetch task data for dashboard", exc_info=True)

    # Recent communications
    recent_communications_count = 0
    communications_chart_data = {
        "labels": ["Call", "Email", "Meeting"],
        "values": [0, 0, 0],
        "title": "Communications by Type",
    }
    try:
        from communications.models import CommunicationLog

        recent_communications_count = CommunicationLog.objects.count()

        comm_type_counts = (
            CommunicationLog.objects.values("communication_type")
            .annotate(count=Count("id"))
            .order_by("communication_type")
        )

        comm_labels = []
        comm_values = []
        for entry in comm_type_counts:
            comm_type = entry["communication_type"]
            display_name = comm_type.capitalize() if comm_type else "Other"
            for choice_val, choice_label in CommunicationLog.CommunicationType.choices:
                if choice_val == comm_type:
                    display_name = choice_label
                    break
            comm_labels.append(display_name)
            comm_values.append(entry["count"])

        if comm_labels:
            communications_chart_data = {
                "labels": comm_labels,
                "values": comm_values,
                "title": "Communications by Type",
            }
    except Exception:
        logger.warning(
            "Failed to fetch communication data for dashboard", exc_info=True
        )

    # Format pipeline value for display
    pipeline_value_display = _format_pipeline_value(pipeline_value)

    context = {
        "total_customers": total_customers,
        "customers_change": customers_change,
        "active_deals": active_deals,
        "deals_change": deals_change,
        "pipeline_value": pipeline_value_display,
        "pipeline_change": pipeline_change,
        "pending_tasks": pending_tasks,
        "overdue_tasks": overdue_tasks,
        "recent_deals": recent_deals,
        "upcoming_tasks": upcoming_tasks,
        "recent_communications_count": recent_communications_count,
        "stage_choices": stage_choices,
        "pipeline_chart_data": json.dumps(pipeline_chart_data),
        "communications_chart_data": json.dumps(communications_chart_data),
    }

    return render(request, "dashboard.html", context)


def _format_pipeline_value(value):
    """Format a Decimal pipeline value for display in the dashboard widget."""
    if value is None:
        return "0"

    try:
        decimal_value = Decimal(str(value))
    except Exception:
        return "0"

    if decimal_value >= Decimal("1000000"):
        formatted = decimal_value / Decimal("1000000")
        return f"{formatted:.1f}M"
    elif decimal_value >= Decimal("1000"):
        formatted = decimal_value / Decimal("1000")
        return f"{formatted:.1f}K"
    else:
        return f"{decimal_value:.0f}"