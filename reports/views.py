import json
import logging
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Avg, Count, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from core.permissions import role_required
from core.utils import get_client_ip
from reports.forms import ReportFilterForm
from reports.models import Report
from reports.services import ReportService

logger = logging.getLogger(__name__)

report_service = ReportService()


def _check_report_access(user):
    """Check if user has access to reports (admin or sales roles)."""
    if user.is_superuser or user.is_staff:
        return True
    if hasattr(user, "role") and user.role in ("admin", "sales"):
        return True
    return False


@login_required
def report_dashboard_view(request):
    """
    GET: Main reports dashboard with summary widgets, charts, and recent reports.
    """
    if not _check_report_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    total_deals = 0
    total_revenue = Decimal("0.00")
    win_rate = "0.0%"
    active_customers = 0
    deals_change = None
    revenue_change = None
    win_rate_change = None
    customers_change = None

    pipeline_chart_data = json.dumps({
        "labels": [],
        "values": [],
        "amounts": [],
        "title": "Pipeline Overview",
    })
    sales_chart_data = json.dumps({
        "labels": [],
        "values": [],
        "target": [],
        "title": "Sales Performance",
    })
    engagement_chart_data = json.dumps({
        "labels": ["Call", "Email", "Meeting"],
        "values": [0, 0, 0],
        "title": "Engagement Metrics",
    })
    deal_progression_chart_data = json.dumps({
        "labels": [],
        "datasets": [],
        "title": "Deal Progression",
    })

    try:
        from deals.models import Deal, SalesStage

        total_deals = Deal.objects.count()
        agg = Deal.objects.aggregate(total=Sum("value"))
        total_revenue = agg["total"] or Decimal("0.00")

        won_stages = SalesStage.objects.filter(
            name__icontains="won", is_active=True
        ).values_list("pk", flat=True)
        lost_stages = SalesStage.objects.filter(
            name__icontains="lost", is_active=True
        ).values_list("pk", flat=True)

        won_count = Deal.objects.filter(stage_id__in=won_stages).count()
        lost_count = Deal.objects.filter(stage_id__in=lost_stages).count()
        closed_count = won_count + lost_count
        if closed_count > 0:
            win_rate_val = won_count / closed_count * 100
            win_rate = f"{win_rate_val:.1f}%"
        else:
            win_rate = "0.0%"

        active_stages = SalesStage.objects.filter(is_active=True).order_by("order")
        stage_labels = []
        stage_values = []
        stage_amounts = []
        for stage in active_stages:
            stage_deals = Deal.objects.filter(stage=stage)
            count = stage_deals.count()
            value = stage_deals.aggregate(total=Sum("value"))["total"] or Decimal("0.00")
            stage_labels.append(stage.name)
            stage_values.append(count)
            stage_amounts.append(float(value))

        pipeline_chart_data = json.dumps({
            "labels": stage_labels,
            "values": stage_values,
            "amounts": stage_amounts,
            "title": "Pipeline Overview",
        })

        from django.db.models.functions import TruncMonth

        monthly = (
            Deal.objects.annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(revenue=Sum("value"), count=Count("id"))
            .order_by("month")
        )
        sales_labels = []
        sales_values = []
        for entry in monthly:
            if entry["month"]:
                sales_labels.append(entry["month"].strftime("%b %Y"))
                sales_values.append(float(entry["revenue"] or 0))

        sales_chart_data = json.dumps({
            "labels": sales_labels,
            "values": sales_values,
            "title": "Sales Performance",
        })

    except Exception:
        logger.warning("Failed to fetch deal data for report dashboard", exc_info=True)

    try:
        from customers.models import Customer

        active_customers = Customer.objects.count()
    except Exception:
        logger.warning("Failed to fetch customer count for report dashboard", exc_info=True)

    try:
        from communications.models import CommunicationLog

        comm_counts = (
            CommunicationLog.objects.values("communication_type")
            .annotate(count=Count("id"))
            .order_by("communication_type")
        )
        eng_labels = []
        eng_values = []
        for entry in comm_counts:
            comm_type = entry["communication_type"]
            display_name = comm_type.capitalize() if comm_type else "Other"
            for choice_val, choice_label in CommunicationLog.CommunicationType.choices:
                if choice_val == comm_type:
                    display_name = choice_label
                    break
            eng_labels.append(display_name)
            eng_values.append(entry["count"])

        if eng_labels:
            engagement_chart_data = json.dumps({
                "labels": eng_labels,
                "values": eng_values,
                "title": "Engagement Metrics",
            })
    except Exception:
        logger.warning("Failed to fetch communication data for report dashboard", exc_info=True)

    # Format total revenue for display
    if total_revenue >= Decimal("1000000"):
        total_revenue_display = f"${total_revenue / Decimal('1000000'):.1f}M"
    elif total_revenue >= Decimal("1000"):
        total_revenue_display = f"${total_revenue / Decimal('1000'):.1f}K"
    else:
        total_revenue_display = f"${total_revenue:.0f}"

    recent_reports = report_service.get_recent_reports(user=None, limit=10)

    context = {
        "total_deals": total_deals,
        "total_revenue": total_revenue_display,
        "win_rate": win_rate,
        "active_customers": active_customers,
        "deals_change": deals_change,
        "revenue_change": revenue_change,
        "win_rate_change": win_rate_change,
        "customers_change": customers_change,
        "pipeline_chart_data": pipeline_chart_data,
        "sales_chart_data": sales_chart_data,
        "engagement_chart_data": engagement_chart_data,
        "deal_progression_chart_data": deal_progression_chart_data,
        "recent_reports": recent_reports,
    }

    return render(request, "reports/report_dashboard.html", context)


