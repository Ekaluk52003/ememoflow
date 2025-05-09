# Generated by Django 4.2.9 on 2025-04-19 17:12

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('document', '0068_alter_dynamicfield_table_columns'),
    ]

    operations = [
        migrations.CreateModel(
            name='ApprovalAuthorization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('valid_from', models.DateTimeField(default=django.utils.timezone.now)),
                ('valid_until', models.DateTimeField(help_text='When this authorization expires')),
                ('reason', models.TextField(help_text='Reason for the authorization (e.g., vacation, business trip)')),
                ('is_active', models.BooleanField(default=True, help_text='Whether this authorization is currently active')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('authorized_user', models.ForeignKey(help_text='User who is authorized to approve on behalf of the authorizer', on_delete=django.db.models.deletion.CASCADE, related_name='received_authorizations', to=settings.AUTH_USER_MODEL)),
                ('authorizer', models.ForeignKey(help_text='User who is authorizing someone else to approve on their behalf', on_delete=django.db.models.deletion.CASCADE, related_name='given_authorizations', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'Approval Authorization',
                'verbose_name_plural': 'Approval Authorizations',
                'ordering': ['-valid_from'],
            },
        ),
    ]
