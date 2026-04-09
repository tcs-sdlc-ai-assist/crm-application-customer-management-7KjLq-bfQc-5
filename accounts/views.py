from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from accounts.forms import LoginForm, UserProfileForm, UserRegistrationForm
from accounts.models import User
from core.permissions import role_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect("home")

    if request.method == "POST":
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.email}!")
            next_url = request.POST.get("next") or request.GET.get("next") or "home"
            return redirect(next_url)
    else:
        form = LoginForm(request=request)

    next_url = request.GET.get("next", "")
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect("login")


@login_required
@role_required("admin")
def register_view(request):
    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(
                request,
                f"User '{user.get_full_name() or user.email}' has been created successfully.",
            )
            return redirect("user-list")
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_view(request):
    user = request.user

    assigned_deals = []
    try:
        from deals.models import Deal

        assigned_deals = Deal.objects.filter(owner=user).select_related("stage", "customer")[:5]
    except Exception:
        pass

    assigned_deals_count = 0
    try:
        from deals.models import Deal

        assigned_deals_count = Deal.objects.filter(owner=user).count()
    except Exception:
        pass

    open_tasks_count = 0
    completed_tasks_count = 0
    recent_tasks = []
    try:
        from tasks.models import Task

        open_tasks_count = Task.objects.filter(
            assigned_to=user,
        ).exclude(status="completed").count()
        completed_tasks_count = Task.objects.filter(
            assigned_to=user,
            status="completed",
        ).count()
        recent_tasks = Task.objects.filter(assigned_to=user).order_by("-created_at")[:5]
    except Exception:
        pass

    context = {
        "user": user,
        "assigned_deals": assigned_deals,
        "assigned_deals_count": assigned_deals_count,
        "open_tasks_count": open_tasks_count,
        "completed_tasks_count": completed_tasks_count,
        "recent_tasks": recent_tasks,
    }

    return render(request, "accounts/profile.html", context)


@login_required
def profile_edit_view(request):
    user = request.user

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Your profile has been updated successfully.")
            return redirect("profile")
    else:
        form = UserProfileForm(instance=user)

    return render(request, "accounts/profile_edit.html", {"form": form})


@login_required
@role_required("admin")
def user_list_view(request):
    queryset = User.objects.all()

    search_query = request.GET.get("q", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(email__icontains=search_query)
            | Q(first_name__icontains=search_query)
            | Q(last_name__icontains=search_query)
        )

    role_filter = request.GET.get("role", "").strip()
    if role_filter and role_filter in User.Role.values:
        queryset = queryset.filter(role=role_filter)

    paginator = Paginator(queryset, 25)
    page_number = request.GET.get("page", 1)

    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    context = {
        "users": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "role_filter": role_filter,
    }

    return render(request, "accounts/user_list.html", context)


@login_required
@role_required("admin")
def user_detail_view(request, pk):
    try:
        user_obj = User.objects.get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("user-list")

    context = {
        "user_obj": user_obj,
    }

    return render(request, "accounts/user_detail.html", context)


@login_required
@role_required("admin")
def user_update_view(request, pk):
    try:
        user_obj = User.objects.get(pk=pk)
    except User.DoesNotExist:
        messages.error(request, "User not found.")
        return redirect("user-list")

    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=user_obj)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"User '{user_obj.get_full_name() or user_obj.email}' has been updated successfully.",
            )
            return redirect("user-detail", pk=user_obj.pk)
    else:
        form = UserProfileForm(instance=user_obj)

    context = {
        "form": form,
        "user_obj": user_obj,
    }

    return render(request, "accounts/user_update.html", context)