from decimal import Decimal

from rest_framework import serializers

from access_control.constants import ROLE_PROFESSOR
from access_control.models import UserRole
from accounts.models import User
from classrooms.models import ClassTeacher
from core.tenant import get_operational_organization
from students.models import Student

from .models import AttendanceRecord, AttendanceSheet


class AttendanceRecordSerializer(serializers.ModelSerializer):
    aluno_nome = serializers.CharField(source='student.nome', read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ['id', 'student', 'aluno_nome', 'presente']


class AttendanceSheetSerializer(serializers.ModelSerializer):
    records = AttendanceRecordSerializer(many=True, read_only=True)
    status = serializers.CharField(read_only=True)

    class Meta:
        model = AttendanceSheet
        fields = [
            'id',
            'lesson',
            'class_group',
            'professor',
            'professor_presente',
            'visitantes',
            'biblias',
            'revistas',
            'oferta_valor',
            'finalized_at',
            'status',
            'records',
        ]
        read_only_fields = ['finalized_at']

    def validate(self, attrs):
        instance = self.instance
        lesson = attrs.get('lesson') or getattr(instance, 'lesson', None)
        class_group = attrs.get('class_group') or getattr(instance, 'class_group', None)
        professor = attrs.get('professor') if 'professor' in attrs else getattr(instance, 'professor', None)
        request = self.context.get('request')
        organization = get_operational_organization(request) if request else None

        if lesson and class_group and lesson.organization_id != class_group.organization_id:
            raise serializers.ValidationError(
                {'class_group': 'A turma não pertence à mesma igreja da lição.'}
            )
        if lesson and not lesson.is_active:
            raise serializers.ValidationError({'lesson': 'A lição está inativa.'})
        if not instance and lesson and lesson.status == 'FINALIZADA':
            raise serializers.ValidationError(
                {'lesson': 'Não é possível iniciar uma chamada em uma lição encerrada.'}
            )
        if class_group and (not class_group.is_active or not class_group.ativa):
            raise serializers.ValidationError({'class_group': 'A turma está inativa.'})
        if organization and lesson and lesson.organization_id != organization.id:
            raise serializers.ValidationError(
                {'lesson': 'A lição não pertence à igreja selecionada.'}
            )
        if organization and class_group and class_group.organization_id != organization.id:
            raise serializers.ValidationError(
                {'class_group': 'A turma não pertence à igreja selecionada.'}
            )
        if instance:
            if lesson and lesson.pk != instance.lesson_id:
                raise serializers.ValidationError(
                    {'lesson': 'Não é possível trocar a lição de uma chamada existente.'}
                )
            if class_group and class_group.pk != instance.class_group_id:
                raise serializers.ValidationError(
                    {'class_group': 'Não é possível trocar a turma de uma chamada existente.'}
                )
        if professor and class_group and (not instance or 'professor' in attrs):
            validate_professor_for_class(
                professor.id,
                class_group,
                lesson=lesson,
            )

        return attrs


class AttendanceRecordInputSerializer(serializers.Serializer):
    student = serializers.IntegerField(min_value=1)
    presente = serializers.BooleanField()


class AttendanceBulkUpsertSerializer(serializers.Serializer):
    records = AttendanceRecordInputSerializer(many=True, allow_empty=True)

    def validate_records(self, records):
        class_group = self.context.get('class_group')
        if class_group:
            _validate_record_students(records, class_group)
        return records


class AttendanceRegistrationSerializer(serializers.Serializer):
    STATUS_CHOICES = (
        AttendanceSheet.STATUS_RASCUNHO,
        AttendanceSheet.STATUS_CONCLUIDA,
    )

    professor = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    professor_presente = serializers.BooleanField(required=False, default=False)
    visitantes = serializers.IntegerField(required=False, default=0, min_value=0)
    biblias = serializers.IntegerField(required=False, default=0, min_value=0)
    revistas = serializers.IntegerField(required=False, default=0, min_value=0)
    oferta_valor = serializers.DecimalField(
        required=False,
        default=Decimal('0'),
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
    )
    status = serializers.ChoiceField(choices=STATUS_CHOICES)
    records = AttendanceRecordInputSerializer(many=True, allow_empty=True)

    def validate(self, attrs):
        class_group = self.context['class_group']
        lesson = self.context['lesson']
        professor_id = attrs.get('professor')
        if professor_id:
            validate_professor_for_class(
                professor_id,
                class_group,
                lesson=lesson,
            )

        records = attrs['records']
        submitted_ids = _validate_record_students(records, class_group)
        if attrs['status'] == AttendanceSheet.STATUS_CONCLUIDA:
            expected_ids = set(
                Student.objects.filter(
                    organization=class_group.organization,
                    class_group=class_group,
                    ativo=True,
                    is_active=True,
                ).values_list('id', flat=True)
            )
            missing_ids = expected_ids - submitted_ids
            if missing_ids:
                missing_names = list(
                    Student.objects.filter(id__in=missing_ids)
                    .order_by('nome')
                    .values_list('nome', flat=True)
                )
                raise serializers.ValidationError(
                    {
                        'records': (
                            'Para concluir, informe a presença de todos os alunos ativos da turma. '
                            f'Faltando: {", ".join(missing_names)}.'
                        )
                    }
                )

        return attrs


def validate_professor_for_class(professor_id, class_group, *, lesson=None):
    professor = User.objects.filter(pk=professor_id, is_active=True).first()
    if not professor:
        raise serializers.ValidationError({'professor': 'Professor não encontrado ou inativo.'})

    has_active_professor_role = UserRole.objects.filter(
        user=professor,
        organization_id=class_group.organization_id,
        role__nome=ROLE_PROFESSOR,
        role__ativo=True,
        ativo=True,
    ).exists()
    if not has_active_professor_role:
        raise serializers.ValidationError(
            {
                'professor': (
                    'O usuário precisa ter o perfil PROFESSOR ativo na igreja desta chamada.'
                )
            }
        )

    teaches_class = ClassTeacher.objects.filter(
        user=professor,
        class_group=class_group,
    ).exists()
    scheduled_for_lesson = False
    if lesson is not None:
        from lessons.models import LessonSchedule

        scheduled_for_lesson = LessonSchedule.objects.filter(
            organization_id=class_group.organization_id,
            lesson=lesson,
            class_group=class_group,
            professor=professor,
        ).exists()
    if not teaches_class and not scheduled_for_lesson:
        raise serializers.ValidationError(
            {
                'professor': (
                    'O professor não está vinculado à turma nem escalado '
                    'para esta lição.'
                )
            }
        )


def _validate_record_students(records, class_group):
    student_ids = [item['student'] for item in records]
    if len(student_ids) != len(set(student_ids)):
        raise serializers.ValidationError(
            {'records': 'Cada aluno pode aparecer apenas uma vez na chamada.'}
        )

    valid_ids = set(
        Student.objects.filter(
            id__in=student_ids,
            organization=class_group.organization,
            class_group=class_group,
            ativo=True,
            is_active=True,
        ).values_list('id', flat=True)
    )
    invalid_ids = set(student_ids) - valid_ids
    if invalid_ids:
        raise serializers.ValidationError(
            {
                'records': (
                    'Há aluno inexistente, inativo ou que não pertence à turma e à igreja '
                    f'desta chamada: {", ".join(map(str, sorted(invalid_ids)))}.'
                )
            }
        )
    return valid_ids
