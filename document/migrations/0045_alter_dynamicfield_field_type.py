# Generated by Django 5.0.3 on 2024-10-06 05:12

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0044_alter_dynamicfield_field_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='dynamicfield',
            name='field_type',
            field=models.CharField(choices=[('text', 'Text'), ('textarea', 'Text Area'), ('number', 'Number'), ('date', 'Date'), ('boolean', 'Yes/No'), ('choice', 'Multiple Choice'), ('multiple_choice', 'Multiple Choice'), ('attachment', 'File Attachment'), ('product_list', 'Product List')], max_length=20),
        ),
    ]
