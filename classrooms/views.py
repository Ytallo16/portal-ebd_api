from django.db.models import Count, Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.scoping import is_somente_professor
from core.viewmixins import OrganizationScopedViewMixin
from lessons.models import Lesson
from lessons.querysets import with_attendance_totals
from lessons.serializers import LessonSerializer

from .models import ClassGroup, ClassTeacher
from .serializers import ClassGroupSerializer


class ClassGroupViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = ClassGroupSerializer
    search_fields = ['nome', 'faixa_etaria']
    use_operational_organization = True

    def get_queryset(self):
        organization = self.get_active_organization()
        queryset = (
            ClassGroup.objects.filter(organization=organization, is_active=True)
            .annotate(
                total_alunos=Count(
                    'students',
                    filter=Q(students__is_active=True, students__ativo=True),
                    distinct=True,
                )
            )
            .order_by('nome')
        )
        class_ids = self.get_teaching_class_filter(organization)
        if class_ids is not None:
            queryset = queryset.filter(id__in=class_ids)
        return queryset

    def perform_create(self, serializer):
        organization = self.get_active_organization()
        if is_somente_professor(self.request.user, organization):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Professores não podem criar turmas.')
        serializer.save(organization=organization, created_by=self.request.user)

    def perform_update(self, serializer):
        organization = self.get_active_organization()
        if is_somente_professor(self.request.user, organization):
            from rest_framework.exceptions import PermissionDenied

            raise PermissionDenied('Professores não podem editar turmas.')
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

        queryset = Lesson.objects.filter(
            organization=class_group.organization,
            is_active=True,
        )
        if trimester:
            queryset = queryset.filter(trimestre=trimester)
        if year:
            queryset = queryset.filter(ano=year)

        serializer = LessonSerializer(
            with_attendance_totals(queryset).order_by('data'),
            many=True,
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class ClassTeacherViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, module_permission('turmas', 'editar')]
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = ClassTeacher.objects.filter(
            class_group__organization=org,
            class_group__is_active=True,
        ).select_related('class_group', 'user')
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        return queryset

    def get_serializer_class(self):
        from .serializers import ClassTeacherSerializer

        return ClassTeacherSerializer

    def perform_create(self, serializer):
        class_group = serializer.validated_data['class_group']
        org = self.get_active_organization()
        if class_group.organization_id != org.id:
            from rest_framework.exceptions import ValidationError

            raise ValidationError({'class_group': 'Turma inválida para esta igreja.'})
        serializer.save(created_by=self.request.user)
