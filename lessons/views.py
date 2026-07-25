from django.db.models import Q
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceSheet
from classrooms.models import ClassGroup
from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin

from .models import Lesson, Trimester
from .querysets import with_attendance_totals
from .serializers import LessonSerializer, TrimesterSerializer
from .services import can_edit_lesson, can_manage_lessons, can_manage_trimesters


class TrimesterViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = TrimesterSerializer
    search_fields = ['titulo']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = Trimester.objects.filter(organization=org, is_active=True).order_by('-ano', '-numero')

        ano = self.request.query_params.get('ano')
        numero = self.request.query_params.get('numero')
        status_filter = self.request.query_params.get('status')

        if ano:
            queryset = queryset.filter(ano=ano)
        if numero:
            queryset = queryset.filter(numero=numero)
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        return queryset

    def perform_create(self, serializer):
        organization = self.get_active_organization()
        if not can_manage_trimesters(self.request.user, organization):
            raise PermissionDenied('Apenas secretários podem gerenciar trimestres.')
        serializer.save(organization=organization, created_by=self.request.user)

    def perform_update(self, serializer):
        if not can_manage_trimesters(self.request.user, serializer.instance.organization):
            raise PermissionDenied('Apenas secretários podem gerenciar trimestres.')
        serializer.save(updated_by=self.request.user)

    def destroy(self, request, *args, **kwargs):
        trimester = self.get_object()
        if not can_manage_trimesters(request.user, trimester.organization):
            raise PermissionDenied('Apenas secretários podem gerenciar trimestres.')
        return super().destroy(request, *args, **kwargs)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('licoes', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('licoes', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('licoes', 'excluir')]
        return [perm() for perm in perms]


class LessonViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    search_fields = ['tema', 'revista']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = Lesson.objects.filter(organization=org, is_active=True).order_by('-data', 'numero')

        trimestre = self.request.query_params.get('trimestre')
        ano = self.request.query_params.get('ano')
        status_filter = self.request.query_params.get('status')

        if trimestre:
            queryset = queryset.filter(trimestre=trimestre)
        if ano:
            queryset = queryset.filter(ano=ano)
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(
                Q(attendance_sheets__class_group_id__in=class_ids)
                | Q(schedules__professor=self.request.user)
            ).distinct()

        return with_attendance_totals(queryset)

    def perform_create(self, serializer):
        serializer.save(organization=self.get_active_organization(), created_by=self.request.user)

    def perform_update(self, serializer):
        lesson = self.get_object()
        if not can_edit_lesson(self.request.user, lesson):
            raise PermissionDenied('Você não pode editar esta lição fora da data permitida.')
        serializer.save(updated_by=self.request.user)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('licoes', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('licoes', 'criar')]
        elif self.action in ['partial_update', 'update', 'finalize']:
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('licoes', 'excluir')]
        return [perm() for perm in perms]

    @action(detail=True, methods=['POST'])
    def finalize(self, request, pk=None):
        lesson = self.get_object()
        if lesson.status == 'FINALIZADA':
            return Response({'detail': 'Lição já finalizada.'}, status=status.HTTP_200_OK)

        if not can_manage_lessons(request.user, lesson.organization):
            raise PermissionDenied('Apenas secretários podem finalizar a lição.')

        active_classes = ClassGroup.objects.filter(
            organization=lesson.organization,
            ativa=True,
            is_active=True,
        )
        pending = []
        for class_group in active_classes:
            sheet = AttendanceSheet.objects.filter(
                lesson=lesson,
                class_group=class_group,
            ).first()
            if not sheet or sheet.finalized_at is None:
                pending.append(class_group.nome)

        if pending:
            raise ValidationError(
                {
                    'detail': (
                        'Conclua a chamada de todas as turmas ativas antes de encerrar a lição.'
                    ),
                    'turmas_pendentes': pending,
                }
            )

        lesson.status = 'FINALIZADA'
        lesson.updated_by = request.user
        lesson.save(update_fields=['status', 'updated_by', 'updated_at'])
        return Response(LessonSerializer(lesson).data, status=status.HTTP_200_OK)
