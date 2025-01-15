from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    job_title = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.email