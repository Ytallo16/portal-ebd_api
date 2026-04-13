from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from attendance.models import AttendanceSheet
from core.permissions import module_permission
from core.tenant import get_user_organization

from .models import Lesson, Trimester
from .serializers import LessonSerializer, TrimesterSerializer
from .services import can_edit_lesson


class TrimesterViewSet(viewsets.ModelViewSet):
    serializer_class = TrimesterSerializer
    search_fields = ['titulo']

    def get_queryset(self):
        org = get_user_organization(self.request)
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
        serializer.save(organization=get_user_organization(self.request), created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

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


class LessonViewSet(viewsets.ModelViewSet):
    serializer_class = LessonSerializer
    search_fields = ['tema', 'revista']

    def get_queryset(self):
        org = get_user_organization(self.request)
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

        return queryset

    def perform_create(self, serializer):
        serializer.save(organization=get_user_organization(self.request), created_by=self.request.user)

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

        has_sheet = AttendanceSheet.objects.filter(lesson=lesson).exists()
        if not has_sheet:
            raise ValidationError('Não é possível finalizar sem ao menos uma chamada por turma.')

        lesson.status = 'FINALIZADA'
        lesson.updated_by = request.user
        lesson.save(update_fields=['status', 'updated_by', 'updated_at'])
        return Response(LessonSerializer(lesson).data, status=status.HTTP_200_OK)
