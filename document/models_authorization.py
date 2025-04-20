from django.db import models
from django.utils import timezone
from accounts.models import CustomUser
from django.core.exceptions import ValidationError


class ApprovalAuthorization(models.Model):
    """
    Model to track authorization for document approvals.
    This allows a user to authorize another user to approve documents on their behalf.
    """
    authorizer = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='given_authorizations',
        help_text="User who is authorizing someone else to approve on their behalf",
        null=False,  # Ensure this field cannot be null
        blank=False  # Ensure this field cannot be blank
    )
    authorized_user = models.ForeignKey(
        CustomUser, 
        on_delete=models.CASCADE, 
        related_name='received_authorizations',
        help_text="User who is authorized to approve on behalf of the authorizer"
    )
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(
        help_text="When this authorization expires"
    )
    reason = models.TextField(
        help_text="Reason for the authorization (e.g., vacation, business trip)"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this authorization is currently active"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-valid_from']
        verbose_name = "Approval Authorization"
        verbose_name_plural = "Approval Authorizations"
    
    def __str__(self):
        return f"{self.authorizer.username} → {self.authorized_user.username} (until {self.valid_until.strftime('%Y-%m-%d')})"
    
    def clean(self):
        """Validate the authorization"""
        # Check that authorizer and authorized_user are different
        if self.authorizer == self.authorized_user:
            raise ValidationError("You cannot authorize yourself.")
        
        # Check that valid_until is in the future
        if self.valid_until <= timezone.now():
            raise ValidationError("End date must be in the future.")
        
        # Check that valid_until is after valid_from
        if self.valid_until <= self.valid_from:
            raise ValidationError("End date must be after start date.")
        
        # Check for overlapping authorizations
        overlapping = ApprovalAuthorization.objects.filter(
            authorizer=self.authorizer,
            authorized_user=self.authorized_user,
            valid_from__lt=self.valid_until,
            valid_until__gt=self.valid_from,
            is_active=True
        )
        
        if self.pk:  # If updating an existing record
            overlapping = overlapping.exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError("There is already an overlapping authorization for this user.")
    
    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
    
    @classmethod
    def get_active_authorizations(cls, user):
        """Get all active authorizations where the user is the authorized_user"""
        now = timezone.now()
        return cls.objects.filter(
            authorized_user=user,
            valid_from__lte=now,
            valid_until__gte=now,
            is_active=True
        )
    
    @classmethod
    def get_active_authorizers(cls, user):
        """Get all users who have authorized this user"""
        now = timezone.now()
        authorizations = cls.objects.filter(
            authorized_user=user,
            valid_from__lte=now,
            valid_until__gte=now,
            is_active=True
        )
        return [auth.authorizer for auth in authorizations]
    
    @classmethod
    def is_authorized(cls, authorizer, authorized_user):
        """Check if authorized_user is authorized by authorizer"""
        now = timezone.now()
        return cls.objects.filter(
            authorizer=authorizer,
            authorized_user=authorized_user,
            valid_from__lte=now,
            valid_until__gte=now,
            is_active=True
        ).exists()
