from django.db import models
from accounts.models import CustomUser
from django.apps import apps

class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    document = models.ForeignKey('document.Document', on_delete=models.CASCADE, related_name='notifications')
    workflow_name = models.CharField(max_length=100)
    url = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.user.username} - {self.message}"
