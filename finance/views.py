from django.db.models import Avg, Sum
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from rest_framework.exceptions import PermissionDenied

from core.permissions import module_permission
from core.viewmixins import OrganizationScopedViewMixin
from lessons.services import can_edit_class_lesson_registration

from .models import Offering
from .serializers import OfferingSerializer


class OfferingViewSet(OrganizationScopedViewMixin, viewsets.ModelViewSet):
    serializer_class = OfferingSerializer
    search_fields = ['class_group__nome', 'lesson__tema']
    use_operational_organization = True

    def get_queryset(self):
        org = self.get_active_organization()
        queryset = Offering.objects.filter(organization=org, is_active=True).select_related('lesson', 'class_group')

        class_ids = self.get_teaching_class_filter(org)
        if class_ids is not None:
            queryset = queryset.filter(class_group_id__in=class_ids)

        class_id = self.request.query_params.get('class_id')
        lesson_id = self.request.query_params.get('lesson_id')
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')

        if class_id:
            queryset = queryset.filter(class_group_id=class_id)
        if lesson_id:
            queryset = queryset.filter(lesson_id=lesson_id)
        if date_from:
            queryset = queryset.filter(data__gte=date_from)
        if date_to:
            queryset = queryset.filter(data__lte=date_to)

        return queryset.order_by('-data')

    def _assert_can_manage_offering(self, offering):
        lesson = offering.lesson
        class_group = offering.class_group
        if lesson and class_group and not can_edit_class_lesson_registration(
            self.request.user, class_group, lesson
        ):
            raise PermissionDenied(
                'Professores só podem lançar ofertas nas turmas em que lecionam.'
            )

    def perform_create(self, serializer):
        class_group = serializer.validated_data.get('class_group')
        lesson = serializer.validated_data.get('lesson')
        if class_group and lesson and not can_edit_class_lesson_registration(
            self.request.user, class_group, lesson
        ):
            raise PermissionDenied(
                'Professores só podem lançar ofertas nas turmas em que lecionam.'
            )
        offering = serializer.save(
            organization=self.get_active_organization(),
            created_by=self.request.user,
        )

    def perform_update(self, serializer):
        offering = self.get_object()
        self._assert_can_manage_offering(offering)
        offering = serializer.save(updated_by=self.request.user)
        self._assert_can_manage_offering(offering)

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            perms = [IsAuthenticated, module_permission('financeiro', 'visualizar')]
        elif self.action == 'create':
            perms = [IsAuthenticated, module_permission('financeiro', 'criar')]
        elif self.action in ['partial_update', 'update']:
            perms = [IsAuthenticated, module_permission('financeiro', 'editar')]
        else:
            perms = [IsAuthenticated, module_permission('financeiro', 'excluir')]
        return [perm() for perm in perms]


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('financeiro', 'visualizar')])
def offering_summary(request):
    from core.tenant import get_operational_organization

    org = get_operational_organization(request)
    data = Offering.objects.filter(organization=org, is_active=True).aggregate(total=Sum('valor'), media=Avg('valor'))
    return Response({'total': data['total'] or 0, 'media': data['media'] or 0})
