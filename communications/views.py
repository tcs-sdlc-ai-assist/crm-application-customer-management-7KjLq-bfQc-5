from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from communications.forms import CommunicationLogForm, MeetingForm
from communications.models import CommunicationLog, Meeting
from communications.services import CommunicationLogService, SchedulerService
from core.utils import get_client_ip


@login_required
def communication_list_view(request):
    queryset = CommunicationLog.objects.select_related("customer", "user").all()

    communication_type = request.GET.get("type", "").strip()
    if communication_type and communication_type in CommunicationLog.CommunicationType.values:
        queryset = queryset.filter(communication_type=communication_type)

    direction = request.GET.get("direction", "").strip()
    if direction and direction in CommunicationLog.Direction.values:
        queryset = queryset.filter(direction=direction)

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(subject__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(body__icontains=search)
        )

    date_from = request.GET.get("date_from", "").strip()
    if date_from:
        queryset = queryset.filter(logged_at__date__gte=date_from)

    date_to = request.GET.get("date_to", "").strip()
    if date_to:
        queryset = queryset.filter(logged_at__date__lte=date_to)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "communications": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "current_filters": {
            "type": communication_type,
            "direction": direction,
            "search": search,
            "date_from": date_from,
            "date_to": date_to,
        },
    }

    return render(request, "communications/communication_list.html", context)


@login_required
def communication_log_view(request):
    if request.method == "POST":
        form = CommunicationLogForm(request.POST)
        if form.is_valid():
            service = CommunicationLogService()
            try:
                ip_address = get_client_ip(request)
                data = {
                    "customer_id": form.cleaned_data["customer"].pk,
                    "communication_type": form.cleaned_data["communication_type"],
                    "subject": form.cleaned_data["subject"],
                    "body": form.cleaned_data.get("body", ""),
                    "direction": form.cleaned_data["direction"],
                }
                service.log_communication(
                    data=data,
                    user=request.user,
                    ip_address=ip_address,
                )
                messages.success(request, "Communication logged successfully.")
                return redirect("communication-list")
            except (ValueError, Exception) as e:
                messages.error(request, f"Failed to log communication: {e}")
    else:
        form = CommunicationLogForm()

    context = {
        "form": form,
    }

    return render(request, "communications/communication_form.html", context)


@login_required
def communication_detail_view(request, pk):
    communication = get_object_or_404(
        CommunicationLog.objects.select_related("customer", "user"),
        pk=pk,
    )

    context = {
        "communication": communication,
    }

    return render(request, "communications/communication_detail.html", context)


@login_required
def communication_edit_view(request, pk):
    communication = get_object_or_404(
        CommunicationLog.objects.select_related("customer", "user"),
        pk=pk,
    )

    if request.method == "POST":
        form = CommunicationLogForm(request.POST, instance=communication)
        if form.is_valid():
            service = CommunicationLogService()
            try:
                ip_address = get_client_ip(request)
                data = {
                    "communication_type": form.cleaned_data["communication_type"],
                    "subject": form.cleaned_data["subject"],
                    "body": form.cleaned_data.get("body", ""),
                    "direction": form.cleaned_data["direction"],
                }
                service.update_communication(
                    communication_id=communication.pk,
                    data=data,
                    user=request.user,
                    ip_address=ip_address,
                )
                messages.success(request, "Communication updated successfully.")
                return redirect("communication-detail", pk=communication.pk)
            except (ValueError, Exception) as e:
                messages.error(request, f"Failed to update communication: {e}")
    else:
        form = CommunicationLogForm(instance=communication)

    context = {
        "form": form,
        "communication": communication,
    }

    return render(request, "communications/communication_form.html", context)


@login_required
def communication_delete_view(request, pk):
    communication = get_object_or_404(CommunicationLog, pk=pk)

    if request.method == "POST":
        service = CommunicationLogService()
        try:
            ip_address = get_client_ip(request)
            deleted = service.delete_communication(
                communication_id=communication.pk,
                user=request.user,
                ip_address=ip_address,
            )
            if deleted:
                messages.success(request, "Communication deleted successfully.")
            else:
                messages.error(request, "Communication not found.")
        except Exception as e:
            messages.error(request, f"Failed to delete communication: {e}")

        return redirect("communication-list")

    context = {
        "communication": communication,
    }

    return render(request, "communications/communication_confirm_delete.html", context)


@login_required
def meeting_list_view(request):
    queryset = Meeting.objects.select_related(
        "customer", "organizer", "communication_log"
    ).all()

    search = request.GET.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(title__icontains=search)
            | Q(customer__name__icontains=search)
            | Q(description__icontains=search)
            | Q(location__icontains=search)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter and status_filter in Meeting.Status.values:
        queryset = queryset.filter(status=status_filter)

    from django.utils import timezone

    now = timezone.now()

    if status_filter == "upcoming":
        queryset = queryset.filter(start_time__gte=now, status=Meeting.Status.SCHEDULED)
    elif status_filter == "past":
        queryset = queryset.filter(start_time__lt=now)

    upcoming_meetings = Meeting.objects.select_related(
        "customer", "organizer"
    ).filter(
        start_time__gte=now,
        status=Meeting.Status.SCHEDULED,
    ).order_by("start_time")[:10]

    past_meetings = Meeting.objects.select_related(
        "customer", "organizer"
    ).filter(
        start_time__lt=now,
    ).order_by("-start_time")[:10]

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "meetings": page_obj.object_list,
        "upcoming_meetings": upcoming_meetings,
        "past_meetings": past_meetings,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "current_filters": {
            "search": search,
            "status": status_filter,
        },
    }

    return render(request, "communications/meeting_list.html", context)


