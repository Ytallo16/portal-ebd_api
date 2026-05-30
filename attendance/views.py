from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin
from lessons.models import Lesson
from lessons.services import can_edit_attendance_sheet

from .models import AttendanceRecord, AttendanceSheet
from .services import sync_offering_from_attendance_sheet
from .serializers import (
    AttendanceBulkUpsertSerializer,
    AttendanceRecordSerializer,
    AttendanceSheetSerializer,
)


class AttendanceSheetViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = AttendanceSheetSerializer
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = AttendanceSheet.objects.filter(
            lesson__organization=org
        ).select_related('lesson', 'class_group', 'professor')
        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(class_group_id__in=class_ids)
        return queryset

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('frequencia', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('frequencia', 'criar')]
        elif self.action in ['partial_update', 'update', 'records']:
            perms = [IsAuthenticated, module_permission('frequencia', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('frequencia', 'excluir')]
        return [perm() for perm in perms]

    def perform_create(self, serializer):
        lesson = serializer.validated_data['lesson']
        class_group = serializer.validated_data['class_group']
        if not serializer.validated_data.get('professor'):
            from lessons.models import LessonSchedule

            schedule = LessonSchedule.objects.filter(lesson=lesson, class_group=class_group).first()
            if schedule and schedule.professor_id:
                serializer.validated_data['professor'] = schedule.professor
        preview = AttendanceSheet(lesson=lesson, class_group=class_group)
        if not can_edit_attendance_sheet(self.request.user, preview):
            raise PermissionDenied(
                'Você só pode registrar a EBD nas turmas em que leciona.'
            )
        sheet = serializer.save(created_by=self.request.user)
        sheet = AttendanceSheet.objects.select_related(
            'lesson', 'class_group__organization'
        ).get(pk=sheet.pk)
        sync_offering_from_attendance_sheet(sheet)

    def perform_update(self, serializer):
        sheet = self.get_object()
        if not can_edit_attendance_sheet(self.request.user, sheet):
            raise PermissionDenied('Você não pode editar este registro da EBD.')
        sheet = serializer.save(updated_by=self.request.user)
        if sheet.finalized_at is not None:
            sheet.finalized_at = None
            sheet.save(update_fields=['finalized_at', 'updated_at'])
        sheet = AttendanceSheet.objects.select_related(
            'lesson', 'class_group__organization'
        ).get(pk=sheet.pk)
        sync_offering_from_attendance_sheet(sheet)

    @action(detail=True, methods=['POST'], url_path='records')
    def records(self, request, pk=None):
        sheet = self.get_object()

        if not can_edit_attendance_sheet(request.user, sheet):
            raise PermissionDenied('Você não pode editar este registro da EBD.')

        serializer = AttendanceBulkUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data['records']:
            AttendanceRecord.objects.update_or_create(
                attendance_sheet=sheet,
                student_id=item['student'],
                defaults={'presente': bool(item.get('presente', False)), 'updated_by': request.user},
            )

        if sheet.finalized_at is not None:
            sheet.finalized_at = None
            sheet.updated_by = request.user
            sheet.save(update_fields=['finalized_at', 'updated_by', 'updated_at'])

        return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('frequencia', 'visualizar')])
def lesson_class_attendance(request, lesson_id, class_id):
    from core.tenant import get_operational_organization

    org = get_operational_organization(request)
    sheet = AttendanceSheet.objects.filter(
        lesson_id=lesson_id,
        class_group_id=class_id,
        lesson__organization=org,
    ).first()

    if not sheet:
        return Response({'detail': 'Chamada não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)
