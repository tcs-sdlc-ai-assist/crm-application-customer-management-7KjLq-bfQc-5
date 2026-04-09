from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from core.utils import get_client_ip
from customers.models import Customer
from deals.models import Deal
from tasks.forms import TaskForm
from tasks.models import Task
from tasks.services import TaskManagerService


task_service = TaskManagerService()


@login_required
def task_list_view(request):
    queryset = Task.objects.select_related(
        "customer", "deal", "assigned_to", "created_by"
    ).all()

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(description__icontains=search)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter and status_filter in Task.Status.values:
        queryset = queryset.filter(status=status_filter)

    priority_filter = request.GET.get("priority", "").strip()
    if priority_filter and priority_filter in Task.Priority.values:
        queryset = queryset.filter(priority=priority_filter)

    assignee_filter = request.GET.get("assignee", "").strip()
    if assignee_filter:
        queryset = queryset.filter(assigned_to_id=assignee_filter)

    customer_filter = request.GET.get("customer", "").strip()
    if customer_filter:
        queryset = queryset.filter(customer_id=customer_filter)

    deal_filter = request.GET.get("deal", "").strip()
    if deal_filter:
        queryset = queryset.filter(deal_id=deal_filter)

    due_date_from = request.GET.get("due_date_from", "").strip()
    if due_date_from:
        queryset = queryset.filter(due_date__gte=due_date_from)

    due_date_to = request.GET.get("due_date_to", "").strip()
    if due_date_to:
        queryset = queryset.filter(due_date__lte=due_date_to)

    is_overdue = request.GET.get("is_overdue", "").strip()
    if is_overdue == "true":
        today = timezone.now().date()
        queryset = queryset.filter(
            due_date__lt=today,
        ).exclude(
            status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED],
        )

    assignees = User.objects.filter(is_active=True).order_by(
        "first_name", "last_name", "email"
    )

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "tasks": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "assignees": assignees,
        "current_filters": {
            "search": search,
            "status": status_filter,
            "priority": priority_filter,
            "assignee": assignee_filter,
            "customer": customer_filter,
            "deal": deal_filter,
            "due_date_from": due_date_from,
            "due_date_to": due_date_to,
            "is_overdue": is_overdue,
        },
    }

    return render(request, "tasks/task_list.html", context)


@login_required
def task_detail_view(request, pk):
    task = get_object_or_404(
        Task.objects.select_related(
            "customer", "deal", "assigned_to", "created_by"
        ),
        pk=pk,
    )

    context = {
        "task": task,
    }

    return render(request, "tasks/task_detail.html", context)


@login_required
def task_create_view(request):
    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            if not task.assigned_to:
                task.assigned_to = request.user
            task.save()
            messages.success(
                request,
                f'Task "{task.title}" created successfully.',
            )
            return redirect("task-detail", pk=task.pk)
    else:
        initial = {}
        customer_id = request.GET.get("customer", "").strip()
        if customer_id:
            try:
                customer = Customer.objects.get(pk=customer_id)
                initial["customer"] = customer
            except Customer.DoesNotExist:
                pass

        deal_id = request.GET.get("deal", "").strip()
        if deal_id:
            try:
                deal = Deal.objects.get(pk=deal_id)
                initial["deal"] = deal
                if not customer_id and deal.customer:
                    initial["customer"] = deal.customer
            except Deal.DoesNotExist:
                pass

        form = TaskForm(initial=initial)

    context = {
        "form": form,
    }

    return render(request, "tasks/task_form.html", context)


@login_required
def task_edit_view(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Task "{task.title}" updated successfully.',
            )
            return redirect("task-detail", pk=task.pk)
    else:
        form = TaskForm(instance=task)

    context = {
        "form": form,
        "task": task,
    }

    return render(request, "tasks/task_form.html", context)


@login_required
def task_delete_view(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        task_title = task.title
        task.delete()
        messages.success(
            request,
            f'Task "{task_title}" deleted successfully.',
        )
        return redirect("task-list")

    context = {
        "task": task,
    }

    return render(request, "tasks/task_confirm_delete.html", context)


@login_required
def task_complete_view(request, pk):
    task = get_object_or_404(Task, pk=pk)

    if request.method == "POST":
        try:
            ip_address = get_client_ip(request)
            completed_task = task_service.complete_task(
                task_id=task.pk,
                user=request.user,
                ip_address=ip_address,
            )
            if completed_task:
                messages.success(
                    request,
                    f'Task "{task.title}" marked as completed.',
                )
            else:
                messages.error(request, "Task not found.")
        except (ValueError, Exception) as e:
            messages.error(request, f"Failed to complete task: {e}")

    return redirect("task-detail", pk=task.pk)


@login_required
def task_dashboard_view(request):
    user = request.user

    base_queryset = Task.objects.select_related(
        "customer", "deal", "assigned_to", "created_by"
    ).filter(assigned_to=user)

    pending_tasks = base_queryset.filter(
        status=Task.Status.PENDING,
    ).order_by("due_date", "-priority", "-created_at")

    in_progress_tasks = base_queryset.filter(
        status=Task.Status.IN_PROGRESS,
    ).order_by("due_date", "-priority", "-created_at")

    completed_tasks = base_queryset.filter(
        status=Task.Status.COMPLETED,
    ).order_by("-completed_at", "-updated_at")[:20]

    today = timezone.now().date()
    overdue_tasks = base_queryset.filter(
        due_date__lt=today,
        due_date__isnull=False,
    ).exclude(
        status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED],
    ).order_by("due_date")

    overdue_count = overdue_tasks.count()

    upcoming_reminders = base_queryset.filter(
        reminder_date__isnull=False,
        reminder_date__gte=timezone.now(),
    ).exclude(
        status__in=[Task.Status.COMPLETED, Task.Status.CANCELLED],
    ).order_by("reminder_date")[:10]

    context = {
        "pending_tasks": pending_tasks,
        "in_progress_tasks": in_progress_tasks,
        "completed_tasks": completed_tasks,
        "overdue_tasks": overdue_tasks,
        "overdue_count": overdue_count,
        "upcoming_reminders": upcoming_reminders,
    }

    return render(request, "tasks/task_dashboard.html", context)