@login_required
def report_list_view(request):
    """
    GET: List all reports with filtering.
    """
    if not _check_report_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    filters = {}

    report_type = request.GET.get("report_type", "").strip()
    if report_type:
        filters["report_type"] = report_type

    status = request.GET.get("status", "").strip()
    if status:
        filters["status"] = status

    search = request.GET.get("search", "").strip()
    if search:
        filters["search"] = search

    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        filters["date_from"] = date_from

    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        filters["date_to"] = date_to

    queryset = report_service.list_reports(filters=filters, user=request.user)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    report_types = Report.REPORT_TYPE_CHOICES
    status_choices = Report.STATUS_CHOICES

    context = {
        "reports": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "report_types": report_types,
        "status_choices": status_choices,
        "current_filters": {
            "report_type": report_type,
            "status": status,
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    return render(request, "reports/report_list.html", context)


@login_required
def report_generate_view(request):
    """
    GET: Display report generation form with filters.
    POST: Generate a new report based on form data.
    """
    if not _check_report_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    if request.method == "POST":
        form = ReportFilterForm(request.POST)
        if form.is_valid():
            report_type = form.cleaned_data["report_type"]
            title = form.cleaned_data["title"]
            output_format = form.cleaned_data["format"]
            parameters = form.get_report_parameters()

            try:
                ip_address = get_client_ip(request)
                report = report_service.generate_report(
                    report_type=report_type,
                    parameters=parameters,
                    user=request.user,
                    title=title,
                    output_format=output_format,
                    ip_address=ip_address,
                )
                messages.success(
                    request,
                    f'Report "{report.title}" generated successfully.',
                )

                if output_format in ("csv", "pdf") and report.status == "completed":
                    return redirect("report-export", pk=report.pk, format=output_format)

                return redirect("report-detail", pk=report.pk)

            except ValueError as e:
                messages.error(request, f"Failed to generate report: {e}")
            except Exception as e:
                logger.error(
                    "Report generation failed: user=%s error=%s",
                    request.user.email,
                    str(e),
                    exc_info=True,
                )
                messages.error(
                    request,
                    "An unexpected error occurred while generating the report. Please try again.",
                )
    else:
        initial = {}
        report_type_param = request.GET.get("report_type", "").strip()
        if report_type_param:
            initial["report_type"] = report_type_param

        format_param = request.GET.get("format", "").strip()
        if format_param:
            initial["format"] = format_param

        form = ReportFilterForm(initial=initial)

    context = {
        "form": form,
    }

    return render(request, "reports/report_generate.html", context)


@login_required
def report_detail_view(request, pk):
    """
    GET: Display a single report with Chart.js visualization.
    """
    if not _check_report_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    report = get_object_or_404(Report.objects.select_related("generated_by"), pk=pk)

    report_data_json = "{}"
    if report.data and isinstance(report.data, dict):
        try:
            report_data_json = json.dumps(report.data)
        except (TypeError, ValueError):
            report_data_json = "{}"

    context = {
        "report": report,
        "report_data_json": report_data_json,
    }

    return render(request, "reports/report_detail.html", context)


@login_required
def report_export_view(request, pk, format):
    """
    GET: Export a report as CSV or PDF.
    """
    if not _check_report_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    valid_formats = ("csv", "pdf")
    if format not in valid_formats:
        messages.error(request, f"Invalid export format: {format}. Must be one of: {', '.join(valid_formats)}")
        return redirect("report-detail", pk=pk)

    try:
        ip_address = get_client_ip(request)
        response = report_service.export_report(
            report_id=pk,
            export_format=format,
            user=request.user,
            ip_address=ip_address,
        )
        return response

    except ValueError as e:
        messages.error(request, str(e))
        return redirect("report-detail", pk=pk)
    except Exception as e:
        logger.error(
            "Report export failed: report_id=%s format=%s user=%s error=%s",
            pk,
            format,
            request.user.email,
            str(e),
            exc_info=True,
        )
        messages.error(
            request,
            f"Failed to export report as {format.upper()}. Please try again.",
        )
        return redirect("report-detail", pk=pk)


@login_required
def report_delete_view(request, pk):
    """
    POST: Delete a report.
    """
    if not _check_report_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    report = get_object_or_404(Report, pk=pk)

    if request.method == "POST":
        try:
            ip_address = get_client_ip(request)
            deleted = report_service.delete_report(
                report_id=report.pk,
                user=request.user,
                ip_address=ip_address,
            )
            if deleted:
                messages.success(request, f'Report "{report.title}" deleted successfully.')
            else:
                messages.error(request, "Report not found.")
        except Exception as e:
            logger.error(
                "Report deletion failed: report_id=%s user=%s error=%s",
                pk,
                request.user.email,
                str(e),
                exc_info=True,
            )
            messages.error(request, f"Failed to delete report: {e}")

        return redirect("report-list")

    context = {
        "report": report,
    }

    return render(request, "reports/report_confirm_delete.html", context)