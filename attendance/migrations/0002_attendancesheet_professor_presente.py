from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('attendance', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancesheet',
            name='professor_presente',
            field=models.BooleanField(default=False),
        ),
    ]
