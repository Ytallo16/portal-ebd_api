from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0002_user_active_organization'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='foto',
            field=models.ImageField(blank=True, null=True, upload_to='avatars/'),
        ),
    ]
