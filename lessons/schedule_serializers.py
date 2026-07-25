from django.db import transaction
from rest_framework import serializers

from accounts.models import User
from access_control.models import UserRole
from classrooms.models import ClassGroup

from .models import Lesson, LessonSchedule


def _professor_has_role(professor, organization):
    return UserRole.objects.filter(
        user=professor,
        ativo=True,
        role__nome='PROFESSOR',
        organization=organization,
    ).exists()


def _schedule_conflict(professor, lesson, *, exclude_id=None, exclude_class_ids=()):
    queryset = LessonSchedule.objects.filter(
        professor=professor,
        lesson__data=lesson.data,
    )
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    if exclude_class_ids:
        queryset = queryset.exclude(
            lesson=lesson,
            class_group_id__in=exclude_class_ids,
        )
    return queryset.select_related('lesson', 'class_group').first()


def _conflict_message(conflict):
    return (
        f'{conflict.professor.nome} já está escalado para '
        f'{conflict.class_group.nome} em {conflict.lesson.data:%d/%m/%Y}.'
    )


class LessonScheduleSerializer(serializers.ModelSerializer):
    professor_nome = serializers.CharField(source='professor.nome', read_only=True)
    class_group_nome = serializers.CharField(source='class_group.nome', read_only=True)
    lesson_numero = serializers.IntegerField(source='lesson.numero', read_only=True)

    class Meta:
        model = LessonSchedule
        fields = [
            'id',
            'organization',
            'lesson',
            'class_group',
            'class_group_nome',
            'professor',
            'professor_nome',
            'lesson_numero',
        ]
        read_only_fields = ['organization']

    def validate(self, attrs):
        lesson = attrs.get('lesson') or getattr(self.instance, 'lesson', None)
        class_group = attrs.get('class_group') or getattr(self.instance, 'class_group', None)
        professor = attrs.get('professor') if 'professor' in attrs else getattr(self.instance, 'professor', None)

        if lesson and class_group and lesson.organization_id != class_group.organization_id:
            raise serializers.ValidationError({'class_group': 'Turma inválida para esta lição.'})

        if professor and class_group and lesson:
            if not _professor_has_role(professor, class_group.organization):
                raise serializers.ValidationError({'professor': 'O usuário selecionado não é professor desta igreja.'})
            conflict = _schedule_conflict(
                professor,
                lesson,
                exclude_id=getattr(self.instance, 'pk', None),
            )
            if conflict:
                raise serializers.ValidationError(
                    {'professor': _conflict_message(conflict)}
                )

        return attrs


class LessonScheduleAssignmentSerializer(serializers.Serializer):
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects.all())
    professor = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(is_active=True),
        required=False,
        allow_null=True,
    )


class LessonScheduleBulkSerializer(serializers.Serializer):
    lesson = serializers.PrimaryKeyRelatedField(queryset=Lesson.objects.filter(is_active=True))
    assignments = LessonScheduleAssignmentSerializer(many=True)

    def validate(self, attrs):
        request = self.context.get('request')
        org = None
        if request:
            from core.tenant import get_operational_organization

            org = get_operational_organization(request)

        lesson = attrs['lesson']
        if org and lesson.organization_id != org.id:
            raise serializers.ValidationError({'lesson': 'Lição inválida para esta igreja.'})

        assignments = attrs['assignments']
        assignment_class_ids = {item['class_group'].id for item in assignments}
        if len(assignment_class_ids) != len(assignments):
            raise serializers.ValidationError(
                {'assignments': 'A mesma turma foi informada mais de uma vez.'}
            )

        assigned_professor_ids = set()
        for item in assignments:
            class_group = item['class_group']
            if class_group.organization_id != lesson.organization_id:
                raise serializers.ValidationError(
                    {'assignments': f'Turma {class_group.nome} não pertence a esta igreja.'}
                )
            if not class_group.is_active or not class_group.ativa:
                raise serializers.ValidationError(
                    {'assignments': f'Turma {class_group.nome} está inativa.'}
                )

            professor = item.get('professor')
            if professor is None:
                continue
            if not _professor_has_role(professor, class_group.organization):
                raise serializers.ValidationError(
                    {'assignments': f'{professor.nome} não é professor desta igreja.'}
                )
            if professor.id in assigned_professor_ids:
                raise serializers.ValidationError(
                    {
                        'assignments': (
                            f'{professor.nome} não pode ser escalado em duas turmas '
                            'na mesma lição.'
                        )
                    }
                )
            assigned_professor_ids.add(professor.id)

            conflict = _schedule_conflict(
                professor,
                lesson,
                exclude_class_ids=assignment_class_ids,
            )
            if conflict:
                raise serializers.ValidationError(
                    {'assignments': _conflict_message(conflict)}
                )

        return attrs

    @transaction.atomic
    def save(self):
        request = self.context['request']
        lesson = self.validated_data['lesson']
        assignments = self.validated_data['assignments']
        payloads = []

        for item in assignments:
            professor = item.get('professor')
            schedule, _ = LessonSchedule.objects.update_or_create(
                lesson=lesson,
                class_group=item['class_group'],
                defaults={
                    'organization': lesson.organization,
                    'professor': professor,
                    'updated_by': request.user,
                },
            )
            if schedule.created_by_id is None:
                schedule.created_by = request.user
                schedule.save(update_fields=['created_by'])
            payloads.append(schedule)

        return payloads
