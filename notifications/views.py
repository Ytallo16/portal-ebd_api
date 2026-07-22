from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.scoping import get_org_descendant_ids, is_campo_organization
from core.tenant import resolve_active_organization

from .models import Notification
from .serializers import NotificationSerializer
from .services import mark_notification_read, sync_user_notifications


def _should_sync(request):
    raw = request.query_params.get('sync', '1')
    return str(raw).lower() not in ('0', 'false', 'no')


def _notification_scope(request):
    """Resolve o escopo de notificações do contexto ativo.

    - Igreja: apenas a própria organização.
    - Campo: agrega todas as igrejas descendentes do campo.

    Retorna (orgs_para_sync, filtro_orm), onde `filtro_orm` é aplicado nas
    queries de Notification.
    """
    org = resolve_active_organization(request, required=True)
    if is_campo_organization(org):
        from organizations.models import Organization

        igreja_ids = get_org_descendant_ids(org, include_self=False)
        orgs = list(Organization.objects.filter(id__in=igreja_ids, is_active=True))
        return orgs, {'organization_id__in': igreja_ids}
    return [org], {'organization': org}


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    orgs, org_filter = _notification_scope(request)
    if _should_sync(request):
        for org in orgs:
            sync_user_notifications(request.user, org)

    base = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,
        **org_filter,
    )
    queryset = base.order_by('-created_at')[:20]
    unread_count = base.count()

    return Response(
        {
            'results': NotificationSerializer(queryset, many=True).data,
            'unread_count': unread_count,
        }
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def notification_read(request, pk):
    _orgs, org_filter = _notification_scope(request)
    try:
        notification = Notification.objects.get(pk=pk, user=request.user, **org_filter)
    except Notification.DoesNotExist:
        return Response({'detail': 'Notificação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    mark_notification_read(notification)
    unread_count = Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,
        **org_filter,
    ).count()
    return Response(
        {
            'notification': NotificationSerializer(notification).data,
            'unread_count': unread_count,
        }
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def notification_read_all(request):
    _orgs, org_filter = _notification_scope(request)
    now = timezone.now()
    Notification.objects.filter(
        user=request.user,
        read_at__isnull=True,
        **org_filter,
    ).update(read_at=now, updated_at=now)
    return Response({'unread_count': 0})
