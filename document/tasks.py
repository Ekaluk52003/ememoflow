from celery import shared_task
import logging
from .models import DynamicFieldValue

@shared_task
def upload_file_task(document_id, field_id, file_path):
    from django.core.files import File
    with open(file_path, 'rb') as file:
        DynamicFieldValue.objects.create(
            document_id=document_id,
            field_id=field_id,
            file=File(file)
        )
        
logger = logging.getLogger(__name__)

@shared_task
def test_task(message="Hello, this is a test of the Celery task system!"):
    logger.info(message)
    return message