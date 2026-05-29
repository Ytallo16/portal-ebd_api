from django.db import migrations


def remove_professor_revistas_permission(apps, schema_editor):
    Role = apps.get_model('access_control', 'Role')
    RolePermission = apps.get_model('access_control', 'RolePermission')
    ModulePermission = apps.get_model('access_control', 'ModulePermission')

    try:
        role = Role.objects.get(nome='PROFESSOR')
        permission = ModulePermission.objects.get(modulo='revistas')
    except (Role.DoesNotExist, ModulePermission.DoesNotExist):
        return

    RolePermission.objects.filter(role=role, permission=permission).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('access_control', '0003_rename_legacy_roles'),
    ]

    operations = [
        migrations.RunPython(remove_professor_revistas_permission, migrations.RunPython.noop),
    ]
