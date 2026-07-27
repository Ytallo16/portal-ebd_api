from datetime import datetime, time

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from core.permissions import IsAdminSistema
from core.tenant import resolve_active_organization

from .models import ActivityLog
from .serializers import ActivityLogSerializer


class ActivityLogListView(ListAPIView):
    serializer_class = ActivityLogSerializer
    permission_classes = [IsAuthenticated, IsAdminSistema]

    def get_queryset(self):
        organization = resolve_active_organization(self.request, required=True)
        queryset = ActivityLog.objects.filter(
            organization=organization,
        ).select_related('actor', 'organization')

        search = self.request.query_params.get('search', '').strip()
        if search:
            queryset = queryset.filter(
                Q(actor_name__icontains=search)
                | Q(actor_email__icontains=search)
                | Q(action__icontains=search)
                | Q(resource__icontains=search)
                | Q(object_reference__icontains=search)
                | Q(path__icontains=search)
            )

        result = self.request.query_params.get('result', '').lower()
        if result == 'success':
            queryset = queryset.filter(succeeded=True)
        elif result == 'failure':
            queryset = queryset.filter(succeeded=False)

        method = self.request.query_params.get('method', '').upper()
        if method in {'POST', 'PUT', 'PATCH', 'DELETE'}:
            queryset = queryset.filter(method=method)

        event_type = self.request.query_params.get('event_type', '').upper()
        if event_type in {'CREATE', 'UPDATE', 'DELETE', 'LOGIN', 'REQUEST'}:
            queryset = queryset.filter(event_type=event_type)

        date_from = parse_date(self.request.query_params.get('date_from', ''))
        if date_from:
            start = timezone.make_aware(datetime.combine(date_from, time.min))
            queryset = queryset.filter(created_at__gte=start)

        date_to = parse_date(self.request.query_params.get('date_to', ''))
        if date_to:
            end = timezone.make_aware(datetime.combine(date_to, time.max))
            queryset = queryset.filter(created_at__lte=end)

        return queryset
