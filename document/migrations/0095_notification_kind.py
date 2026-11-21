from django.db import migrations, models


def backfill(apps, schema_editor):
    N = apps.get_model('document', 'Notification')
    N.objects.filter(message__contains=' mentioned you on #').update(kind='mention')
    N.objects.filter(message__contains=' replied to your comment on #').update(kind='reply')


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0094_notification_preview'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='kind',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.RunPython(backfill, migrations.RunPython.noop),
    ]
