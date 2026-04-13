from django.db.models import Count
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.tenant import get_user_organization
from lessons.models import Lesson
from lessons.serializers import LessonSerializer

from .models import ClassGroup, ClassTeacher
from .serializers import ClassGroupSerializer


class ClassGroupViewSet(viewsets.ModelViewSet):
    serializer_class = ClassGroupSerializer
    search_fields = ['nome', 'faixa_etaria']

    def get_queryset(self):
        organization = get_user_organization(self.request)
        return (
            ClassGroup.objects.filter(organization=organization, is_active=True)
            .annotate(total_alunos=Count('students', distinct=True))
            .order_by('nome')
        )

    def perform_create(self, serializer):
        serializer.save(organization=get_user_organization(self.request), created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'lessons']:
            perms = [IsAuthenticated, module_permission('turmas', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('turmas', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('turmas', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('turmas', 'excluir')]
        return [perm() for perm in perms]

    @action(detail=True, methods=['GET'], url_path='lessons')
    def lessons(self, request, pk=None):
        class_group = self.get_object()
        trimester = request.query_params.get('trimestre')
        year = request.query_params.get('ano')

        queryset = Lesson.objects.filter(organization=class_group.organization)
        if trimester:
            queryset = queryset.filter(trimestre=trimester)
        if year:
            queryset = queryset.filter(ano=year)

        serializer = LessonSerializer(queryset.order_by('data'), many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClassTeacherViewSet(viewsets.ModelViewSet):
    queryset = ClassTeacher.objects.select_related('class_group', 'user')
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        from .serializers import ClassTeacherSerializer

        return ClassTeacherSerializer
