from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.scoping import get_teaching_class_ids, is_somente_professor
from core.tenant import get_operational_organization
from core.viewmixins import OrganizationScopedViewMixin
from classrooms.models import ClassGroup, ClassTeacher
from lessons.models import Lesson, LessonSchedule
from lessons.services import can_edit_attendance_sheet

from .models import AttendanceRecord, AttendanceSheet
from .services import save_attendance_registration, sync_offering_from_attendance_sheet
from .serializers import (
    AttendanceBulkUpsertSerializer,
    AttendanceRegistrationSerializer,
    AttendanceSheetSerializer,
    validate_professor_for_class,
)


class AttendanceSheetViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = AttendanceSheetSerializer
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = AttendanceSheet.objects.filter(
            lesson__organization=org,
            class_group__organization=org,
        ).select_related(
            'lesson',
            'class_group',
            'professor',
        ).prefetch_related('records__student')
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

    @transaction.atomic
    def perform_create(self, serializer):
        lesson = serializer.validated_data['lesson']
        class_group = serializer.validated_data['class_group']
        if not serializer.validated_data.get('professor'):
            from lessons.models import LessonSchedule

            schedule = LessonSchedule.objects.filter(lesson=lesson, class_group=class_group).first()
            if schedule and schedule.professor_id:
                validate_professor_for_class(
                    schedule.professor_id,
                    class_group,
                    lesson=lesson,
                )
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

    @transaction.atomic
    def perform_update(self, serializer):
        sheet = self.get_object()
        if not can_edit_attendance_sheet(self.request.user, sheet):
            raise PermissionDenied('Você não pode editar este registro da EBD.')
        registration_fields = {
            'lesson',
            'class_group',
            'visitantes',
            'biblias',
            'revistas',
            'oferta_valor',
        }
        reopens_registration = bool(
            registration_fields.intersection(serializer.validated_data)
        )
        sheet = serializer.save(updated_by=self.request.user)
        if (
            reopens_registration
            and sheet.finalized_at is not None
            and sheet.lesson.status != 'FINALIZADA'
        ):
            sheet.finalized_at = None
            sheet.save(update_fields=['finalized_at', 'updated_at'])
        sheet = AttendanceSheet.objects.select_related(
            'lesson', 'class_group__organization'
        ).get(pk=sheet.pk)
        sync_offering_from_attendance_sheet(sheet)

    @action(detail=True, methods=['POST'], url_path='records')
    @transaction.atomic
    def records(self, request, pk=None):
        sheet = self.get_object()

        if not can_edit_attendance_sheet(request.user, sheet):
            raise PermissionDenied('Você não pode editar este registro da EBD.')

        serializer = AttendanceBulkUpsertSerializer(
            data=request.data,
            context={'class_group': sheet.class_group},
        )
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data['records']:
            AttendanceRecord.objects.update_or_create(
                attendance_sheet=sheet,
                student_id=item['student'],
                defaults={'presente': bool(item.get('presente', False)), 'updated_by': request.user},
            )

        if sheet.finalized_at is not None and sheet.lesson.status != 'FINALIZADA':
            sheet.finalized_at = None
            sheet.updated_by = request.user
            sheet.save(update_fields=['finalized_at', 'updated_by', 'updated_at'])

        sheet = (
            AttendanceSheet.objects.select_related(
                'lesson',
                'class_group__organization',
                'professor',
            )
            .prefetch_related('records__student')
            .get(pk=sheet.pk)
        )
        sync_offering_from_attendance_sheet(sheet)
        return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)


class LessonClassAttendanceView(APIView):
    def get_permissions(self):
        permissions = [IsAuthenticated()]
        if self.request.method == 'GET':
            permissions.append(module_permission('frequencia', 'visualizar')())
        return permissions

    def _get_context(self, request, lesson_id, class_id, *, for_write=False):
        organization = get_operational_organization(request)
        lessons = Lesson.objects.filter(organization=organization)
        if for_write:
            lessons = lessons.filter(is_active=True)
        lesson = get_object_or_404(
            lessons,
            pk=lesson_id,
        )
        classes = ClassGroup.objects.filter(organization=organization)
        if for_write:
            classes = classes.filter(ativa=True, is_active=True)
        class_group = get_object_or_404(
            classes,
            pk=class_id,
        )

        if is_somente_professor(request.user, organization):
            if for_write:
                teaches_class = (
                    class_group.id
                    in get_teaching_class_ids(request.user, organization)
                )
            else:
                teaches_class = ClassTeacher.objects.filter(
                    user=request.user,
                    class_group=class_group,
                ).exists()
            teaches_class = teaches_class or LessonSchedule.objects.filter(
                organization=organization,
                lesson=lesson,
                class_group=class_group,
                professor=request.user,
            ).exists()
            if not teaches_class:
                raise PermissionDenied(
                    'Você só pode acessar a chamada das turmas em que leciona.'
                )

        return organization, lesson, class_group

    def _check_write_permission(self, request, lesson, class_group):
        sheet_exists = AttendanceSheet.objects.filter(
            lesson=lesson,
            class_group=class_group,
        ).exists()
        permission_action = 'editar' if sheet_exists else 'criar'
        permission = module_permission('frequencia', permission_action)()
        if not permission.has_permission(request, self):
            operation = 'editar' if sheet_exists else 'iniciar'
            raise PermissionDenied(
                f'Você não tem permissão para {operation} esta chamada.'
            )

    def get(self, request, lesson_id, class_id):
        _, lesson, class_group = self._get_context(
            request,
            lesson_id,
            class_id,
        )
        sheet = (
            AttendanceSheet.objects.filter(
                lesson=lesson,
                class_group=class_group,
            )
            .select_related('lesson', 'class_group', 'professor')
            .prefetch_related('records__student')
            .first()
        )
        if not sheet:
            return Response(
                {'detail': 'Chamada não iniciada.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)

    def put(self, request, lesson_id, class_id):
        _, lesson, class_group = self._get_context(
            request,
            lesson_id,
            class_id,
            for_write=True,
        )
        self._check_write_permission(request, lesson, class_group)
        preview = AttendanceSheet(lesson=lesson, class_group=class_group)
        if not can_edit_attendance_sheet(request.user, preview):
            raise PermissionDenied(
                'Você só pode registrar a EBD nas turmas em que leciona.'
            )

        serializer = AttendanceRegistrationSerializer(
            data=request.data,
            context={
                'request': request,
                'lesson': lesson,
                'class_group': class_group,
            },
        )
        serializer.is_valid(raise_exception=True)
        sheet = save_attendance_registration(
            lesson=lesson,
            class_group=class_group,
            data=serializer.validated_data,
            user=request.user,
        )
        return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)
