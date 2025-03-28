# Generated by Django 5.0.3 on 2024-07-27 16:38

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0016_approvalworkflow_cc_emails_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalworkflow',
            name='send_reject_email',
            field=models.BooleanField(default=True, help_text='Send email on document rejection'),
        ),
        migrations.AddField(
            model_name='approvalworkflow',
            name='send_withdraw_email',
            field=models.BooleanField(default=True, help_text='Send email on document withdrawal'),
        ),
    ]
