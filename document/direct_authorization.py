from django import forms
from django.utils import timezone
from django.db import models
from accounts.models import CustomUser
from document.models_authorization import ApprovalAuthorization

class DirectAuthorizationForm(forms.Form):
    """A direct form for creating authorizations without using ModelForm"""
    
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
    
    def __init__(self, *args, **kwargs):
        self.authorizer = kwargs.pop('authorizer', None)
        super().__init__(*args, **kwargs)
        
        # Filter out the authorizer from the authorized_user queryset
        if self.authorizer:
            self.fields['authorized_user'].queryset = CustomUser.objects.filter(
                is_active=True
            ).exclude(
                id=self.authorizer.id
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
        
        # Check for overlapping authorizations
        if self.authorizer and authorized_user:
            overlapping = ApprovalAuthorization.objects.filter(
                authorizer=self.authorizer,
                authorized_user=authorized_user,
                valid_from__lt=valid_until,
                valid_until__gt=valid_from,
                is_active=True
            )
            
            if overlapping.exists():
                raise forms.ValidationError(
                    "There is already an overlapping authorization for this user."
                )
        
        return cleaned_data
    
    def save(self):
        """Create and save a new ApprovalAuthorization instance"""
        if not self.authorizer:
            raise ValueError("Authorizer is required")
        
        data = self.cleaned_data
        
        # Create the authorization
        authorization = ApprovalAuthorization(
            authorizer=self.authorizer,
            authorized_user=data['authorized_user'],
            valid_from=data['valid_from'],
            valid_until=data['valid_until'],
            reason=data['reason'],
            is_active=True
        )
        
        # Save the authorization
        authorization.save()
        
        return authorization

def create_direct_authorization(request):
    """Function to create an authorization directly without using ModelForm"""
    from django.contrib.auth.decorators import login_required
    from django.shortcuts import render, redirect
    from django.contrib import messages
    
    @login_required
    def view_func(request):
        if request.method == 'POST':
            form = DirectAuthorizationForm(request.POST, authorizer=request.user)
            if form.is_valid():
                try:
                    authorization = form.save()
                    messages.success(
                        request, 
                        f"Successfully authorized {authorization.authorized_user.username} to approve documents on your behalf."
                    )
                    return redirect('document_approval:authorization_list')
                except Exception as e:
                    print(f"Error creating authorization: {str(e)}")
                    messages.error(request, f"Error creating authorization: {str(e)}")
            else:
                print(f"Form errors: {form.errors}")
        else:
            form = DirectAuthorizationForm(authorizer=request.user)
        
        return render(request, 'document/authorization_form.html', {
            'form': form,
            'title': 'Create Authorization',
        })
    
    return view_func(request)
