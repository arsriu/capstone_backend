# Generated by Django 4.2.13 on 2024-11-11 04:57

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quick_chat', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='quickchatroom',
            name='quick_final_participants',
            field=models.JSONField(blank=True, default=list),
        ),
    ]
