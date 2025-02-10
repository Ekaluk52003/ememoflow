# notification_service.py
import redis
import json
from django.urls import reverse
from django.utils import timezone
from django.conf import settings

def send_approval_notification(document, approver):
    """Send an approval notification via Redis pub/sub"""
    try:
        redis_client = redis.Redis.from_url(settings.CELERY_BROKER_URL)
        
        notification = {
            'message': f"Document #{document.document_reference} - {document.title}",
            'workflow_name': document.workflow.name,
            'url': reverse('document_approval:document_detail', 
                         kwargs={'reference_id': document.document_reference}),
            'timestamp': timezone.now().isoformat(),
            'type': 'notification'
        }
        
        redis_client.publish(
            f'user_{approver.id}',
            json.dumps(notification)
        )
    except Exception as e:
        print(f"Error sending notification: {e}")
    finally:
        redis_client.close()