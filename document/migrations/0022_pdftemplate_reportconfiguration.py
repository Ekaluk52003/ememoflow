# Generated by Django 5.0.3 on 2024-07-29 06:09

import django.core.files.storage
import pathlib
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0021_remove_approvalstep_email_approved_body_template_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PDFTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('html_content', models.TextField()),
                ('css_content', models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name='ReportConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('company_name', models.CharField(max_length=200)),
                ('company_address', models.TextField()),
                ('company_logo', models.ImageField(storage=django.core.files.storage.FileSystemStorage(location=pathlib.PureWindowsPath('D:/Django/djangox/media')), upload_to='report_logos/')),
                ('footer_text', models.TextField()),
            ],
        ),
    ]
