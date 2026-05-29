from django.db import migrations


def grant_alunos_excluir(apps, schema_editor):
    ModulePermission = apps.get_model('access_control', 'ModulePermission')
    ModulePermission.objects.filter(modulo='alunos').update(excluir=True)


class Migration(migrations.Migration):
    dependencies = [
        ('access_control', '0005_remove_professor_financeiro_permission'),
    ]

    operations = [
        migrations.RunPython(grant_alunos_excluir, migrations.RunPython.noop),
    ]
