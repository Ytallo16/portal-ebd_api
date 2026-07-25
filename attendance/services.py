from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from finance.models import Offering

from .models import AttendanceRecord, AttendanceSheet


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
    sheet.professor_presente = data.get('professor_presente', False)
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
        'professor_presente',
        'visitantes',
        'biblias',
        'revistas',
        'oferta_valor',
        'finalized_at',
        'updated_by',
        'updated_at',
    ]
    if created and sheet.created_by_id is None:
        sheet.created_by = user
        update_fields.append('created_by')
    sheet.save(update_fields=update_fields)

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
