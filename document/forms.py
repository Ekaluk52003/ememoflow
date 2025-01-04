from django import forms
from .models import Document, ApprovalStep
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field
from django import forms
import re

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

    def clean_content(self):
        content = self.cleaned_data.get('content', '')
        # Remove all HTML tags
        content_without_tags = re.sub(r'<[^>]+>', '', content)
        # Remove all whitespace
        content_stripped = content_without_tags.strip()
        # if not content_stripped:
        #     raise forms.ValidationError("Content is required.")
        return content