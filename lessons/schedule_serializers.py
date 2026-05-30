from rest_framework import serializers

from access_control.models import UserRole
from classrooms.models import ClassGroup

from .models import Lesson, LessonSchedule


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

        if professor and class_group:
            is_professor = UserRole.objects.filter(
                user=professor,
                ativo=True,
                role__nome='PROFESSOR',
                organization=class_group.organization,
            ).exists()
            if not is_professor:
                raise serializers.ValidationError({'professor': 'O usuário selecionado não é professor desta igreja.'})

        return attrs


class LessonScheduleAssignmentSerializer(serializers.Serializer):
    class_group = serializers.PrimaryKeyRelatedField(queryset=ClassGroup.objects.all())
    professor = serializers.IntegerField(required=False, allow_null=True)


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

        for item in attrs['assignments']:
            class_group = item['class_group']
            if class_group.organization_id != lesson.organization_id:
                raise serializers.ValidationError(
                    {'assignments': f'Turma {class_group.nome} não pertence a esta igreja.'}
                )

        return attrs

    def save(self):
        request = self.context['request']
        lesson = self.validated_data['lesson']
        assignments = self.validated_data['assignments']
        payloads = []

        for item in assignments:
            professor_id = item.get('professor')
            schedule, _ = LessonSchedule.objects.update_or_create(
                lesson=lesson,
                class_group=item['class_group'],
                defaults={
                    'organization': lesson.organization,
                    'professor_id': professor_id,
                    'updated_by': request.user,
                },
            )
            if schedule.created_by_id is None:
                schedule.created_by = request.user
                schedule.save(update_fields=['created_by'])
            payloads.append(schedule)

        return payloads
