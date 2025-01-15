# Generated by Django 5.0.3 on 2024-07-29 05:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0019_dynamicfield_allowed_extensions_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalstep',
            name='email_approved_body_template',
            field=models.TextField(blank=True, help_text='Use {document}, {approver}, and {step} as placeholders'),
        ),
        migrations.AddField(
            model_name='approvalstep',
            name='email_approved_subject',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='approvalstep',
            name='send_approved_email',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='approvalstep',
            name='cc_emails',
            field=models.TextField(blank=True, help_text='Comma-separated email addresses for CC for'),
        ),
    ]
