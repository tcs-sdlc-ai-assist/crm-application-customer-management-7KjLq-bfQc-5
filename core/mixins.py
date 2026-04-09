from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.http import HttpResponseForbidden
from django.utils.functional import cached_property


class AuditLogMixin:
    """
    Mixin that automatically creates audit log entries on model save/delete
    in CreateView, UpdateView, and DeleteView.
    """

    def _get_audit_action(self):
        from django.views.generic.edit import CreateView, DeleteView, UpdateView

        if isinstance(self, CreateView):
            return "CREATE"
        elif isinstance(self, UpdateView):
            return "UPDATE"
        elif isinstance(self, DeleteView):
            return "DELETE"
        return "UNKNOWN"

    def _create_audit_log(self, instance, action):
        try:
            from core.models import AuditLog
        except ImportError:
            return

        user = self.request.user if self.request.user.is_authenticated else None
        content_type = ContentType.objects.get_for_model(instance)
        object_repr = str(instance)

        try:
            AuditLog.objects.create(
                user=user,
                action=action,
                content_type=content_type,
                object_id=str(instance.pk),
                object_repr=object_repr[:200],
            )
        except Exception:
            pass

    def form_valid(self, form):
        response = super().form_valid(form)
        action = self._get_audit_action()
        self._create_audit_log(self.object, action)
        return response

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        action = "DELETE"
        instance_repr = str(self.object)
        instance_pk = str(self.object.pk)
        content_type = ContentType.objects.get_for_model(self.object)

        response = super().delete(request, *args, **kwargs)

        try:
            from core.models import AuditLog
        except ImportError:
            return response

        user = request.user if request.user.is_authenticated else None

        try:
            AuditLog.objects.create(
                user=user,
                action=action,
                content_type=content_type,
                object_id=instance_pk,
                object_repr=instance_repr[:200],
            )
        except Exception:
            pass

        return response


class RBACMixin:
    """
    Mixin that enforces role-based access control on class-based views.

    Set `allowed_roles` on the view to a list of role names that are
    permitted to access the view. If the user does not have one of the
    allowed roles, a 403 Forbidden response is returned.

    Example:
        class LeadCreateView(RBACMixin, CreateView):
            allowed_roles = ['admin', 'sales_manager', 'sales_rep']
    """

    allowed_roles = None

    def get_allowed_roles(self):
        if self.allowed_roles is None:
            return []
        return list(self.allowed_roles)

    def _get_user_roles(self, user):
        if not user.is_authenticated:
            return []

        if user.is_superuser:
            return None

        roles = set()

        if hasattr(user, 'role'):
            role_value = user.role
            if callable(role_value):
                role_value = role_value()
            if isinstance(role_value, str):
                roles.add(role_value)
            elif hasattr(role_value, '__iter__'):
                roles.update(str(r) for r in role_value)

        if hasattr(user, 'roles'):
            user_roles = user.roles
            if hasattr(user_roles, 'all'):
                for role_obj in user_roles.all():
                    if hasattr(role_obj, 'name'):
                        roles.add(str(role_obj.name))
                    else:
                        roles.add(str(role_obj))
            elif hasattr(user_roles, '__iter__'):
                roles.update(str(r) for r in user_roles)

        if hasattr(user, 'groups'):
            for group in user.groups.all():
                roles.add(group.name)

        return list(roles)

    def dispatch(self, request, *args, **kwargs):
        allowed = self.get_allowed_roles()

        if not allowed:
            return super().dispatch(request, *args, **kwargs)

        if not request.user.is_authenticated:
            return HttpResponseForbidden(
                "You do not have permission to access this resource."
            )

        user_roles = self._get_user_roles(request.user)

        if user_roles is None:
            return super().dispatch(request, *args, **kwargs)

        if not any(role in allowed for role in user_roles):
            return HttpResponseForbidden(
                "You do not have permission to access this resource."
            )

        return super().dispatch(request, *args, **kwargs)


class PaginationMixin:
    """
    Mixin that adds pagination context to list views.

    Attributes:
        paginate_by: Number of items per page (default: 25).
        page_kwarg: The query parameter name for the page number (default: 'page').
        max_page_size: Maximum allowed page size when using dynamic page sizes (default: 100).
        page_size_kwarg: Query parameter to allow dynamic page size (default: 'page_size').
    """

    paginate_by = 25
    page_kwarg = "page"
    max_page_size = 100
    page_size_kwarg = "page_size"

    def get_paginate_by(self, queryset):
        page_size = self.request.GET.get(self.page_size_kwarg)
        if page_size is not None:
            try:
                page_size = int(page_size)
                if 1 <= page_size <= self.max_page_size:
                    return page_size
            except (ValueError, TypeError):
                pass
        return self.paginate_by

    def get_pagination_context(self, queryset):
        page_size = self.get_paginate_by(queryset)
        paginator = Paginator(queryset, page_size)
        page_number = self.request.GET.get(self.page_kwarg, 1)

        try:
            page_obj = paginator.page(page_number)
        except PageNotAnInteger:
            page_obj = paginator.page(1)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        page_range = paginator.get_elided_page_range(
            page_obj.number, on_each_side=2, on_ends=1
        )

        return {
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "object_list": page_obj.object_list,
            "elided_page_range": list(page_range),
            "total_count": paginator.count,
            "num_pages": paginator.num_pages,
            "current_page": page_obj.number,
            "page_size": page_size,
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        queryset = context.get("object_list", self.get_queryset())
        pagination_context = self.get_pagination_context(queryset)
        context.update(pagination_context)
        return context