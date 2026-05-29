from django.db import migrations


def rename_legacy_roles(apps, schema_editor):
    Role = apps.get_model('access_control', 'Role')
    mapping = {
        'ADMINISTRADOR_CAMPO': 'SECRETARIO_CAMPO',
        'SECRETARIA': 'SECRETARIO_IGREJA',
    }
    for old_name, new_name in mapping.items():
        role = Role.objects.filter(nome=old_name).first()
        if not role:
            continue
        existing = Role.objects.filter(nome=new_name).first()
        if existing and existing.id != role.id:
            role.delete()
        else:
            role.nome = new_name
            role.save(update_fields=['nome'])

    Role.objects.filter(nome='TESOUREIRO').update(ativo=False)


class Migration(migrations.Migration):

    dependencies = [
        ('access_control', '0002_initial'),
    ]

    operations = [
        migrations.RunPython(rename_legacy_roles, migrations.RunPython.noop),
    ]
