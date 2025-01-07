from storages.backends.s3boto3 import S3Boto3Storage
from django.utils.timezone import now
import os

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
        timestamp = now().strftime("%Y%m%d%H%M%S")
        name = os.path.join(dir_name, f"{base_name}_{timestamp}{ext}")
        return super().get_available_name(name, max_length)

    def generate_path(self, instance, filename):
        """
        Generate a dynamic file path based on the instance's attributes.
        """
        document_reference = getattr(instance.document, 'document_reference', 'default') if hasattr(instance, 'document') else 'default'
        base_path = f"documents/{document_reference}/{filename}"
        return self.get_available_name(base_path)
