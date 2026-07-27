from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('activity_logs', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='activitylog',
            name='changes',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name='activitylog',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('CREATE', 'Criação'),
                    ('UPDATE', 'Edição'),
                    ('DELETE', 'Exclusão'),
                    ('LOGIN', 'Acesso'),
                    ('REQUEST', 'Operação'),
                ],
                default='REQUEST',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='activitylog',
            name='model_label',
            field=models.CharField(blank=True, max_length=150),
        ),
    ]
