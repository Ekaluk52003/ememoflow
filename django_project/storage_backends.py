from storages.backends.s3boto3 import S3Boto3Storage
from django.utils.timezone import now
import os
import re

class CustomS3Storage(S3Boto3Storage):
    """
    Custom S3 storage class for handling file uploads.
    """

    def get_available_name(self, name, max_length=None):
        """
        Override to avoid overwriting files by appending a timestamp to the name.
        """
        dir_name, file_name = os.path.split(name)
        base_name, ext = os.path.splitext(file_name)

        match = re.search(r"_(\d{14})$", base_name)
        if match:
            base_name = base_name[:match.start()]

        MAX_BASE_LENGTH = 50
        if len(base_name) > MAX_BASE_LENGTH:
            base_name = base_name[:MAX_BASE_LENGTH]

        if not base_name:
            base_name = "file"

        timestamp = now().strftime("%Y%m%d%H%M%S")
        new_file_name = f"{base_name}_{timestamp}{ext.lower()}"
        name = os.path.join(dir_name, new_file_name)
        return super().get_available_name(name, max_length)

    def generate_path(self, instance, filename):
        """
        Generate a dynamic file path based on the instance's attributes.
        """
        if hasattr(instance, 'document') and getattr(instance.document, 'document_reference', None):
            document_reference = instance.document.document_reference
        else:
            document_reference = 'default'

        base_path = f"documents/{document_reference}/{filename}"
        return base_path
