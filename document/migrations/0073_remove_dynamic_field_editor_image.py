# Generated by Django 4.2.9 on 2025-04-28 14:43

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0072_alter_approvalstep_email_body_template_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='DynamicFieldEditorImage',
        ),
    ]
