# Generated by Django 5.0.3 on 2024-08-31 11:20

from django.conf import settings
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0040_remove_approval_unique_active_approval_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='approval',
            name='unique_pending_approval',
        ),
        migrations.AlterUniqueTogether(
            name='approval',
            unique_together={('document', 'step', 'approver')},
        ),
    ]
