import django.db.models.deletion
from django.db import migrations, models


def assign_trimester_to_controls(apps, schema_editor):
    PublicationControl = apps.get_model('publications', 'PublicationControl')
    Trimester = apps.get_model('lessons', 'Trimester')

    for control in PublicationControl.objects.filter(trimester__isnull=True).iterator():
        trimester = (
            Trimester.objects.filter(
                organization_id=control.organization_id,
                status='EM_ANDAMENTO',
                is_active=True,
            )
            .order_by('-ano', '-numero')
            .first()
        )
        if not trimester:
            trimester = (
                Trimester.objects.filter(organization_id=control.organization_id, is_active=True)
                .order_by('-ano', '-numero')
                .first()
            )
        if trimester:
            control.trimester_id = trimester.id
            control.save(update_fields=['trimester_id'])
        else:
            control.delete()


class Migration(migrations.Migration):

    dependencies = [
        ('lessons', '0002_trimester'),
        ('publications', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicationcontrol',
            name='trimester',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='publication_controls',
                to='lessons.trimester',
            ),
        ),
        migrations.RunPython(assign_trimester_to_controls, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='publicationcontrol',
            name='trimester',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='publication_controls',
                to='lessons.trimester',
            ),
        ),
        migrations.AddConstraint(
            model_name='publicationcontrol',
            constraint=models.UniqueConstraint(
                condition=models.Q(('student__isnull', False)),
                fields=('organization', 'class_group', 'student', 'trimester'),
                name='uniq_pubcontrol_student_trimester',
            ),
        ),
        migrations.AddConstraint(
            model_name='publicationcontrol',
            constraint=models.UniqueConstraint(
                condition=models.Q(('professor__isnull', False)),
                fields=('organization', 'class_group', 'professor', 'trimester'),
                name='uniq_pubcontrol_professor_trimester',
            ),
        ),
    ]
