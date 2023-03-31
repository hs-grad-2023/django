# Generated by Django 4.1.7 on 2023-03-31 18:35

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('muapp', '0003_clothestest_photos'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='clothestest',
            name='uploadUser',
        ),
        migrations.RemoveField(
            model_name='clothes',
            name='group',
        ),
        migrations.RemoveField(
            model_name='clothes',
            name='id',
        ),
        migrations.RemoveField(
            model_name='clothes',
            name='imgfile',
        ),
        migrations.AlterField(
            model_name='clothes',
            name='groupID',
            field=models.CharField(max_length=10, primary_key=True, serialize=False),
        ),
        migrations.AlterField(
            model_name='photos',
            name='groupID',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='muapp.clothes', verbose_name='groupClothes'),
        ),
        migrations.DeleteModel(
            name='ClothesGroup',
        ),
        migrations.DeleteModel(
            name='clothesTest',
        ),
    ]
