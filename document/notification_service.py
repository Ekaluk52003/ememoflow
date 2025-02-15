# notification_service.py
import redis
import json
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from .notification_models import Notification

def send_approval_notification(document, approver):
    """Create a notification in database and send via Redis pub/sub"""
    try:
        print(f"Creating notification for user: {approver.username}")
        
        # Create notification in database
        notification = Notification.objects.create(
            user=approver,
            message=f"Document #{document.document_reference} - {document.title}",
            document=document,
            workflow_name=document.workflow.name,
            url=reverse('document_approval:document_detail', 
                     kwargs={'reference_id': document.document_reference}),
            is_read=False  # Explicitly set is_read
        )
        
        print(f"Created notification: ID={notification.id}, is_read={notification.is_read}")

        # Send real-time notification via Redis
        redis_client = redis.Redis.from_url(settings.REDIS_URL)
        notification_data = {
            'type': 'notification',
            'notification': {
                'id': notification.id,
                'message': notification.message,
                'workflow_name': notification.workflow_name,
                'url': notification.url,
                'timestamp': notification.timestamp.isoformat(),
                'is_read': notification.is_read  # Include is_read in the notification data
            }
        }
        
        print(f"Sending notification data: {notification_data}")
        
        redis_client.publish(
            f'user_{approver.id}',
            json.dumps(notification_data)
        )
        
        print("Notification sent successfully")
        
    except Exception as e:
        print(f"Error sending notification: {e}")
    finally:
        if 'redis_client' in locals():
            redis_client.close()