import uuid
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Tuple, Union

from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils import timezone


def format_currency(amount: Union[Decimal, float, int, str, None], currency_symbol: str = "$", decimal_places: int = 2) -> str:
    """
    Format a numeric value as a currency string.

    Args:
        amount: The numeric amount to format.
        currency_symbol: The currency symbol to prepend (default: "$").
        decimal_places: Number of decimal places (default: 2).

    Returns:
        A formatted currency string, e.g. "$1,234.56".
    """
    if amount is None:
        return f"{currency_symbol}0.{'0' * decimal_places}"

    try:
        decimal_amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        return f"{currency_symbol}0.{'0' * decimal_places}"

    quantize_str = "0." + "0" * decimal_places if decimal_places > 0 else "1"
    rounded = decimal_amount.quantize(Decimal(quantize_str))

    sign = ""
    if rounded < 0:
        sign = "-"
        rounded = abs(rounded)

    integer_part, _, fractional_part = str(rounded).partition(".")

    groups: List[str] = []
    while len(integer_part) > 3:
        groups.insert(0, integer_part[-3:])
        integer_part = integer_part[:-3]
    groups.insert(0, integer_part)

    formatted_integer = ",".join(groups)

    if decimal_places > 0:
        fractional_part = fractional_part.ljust(decimal_places, "0")
        return f"{sign}{currency_symbol}{formatted_integer}.{fractional_part}"
    return f"{sign}{currency_symbol}{formatted_integer}"


def format_date(
    value: Optional[datetime],
    fmt: str = "%b %d, %Y",
    default: str = "",
) -> str:
    """
    Format a datetime object into a human-readable string.

    Args:
        value: The datetime to format.
        fmt: The strftime format string (default: "%b %d, %Y").
        default: The string to return if value is None.

    Returns:
        A formatted date string or the default value.
    """
    if value is None:
        return default

    if not isinstance(value, datetime):
        return default

    try:
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime(fmt)
    except (ValueError, AttributeError):
        return default


def generate_uuid() -> str:
    """
    Generate a new UUID4 string.

    Returns:
        A lowercase UUID string without hyphens is NOT used; returns standard
        UUID format string, e.g. "550e8400-e29b-41d4-a716-446655440000".
    """
    return str(uuid.uuid4())


def get_client_ip(request: HttpRequest) -> str:
    """
    Extract the client IP address from a Django HttpRequest.

    Checks the X-Forwarded-For header first (for proxied requests),
    then falls back to REMOTE_ADDR.

    Args:
        request: The Django HttpRequest object.

    Returns:
        The client IP address as a string.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "0.0.0.0")
    return ip


def paginate_queryset(
    queryset: QuerySet,
    page_number: Optional[Union[int, str]] = 1,
    per_page: int = 25,
) -> Tuple[Any, Paginator]:
    """
    Paginate a Django queryset.

    Args:
        queryset: The queryset to paginate.
        page_number: The requested page number (default: 1).
        per_page: Number of items per page (default: 25).

    Returns:
        A tuple of (page_object, paginator).
        The page_object is a Django Page instance with .object_list,
        .has_next(), .has_previous(), etc.
    """
    if per_page < 1:
        per_page = 25

    paginator = Paginator(queryset, per_page)

    try:
        page = paginator.page(page_number)
    except PageNotAnInteger:
        page = paginator.page(1)
    except EmptyPage:
        page = paginator.page(paginator.num_pages)

    return page, paginator


def build_filter_params(
    request_params: Dict[str, Any],
    allowed_filters: List[str],
    filter_mapping: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Build a dictionary of ORM-compatible filter parameters from request data.

    Only includes keys that are present in allowed_filters and have
    non-empty values. Optionally maps user-facing parameter names to
    ORM lookup field names via filter_mapping.

    Args:
        request_params: A dictionary of request parameters (e.g., request.GET).
        allowed_filters: A list of parameter names that are permitted.
        filter_mapping: An optional dict mapping parameter names to ORM
            lookup expressions (e.g., {"name": "name__icontains",
            "status": "status__exact"}).

    Returns:
        A dictionary suitable for passing to queryset.filter(**result).

    Example:
        >>> params = {"name": "Acme", "status": "active", "hack": "drop table"}
        >>> allowed = ["name", "status"]
        >>> mapping = {"name": "name__icontains", "status": "status__exact"}
        >>> build_filter_params(params, allowed, mapping)
        {"name__icontains": "Acme", "status__exact": "active"}
    """
    if filter_mapping is None:
        filter_mapping = {}

    filters: Dict[str, Any] = {}

    for param_name in allowed_filters:
        value = request_params.get(param_name)

        if value is None:
            continue

        if isinstance(value, str) and value.strip() == "":
            continue

        orm_field = filter_mapping.get(param_name, param_name)
        filters[orm_field] = value

    return filters