from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

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
    permission_classes = [IsAuthenticated]
    search_fields = ['nome']

    @action(detail=True, methods=['GET', 'PUT'], url_path='permissions')
    def permissions(self, request, pk=None):
        role = self.get_object()

        if request.method == 'GET':
            permissions = [rp.permission for rp in role.permissions.select_related('permission').all()]
            return Response(ModulePermissionSerializer(permissions, many=True).data)

        serializer = RolePermissionsUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        permission_ids = serializer.validated_data['permission_ids']
        RolePermission.objects.filter(role=role).exclude(permission_id__in=permission_ids).delete()

        current_ids = set(
            RolePermission.objects.filter(role=role).values_list('permission_id', flat=True)
        )
        for permission_id in permission_ids:
            if permission_id not in current_ids:
                RolePermission.objects.create(role=role, permission_id=permission_id)

        permissions = [rp.permission for rp in role.permissions.select_related('permission').all()]
        return Response(ModulePermissionSerializer(permissions, many=True).data, status=status.HTTP_200_OK)


class ModulePermissionViewSet(viewsets.ModelViewSet):
    queryset = ModulePermission.objects.all().order_by('modulo')
    serializer_class = ModulePermissionSerializer
    permission_classes = [IsAuthenticated]


class UserRoleViewSet(viewsets.ModelViewSet):
    queryset = UserRole.objects.select_related('user', 'role', 'organization').all()
    serializer_class = UserRoleSerializer
    permission_classes = [IsAuthenticated]
