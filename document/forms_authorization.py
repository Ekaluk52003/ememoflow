from django import forms
from django.utils import timezone
from accounts.models import CustomUser
from .models_authorization import ApprovalAuthorization


class ApprovalAuthorizationForm(forms.ModelForm):
    """Form for creating and updating approval authorizations"""
    
    authorized_user = forms.ModelChoiceField(
        queryset=CustomUser.objects.filter(is_active=True).order_by('username'),
        label="Authorize User",
        help_text="Select the user who will approve documents on your behalf"
    )
    
    valid_from = forms.DateTimeField(
        label="Valid From",
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M'
        ),
        initial=timezone.now,
        help_text="When this authorization becomes active"
    )
    
    valid_until = forms.DateTimeField(
        label="Valid Until",
        widget=forms.DateTimeInput(
            attrs={'type': 'datetime-local'},
            format='%Y-%m-%dT%H:%M'
        ),
        help_text="When this authorization expires"
    )
    
    reason = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text="Reason for the authorization (e.g., vacation, business trip)"
    )
    
    class Meta:
        model = ApprovalAuthorization
        # Only include these fields in the form
        fields = ['authorized_user', 'valid_from', 'valid_until', 'reason']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Get the current user from the request
        request = None
        if args and hasattr(args[0], 'user'):
            request = args[0]
        
        # Filter out the current user from the authorized_user queryset
        self.fields['authorized_user'].queryset = CustomUser.objects.filter(
            is_active=True
        ).order_by('username')
    
    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')
        authorized_user = cleaned_data.get('authorized_user')
        
        if valid_from and valid_until and valid_from >= valid_until:
            raise forms.ValidationError("End date must be after start date.")
        
        if valid_until and valid_until <= timezone.now():
            raise forms.ValidationError("End date must be in the future.")
        
        # We'll check for overlapping authorizations in the view
        
        return cleaned_data
    
    def save(self, commit=True):
        # Get the form data without saving
        instance = super().save(commit=False)
        
        # We'll set the authorizer in the view
        
        # Save if commit is True
        if commit:
            instance.save()
        
        return instance
