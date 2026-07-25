from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import IsAdminSistema, module_permission
from core.scoping import get_org_descendant_ids, is_admin_sistema, is_campo_organization
from core.tenant import resolve_active_organization

from .models import ModulePermission, Role, RolePermission, UserRole
from .serializers import (
    ModulePermissionSerializer,
    RolePermissionsUpdateSerializer,
    RoleSerializer,
    UserRoleSerializer,
)


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.filter(ativo=True).order_by('nome')
    serializer_class = RoleSerializer
    search_fields = ['nome']

    def get_permissions(self):
        is_read = self.action in ['list', 'retrieve'] or (
            self.action == 'permissions' and self.request.method == 'GET'
        )
        if is_read:
            perms = [IsAuthenticated, module_permission('usuarios', 'visualizar', require_organization=False)]
        else:
            perms = [IsAuthenticated, IsAdminSistema]
        return [perm() for perm in perms]

    @action(detail=True, methods=['GET', 'PUT'], url_path='permissions')
    def permissions(self, request, pk=None):
        role = self.get_object()

        if request.method == 'GET':
            permissions = [rp.permission for rp in role.permissions.select_related('permission').all()]
            return Response(ModulePermissionSerializer(permissions, many=True).data)

        serializer = RolePermissionsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permission_ids = serializer.validated_data['permission_ids']
        with transaction.atomic():
            RolePermission.objects.filter(role=role).exclude(permission_id__in=permission_ids).delete()

            current_ids = set(
                RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
            )
            RolePermission.objects.bulk_create(
                [
                    RolePermission(role=role, permission_id=permission_id)
                    for permission_id in permission_ids
                    if permission_id not in current_ids
                ]
            )

        permissions = [rp.permission for rp in role.permissions.select_related('permission').all()]
        return Response(ModulePermissionSerializer(permissions, many=True).data, status=status.HTTP_200_OK)


class ModulePermissionViewSet(viewsets.ModelViewSet):
    queryset = ModulePermission.objects.all().order_by('modulo')
    serializer_class = ModulePermissionSerializer

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [
                IsAuthenticated,
                module_permission('usuarios', 'visualizar', require_organization=False),
            ]
        else:
            perms = [IsAuthenticated, IsAdminSistema]
        return [perm() for perm in perms]


class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.select_related('user', 'role', 'organization').order_by('id')
    serializer_class = UserRoleSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        if is_admin_sistema(self.request.user):
            return queryset

        active_org = resolve_active_organization(self.request, required=False)
        if active_org is None:
            return queryset.none()

        organization_ids = (
            get_org_descendant_ids(active_org)
            if is_campo_organization(active_org)
            else [active_org.id]
        )
        return queryset.filter(organization_id__in=organization_ids)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('usuarios', 'visualizar', require_organization=False)]
        else:
            perms = [IsAuthenticated, module_permission('usuarios', 'editar', require_organization=False)]
        return [perm() for perm in perms]
