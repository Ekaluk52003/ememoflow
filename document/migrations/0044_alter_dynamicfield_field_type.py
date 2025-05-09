# Generated by Django 5.0.3 on 2024-10-06 04:52

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0043_alter_approval_unique_together'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dynamicfield',
            name='field_type',
            field=models.CharField(choices=[('text', 'Text'), ('textarea', 'Text Area'), ('number', 'Number'), ('date', 'Date'), ('boolean', 'Yes/No'), ('choice', 'Multiple Choice'), ('radio', 'Radio Buttons'), ('attachment', 'File Attachment'), ('product_list', 'Product List')], max_length=20),
        ),
    ]
