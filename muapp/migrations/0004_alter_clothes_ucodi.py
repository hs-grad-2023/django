# Generated by Django 4.1.7 on 2023-04-10 09:46

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('muapp', '0003_comment'),
    ]

    operations = [
        migrations.AlterField(
            model_name='clothes',
            name='ucodi',
            field=models.BooleanField(blank=True, null=True),
        ),
    ]
