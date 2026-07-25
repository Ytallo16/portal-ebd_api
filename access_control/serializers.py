from rest_framework import serializers

from access_control.constants import (
    ROLE_ADMINISTRADOR,
    ROLE_PROFESSOR,
    ROLE_SECRETARIO_CAMPO,
    ROLE_SECRETARIO_IGREJA,
)
from core.scoping import (
    get_creatable_user_roles,
    get_org_descendant_ids,
    is_admin_sistema,
    is_campo_organization,
    is_igreja_organization,
)
from core.tenant import resolve_active_organization
from organizations.models import OrganizationMembership

from .models import ModulePermission, Role, RolePermission, UserRole


class ModulePermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModulePermission
        fields = ['id', 'modulo', 'visualizar', 'criar', 'editar', 'excluir', 'aprovar']


class RolePermissionSerializer(serializers.ModelSerializer):
    permission_detail = ModulePermissionSerializer(source='permission', read_only=True)

    class Meta:
        model = RolePermission
        fields = ['id', 'role', 'permission', 'permission_detail']


class RoleSerializer(serializers.ModelSerializer):
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = ['id', 'nome', 'descricao', 'ativo', 'permissions']

    def get_permissions(self, obj):
        return ModulePermissionSerializer(
            [rp.permission for rp in obj.permissions.select_related('permission').all()], many=True
        ).data


class RolePermissionsUpdateSerializer(serializers.Serializer):
    permission_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=True)

    def validate_permission_ids(self, value):
        permission_ids = list(dict.fromkeys(value))
        existing_ids = set(
            ModulePermission.objects.filter(id__in=permission_ids).values_list('id', flat=True)
        )
        missing_ids = sorted(set(permission_ids) - existing_ids)
        if missing_ids:
            raise serializers.ValidationError(
                f'Permissões inexistentes: {", ".join(map(str, missing_ids))}.'
            )
        return permission_ids


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'organization', 'ativo']

    def validate(self, attrs):
        instance = self.instance
        user = attrs.get('user', getattr(instance, 'user', None))
        role = attrs.get('role', getattr(instance, 'role', None))
        organization = attrs.get('organization', getattr(instance, 'organization', None))

        if role is None or user is None:
            return attrs

        role_name = role.nome.upper()
        assignment_changed = instance is None or any(
            field in attrs for field in ('user', 'role', 'organization')
        )

        if assignment_changed and not role.ativo:
            raise serializers.ValidationError({'role': 'O perfil selecionado está inativo.'})

        self._validate_role_organization(role_name, organization)

        request = self.context.get('request')
        if request is None or is_admin_sistema(request.user):
            return attrs

        active_org = resolve_active_organization(request, required=True)
        if role_name not in get_creatable_user_roles(request.user, active_org):
            raise serializers.ValidationError(
                {'role': 'Sem permissão para atribuir este perfil.'}
            )

        organization_ids = (
            get_org_descendant_ids(active_org)
            if is_campo_organization(active_org)
            else [active_org.id]
        )
        if organization is None or organization.id not in organization_ids:
            raise serializers.ValidationError(
                {'organization': 'Organização fora do escopo ativo do usuário.'}
            )

        if assignment_changed and not OrganizationMembership.objects.filter(
            user=user,
            organization=organization,
            ativo=True,
        ).exists():
            raise serializers.ValidationError(
                {'user': 'O usuário deve possuir vínculo ativo com a organização informada.'}
            )

        return attrs

    def _validate_role_organization(self, role_name, organization):
        if role_name == ROLE_ADMINISTRADOR:
            if organization is not None:
                raise serializers.ValidationError(
                    {'organization': 'Administrador do sistema deve possuir escopo global.'}
                )
            return

        if role_name == ROLE_SECRETARIO_CAMPO:
            if organization is None or not is_campo_organization(organization):
                raise serializers.ValidationError(
                    {'organization': 'Secretário de campo exige uma organização do tipo campo.'}
                )
            return

        if role_name in (ROLE_SECRETARIO_IGREJA, ROLE_PROFESSOR):
            if organization is None or not is_igreja_organization(organization):
                raise serializers.ValidationError(
                    {'organization': 'Este perfil exige uma organização do tipo igreja.'}
                )
