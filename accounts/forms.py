from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from allauth.account.forms import SignupForm
from .models import CustomUser
import os


class CustomUserCreationForm(UserCreationForm):

    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('email', 'username','job_title',)


class CustomUserChangeForm(UserChangeForm):

    class Meta:
        model = CustomUser
        fields = ('email', 'username','job_title',)


class CustomSignupForm(SignupForm):
    first_name = forms.CharField(max_length=30, required=True, label="First Name")
    last_name = forms.CharField(max_length=30, required=True, label="Last Name")
    job_title = forms.CharField(max_length=255, required=False, label="Job Title")

    def clean_email(self):
        email = self.cleaned_data.get('email')

        # Fetch allowed domains from the environment variable with a default empty string
        allowed_domains = os.environ.get("ALLOWED_DOMAINS", "")

        # Handle empty allowed_domains gracefully
        if not allowed_domains:
            raise ValidationError("Allowed email domains are not configured in the environment.")

        # Split the domains into a list
        allowed_domains_list = [domain.strip() for domain in allowed_domains.split(",") if domain.strip()]

        # Extract the domain from the email
        domain = email.split('@')[-1]

        if domain not in allowed_domains_list:
            raise ValidationError(f"Email domain must be one of the following: {', '.join(allowed_domains_list)}")

        return email

    def save(self, request):
        user = super().save(request)
        user.first_name = self.cleaned_data.get('first_name')
        user.last_name = self.cleaned_data.get('last_name')
        user.job_title = self.cleaned_data.get('job_title')
        user.save()
        return user
