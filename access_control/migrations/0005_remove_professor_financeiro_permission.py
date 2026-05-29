from django.db import migrations


def remove_professor_financeiro_permission(apps, schema_editor):
    Role = apps.get_model('access_control', 'Role')
    RolePermission = apps.get_model('access_control', 'RolePermission')
    ModulePermission = apps.get_model('access_control', 'ModulePermission')

    try:
        role = Role.objects.get(nome='PROFESSOR')
        permission = ModulePermission.objects.get(modulo='financeiro')
    except (Role.DoesNotExist, ModulePermission.DoesNotExist):
        return

    RolePermission.objects.filter(role=role, permission=permission).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('access_control', '0004_remove_professor_revistas_permission'),
    ]

    operations = [
        migrations.RunPython(remove_professor_financeiro_permission, migrations.RunPython.noop),
    ]
