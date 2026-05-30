import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('publications', '0002_publicationcontrol_trimester'),
    ]

    operations = [
        migrations.AddField(
            model_name='publicationcontrol',
            name='metodo_pagamento',
            field=models.CharField(
                blank=True,
                choices=[
                    ('DINHEIRO', 'Dinheiro'),
                    ('PIX', 'PIX'),
                    ('CARTAO', 'Cartão'),
                    ('TRANSFERENCIA', 'Transferência'),
                    ('OUTRO', 'Outro'),
                ],
                default='',
                max_length=20,
            ),
        ),
    ]
