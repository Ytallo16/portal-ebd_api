from decimal import Decimal

from finance.models import Offering


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
        is_active=True,
    ).order_by('id')

    if existing.exists():
        offering = existing.first()
        offering.data = sheet.lesson.data
        offering.valor = valor
        offering.is_active = True
        offering.deleted_at = None
        offering.save(update_fields=['data', 'valor', 'is_active', 'deleted_at', 'updated_at'])
        existing.exclude(id=offering.id).update(is_active=False)
        return

    Offering.objects.create(
        organization=organization,
        lesson_id=sheet.lesson_id,
        class_group_id=sheet.class_group_id,
        data=sheet.lesson.data,
        valor=valor,
    )
