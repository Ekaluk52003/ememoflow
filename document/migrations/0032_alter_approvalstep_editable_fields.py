# Generated by Django 5.0.3 on 2024-08-28 16:33

import document.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0031_alter_approvalstep_options'),
    ]

    operations = [
        migrations.AlterField(
            model_name='approvalstep',
            name='editable_fields',
            field=document.models.WorkflowSpecificManyToManyField(blank=True, related_name='approval_steps', to='document.dynamicfield'),
        ),
    ]
