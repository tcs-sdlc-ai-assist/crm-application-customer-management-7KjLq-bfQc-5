from functools import wraps

from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def role_required(*required_roles):
    """
    Decorator for Django views that checks if the authenticated user
    has one of the required roles. Raises PermissionDenied (403) if not.

    Usage:
        @role_required('admin', 'sales')
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                raise PermissionDenied("Authentication required.")
            user_role = getattr(request.user, 'role', None)
            if user_role is None:
                raise PermissionDenied("User does not have a role assigned.")
            if user_role not in required_roles:
                raise PermissionDenied(
                    f"Role '{user_role}' is not authorized. "
                    f"Required roles: {', '.join(required_roles)}."
                )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


class RoleBasePermission(BasePermission):
    """
    Base DRF permission class that checks user.role against allowed_roles.
    Subclasses must define allowed_roles as a tuple of role strings.
    """
    allowed_roles = ()

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        user_role = getattr(request.user, 'role', None)
        if user_role is None:
            return False
        return user_role in self.allowed_roles


class IsAdmin(RoleBasePermission):
    """
    Allows access only to users with the 'admin' role.
    """
    allowed_roles = ('admin',)
    message = "Only admin users are allowed to perform this action."


class IsSales(RoleBasePermission):
    """
    Allows access only to users with the 'sales' role.
    """
    allowed_roles = ('sales',)
    message = "Only sales users are allowed to perform this action."


class IsSupport(RoleBasePermission):
    """
    Allows access only to users with the 'support' role.
    """
    allowed_roles = ('support',)
    message = "Only support users are allowed to perform this action."


class IsAdminOrSales(RoleBasePermission):
    """
    Allows access to users with either the 'admin' or 'sales' role.
    """
    allowed_roles = ('admin', 'sales')
    message = "Only admin or sales users are allowed to perform this action."