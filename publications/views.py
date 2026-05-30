from django.db.models import Case, IntegerField, Value, When
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin
from lessons.models import Trimester

from .constants import PAYMENT_METHOD_CHOICES
from .models import PublicationControl
from .serializers import PublicationControlSerializer
from .services import sync_publication_controls


class PublicationControlViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = PublicationControlSerializer
    search_fields = ['person_name']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = PublicationControl.objects.filter(organization=org, is_active=True).select_related(
            'class_group',
            'trimester',
        )

        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(class_group_id__in=class_ids)

        trimester_id = self.request.query_params.get('trimester_id')
        trimestre = self.request.query_params.get('trimestre')
        ano = self.request.query_params.get('ano')
        class_id = self.request.query_params.get('class_id')
        person_type = self.request.query_params.get('person_type')

        if trimester_id:
            queryset = queryset.filter(trimester_id=trimester_id)
        elif trimestre and ano:
            queryset = queryset.filter(trimester__numero=trimestre, trimester__ano=ano)

        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        if person_type:
            queryset = queryset.filter(person_type=person_type)

        return queryset.order_by(
            Case(
                When(person_type='professor', then=Value(0)),
                default=Value(1),
                output_field=IntegerField(),
            ),
            'person_name',
        )

    def perform_create(self, serializer):
        serializer.save(organization=self.get_active_organization(), created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('revistas', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('revistas', 'criar')]
        elif self.action in ['partial_update', 'update', 'toggle', 'bulk_toggle']:
            perms = [IsAuthenticated, module_permission('revistas', 'editar')]
        elif self.action == 'sync':
            perms = [IsAuthenticated, module_permission('revistas', 'criar')]
        else:
            perms = [IsAuthenticated, module_permission('revistas', 'excluir')]
        return [perm() for perm in perms]

    @action(detail=True, methods=['PATCH'])
    def toggle(self, request, pk=None):
        item = self.get_object()
        update_fields = ['updated_by', 'updated_at']

        if 'recebeu' in request.data:
            item.recebeu = bool(request.data['recebeu'])
            update_fields.append('recebeu')

        if 'pagou' in request.data:
            item.pagou = bool(request.data['pagou'])
            update_fields.append('pagou')
            if not item.pagou:
                item.metodo_pagamento = ''
                update_fields.append('metodo_pagamento')

        if 'metodo_pagamento' in request.data:
            metodo = request.data['metodo_pagamento'] or ''
            valid_values = {choice[0] for choice in PAYMENT_METHOD_CHOICES}
            if metodo and metodo not in valid_values:
                return Response({'metodo_pagamento': ['Método inválido.']}, status=status.HTTP_400_BAD_REQUEST)
            item.metodo_pagamento = metodo
            update_fields.append('metodo_pagamento')
            if metodo and not item.pagou:
                item.pagou = True
                if 'pagou' not in update_fields:
                    update_fields.append('pagou')

        item.updated_by = request.user
        item.save(update_fields=list(dict.fromkeys(update_fields)))
        return Response(PublicationControlSerializer(item).data)

    @action(detail=False, methods=['POST'])
    def sync(self, request):
        org = self.get_active_organization()
        trimester_id = request.data.get('trimester_id')
        class_id = request.data.get('class_id')
        if not trimester_id:
            return Response({'trimester_id': ['Obrigatório.']}, status=status.HTTP_400_BAD_REQUEST)

        trimester = Trimester.objects.filter(id=trimester_id, organization=org, is_active=True).first()
        if not trimester:
            return Response({'trimester_id': ['Trimestre não encontrado.']}, status=status.HTTP_404_NOT_FOUND)

        try:
            created_count = sync_publication_controls(
                org,
                trimester,
                created_by=request.user,
                class_group_id=class_id,
            )
        except DjangoValidationError as exc:
            return Response(exc.message_dict, status=status.HTTP_400_BAD_REQUEST)

        queryset = self.get_queryset().filter(trimester=trimester)
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        return Response(
            {
                'created_count': created_count,
                'total_count': queryset.count(),
                'items': PublicationControlSerializer(queryset, many=True).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=['PATCH'], url_path='bulk-toggle')
    def bulk_toggle(self, request):
        trimester_id = request.data.get('trimester_id')
        field = request.data.get('field')
        value = request.data.get('value')

        if not trimester_id:
            return Response({'trimester_id': ['Obrigatório.']}, status=status.HTTP_400_BAD_REQUEST)
        if field not in ('recebeu', 'pagou'):
            return Response({'field': ['Use recebeu ou pagou.']}, status=status.HTTP_400_BAD_REQUEST)

        org = self.get_active_organization()
        queryset = PublicationControl.objects.filter(
            organization=org,
            trimester_id=trimester_id,
            is_active=True,
        )

        class_id = request.data.get('class_id')
        person_type = request.data.get('person_type')
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        if person_type:
            queryset = queryset.filter(person_type=person_type)

        updated_count = queryset.update(**{field: bool(value), 'updated_by': request.user})
        return Response({'updated_count': updated_count})