@login_required
def meeting_schedule_view(request):
    if request.method == "POST":
        form = MeetingForm(request.POST)
        if form.is_valid():
            service = SchedulerService()
            try:
                ip_address = get_client_ip(request)
                calendar_sync = request.POST.get("sync_google_calendar") == "1"
                data = {
                    "customer_id": form.cleaned_data["customer"].pk,
                    "title": form.cleaned_data["title"],
                    "start_time": form.cleaned_data["start_time"],
                    "end_time": form.cleaned_data["end_time"],
                    "description": form.cleaned_data.get("description", ""),
                    "location": form.cleaned_data.get("location", ""),
                    "calendar_sync": calendar_sync,
                }
                meeting = service.schedule_meeting(
                    data=data,
                    user=request.user,
                    ip_address=ip_address,
                )
                messages.success(
                    request,
                    f'Meeting "{meeting.title}" scheduled successfully.',
                )
                return redirect("meeting-detail", pk=meeting.pk)
            except (ValueError, Exception) as e:
                messages.error(request, f"Failed to schedule meeting: {e}")
    else:
        form = MeetingForm()

    context = {
        "form": form,
    }

    return render(request, "communications/meeting_form.html", context)


@login_required
def meeting_detail_view(request, pk):
    meeting = get_object_or_404(
        Meeting.objects.select_related(
            "customer", "organizer", "communication_log"
        ),
        pk=pk,
    )

    context = {
        "meeting": meeting,
    }

    return render(request, "communications/meeting_detail.html", context)


@login_required
def meeting_update_view(request, pk):
    meeting = get_object_or_404(
        Meeting.objects.select_related("customer", "organizer"),
        pk=pk,
    )

    if request.method == "POST":
        form = MeetingForm(request.POST, instance=meeting)
        if form.is_valid():
            service = SchedulerService()
            try:
                ip_address = get_client_ip(request)
                data = {
                    "title": form.cleaned_data["title"],
                    "start_time": form.cleaned_data["start_time"],
                    "end_time": form.cleaned_data["end_time"],
                    "description": form.cleaned_data.get("description", ""),
                    "location": form.cleaned_data.get("location", ""),
                }
                service.update_meeting(
                    meeting_id=meeting.pk,
                    data=data,
                    user=request.user,
                    ip_address=ip_address,
                )
                messages.success(request, f'Meeting "{meeting.title}" updated successfully.')
                return redirect("meeting-detail", pk=meeting.pk)
            except (ValueError, Exception) as e:
                messages.error(request, f"Failed to update meeting: {e}")
    else:
        form = MeetingForm(instance=meeting)

    context = {
        "form": form,
        "meeting": meeting,
    }

    return render(request, "communications/meeting_form.html", context)


@login_required
def meeting_delete_view(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)

    if request.method == "POST":
        service = SchedulerService()
        try:
            ip_address = get_client_ip(request)
            deleted = service.delete_meeting(
                meeting_id=meeting.pk,
                user=request.user,
                ip_address=ip_address,
            )
            if deleted:
                messages.success(request, "Meeting deleted successfully.")
            else:
                messages.error(request, "Meeting not found.")
        except Exception as e:
            messages.error(request, f"Failed to delete meeting: {e}")

        return redirect("meeting-list")

    context = {
        "meeting": meeting,
    }

    return render(request, "communications/meeting_confirm_delete.html", context)


@login_required
def meeting_cancel_view(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)

    if request.method == "POST":
        service = SchedulerService()
        try:
            ip_address = get_client_ip(request)
            service.cancel_meeting(
                meeting_id=meeting.pk,
                user=request.user,
                ip_address=ip_address,
            )
            messages.success(request, f'Meeting "{meeting.title}" cancelled.')
        except (ValueError, Exception) as e:
            messages.error(request, f"Failed to cancel meeting: {e}")

        return redirect("meeting-detail", pk=meeting.pk)

    context = {
        "meeting": meeting,
    }

    return render(request, "communications/meeting_confirm_cancel.html", context)


@login_required
def meeting_complete_view(request, pk):
    meeting = get_object_or_404(Meeting, pk=pk)

    if request.method == "POST":
        service = SchedulerService()
        try:
            ip_address = get_client_ip(request)
            service.complete_meeting(
                meeting_id=meeting.pk,
                user=request.user,
                ip_address=ip_address,
            )
            messages.success(request, f'Meeting "{meeting.title}" marked as completed.')
        except (ValueError, Exception) as e:
            messages.error(request, f"Failed to complete meeting: {e}")

        return redirect("meeting-detail", pk=meeting.pk)

    context = {
        "meeting": meeting,
    }

    return render(request, "communications/meeting_confirm_complete.html", context)