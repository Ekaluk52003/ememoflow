from celery import shared_task
from django.core.management import call_command
from django_celery_results.models import TaskResult
from datetime import datetime, timedelta
from django.utils import timezone
import boto3
from django.conf import settings

@shared_task(
    name='backup_database',
    bind=True,
    track_started=True,
    ignore_result=False
)
def backup_database(self):
    try:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.update_state(state='PROGRESS', meta={'status': 'Starting backup...'})
        
        # Perform the backup without clean flag
        call_command('dbbackup')
        
        # Manual cleanup of old backups in S3
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL
        )
        
        # List all backups in the backup directory
        prefix = f"{settings.DBBACKUP_STORAGE_OPTIONS['location']}/"
        response = s3_client.list_objects_v2(
            Bucket=settings.AWS_STORAGE_BUCKET_NAME,
            Prefix=prefix
        )
        
        if 'Contents' in response:
            # Sort backups by last modified date
            backups = sorted(
                response['Contents'],
                key=lambda x: x['LastModified'],
                reverse=True
            )
            
            # Keep only the specified number of recent backups
            keep_count = getattr(settings, 'DBBACKUP_CLEANUP_KEEP', 3)
            backups_to_delete = backups[keep_count:]
            
            # Delete old backups
            for backup in backups_to_delete:
                s3_client.delete_object(
                    Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                    Key=backup['Key']
                )
                self.update_state(
                    state='PROGRESS',
                    meta={'status': f'Deleted old backup: {backup["Key"]}'}
                )
        
        self.update_state(state='SUCCESS', meta={'status': f'Backup completed at {timestamp}'})
        return {'status': 'success', 'message': f"Database backup completed successfully at {timestamp}"}
    except Exception as e:
        self.update_state(state='FAILURE', meta={'status': f'Backup failed: {str(e)}'})
        return {'status': 'error', 'message': f"Database backup failed: {str(e)}"}

@shared_task
def cleanup_old_task_results():
    """
    Remove Celery task results older than 3 hours.
    Returns the number of deleted results.
    """
    # Calculate the cutoff date (3 hours ago)
    cutoff_date = timezone.now() - timedelta(hours=24)
    
    # Delete old results and get count
    deleted_count = TaskResult.objects.filter(
        date_done__lt=cutoff_date
    ).delete()[0]
    
    return f"Deleted {deleted_count} task results older than {cutoff_date}"
