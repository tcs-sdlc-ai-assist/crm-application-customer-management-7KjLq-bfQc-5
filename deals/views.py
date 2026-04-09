from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q, Sum
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from core.permissions import role_required
from core.utils import format_currency, get_client_ip
from customers.models import Customer
from deals.forms import DealAssignForm, DealForm, SalesStageForm
from deals.models import Deal, SalesStage
from deals.services import DealService, SalesStageService


deal_service = DealService()
stage_service = SalesStageService()


@login_required
def deal_list_view(request):
    queryset = Deal.objects.select_related("customer", "owner", "stage").all()

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(description__icontains=search)
        )

    stage_filter = request.GET.get("stage", "").strip()
    if stage_filter:
        queryset = queryset.filter(stage_id=stage_filter)

    owner_filter = request.GET.get("owner", "").strip()
    if owner_filter:
        queryset = queryset.filter(owner_id=owner_filter)

    customer_filter = request.GET.get("customer", "").strip()
    if customer_filter:
        queryset = queryset.filter(customer_id=customer_filter)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    stages = SalesStage.objects.filter(is_active=True).order_by("order")
    stage_choices = [(str(s.pk), s.name) for s in stages]

    owners = User.objects.filter(is_active=True).order_by("first_name", "last_name")

    context = {
        "deals": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "stage_choices": stage_choices,
        "owners": owners,
        "search_query": search,
        "current_filters": {
            "search": search,
            "stage": stage_filter,
            "owner": owner_filter,
            "customer": customer_filter,
        },
    }

    return render(request, "deals/deal_list.html", context)


@login_required
def deal_detail_view(request, pk):
    deal = get_object_or_404(
        Deal.objects.select_related("customer", "owner", "stage"),
        pk=pk,
    )

    tasks = []
    try:
        from tasks.models import Task

        tasks = Task.objects.filter(deal=deal).select_related(
            "assigned_to"
        ).order_by("-created_at")
    except Exception:
        pass

    communications = []
    try:
        from communications.models import CommunicationLog

        if deal.customer:
            communications = CommunicationLog.objects.filter(
                customer=deal.customer
            ).select_related("user").order_by("-logged_at")[:10]
    except Exception:
        pass

    available_owners = User.objects.filter(is_active=True).order_by(
        "first_name", "last_name"
    )

    context = {
        "deal": deal,
        "tasks": tasks,
        "communications": communications,
        "available_owners": available_owners,
    }

    return render(request, "deals/deal_detail.html", context)


@login_required
def deal_create_view(request):
    if request.method == "POST":
        form = DealForm(request.POST)
        if form.is_valid():
            deal = form.save(commit=False)
            if not deal.owner:
                deal.owner = request.user
            deal.save()
            messages.success(
                request,
                f'Deal "{deal.name}" created successfully.',
            )
            return redirect("deal-detail", pk=deal.pk)
    else:
        form = DealForm()

    context = {
        "form": form,
    }

    return render(request, "deals/deal_form.html", context)


@login_required
def deal_edit_view(request, pk):
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == "POST":
        form = DealForm(request.POST, instance=deal)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Deal "{deal.name}" updated successfully.',
            )
            return redirect("deal-detail", pk=deal.pk)
    else:
        form = DealForm(instance=deal)

    context = {
        "form": form,
        "deal": deal,
    }

    return render(request, "deals/deal_form.html", context)


@login_required
def deal_delete_view(request, pk):
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == "POST":
        deal_name = deal.name
        deal.delete()
        messages.success(request, f'Deal "{deal_name}" deleted successfully.')
        return redirect("deal-list")

    context = {
        "deal": deal,
    }

    return render(request, "deals/deal_confirm_delete.html", context)


@login_required
def deal_assign_view(request, pk):
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == "POST":
        form = DealAssignForm(request.POST, deal=deal)
        if form.is_valid():
            form.save()
            new_owner = form.cleaned_data["owner"]
            messages.success(
                request,
                f'Deal "{deal.name}" assigned to {new_owner.get_full_name() or new_owner.email}.',
            )
            return redirect("deal-detail", pk=deal.pk)
        else:
            messages.error(request, "Failed to assign deal owner. Please try again.")
            return redirect("deal-detail", pk=deal.pk)

    return redirect("deal-detail", pk=deal.pk)


