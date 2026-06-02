from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.tenant import get_operational_organization

from .models import Notification
from .serializers import NotificationSerializer
from .services import mark_all_notifications_read, mark_notification_read, sync_user_notifications


def _should_sync(request):
    raw = request.query_params.get('sync', '1')
    return str(raw).lower() not in ('0', 'false', 'no')


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    org = get_operational_organization(request)
    if _should_sync(request):
        sync_user_notifications(request.user, org)

    queryset = (
        Notification.objects.filter(
            user=request.user,
            organization=org,
            read_at__isnull=True,
        )
        .order_by('-created_at')[:20]
    )
    unread_count = Notification.objects.filter(
        user=request.user,
        organization=org,
        read_at__isnull=True,
    ).count()

    return Response(
        {
            'results': NotificationSerializer(queryset, many=True).data,
            'unread_count': unread_count,
        }
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def notification_read(request, pk):
    org = get_operational_organization(request)
    try:
        notification = Notification.objects.get(pk=pk, user=request.user, organization=org)
    except Notification.DoesNotExist:
        return Response({'detail': 'Notificação não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    mark_notification_read(notification)
    unread_count = Notification.objects.filter(
        user=request.user,
        organization=org,
        read_at__isnull=True,
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
    org = get_operational_organization(request)
    mark_all_notifications_read(request.user, org)
    return Response({'unread_count': 0})
