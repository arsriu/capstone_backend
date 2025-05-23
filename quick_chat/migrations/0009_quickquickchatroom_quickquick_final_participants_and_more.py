# Generated by Django 4.2.13 on 2024-11-25 23:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quick_chat', '0008_quickchatroom_quick_final_participants_saved'),
    ]

    operations = [
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_final_participants',
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_final_participants_saved',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_is_settled',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_max_participants',
            field=models.IntegerField(default=4),
        ),
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_min_participants',
            field=models.IntegerField(default=2),
        ),
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_participant_count',
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name='quickquickchatroom',
            name='quickquick_updated_at',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
