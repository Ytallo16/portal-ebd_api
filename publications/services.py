from django.core.exceptions import ValidationError

from classrooms.models import ClassGroup, ClassTeacher
from students.models import Student

from .models import PublicationControl


def sync_publication_controls(organization, trimester, created_by=None, class_group_id=None):
    if trimester.organization_id != organization.id:
        raise ValidationError({'trimester_id': 'Trimestre não pertence à igreja selecionada.'})

    created_count = 0
    turmas = ClassGroup.objects.filter(organization=organization, is_active=True, ativa=True)
    if class_group_id:
        turmas = turmas.filter(id=class_group_id)

    for turma in turmas:
        students = Student.objects.filter(
            organization=organization,
            class_group=turma,
            is_active=True,
            ativo=True,
        )
        for student in students:
            _, created = PublicationControl.objects.get_or_create(
                organization=organization,
                class_group=turma,
                student=student,
                trimester=trimester,
                defaults={
                    'person_type': 'aluno',
                    'person_name': student.nome,
                    'professor': None,
                    'recebeu': False,
                    'pagou': False,
                    'created_by': created_by,
                },
            )
            if created:
                created_count += 1

        for teacher_rel in ClassTeacher.objects.filter(class_group=turma).select_related('user'):
            _, created = PublicationControl.objects.get_or_create(
                organization=organization,
                class_group=turma,
                professor=teacher_rel.user,
                trimester=trimester,
                defaults={
                    'person_type': 'professor',
                    'person_name': teacher_rel.user.nome,
                    'student': None,
                    'recebeu': False,
                    'pagou': False,
                    'created_by': created_by,
                },
            )
            if created:
                created_count += 1

    return created_count
