import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('organizations', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('kind', models.CharField(
                    choices=[
                        ('ATTENDANCE_PENDING', 'Chamada pendente'),
                        ('LESSON_TODAY', 'Aula hoje'),
                        ('LESSON_FINALIZE', 'Lição a finalizar'),
                        ('MAGAZINE_PAYMENT', 'Revista aguardando pagamento'),
                        ('BIRTHDAY_TODAY', 'Aniversário hoje'),
                    ],
                    max_length=40,
                )),
                ('dedupe_key', models.CharField(max_length=255)),
                ('title', models.CharField(max_length=255)),
                ('body', models.TextField(blank=True, default='')),
                ('action_path', models.CharField(max_length=512)),
                ('severity', models.CharField(
                    choices=[('info', 'Info'), ('warning', 'Aviso')],
                    default='info',
                    max_length=20,
                )),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(blank=True, null=True)),
                (
                    'organization',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to='organizations.organization',
                    ),
                ),
                (
                    'user',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='notifications',
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='notification',
            index=models.Index(fields=['user', 'organization', 'read_at'], name='notificatio_user_id_8e0f0d_idx'),
        ),
        migrations.AddConstraint(
            model_name='notification',
            constraint=models.UniqueConstraint(
                fields=('user', 'organization', 'dedupe_key'),
                name='uniq_notification_user_org_dedupe',
            ),
        ),
    ]
