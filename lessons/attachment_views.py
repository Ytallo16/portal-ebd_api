from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin

from .attachment_serializers import LessonAttachmentSerializer
from .models import LessonAttachment
from .services import can_delete_lesson_attachment, can_upload_lesson_attachment


class LessonAttachmentViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = LessonAttachmentSerializer
    parser_classes = [MultiPartParser, FormParser]
    use_operational_organization = True
    http_method_names = ['get', 'post', 'delete', 'head', 'options']

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = (
            LessonAttachment.objects.filter(organization=org, is_active=True)
            .select_related('lesson', 'created_by')
            .order_by('-created_at')
        )

        lesson_id = self.request.query_params.get('lesson_id')
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)

        return queryset

    def perform_create(self, serializer):
        org = self.get_active_organization()
        lesson = serializer.validated_data['lesson']

        if lesson.organization_id != org.id:
            raise ValidationError({'lesson': 'A lição não pertence à organização ativa.'})

        if not can_upload_lesson_attachment(self.request.user, lesson):
            raise PermissionDenied(
                'Apenas secretários, administradores ou o professor escalado podem anexar arquivos.'
            )

        arquivo = serializer.validated_data['arquivo']
        serializer.save(
            organization=org,
            created_by=self.request.user,
            nome_original=arquivo.name[:255],
            tamanho=arquivo.size,
            content_type=getattr(arquivo, 'content_type', '')[:120],
        )

    def destroy(self, request, *args, **kwargs):
        anexo = self.get_object()

        if not can_delete_lesson_attachment(request.user, anexo):
            raise PermissionDenied('Você não pode excluir este anexo.')

        anexo.is_active = False
        anexo.deleted_at = timezone.now()
        anexo.updated_by = request.user
        anexo.save(update_fields=['is_active', 'deleted_at', 'updated_by', 'updated_at'])

        return Response(status=status.HTTP_204_NO_CONTENT)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('licoes', 'visualizar')]
        else:
            perms = [IsAuthenticated, module_permission('licoes', 'editar')]
        return [perm() for perm in perms]
