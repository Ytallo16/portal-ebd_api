from django.db import transaction
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin

from .import_service import (
    ImportBatchConflict,
    confirm_students_import,
    serialize_import_batch,
    serialize_import_batch_summary,
    undo_students_import,
    validate_students_csv,
)
from .models import Student, StudentHistory, StudentImportBatch
from .serializers import StudentHistorySerializer, StudentSerializer
from .services import record_student_history, student_changes, student_snapshot


class StudentPagination(PageNumberPagination):
    page_size = 24
    page_size_query_param = 'page_size'
    max_page_size = 100


class StudentViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = StudentSerializer
    pagination_class = StudentPagination
    search_fields = ['nome', 'class_group__nome']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = (
            Student.objects.filter(organization=org)
            .select_related('class_group', 'endereco')
            .prefetch_related('responsaveis')
            .order_by('nome')
        )
        if self.action == 'inactive':
            queryset = queryset.filter(is_active=False)
        elif self.action not in ('restore', 'history'):
            queryset = queryset.filter(is_active=True)
        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(class_group_id__in=class_ids)
        class_id = self.request.query_params.get('class_id')
        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        return queryset

    def perform_create(self, serializer):
        with transaction.atomic():
            student = serializer.save(
                organization=self.get_active_organization(),
                created_by=self.request.user,
            )
            record_student_history(
                student=student,
                action=StudentHistory.ACTION_CREATED,
                actor=self.request.user,
            )

    def perform_update(self, serializer):
        with transaction.atomic():
            before = student_snapshot(serializer.instance)
            student = serializer.save(updated_by=self.request.user)
            if student_changes(before, student_snapshot(student)):
                record_student_history(
                    student=student,
                    action=StudentHistory.ACTION_UPDATED,
                    actor=self.request.user,
                    before=before,
                )

    def perform_destroy(self, instance):
        with transaction.atomic():
            before = student_snapshot(instance)
            instance.is_active = False
            instance.ativo = False
            instance.deleted_at = timezone.now()
            instance.updated_by = self.request.user
            instance.save(
                update_fields=[
                    'is_active',
                    'ativo',
                    'deleted_at',
                    'updated_by',
                    'updated_at',
                ]
            )
            record_student_history(
                student=instance,
                action=StudentHistory.ACTION_DEACTIVATED,
                actor=self.request.user,
                before=before,
                metadata={'frequencias_preservadas': True},
            )

    def get_permissions(self):
        if self.action in ['list', 'retrieve', 'history']:
            perms = [IsAuthenticated, module_permission('alunos', 'visualizar')]
        elif self.action in ['create', 'import_bulk', 'confirm_import', 'import_history']:
            perms = [IsAuthenticated, module_permission('alunos', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('alunos', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('alunos', 'excluir')]
        return [perm() for perm in perms]

    def get_serializer_context(self):
        context = super().get_serializer_context()
        organization = self.get_active_organization()
        context['organization'] = organization
        context['allowed_class_ids'] = self.get_teaching_class_filter(organization)
        return context

    @action(
        detail=False,
        methods=['POST'],
        url_path='import',
        parser_classes=[MultiPartParser, FormParser],
    )
    def import_bulk(self, request):
        uploaded_file = request.FILES.get('arquivo')
        if not uploaded_file:
            return Response(
                {'detail': 'Envie um arquivo CSV no campo "arquivo".'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        organization = self.get_active_organization()
        allowed_class_ids = self.get_teaching_class_filter(organization)
        result = validate_students_csv(
            uploaded_file=uploaded_file,
            organization=organization,
            user=request.user,
            allowed_class_ids=allowed_class_ids,
        )
        return Response(result, status=status.HTTP_200_OK)

    @action(
        detail=False,
        methods=['POST'],
        url_path=r'import/(?P<batch_id>[0-9a-f-]+)/confirm',
    )
    def confirm_import(self, request, batch_id=None):
        organization = self.get_active_organization()
        batch = StudentImportBatch.objects.filter(
            public_id=batch_id,
            organization=organization,
        ).first()
        if not batch:
            return Response(
                {'detail': 'Lote de importação não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            result = confirm_students_import(
                batch=batch,
                organization=organization,
                user=request.user,
                allowed_class_ids=self.get_teaching_class_filter(organization),
            )
        except ImportBatchConflict as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result)

    @action(
        detail=False,
        methods=['POST'],
        url_path=r'import/(?P<batch_id>[0-9a-f-]+)/undo',
    )
    def undo_import(self, request, batch_id=None):
        organization = self.get_active_organization()
        batch = StudentImportBatch.objects.filter(
            public_id=batch_id,
            organization=organization,
        ).first()
        if not batch:
            return Response(
                {'detail': 'Lote de importação não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            result = undo_students_import(
                batch=batch,
                organization=organization,
                user=request.user,
            )
        except ImportBatchConflict as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(result)

    @action(detail=False, methods=['GET'], url_path='imports')
    def import_history(self, request):
        organization = self.get_active_organization()
        queryset = (
            StudentImportBatch.objects.filter(organization=organization)
            .select_related('created_by', 'confirmed_by', 'undone_by')
            .order_by('-created_at')
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                [serialize_import_batch_summary(batch) for batch in page]
            )
        return Response([serialize_import_batch_summary(batch) for batch in queryset])

    @action(
        detail=False,
        methods=['GET'],
        url_path=r'import/(?P<batch_id>[0-9a-f-]+)',
    )
    def import_detail(self, request, batch_id=None):
        organization = self.get_active_organization()
        batch = (
            StudentImportBatch.objects.filter(
                public_id=batch_id,
                organization=organization,
            )
            .prefetch_related('rows')
            .first()
        )
        if not batch:
            return Response(
                {'detail': 'Lote de importação não encontrado.'},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(serialize_import_batch(batch))

    @action(detail=False, methods=['GET'], url_path='inactive')
    def inactive(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                self.get_serializer(page, many=True).data
            )
        return Response(self.get_serializer(queryset, many=True).data)

    @action(detail=True, methods=['POST'], url_path='restore')
    def restore(self, request, pk=None):
        student = self.get_object()
        if student.is_active:
            return Response(
                {'detail': 'Este aluno já está ativo.'},
                status=status.HTTP_409_CONFLICT,
            )

        class_group_id = request.data.get('class_group', student.class_group_id)
        if not class_group_id:
            raise ValidationError(
                {'class_group': 'Selecione uma turma ativa para restaurar o aluno.'}
            )
        serializer = self.get_serializer(
            student,
            data={'class_group': class_group_id},
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            before = student_snapshot(student)
            student = serializer.save(updated_by=request.user)
            student.is_active = True
            student.ativo = True
            student.deleted_at = None
            student.updated_by = request.user
            student.save(
                update_fields=[
                    'is_active',
                    'ativo',
                    'deleted_at',
                    'updated_by',
                    'updated_at',
                ]
            )
            record_student_history(
                student=student,
                action=StudentHistory.ACTION_RESTORED,
                actor=request.user,
                before=before,
            )
        return Response(self.get_serializer(student).data)

    @action(detail=True, methods=['GET'], url_path='history')
    def history(self, request, pk=None):
        student = self.get_object()
        queryset = student.historico.select_related('actor').order_by('-created_at')
        page = self.paginate_queryset(queryset)
        if page is not None:
            return self.get_paginated_response(
                StudentHistorySerializer(page, many=True).data
            )
        return Response(StudentHistorySerializer(queryset, many=True).data)
