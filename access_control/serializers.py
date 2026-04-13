from rest_framework import serializers

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


class UserRoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserRole
        fields = ['id', 'user', 'role', 'organization', 'ativo']