@login_required
def deal_stage_update_view(request, pk):
    deal = get_object_or_404(Deal, pk=pk)

    if request.method == "POST":
        stage_id = request.POST.get("stage", "").strip()
        if stage_id:
            try:
                new_stage = SalesStage.objects.get(pk=stage_id)
                old_stage = deal.stage
                deal.stage = new_stage
                deal.save(update_fields=["stage", "updated_at"])
                messages.success(
                    request,
                    f'Deal "{deal.name}" moved from "{old_stage.name}" to "{new_stage.name}".',
                )
            except SalesStage.DoesNotExist:
                messages.error(request, "Invalid sales stage.")
        else:
            messages.error(request, "No stage specified.")

    return redirect("deal-detail", pk=deal.pk)


@login_required
def pipeline_list_view(request):
    stages = SalesStage.objects.filter(is_active=True).order_by("order")

    deals_queryset = Deal.objects.select_related(
        "customer", "owner", "stage"
    ).all()

    search = request.GET.get("search", "").strip()
    if search:
        deals_queryset = deals_queryset.filter(
            Q(name__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(description__icontains=search)
        )

    owner_filter = request.GET.get("owner", "").strip()
    if owner_filter:
        deals_queryset = deals_queryset.filter(owner_id=owner_filter)

    customer_filter = request.GET.get("customer", "").strip()
    if customer_filter:
        deals_queryset = deals_queryset.filter(customer_id=customer_filter)

    deals_by_stage = {}
    for deal in deals_queryset:
        stage_id = str(deal.stage_id)
        if stage_id not in deals_by_stage:
            deals_by_stage[stage_id] = []
        deals_by_stage[stage_id].append(deal)

    pipeline_stages = []
    total_deals = 0
    total_value = 0

    for stage in stages:
        stage_deals = deals_by_stage.get(str(stage.pk), [])
        stage_value = sum(d.value for d in stage_deals)
        total_deals += len(stage_deals)
        total_value += stage_value

        stage_key = stage.name.lower().replace(" ", "_")

        pipeline_stages.append({
            "key": stage_key,
            "label": stage.name,
            "id": stage.pk,
            "deals": stage_deals,
            "total_value": format_currency(stage_value),
            "count": len(stage_deals),
        })

    owners = User.objects.filter(is_active=True).order_by("first_name", "last_name")
    customers = Customer.objects.all().order_by("name")

    context = {
        "stages": pipeline_stages,
        "total_deals": total_deals,
        "total_value": format_currency(total_value),
        "owners": owners,
        "customers": customers,
        "current_filters": {
            "search": search,
            "owner": owner_filter,
            "customer": customer_filter,
        },
    }

    return render(request, "deals/pipeline.html", context)


@login_required
@role_required("admin")
def sales_stage_list_view(request):
    stages = SalesStage.objects.all().order_by("order")

    stages_with_counts = []
    for stage in stages:
        deal_count = Deal.objects.filter(stage=stage).count()
        stage.deal_count = deal_count
        stages_with_counts.append(stage)

    context = {
        "stages": stages_with_counts,
    }

    return render(request, "deals/sales_stages.html", context)


@login_required
@role_required("admin")
def sales_stage_create_view(request):
    if request.method == "POST":
        form = SalesStageForm(request.POST)
        if form.is_valid():
            stage = form.save()
            messages.success(
                request,
                f'Sales stage "{stage.name}" created successfully.',
            )
            return redirect("sales-stage-list")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")
            return redirect("sales-stage-list")

    return redirect("sales-stage-list")


@login_required
@role_required("admin")
def sales_stage_edit_view(request, pk):
    stage = get_object_or_404(SalesStage, pk=pk)

    if request.method == "POST":
        form = SalesStageForm(request.POST, instance=stage)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Sales stage "{stage.name}" updated successfully.',
            )
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{error}")

        return redirect("sales-stage-list")

    form = SalesStageForm(instance=stage)

    context = {
        "form": form,
        "stage": stage,
    }

    return render(request, "deals/sales_stage_form.html", context)


@login_required
@role_required("admin")
def sales_stage_delete_view(request, pk):
    stage = get_object_or_404(SalesStage, pk=pk)

    if request.method == "POST":
        deal_count = Deal.objects.filter(stage=stage).count()
        if deal_count > 0:
            messages.error(
                request,
                f'Cannot delete sales stage "{stage.name}" because it has '
                f"{deal_count} associated deal(s). Reassign or delete them first.",
            )
            return redirect("sales-stage-list")

        stage_name = stage.name
        stage.delete()
        messages.success(
            request,
            f'Sales stage "{stage_name}" deleted successfully.',
        )
        return redirect("sales-stage-list")

    context = {
        "stage": stage,
    }

    return render(request, "deals/sales_stage_confirm_delete.html", context)