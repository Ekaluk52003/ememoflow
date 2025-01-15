# Generated by Django 5.0.3 on 2024-07-27 16:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0015_approvalstep_cc_emails'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalworkflow',
            name='cc_emails',
            field=models.TextField(blank=True, help_text='Comma-separated email addresses for CC'),
        ),
        migrations.AddField(
            model_name='approvalworkflow',
            name='reject_email_body',
            field=models.TextField(blank=True, help_text='Body template for rejection emails'),
        ),
        migrations.AddField(
            model_name='approvalworkflow',
            name='reject_email_subject',
            field=models.TextField(blank=True, help_text='Subject for rejection emails'),
        ),
        migrations.AddField(
            model_name='approvalworkflow',
            name='withdraw_email_body',
            field=models.TextField(blank=True, help_text='Body template for withdrawal emails'),
        ),
        migrations.AddField(
            model_name='approvalworkflow',
            name='withdraw_email_subject',
            field=models.TextField(blank=True, help_text='Subject for withdrawal emails'),
        ),
    ]
