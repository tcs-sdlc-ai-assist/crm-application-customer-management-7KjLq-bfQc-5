from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden
from django.shortcuts import render

from audit_logs.models import AuditLog


@login_required
def audit_log_list_view(request):
    if not (request.user.is_staff or request.user.is_superuser):
        return HttpResponseForbidden("You do not have permission to access this resource.")

    queryset = AuditLog.objects.select_related("user").all()

    entity_type = request.GET.get("entity_type", "").strip()
    if entity_type:
        queryset = queryset.filter(entity_type__icontains=entity_type)

    action = request.GET.get("action", "").strip()
    if action and action in AuditLog.Action.values:
        queryset = queryset.filter(action=action)

    user_id = request.GET.get("user", "").strip()
    if user_id:
        queryset = queryset.filter(user__id=user_id)

    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        queryset = queryset.filter(timestamp__date__gte=date_from)

    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        queryset = queryset.filter(timestamp__date__lte=date_to)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    action_choices = AuditLog.Action.choices

    entity_types = (
        AuditLog.objects.values_list("entity_type", flat=True)
        .distinct()
        .order_by("entity_type")
    )

    context = {
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "audit_logs": page_obj.object_list,
        "action_choices": action_choices,
        "entity_types": entity_types,
        "current_filters": {
            "entity_type": entity_type,
            "action": action,
            "user": user_id,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    return render(request, "audit_logs/audit_log_list.html", context)