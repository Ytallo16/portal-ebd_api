from django.db.models import Avg, Sum
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.tenant import get_user_organization

from .models import Offering
from .serializers import OfferingSerializer


class OfferingViewSet(viewsets.ModelViewSet):
    serializer_class = OfferingSerializer
    search_fields = ['class_group__nome', 'lesson__tema']

    def get_queryset(self):
        org = get_user_organization(self.request)
        queryset = Offering.objects.filter(organization=org, is_active=True).select_related('lesson', 'class_group')

        class_id = self.request.query_params.get('class_id')
        lesson_id = self.request.query_params.get('lesson_id')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        if date_from:
            queryset = queryset.filter(data__gte=date_from)
        if date_to:
            queryset = queryset.filter(data__lte=date_to)

        return queryset.order_by('-data')

    def perform_create(self, serializer):
        serializer.save(organization=get_user_organization(self.request), created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('financeiro', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('financeiro', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('financeiro', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('financeiro', 'excluir')]
        return [perm() for perm in perms]


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def offering_summary(request):
    org = get_user_organization(request)
    data = Offering.objects.filter(organization=org, is_active=True).aggregate(total=Sum('valor'), media=Avg('valor'))
    return Response({'total': data['total'] or 0, 'media': data['media'] or 0})
