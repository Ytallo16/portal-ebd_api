from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin

from .models import Student
from .serializers import StudentSerializer


class StudentViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    search_fields = ['nome']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = (
            Student.objects.filter(organization=org, is_active=True)
            .select_related('class_group', 'endereco')
            .prefetch_related('responsaveis')
            .order_by('nome')
        )
        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(class_group_id__in=class_ids)
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(organization=self.get_active_organization(), created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('alunos', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('alunos', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('alunos', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('alunos', 'excluir')]
        return [perm() for perm in perms]
