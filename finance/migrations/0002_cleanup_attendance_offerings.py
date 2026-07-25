from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone


def repair_attendance_offerings(apps, schema_editor):
    AttendanceSheet = apps.get_model('attendance', 'AttendanceSheet')
    Offering = apps.get_model('finance', 'Offering')
    now = timezone.now()

    sheets = AttendanceSheet.objects.select_related('lesson', 'class_group').all()
    for sheet in sheets.iterator():
        key = (
            sheet.class_group.organization_id,
            sheet.lesson_id,
            sheet.class_group_id,
        )
        offerings = Offering.objects.filter(
            organization_id=key[0],
            lesson_id=key[1],
            class_group_id=key[2],
        ).order_by('-is_active', 'id')

        if sheet.finalized_at is None:
            offerings.filter(is_active=True).update(
                is_active=False,
                deleted_at=now,
            )
            continue

        canonical = offerings.first()
        if canonical is None:
            Offering.objects.create(
                organization_id=key[0],
                lesson_id=key[1],
                class_group_id=key[2],
                data=sheet.lesson.data,
                valor=sheet.oferta_valor,
                is_active=True,
            )
            continue

        canonical.data = sheet.lesson.data
        canonical.valor = sheet.oferta_valor
        canonical.is_active = True
        canonical.deleted_at = None
        canonical.save(
            update_fields=['data', 'valor', 'is_active', 'deleted_at', 'updated_at']
        )
        offerings.exclude(pk=canonical.pk).filter(is_active=True).update(
            is_active=False,
            deleted_at=now,
        )

    # Também saneia duplicatas antigas que não vieram de uma ficha. Assim a
    # restrição adicionada abaixo pode ser aplicada com segurança.
    duplicate_keys = (
        Offering.objects.filter(
            is_active=True,
            lesson_id__isnull=False,
            class_group_id__isnull=False,
        )
        .values('organization_id', 'lesson_id', 'class_group_id')
        .annotate(total=models.Count('id'))
        .filter(total__gt=1)
    )
    for key in duplicate_keys.iterator():
        offerings = Offering.objects.filter(
            organization_id=key['organization_id'],
            lesson_id=key['lesson_id'],
            class_group_id=key['class_group_id'],
            is_active=True,
        ).order_by('id')
        canonical = offerings.first()
        offerings.exclude(pk=canonical.pk).update(
            is_active=False,
            deleted_at=now,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0002_attendancesheet_professor_presente'),
        ('finance', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            repair_attendance_offerings,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name='offering',
            constraint=models.UniqueConstraint(
                fields=('organization', 'lesson', 'class_group'),
                condition=Q(
                    is_active=True,
                    lesson__isnull=False,
                    class_group__isnull=False,
                ),
                name='uniq_active_offering_lesson_class',
            ),
        ),
    ]
