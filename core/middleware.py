import re

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin

from core.utils import get_client_ip


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware that logs request metadata for the audit trail.
    Attaches request metadata (IP address, timestamp, user) to the request
    object so downstream views and mixins can use it for audit logging.
    """

    def process_request(self, request):
        request.audit_ip = get_client_ip(request)
        request.audit_timestamp = timezone.now()
        request.audit_user = None
        return None

    def process_view(self, request, view_func, view_args, view_kwargs):
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.audit_user = request.user
        return None

    def process_response(self, request, response):
        if not hasattr(request, 'audit_user'):
            return response

        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            self._log_write_request(request, response)

        return response

    def _log_write_request(self, request, response):
        try:
            from audit_logs.models import AuditLog
        except ImportError:
            return

        if not hasattr(request, 'audit_user') or request.audit_user is None:
            return

        if response.status_code >= 400:
            return

        method_action_map = {
            'POST': AuditLog.Action.CREATE,
            'PUT': AuditLog.Action.UPDATE,
            'PATCH': AuditLog.Action.UPDATE,
            'DELETE': AuditLog.Action.DELETE,
        }

        action = method_action_map.get(request.method)
        if action is None:
            return

        try:
            import uuid as uuid_mod
            entity_id = uuid_mod.uuid4()

            AuditLog.create_entry(
                entity_type=request.path,
                entity_id=entity_id,
                action=action,
                user=request.audit_user,
                changes={
                    'method': request.method,
                    'path': request.path,
                    'status_code': response.status_code,
                },
                ip_address=getattr(request, 'audit_ip', None),
            )
        except Exception:
            pass


class LoginRequiredMiddleware(MiddlewareMixin):
    """
    Middleware that redirects unauthenticated users to the login page.
    Excludes public paths defined in settings.PUBLIC_PATHS or a default set.
    """

    def _get_public_paths(self):
        default_public_paths = [
            '/admin/login/',
            '/api/v1/auth/login/',
            '/api/v1/auth/register/',
        ]
        public_paths = getattr(settings, 'PUBLIC_PATHS', default_public_paths)
        return public_paths

    def _get_public_path_patterns(self):
        default_patterns = [
            r'^/admin/.*$',
            r'^/api/v1/auth/.*$',
            r'^/static/.*$',
            r'^/media/.*$',
            r'^/health/?$',
        ]
        patterns = getattr(settings, 'PUBLIC_PATH_PATTERNS', default_patterns)
        compiled = []
        for pattern in patterns:
            try:
                compiled.append(re.compile(pattern))
            except re.error:
                pass
        return compiled

    def _is_public_path(self, path):
        public_paths = self._get_public_paths()
        if path in public_paths:
            return True

        public_patterns = self._get_public_path_patterns()
        for pattern in public_patterns:
            if pattern.match(path):
                return True

        return False

    def process_request(self, request):
        if self._is_public_path(request.path):
            return None

        if hasattr(request, 'user') and request.user.is_authenticated:
            return None

        login_url = getattr(settings, 'LOGIN_URL', '/admin/login/')

        try:
            login_url = reverse('login')
        except Exception:
            pass

        if request.path == login_url:
            return None

        if request.path.startswith('/api/'):
            return HttpResponseForbidden('Authentication required.')

        return redirect(f'{login_url}?next={request.path}')


class RoleCheckMiddleware(MiddlewareMixin):
    """
    Middleware that enforces role-based access control on URL patterns.
    Configure ROLE_REQUIRED_PATHS in settings as a list of tuples:
        ROLE_REQUIRED_PATHS = [
            (r'^/reports/.*$', ['admin', 'sales']),
            (r'^/automation/.*$', ['admin']),
        ]
    Each tuple contains a regex pattern and a list of allowed roles.
    Superusers bypass all role checks.
    """

    def _get_role_required_paths(self):
        raw_paths = getattr(settings, 'ROLE_REQUIRED_PATHS', [])
        compiled = []
        for pattern_str, roles in raw_paths:
            try:
                compiled.append((re.compile(pattern_str), roles))
            except re.error:
                pass
        return compiled

    def process_request(self, request):
        if not hasattr(request, 'user') or not request.user.is_authenticated:
            return None

        if request.user.is_superuser:
            return None

        role_paths = self._get_role_required_paths()
        if not role_paths:
            return None

        for pattern, allowed_roles in role_paths:
            if pattern.match(request.path):
                user_role = getattr(request.user, 'role', None)
                if user_role is None:
                    return HttpResponseForbidden(
                        'You do not have permission to access this resource.'
                    )
                if user_role not in allowed_roles:
                    return HttpResponseForbidden(
                        'You do not have permission to access this resource.'
                    )
                break

        return None