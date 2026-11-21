from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('document', '0093_comment_parent'),
    ]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='preview',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
