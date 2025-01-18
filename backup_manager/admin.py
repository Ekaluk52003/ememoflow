from django.contrib import admin
from django.urls import path
from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.management import call_command
from django.conf import settings
from django.conf import settings
import os
from io import StringIO
from .models import BackupManagement
from django.db import connection
from django.http import FileResponse, Http404
from django.views.decorators.csrf import csrf_protect
from django.utils.decorators import method_decorator
from django.core.files.storage import FileSystemStorage
from django.conf import settings


@admin.register(BackupManagement)
class BackupManagementAdmin(admin.ModelAdmin):
    change_list_template = 'admin/backup_changelist.html'

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context['backups'] = self.get_backups()
        return super().changelist_view(request, extra_context=extra_context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('create_backup/', self.admin_site.admin_view(self.create_backup_view),
                 name='backup_manager_backupmanagement_create_backup'),
            path('restore_db/<path:filename>/',
                 self.admin_site.admin_view(self.restore_db_view),
                 name='backup_manager_backupmanagement_restore_db'),
            path('confirm_restore_db/<path:filename>/',
                 self.admin_site.admin_view(self.confirm_restore_db_view),
                 name='backup_manager_backupmanagement_confirm_restore_db'),
            path('download_backup/<path:filename>/',
                 self.admin_site.admin_view(self.download_backup_view),
                 name='backup_manager_backupmanagement_download_backup'),
            path('upload_backup/',
                 self.admin_site.admin_view(self.upload_backup_view),
                 name='backup_manager_backupmanagement_upload_backup'),
        ]
        return custom_urls + urls

    def get_backups(self):
        if settings.DBBACKUP_STORAGE == 'storages.backends.s3boto3.S3Boto3Storage':
            import boto3
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.DBBACKUP_STORAGE_OPTIONS['access_key'],
                aws_secret_access_key=settings.DBBACKUP_STORAGE_OPTIONS['secret_key'],
                endpoint_url=settings.DBBACKUP_STORAGE_OPTIONS['endpoint_url'],
            )
            
            bucket = settings.DBBACKUP_STORAGE_OPTIONS['bucket_name']
            prefix = settings.DBBACKUP_STORAGE_OPTIONS.get('location', '')
            backups = []
            
            response = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
            if 'Contents' in response:
                for obj in response['Contents']:
                    if obj['Key'].endswith('.psql'):
                        # Strip the prefix/location from the displayed name
                        display_name = obj['Key']
                        if prefix and display_name.startswith(prefix):
                            display_name = display_name[len(prefix):]
                        if display_name.startswith('/'):
                            display_name = display_name[1:]
                        backups.append({'name': display_name, 'key': obj['Key']})
            return sorted(backups, reverse=True, key=lambda x: x['name'])
        else:
            backup_dir = settings.DBBACKUP_STORAGE_OPTIONS['location']
            backups = []
            if os.path.exists(backup_dir):
                for file in os.listdir(backup_dir):
                    if file.endswith('.psql'):
                        backups.append(file)
            return sorted(backups, reverse=True)

    def download_backup_view(self, request, filename):
        if settings.DBBACKUP_STORAGE == 'storages.backends.s3boto3.S3Boto3Storage':
            import boto3
            s3 = boto3.client(
                's3',
                aws_access_key_id=settings.DBBACKUP_STORAGE_OPTIONS['access_key'],
                aws_secret_access_key=settings.DBBACKUP_STORAGE_OPTIONS['secret_key'],
                endpoint_url=settings.DBBACKUP_STORAGE_OPTIONS['endpoint_url'],
            )
            
            bucket = settings.DBBACKUP_STORAGE_OPTIONS['bucket_name']
            
            try:
                response = s3.get_object(Bucket=bucket, Key=filename)
                content = response['Body'].read()
                
                # Get just the filename without path for the download
                display_name = filename.split('/')[-1]
                
                response = FileResponse(content)
                response['Content-Disposition'] = f'attachment; filename="{display_name}"'
                return response
            except Exception as e:
                raise Http404(f"Backup file not found: {str(e)}")
        else:
            backup_dir = settings.DBBACKUP_STORAGE_OPTIONS['location']
            file_path = os.path.join(backup_dir, filename)

            if os.path.exists(file_path):
                response = FileResponse(open(file_path, 'rb'))
                response['Content-Disposition'] = f'attachment; filename="{filename}"'
                return response
            else:
                raise Http404("Backup file not found")

    @method_decorator(csrf_protect)
    def upload_backup_view(self, request):
        if request.method == 'POST' and request.FILES.get('backup_file'):
            uploaded_file = request.FILES['backup_file']
            if not uploaded_file.name.endswith('.psql'):
                messages.error(request, "Only .psql files are allowed.")
                return redirect('..')

            backup_dir = settings.DBBACKUP_STORAGE_OPTIONS['location']

            os.makedirs(backup_dir, exist_ok=True)

            fs = FileSystemStorage(location=backup_dir)

            filename = fs.save(uploaded_file.name, uploaded_file)

            messages.success(request, f"Backup file '{uploaded_file.name}' uploaded successfully.")
            return redirect('..')
        
        return render(request, 'admin/upload_backup.html')

    def create_backup_view(self, request):
        import boto3
        from botocore.config import Config
        from datetime import datetime
        
        # Get list of files before backup
        s3 = boto3.client(
            's3',
            aws_access_key_id=settings.DBBACKUP_STORAGE_OPTIONS['access_key'],
            aws_secret_access_key=settings.DBBACKUP_STORAGE_OPTIONS['secret_key'],
            endpoint_url=settings.DBBACKUP_STORAGE_OPTIONS['endpoint_url'],
            config=Config(signature_version='s3v4')
        )
        bucket = settings.DBBACKUP_STORAGE_OPTIONS['bucket_name']
        prefix = settings.DBBACKUP_STORAGE_OPTIONS['location']
        
        # Get list of files before backup
        response_before = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        files_before = set()
        if 'Contents' in response_before:
            files_before = {obj['Key'] for obj in response_before['Contents']}
        
        # Create backup with clean option to keep only recent backups
        output = StringIO()
        call_command('dbbackup', '--clean', '--noinput', stdout=output, stderr=output)
        
        # Get list of files after backup
        response_after = s3.list_objects_v2(Bucket=bucket, Prefix=prefix)
        files_after = set()
        if 'Contents' in response_after:
            files_after = {obj['Key'] for obj in response_after['Contents']}
        
        # Find new files
        new_files = files_after - files_before
        
        if new_files:
            new_file = list(new_files)[0]  # Get the first new file
            messages.success(request, f'Backup created successfully: {os.path.basename(new_file)}')
        else:
            messages.warning(request, 'Backup command executed, but no new backup file was found. Check S3 storage.')
        
        return redirect('..')

    def restore_db_view(self, request, filename):
        if not request.user.is_superuser:
            messages.error(request, "Only superusers can restore database backups.")
            return redirect('..')

        # Show confirmation page first
        return render(request, 'admin/restore_db_confirm.html', {'filename': filename})

    def confirm_restore_db_view(self, request, filename):
        if request.method != 'POST':
            return redirect('..')

        if not request.user.is_superuser:
            messages.error(request, "Only superusers can restore database backups.")
            return redirect('..')
            
        if settings.DBBACKUP_STORAGE == 'storages.backends.s3boto3.S3Boto3Storage':
            try:
                # Remove any existing backupdb/ prefix since it's added by the storage
                clean_filename = filename.replace('backupdb/', '')
               
                
                # Use the S3 path directly with dbrestore
                output = StringIO()
                call_command('dbrestore', '--noinput', '--input-filename', clean_filename, stdout=output, stderr=output)                
                
                # Verify database state
                if self.verify_database_state():
                    messages.success(request, f'Database restored successfully from {os.path.basename(filename)}.')
      
                else:
                    messages.warning(request, f'Database restore completed, but please verify the database state.')
           
                
            except Exception as e:
       
                messages.error(request, f"Error restoring database: {str(e)}")
        else:
            backup_file = os.path.join(settings.DBBACKUP_STORAGE_OPTIONS['location'], filename)
            
            try:
                output = StringIO()
                call_command('dbrestore', '--noinput', '--input-filename', backup_file, stdout=output, stderr=output)
                
                # Verify database state
                if self.verify_database_state():
                    messages.success(request, f'Database restored successfully from {filename}.')
                else:
                    messages.warning(request, f'Database restore completed, but please verify the database state.')
                    
            except Exception as e:
                messages.error(request, f"Error restoring database: {str(e)}")

        return redirect('admin:backup_manager_backupmanagement_changelist')

    def verify_database_state(self):
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")
            table_count = cursor.fetchone()[0]
        return table_count > 0