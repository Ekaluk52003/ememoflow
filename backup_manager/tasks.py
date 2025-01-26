from celery import shared_task
from django.core.management import call_command
from django_celery_results.models import TaskResult
from datetime import datetime, timedelta
from django.utils import timezone

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
        call_command('dbbackup', '--clean')
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
    
    # cutoff_date = timezone.now() - timedelta(days=7)
      
    # Calculate the cutoff date (3 hours ago)
    cutoff_date = timezone.now() - timedelta(hours=24)
    
    # Delete old results and get count
    deleted_count = TaskResult.objects.filter(
        date_done__lt=cutoff_date
    ).delete()[0]
    
    return f"Deleted {deleted_count} task results older than {cutoff_date}"
