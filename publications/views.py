from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin

from .models import PublicationControl
from .serializers import PublicationControlSerializer


class PublicationControlViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = PublicationControlSerializer
    search_fields = ['person_name']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = PublicationControl.objects.filter(organization=org, is_active=True).select_related('class_group')

        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(class_group_id__in=class_ids)

        class_id = self.request.query_params.get('class_id')
        person_type = self.request.query_params.get('person_type')

        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        if person_type:
            queryset = queryset.filter(person_type=person_type)

        return queryset.order_by('person_name')

    def perform_create(self, serializer):
        serializer.save(organization=self.get_active_organization(), created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('revistas', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('revistas', 'criar')]
        elif self.action in ['partial_update', 'update', 'toggle']:
            perms = [IsAuthenticated, module_permission('revistas', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('revistas', 'excluir')]
        return [perm() for perm in perms]

    @action(detail=True, methods=['PATCH'])
    def toggle(self, request, pk=None):
        item = self.get_object()
        if 'recebeu' in request.data:
            item.recebeu = bool(request.data['recebeu'])
        if 'pagou' in request.data:
            item.pagou = bool(request.data['pagou'])
        item.updated_by = request.user
        item.save(update_fields=['recebeu', 'pagou', 'updated_by', 'updated_at'])
        return Response(PublicationControlSerializer(item).data)
