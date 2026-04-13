from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import module_permission

from .models import Organization, OrganizationMembership
from .serializers import OrganizationMembershipSerializer, OrganizationSerializer


class OrganizationViewSet(viewsets.ModelViewSet):
    queryset = Organization.objects.filter(is_active=True).order_by('nome')
    serializer_class = OrganizationSerializer
    search_fields = ['nome', 'sigla', 'cidade', 'uf']

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


class OrganizationMembershipViewSet(
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet,
):
    queryset = OrganizationMembership.objects.select_related('user', 'organization')
    serializer_class = OrganizationMembershipSerializer
    permission_classes = [IsAuthenticated]
