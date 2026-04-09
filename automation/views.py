from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from automation.forms import AutomationRuleForm
from automation.models import AutomationLog, AutomationRule


def _check_admin_access(user):
    """Check if user has admin access (staff, superuser, or admin role)."""
    if user.is_superuser or user.is_staff:
        return True
    if hasattr(user, 'role') and user.role == 'admin':
        return True
    return False


@login_required
def automation_rule_list_view(request):
    if not _check_admin_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    queryset = AutomationRule.objects.select_related("created_by").all()

    trigger_type = request.GET.get("trigger_type", "").strip()
    if trigger_type:
        queryset = queryset.filter(trigger_type=trigger_type)

    action_type = request.GET.get("action_type", "").strip()
    if action_type:
        queryset = queryset.filter(action_type=action_type)

    is_active = request.GET.get("is_active", "").strip()
    if is_active == "true":
        queryset = queryset.filter(is_active=True)
    elif is_active == "false":
        queryset = queryset.filter(is_active=False)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "rules": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "filter_form": True,
        "current_filters": {
            "trigger_type": trigger_type,
            "action_type": action_type,
            "is_active": is_active,
        },
    }

    return render(request, "automation/rule_list.html", context)


@login_required
def automation_rule_create_view(request):
    if not _check_admin_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    if request.method == "POST":
        form = AutomationRuleForm(request.POST)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.created_by = request.user
            rule.save()
            messages.success(request, f'Automation rule "{rule.name}" created successfully.')
            return redirect("automation-list")
    else:
        form = AutomationRuleForm()

    context = {
        "form": form,
    }

    return render(request, "automation/rule_form.html", context)


@login_required
def automation_rule_detail_view(request, pk):
    if not _check_admin_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    rule = get_object_or_404(AutomationRule.objects.select_related("created_by"), pk=pk)

    recent_logs = AutomationLog.objects.filter(rule=rule).select_related(
        "triggered_by"
    ).order_by("-executed_at")[:10]

    context = {
        "rule": rule,
        "recent_logs": recent_logs,
    }

    return render(request, "automation/rule_detail.html", context)


@login_required
def automation_rule_edit_view(request, pk):
    if not _check_admin_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    rule = get_object_or_404(AutomationRule, pk=pk)

    if request.method == "POST":
        form = AutomationRuleForm(request.POST, instance=rule)
        if form.is_valid():
            form.save()
            messages.success(request, f'Automation rule "{rule.name}" updated successfully.')
            return redirect("automation-list")
    else:
        form = AutomationRuleForm(instance=rule)

    context = {
        "form": form,
    }

    return render(request, "automation/rule_form.html", context)


@login_required
def automation_rule_delete_view(request, pk):
    if not _check_admin_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    rule = get_object_or_404(AutomationRule, pk=pk)

    if request.method == "POST":
        rule_name = rule.name
        rule.delete()
        messages.success(request, f'Automation rule "{rule_name}" deleted successfully.')
        return redirect("automation-list")

    context = {
        "rule": rule,
    }

    return render(request, "automation/rule_confirm_delete.html", context)


@login_required
def automation_log_list_view(request):
    if not _check_admin_access(request.user):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    queryset = AutomationLog.objects.select_related(
        "rule", "triggered_by"
    ).all()

    status = request.GET.get("status", "").strip()
    if status and status in dict(AutomationLog.STATUS_CHOICES):
        queryset = queryset.filter(status=status)

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(rule__name__icontains=search)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "automation_logs": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "current_filters": {
            "status": status,
            "search": search,
        },
    }

    return render(request, "automation/automation_logs.html", context)