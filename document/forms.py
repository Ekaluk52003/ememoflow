from django import forms
from .models import Document
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field

class DocumentSubmissionForm(forms.ModelForm):
    class Meta:
        model = Document
        fields = ['title', 'content']
        widgets = {
            'content': forms.HiddenInput(),  # We'll use this to store Quill.js content
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_method = 'post'
        self.helper.layout = Layout(
            Field('title', css_class='form-control'),
            Field('content'),
            Submit('submit', 'Submit Document', css_class='btn btn-primary')
        )
