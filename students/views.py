from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from core.permissions import module_permission
from core.tenant import get_user_organization

from .models import Student
from .serializers import StudentSerializer


class StudentViewSet(viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    search_fields = ['nome']

    def get_queryset(self):
        org = get_user_organization(self.request)
        queryset = (
            Student.objects.filter(organization=org, is_active=True)
            .select_related('class_group', 'endereco')
            .prefetch_related('responsaveis')
            .order_by('nome')
        )
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        return queryset

    def perform_create(self, serializer):
        serializer.save(organization=get_user_organization(self.request), created_by=self.request.user)

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
