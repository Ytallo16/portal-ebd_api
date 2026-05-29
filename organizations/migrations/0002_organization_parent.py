from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('organizations', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='organization',
            name='parent',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='children',
                to='organizations.organization',
            ),
        ),
        migrations.AddIndex(
            model_name='organization',
            index=models.Index(fields=['parent'], name='organizatio_parent__idx'),
        ),
        migrations.AddIndex(
            model_name='organization',
            index=models.Index(fields=['tipo'], name='organizatio_tipo_idx'),
        ),
    ]
