from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.scoping import (
    can_manage_igrejas,
    get_igrejas_do_campo,
    get_org_descendant_ids,
    is_admin_sistema,
    is_campo_organization,
    is_igreja_organization,
)
from core.tenant import get_user_organization
from organizations.constants import TIPO_IGREJA

from .models import Organization, OrganizationMembership
from .serializers import ChurchSerializer, OrganizationMembershipSerializer, OrganizationSerializer


def _resolve_campo_for_churches(request):
    """Campo explícito ou campo pai da igreja ativa — mantém contexto de igreja na top bar."""
    active_org = get_user_organization(request)
    if is_campo_organization(active_org):
        campo = active_org
    elif is_igreja_organization(active_org) and active_org.parent_id:
        campo = active_org.parent
    else:
        raise ValidationError(
            {'detail': 'Selecione o campo ou uma igreja do seu campo para gerenciar igrejas.'}
        )
    if not can_manage_igrejas(request.user, campo):
        raise PermissionDenied('Sem permissão para gerenciar igrejas deste campo.')
    return campo


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    search_fields = ['nome', 'sigla', 'cidade', 'uf']

    def get_queryset(self):
        user = self.request.user
        if is_admin_sistema(user):
            return Organization.objects.filter(is_active=True).select_related('parent').order_by('nome')

        active_org = get_user_organization(self.request)
        if is_campo_organization(active_org):
            org_ids = get_org_descendant_ids(active_org)
            return Organization.objects.filter(id__in=org_ids, is_active=True).select_related('parent').order_by('nome')

        return Organization.objects.filter(id=active_org.id, is_active=True).select_related('parent')

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('organizacoes', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('organizacoes', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('organizacoes', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('organizacoes', 'excluir')]
        return [perm() for perm in perms]


class ChurchViewSet(viewsets.ModelViewSet):
    serializer_class = ChurchSerializer
    search_fields = ['nome', 'sigla', 'cidade', 'uf', 'responsavel']

    def get_queryset(self):
        campo = _resolve_campo_for_churches(self.request)
        include_inactive = self.request.query_params.get('include_inactive', '').lower() in ('1', 'true', 'yes')
        return get_igrejas_do_campo(campo, include_inactive=include_inactive)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('organizacoes', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('organizacoes', 'criar')]
        elif self.action in ['partial_update', 'update', 'activate', 'deactivate']:
            perms = [IsAuthenticated, module_permission('organizacoes', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('organizacoes', 'excluir')]
        return [perm() for perm in perms]

    def perform_create(self, serializer):
        campo = _resolve_campo_for_churches(self.request)
        serializer.save(
            parent=campo,
            tipo=TIPO_IGREJA,
            formato='',
            created_by=self.request.user,
        )

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def perform_destroy(self, instance):
        from classrooms.models import ClassGroup
        from students.models import Student

        has_classes = ClassGroup.objects.filter(organization=instance, is_active=True).exists()
        has_students = Student.objects.filter(organization=instance, is_active=True).exists()
        if has_classes or has_students:
            raise ValidationError(
                {'detail': 'Não é possível excluir igreja com turmas ou alunos ativos. Desative-a primeiro.'}
            )
        instance.is_active = False
        instance.deleted_at = timezone.now()
        instance.status = 'INATIVA'
        instance.updated_by = self.request.user
        instance.save(update_fields=['is_active', 'deleted_at', 'status', 'updated_by', 'updated_at'])

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        church = self.get_object()
        church.is_active = False
        church.status = 'INATIVA'
        church.updated_by = request.user
        church.save(update_fields=['is_active', 'status', 'updated_by', 'updated_at'])
        return Response(ChurchSerializer(church).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        church = self.get_object()
        church.is_active = True
        church.status = 'ATIVA'
        church.deleted_at = None
        church.updated_by = request.user
        church.save(update_fields=['is_active', 'status', 'deleted_at', 'updated_by', 'updated_at'])
        return Response(ChurchSerializer(church).data)


class OrganizationMembershipViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated, module_permission('usuarios', 'visualizar')]

    def get_queryset(self):
        org = get_user_organization(self.request)
        org_ids = get_org_descendant_ids(org) if is_campo_organization(org) else [org.id]
        return OrganizationMembership.objects.filter(
            organization_id__in=org_ids
        ).select_related('user', 'organization')
