from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from communications.models import CommunicationLog, Meeting
from customers.forms import CustomerForm
from customers.models import Customer
from deals.models import Deal
from tasks.models import Task


@login_required
def customer_list_view(request):
    queryset = Customer.objects.select_related("created_by").all()

    search_query = request.GET.get("search", "").strip()
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query)
            | Q(email__icontains=search_query)
            | Q(company__icontains=search_query)
            | Q(phone__icontains=search_query)
        )

    industry_filter = request.GET.get("industry", "").strip()
    if industry_filter:
        queryset = queryset.filter(industry=industry_filter)

    industries = (
        Customer.objects.values_list("industry", flat=True)
        .distinct()
        .order_by("industry")
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
        "customers": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "search_query": search_query,
        "industry_filter": industry_filter,
        "industries": industries,
    }

    return render(request, "customers/customer_list.html", context)


@login_required
def customer_detail_view(request, pk):
    customer = get_object_or_404(
        Customer.objects.select_related("created_by"),
        pk=pk,
    )

    deals = Deal.objects.filter(customer=customer).select_related(
        "owner", "stage"
    ).order_by("-created_at")

    communications = CommunicationLog.objects.filter(
        customer=customer
    ).select_related("user").order_by("-logged_at")

    tasks = Task.objects.filter(customer=customer).select_related(
        "assigned_to"
    ).order_by("-created_at")

    context = {
        "customer": customer,
        "deals": deals,
        "communications": communications,
        "tasks": tasks,
    }

    return render(request, "customers/customer_detail.html", context)


@login_required
def customer_create_view(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            customer = form.save(commit=False)
            customer.created_by = request.user
            customer.save()
            messages.success(
                request,
                f"Customer '{customer.name}' has been created successfully.",
            )
            return redirect("customer-detail", pk=customer.pk)
    else:
        form = CustomerForm()

    context = {
        "form": form,
    }

    return render(request, "customers/customer_form.html", context)


@login_required
def customer_edit_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f"Customer '{customer.name}' has been updated successfully.",
            )
            return redirect("customer-detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer)

    context = {
        "form": form,
        "customer": customer,
    }

    return render(request, "customers/customer_form.html", context)


@login_required
def customer_delete_view(request, pk):
    customer = get_object_or_404(Customer, pk=pk)

    if request.method == "POST":
        customer_name = customer.name
        customer.delete()
        messages.success(
            request,
            f"Customer '{customer_name}' has been deleted successfully.",
        )
        return redirect("customer-list")

    context = {
        "customer": customer,
    }

    return render(request, "customers/customer_confirm_delete.html", context)