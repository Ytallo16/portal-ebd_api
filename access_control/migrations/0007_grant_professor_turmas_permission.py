from django.db import migrations


def grant_professor_turmas_permission(apps, schema_editor):
    Role = apps.get_model('access_control', 'Role')
    RolePermission = apps.get_model('access_control', 'RolePermission')
    ModulePermission = apps.get_model('access_control', 'ModulePermission')

    try:
        role = Role.objects.get(nome='PROFESSOR')
        permission = ModulePermission.objects.get(modulo='turmas')
    except (Role.DoesNotExist, ModulePermission.DoesNotExist):
        return

    RolePermission.objects.get_or_create(role=role, permission=permission)


class Migration(migrations.Migration):
    dependencies = [
        ('access_control', '0006_grant_alunos_excluir_permission'),
    ]

    operations = [
        migrations.RunPython(grant_professor_turmas_permission, migrations.RunPython.noop),
    ]
