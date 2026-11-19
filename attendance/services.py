from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from finance.models import Offering

from .models import AttendanceRecord, AttendanceSheet, AttendanceTeacher


@transaction.atomic
def save_teacher_presences(*, sheet, teachers, user):
    """Grava a presença de cada professor da turma na lição.

    Upsert por professor: quem não vem no payload fica como está. Isso é o que
    permite dois professores da mesma turma ficarem presentes ao mesmo tempo —
    antes a ficha tinha um único `professor_presente` e cada gravação apagava
    a anterior.
    """
    for item in teachers:
        AttendanceTeacher.objects.update_or_create(
            attendance_sheet=sheet,
            user_id=item['user'],
            defaults={
                'presente': bool(item.get('presente', False)),
                'updated_by': user,
            },
        )

    sync_legacy_professor_presence(sheet)
    return sheet


def sync_legacy_professor_presence(sheet):
    """Espelha em `professor_presente` a presença do professor que ministrou.

    O campo antigo continua existindo para não quebrar leitores legados; a
    verdade passa a ser a tabela `AttendanceTeacher`.
    """
    if not sheet.professor_id:
        return

    presence = AttendanceTeacher.objects.filter(
        attendance_sheet=sheet,
        user_id=sheet.professor_id,
    ).values_list('presente', flat=True).first()
    if presence is None or presence == sheet.professor_presente:
        return

    sheet.professor_presente = presence
    sheet.save(update_fields=['professor_presente', 'updated_at'])


def sync_offering_from_attendance_sheet(sheet):
    """Mantém o lançamento financeiro alinhado à oferta informada na ficha da turma."""
    if not sheet.lesson_id or not sheet.class_group_id:
        return

    organization = sheet.class_group.organization
    valor = sheet.oferta_valor if sheet.oferta_valor is not None else Decimal('0')

    existing = Offering.objects.filter(
        organization=organization,
        lesson_id=sheet.lesson_id,
        class_group_id=sheet.class_group_id,
    ).order_by('-is_active', 'id')

    if sheet.finalized_at is None:
        existing.filter(is_active=True).update(
            is_active=False,
            deleted_at=timezone.now(),
        )
        return None

    if existing.exists():
        offering = existing.first()
        offering.data = sheet.lesson.data
        offering.valor = valor
        offering.is_active = True
        offering.deleted_at = None
        offering.save(update_fields=['data', 'valor', 'is_active', 'deleted_at', 'updated_at'])
        existing.exclude(id=offering.id).filter(is_active=True).update(
            is_active=False,
            deleted_at=timezone.now(),
        )
        return offering

    return Offering.objects.create(
        organization=organization,
        lesson_id=sheet.lesson_id,
        class_group_id=sheet.class_group_id,
        data=sheet.lesson.data,
        valor=valor,
    )


@transaction.atomic
def save_attendance_registration(*, lesson, class_group, data, user):
    """Cria/atualiza ficha, presenças e totais como uma única operação."""
    if (
        lesson.status == 'FINALIZADA'
        and data['status'] == AttendanceSheet.STATUS_RASCUNHO
    ):
        raise ValidationError(
            {
                'status': (
                    'Uma lição encerrada não pode voltar a ter chamada em rascunho. '
                    'Salve a correção mantendo o status concluído.'
                )
            }
        )

    sheet, created = AttendanceSheet.objects.select_for_update().get_or_create(
        lesson=lesson,
        class_group=class_group,
        defaults={
            'created_by': user,
        },
    )

    sheet.professor_id = data.get('professor')
    # A chamada dos alunos só mexe na frequência do professor se ela vier no
    # payload. Omitir preserva o que foi marcado na tela de frequência dos
    # professores.
    informou_presenca_professor = 'professor_presente' in data
    if informou_presenca_professor:
        sheet.professor_presente = data['professor_presente']
    sheet.visitantes = data.get('visitantes', 0)
    sheet.biblias = data.get('biblias', 0)
    sheet.revistas = data.get('revistas', 0)
    sheet.oferta_valor = data.get('oferta_valor', Decimal('0'))
    sheet.finalized_at = (
        sheet.finalized_at or timezone.now()
        if data['status'] == AttendanceSheet.STATUS_CONCLUIDA
        else None
    )
    sheet.updated_by = user
    update_fields = [
        'professor',
        'visitantes',
        'biblias',
        'revistas',
        'oferta_valor',
        'finalized_at',
        'updated_by',
        'updated_at',
    ]
    if informou_presenca_professor:
        update_fields.append('professor_presente')
    if created and sheet.created_by_id is None:
        sheet.created_by = user
        update_fields.append('created_by')
    sheet.save(update_fields=update_fields)

    if informou_presenca_professor and sheet.professor_id:
        AttendanceTeacher.objects.update_or_create(
            attendance_sheet=sheet,
            user_id=sheet.professor_id,
            defaults={
                'presente': sheet.professor_presente,
                'updated_by': user,
            },
        )
    else:
        # Trocar o professor que ministrou não pode deixar o campo legado
        # apontando para a presença de outra pessoa.
        sync_legacy_professor_presence(sheet)

    submitted_student_ids = {item['student'] for item in data['records']}
    for item in data['records']:
        AttendanceRecord.objects.update_or_create(
            attendance_sheet=sheet,
            student_id=item['student'],
            defaults={
                'presente': item['presente'],
                'updated_by': user,
                **({'created_by': user} if created else {}),
            },
        )

    # PUT é substitutivo para o elenco ativo atual. Registros de alunos que já
    # foram inativados, excluídos logicamente ou transferidos de turma são
    # históricos e não devem desaparecer ao corrigir uma chamada antiga.
    sheet.records.filter(
        student__organization=class_group.organization,
        student__class_group=class_group,
        student__ativo=True,
        student__is_active=True,
    ).exclude(student_id__in=submitted_student_ids).delete()

    sync_offering_from_attendance_sheet(
        AttendanceSheet.objects.select_related(
            'lesson',
            'class_group__organization',
        ).get(pk=sheet.pk)
    )
    return AttendanceSheet.objects.prefetch_related('records__student').get(pk=sheet.pk)
