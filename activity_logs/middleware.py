from organizations.models import Organization

from .context import (
    begin_activity_context,
    end_activity_context,
    has_entity_events,
)
from .services import describe_activity, record_activity


class ActivityLogMiddleware:
    tracked_methods = {'POST', 'PUT', 'PATCH', 'DELETE'}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        tokens = begin_activity_context(request)
        try:
            response = self.get_response(request)
            if not has_entity_events():
                self._record(request, response)
            return response
        finally:
            end_activity_context(tokens)

    def _record(self, request, response):
        if request.method not in self.tracked_methods:
            return
        if not request.path.startswith('/api/v1/'):
            return

        user = getattr(request, 'user', None)
        if not user or not user.is_authenticated:
            return

        raw_org_id = (
            request.META.get('HTTP_X_ORGANIZATION_ID')
            or getattr(user, 'active_organization_id', None)
        )
        try:
            organization = Organization.objects.filter(id=raw_org_id).first()
        except (TypeError, ValueError):
            organization = None
        if organization is None:
            return

        action, resource, object_reference = describe_activity(
            request.method,
            request.path,
        )
        record_activity(
            request=request,
            user=user,
            organization=organization,
            action=action,
            resource=resource,
            object_reference=object_reference,
            status_code=response.status_code,
        )
