from django.db.models import Q
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
from organizations.constants import FORMATO_CAMPO, FORMATO_IGREJA_INDIVIDUAL, TIPO_CAMPO, TIPO_IGREJA

from .models import Organization, OrganizationMembership
from .serializers import (
    ChurchSerializer,
    InstanceOrganizationCreateSerializer,
    InstanceOrganizationSerializer,
    InstanceOrganizationUpdateSerializer,
    OrganizationMembershipSerializer,
    OrganizationSerializer,
)


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


def _admin_instance_queryset(include_inactive=False):
    queryset = Organization.objects.filter(parent__isnull=True).filter(
        Q(tipo=TIPO_CAMPO, formato=FORMATO_CAMPO)
        | Q(tipo=TIPO_IGREJA, formato=FORMATO_IGREJA_INDIVIDUAL)
    )
    if not include_inactive:
        queryset = queryset.filter(is_active=True)
    return queryset.select_related('parent').order_by('nome')


def _is_top_level_instance(org):
    if org.parent_id:
        return False
    if org.tipo == TIPO_CAMPO and org.formato == FORMATO_CAMPO:
        return True
    return org.tipo == TIPO_IGREJA and org.formato == FORMATO_IGREJA_INDIVIDUAL


class OrganizationViewSet(viewsets.ModelViewSet):
    serializer_class = OrganizationSerializer
    search_fields = ['nome', 'sigla', 'cidade', 'uf']

    def get_queryset(self):
        user = self.request.user
        if is_admin_sistema(user):
            include_inactive = self.request.query_params.get('include_inactive', '').lower() in (
                '1',
                'true',
                'yes',
            )
            instances_only = self.request.query_params.get('instances_only', 'true').lower() in (
                '1',
                'true',
                'yes',
            )
            if instances_only:
                return _admin_instance_queryset(include_inactive=include_inactive)
            queryset = Organization.objects.all().select_related('parent').order_by('nome')
            if not include_inactive:
                queryset = queryset.filter(is_active=True)
            return queryset

        active_org = get_user_organization(self.request)
        if is_campo_organization(active_org):
            org_ids = get_org_descendant_ids(active_org)
            return Organization.objects.filter(id__in=org_ids, is_active=True).select_related('parent').order_by('nome')

        return Organization.objects.filter(id=active_org.id, is_active=True).select_related('parent')

    def get_serializer_class(self):
        if is_admin_sistema(self.request.user):
            if self.action == 'create':
                return InstanceOrganizationCreateSerializer
            if self.action in ('update', 'partial_update'):
                return InstanceOrganizationUpdateSerializer
            if self.action in ('list', 'retrieve', 'activate', 'deactivate'):
                return InstanceOrganizationSerializer
        return OrganizationSerializer

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

    def _ensure_admin_instance(self):
        if not is_admin_sistema(self.request.user):
            raise PermissionDenied('Somente administrador do sistema pode gerenciar instâncias.')

    def create(self, request, *args, **kwargs):
        self._ensure_admin_instance()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(created_by=request.user)
        output = InstanceOrganizationSerializer(instance, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        if is_admin_sistema(request.user):
            if not _is_top_level_instance(instance):
                raise ValidationError({'detail': 'Somente instâncias de topo podem ser editadas aqui.'})
            serializer = InstanceOrganizationUpdateSerializer(
                instance, data=request.data, partial=partial, context=self.get_serializer_context()
            )
            serializer.is_valid(raise_exception=True)
            serializer.save(updated_by=request.user)
            return Response(InstanceOrganizationSerializer(instance, context=self.get_serializer_context()).data)
        return super().update(request, *args, partial=partial, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        self._ensure_admin_instance()
        if not _is_top_level_instance(instance):
            raise ValidationError({'detail': 'Somente instâncias de topo podem ser removidas aqui.'})
        instance.is_active = False
        instance.deleted_at = timezone.now()
        instance.status = 'INATIVA'
        instance.updated_by = self.request.user
        instance.save(update_fields=['is_active', 'deleted_at', 'status', 'updated_by', 'updated_at'])

    @action(detail=True, methods=['post'])
    def deactivate(self, request, pk=None):
        self._ensure_admin_instance()
        instance = self.get_object()
        if not _is_top_level_instance(instance):
            raise ValidationError({'detail': 'Somente instâncias de topo podem ser desativadas aqui.'})
        instance.is_active = False
        instance.status = 'INATIVA'
        instance.updated_by = request.user
        instance.save(update_fields=['is_active', 'status', 'updated_by', 'updated_at'])
        return Response(InstanceOrganizationSerializer(instance, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        self._ensure_admin_instance()
        instance = self.get_object()
        if not _is_top_level_instance(instance):
            raise ValidationError({'detail': 'Somente instâncias de topo podem ser ativadas aqui.'})
        instance.is_active = True
        instance.status = 'ATIVA'
        instance.deleted_at = None
        instance.updated_by = request.user
        instance.save(update_fields=['is_active', 'status', 'deleted_at', 'updated_by', 'updated_at'])
        return Response(InstanceOrganizationSerializer(instance, context=self.get_serializer_context()).data)

    @action(detail=True, methods=['get'])
    def churches(self, request, pk=None):
        instance = self.get_object()
        if not is_campo_organization(instance):
            return Response([])
        include_inactive = request.query_params.get('include_inactive', '').lower() in ('1', 'true', 'yes')
        igrejas = get_igrejas_do_campo(instance, include_inactive=include_inactive)
        return Response(ChurchSerializer(igrejas, many=True).data)


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
