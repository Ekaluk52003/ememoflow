# your_project_name/celery.py

from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from urllib.parse import quote

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')

app = Celery('django_project')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')


# Load task modules from all registered Django app configs.
app.autodiscover_tasks()
