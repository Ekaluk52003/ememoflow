from django import forms
from .models import Document, ApprovalStep
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Field
from django import forms
import re
from django.conf import settings
from django.core.exceptions import ValidationError

# Constants for file size limits
MAX_IMAGES = 3
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB per image
MAX_TOTAL_SIZE = 4 * 1024 * 1024  # 4MB total

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
        
        # Check for base64 images in content
        base64_pattern = r'data:image\/[^;]+;base64,([^"]+)'
        matches = re.findall(base64_pattern, content)
        
        # Check number of images
        if len(matches) > MAX_IMAGES:
            raise ValidationError(
                f"Maximum of {MAX_IMAGES} images allowed in the editor. Please remove some images."
            )
        
        # Calculate total size of all images
        total_size = 0
        for base64_str in matches:
            try:
                # Calculate size of base64 string (approximate file size)
                file_size = len(base64_str) * 3 / 4  # base64 string is about 4/3 times the size of the file
                total_size += file_size
                
                if file_size > MAX_IMAGE_SIZE:  # 2MB per image
                    raise ValidationError(
                        "One or more images exceed the maximum allowed size of 2MB. "
                        "Please compress your images before uploading."
                    )
            except Exception as e:
                raise ValidationError(
                    "Error processing image. Please ensure all images are valid and under 2MB in size."
                )
        
        # Check total size
        if total_size > MAX_TOTAL_SIZE:  # 4MB total
            raise ValidationError(
                "Total size of all images exceeds the maximum allowed size of 4MB. "
                "Please reduce the number of images or compress them further."
            )
        
        return content