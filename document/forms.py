from django import forms
from .models import Document, ApprovalStep
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field
from django import forms


class DocumentSubmissionForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'content']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('title', css_class='form-control'),
            Field('content'),
            Submit('submit', 'Submit Document', css_class='btn btn-primary')
        )

class ApprovalStepForm(forms.ModelForm):
    class Meta:
        model = ApprovalStep
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        requires_edit = cleaned_data.get('requires_edit')
        editable_fields = cleaned_data.get('editable_fields')

        if requires_edit and not editable_fields:
            raise forms.ValidationError("At least one editable field must be selected if edit is required.")
        return cleaned_data