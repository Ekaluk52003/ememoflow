from django.conf import settings
import redis
import json
from django.urls import reverse
from django.utils import timezone

redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)

def send_approval_notification(document, approver):
    """
    Send an approval notification to a specific approver
    """
    workflow_name = document.workflow.name
    message = f"Document #{document.document_reference} - {document.title}"
    document_url = reverse('document_approval:document_detail', 
                          kwargs={'reference_id': document.document_reference})
    
    notification = {
        'user_id': approver.id,
        'message': message,
        'workflow_name': workflow_name,
        'url': document_url,
        'timestamp': timezone.now().isoformat(),
        'type': 'notification',
        'document_reference': document.document_reference
    }
    redis_client.publish(f'user_{approver.id}', json.dumps(notification))