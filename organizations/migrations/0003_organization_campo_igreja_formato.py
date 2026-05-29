from django.db import migrations, models


def migrate_organization_types(apps, schema_editor):
    Organization = apps.get_model('organizations', 'Organization')
    for org in Organization.objects.all():
        tipo = org.tipo
        if tipo == 'SEDE':
            org.tipo = 'CAMPO'
            org.formato = 'CAMPO'
        elif tipo in ('FILIAL', 'CONGREGACAO'):
            org.tipo = 'IGREJA'
            if org.parent_id:
                org.formato = ''
            else:
                org.formato = 'IGREJA_INDIVIDUAL'
        org.save(update_fields=['tipo', 'formato'])


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0002_organization_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='formato',
            field=models.CharField(blank=True, choices=[('CAMPO', 'Contrato com múltiplas igrejas'), ('IGREJA_INDIVIDUAL', 'Contrato de uma igreja só')], default='', max_length=20),
        ),
        migrations.RunPython(migrate_organization_types, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='organization',
            name='tipo',
            field=models.CharField(choices=[('CAMPO', 'Campo'), ('IGREJA', 'Igreja')], max_length=20),
        ),
        migrations.AddIndex(
            model_name='organization',
            index=models.Index(fields=['formato'], name='organizatio_formato_idx'),
        ),
    ]
