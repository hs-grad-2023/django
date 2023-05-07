# Generated by Django 4.2 on 2023-05-05 16:44

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('muapp', '0002_viton_upload_cloth_viton_upload_model_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='viton_upload_result',
            name='cloth',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='muapp.viton_upload_cloth'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='viton_upload_result',
            name='model',
            field=models.ForeignKey(default=1, on_delete=django.db.models.deletion.CASCADE, to='muapp.viton_upload_model'),
            preserve_default=False,
        ),
    ]
