from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.tenant import get_user_organization
from lessons.models import Lesson
from lessons.services import can_edit_lesson

from .models import AttendanceRecord, AttendanceSheet
from .serializers import (
    AttendanceBulkUpsertSerializer,
    AttendanceRecordSerializer,
    AttendanceSheetSerializer,
)


class AttendanceSheetViewSet(viewsets.ModelViewSet):
    serializer_class = AttendanceSheetSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        org = get_user_organization(self.request)
        return AttendanceSheet.objects.filter(
            lesson__organization=org
        ).select_related('lesson', 'class_group', 'professor')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @action(detail=True, methods=['POST'], url_path='records')
    def records(self, request, pk=None):
        sheet = self.get_object()

        if not can_edit_lesson(request.user, sheet.lesson):
            raise PermissionDenied('Professor só pode editar presença no dia da lição.')

        serializer = AttendanceBulkUpsertSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        for item in serializer.validated_data['records']:
            AttendanceRecord.objects.update_or_create(
                attendance_sheet=sheet,
                student_id=item['student'],
                defaults={'presente': bool(item.get('presente', False)), 'updated_by': request.user},
            )

        if request.data.get('finalize_sheet'):
            sheet.finalized_at = timezone.now()
            sheet.updated_by = request.user
            sheet.save(update_fields=['finalized_at', 'updated_by', 'updated_at'])

        return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def lesson_class_attendance(request, lesson_id, class_id):
    org = get_user_organization(request)
    sheet = AttendanceSheet.objects.filter(
        lesson_id=lesson_id,
        class_group_id=class_id,
        lesson__organization=org,
    ).first()

    if not sheet:
        return Response({'detail': 'Chamada não encontrada.'}, status=status.HTTP_404_NOT_FOUND)

    return Response(AttendanceSheetSerializer(sheet).data, status=status.HTTP_200_OK)
