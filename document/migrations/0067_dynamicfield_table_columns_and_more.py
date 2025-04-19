# Generated by Django 4.2.9 on 2025-04-16 14:32

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0066_approval_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='dynamicfield',
            name='table_columns',
            field=models.TextField(blank=True, help_text="Comma-separated column names for 'table_list' field type"),
        ),
        migrations.AlterField(
            model_name='dynamicfield',
            name='field_type',
            field=models.CharField(choices=[('text', 'Text'), ('textarea', 'Text Area'), ('number', 'Number'), ('date', 'Date'), ('boolean', 'Yes/No'), ('choice', 'Single Choice'), ('multiple_choice', 'Multiple Choice'), ('attachment', 'File Attachment'), ('product_list', 'Product List'), ('table_list', 'Table List')], max_length=20),
        ),
    ]
