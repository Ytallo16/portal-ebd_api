from django.db import migrations


def remove_professor_duplicado_por_igreja(apps, schema_editor):
    ClassTeacher = apps.get_model('classrooms', 'ClassTeacher')
    vistos = set()
    duplicados = []

    for link in ClassTeacher.objects.select_related('class_group').order_by('user_id', 'id'):
        org_id = link.class_group.organization_id
        chave = (link.user_id, org_id)
        if chave in vistos:
            duplicados.append(link.id)
        else:
            vistos.add(chave)

    if duplicados:
        ClassTeacher.objects.filter(id__in=duplicados).delete()


class Migration(migrations.Migration):
    dependencies = [
        ('classrooms', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(remove_professor_duplicado_por_igreja, migrations.RunPython.noop),
    ]
