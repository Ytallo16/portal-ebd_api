from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.scoping import is_somente_professor
from core.viewmixins import OrganizationScopedViewMixin

from .models import LessonSchedule
from .schedule_serializers import (
    LessonScheduleBulkSerializer,
    LessonScheduleSerializer,
)
from .services import can_manage_lessons


class LessonScheduleViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = LessonScheduleSerializer
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = (
            LessonSchedule.objects.filter(organization=org)
            .select_related('lesson', 'class_group', 'professor')
            .order_by('lesson__data', 'class_group__nome')
        )

        lesson_id = self.request.query_params.get('lesson_id')
        class_id = self.request.query_params.get('class_id')
        professor_id = self.request.query_params.get('professor_id')
        trimestre = self.request.query_params.get('trimestre')
        ano = self.request.query_params.get('ano')

        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        if professor_id:
            queryset = queryset.filter(professor_id=professor_id)
        if trimestre:
            queryset = queryset.filter(lesson__trimestre=trimestre)
        if ano:
            queryset = queryset.filter(lesson__ano=ano)

        if is_somente_professor(self.request.user, org):
            queryset = queryset.filter(professor=self.request.user)

        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('licoes', 'visualizar')]
        elif self.action == 'bulk':
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        return [perm() for perm in perms]

    def _ensure_secretary(self, organization):
        if not can_manage_lessons(self.request.user, organization):
            raise PermissionDenied('Apenas secretários podem gerenciar a escala de professores.')

    def _ensure_schedule_scope(self, serializer, organization):
        lesson = serializer.validated_data.get('lesson') or getattr(
            serializer.instance,
            'lesson',
            None,
        )
        class_group = serializer.validated_data.get('class_group') or getattr(
            serializer.instance,
            'class_group',
            None,
        )
        if lesson and lesson.organization_id != organization.id:
            raise ValidationError({'lesson': 'Lição inválida para esta igreja.'})
        if class_group and class_group.organization_id != organization.id:
            raise ValidationError({'class_group': 'Turma inválida para esta igreja.'})

    def perform_create(self, serializer):
        organization = self.get_active_organization()
        self._ensure_secretary(organization)
        self._ensure_schedule_scope(serializer, organization)
        serializer.save(
            organization=organization,
            created_by=self.request.user,
            updated_by=self.request.user,
        )

    def perform_update(self, serializer):
        organization = self.get_active_organization()
        self._ensure_secretary(organization)
        self._ensure_schedule_scope(serializer, organization)
        serializer.save(organization=organization, updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        self._ensure_secretary(self.get_active_organization())
        return super().destroy(request, *args, **kwargs)

    @action(detail=False, methods=['POST'], url_path='bulk')
    def bulk(self, request):
        self._ensure_secretary(self.get_active_organization())
        serializer = LessonScheduleBulkSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        schedules = serializer.save()
        output = LessonScheduleSerializer(schedules, many=True)
        return Response(output.data, status=status.HTTP_200_OK)
