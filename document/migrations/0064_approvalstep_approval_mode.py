# Generated by Django 4.2.9 on 2025-04-08 16:02

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0063_notification'),
    ]

    operations = [
        migrations.AddField(
            model_name='approvalstep',
            name='approval_mode',
            field=models.CharField(choices=[('all', 'All Approvers Required'), ('any', 'Any Approver Sufficient')], default='all', help_text='Determines whether all approvers must approve or any single approver is sufficient', max_length=10),
        ),
    ]
