from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    job_title = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return self.email
    
    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        If both fields are empty, return the username instead.
        """
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name if full_name else self.username