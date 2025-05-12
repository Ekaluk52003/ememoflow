from django.db import models
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from .sendEmails import send_reject_email, send_withdraw_email, send_approved_document_email
import os
from django.utils import timezone
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.db.models import JSONField
from django.db.models import Q
import logging
logger = logging.getLogger(__name__)
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import Group
from django.contrib.auth import get_user_model
from django_project.storage_backends import CustomS3Storage
custom_storage = CustomS3Storage()

User = get_user_model()


class ReportConfiguration(models.Model):
    company_name = models.CharField(max_length=200)
    company_address = models.TextField()
    company_logo = models.ImageField(upload_to='logo/', storage=custom_storage)
    footer_text = models.TextField()

    @property
    def logo_data_uri(self):
        import base64
        import boto3
        from django.conf import settings
        
        if not self.company_logo:
            return ""
            
        # Create S3 client
        s3_client = boto3.client(
            's3',
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
        )
        
        try:
            # Get the image directly from S3
            response = s3_client.get_object(
                Bucket=settings.AWS_STORAGE_BUCKET_NAME,
                Key=self.company_logo.name
            )
            image_content = response['Body'].read()
            encoded_string = base64.b64encode(image_content).decode()
            return f"data:image/png;base64,{encoded_string}"
        except Exception:
            return ""


class PDFTemplate(models.Model):
    name = models.CharField(max_length=100)
    html_content = models.TextField()
    css_content = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ApprovalWorkflow(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    authorized_groups = models.ManyToManyField(
        Group,
        blank=True,
        related_name='authorized_workflows',
        help_text="Groups that have full access to documents in this workflow"
    )
    # Reject email fields
    content_editor = models.BooleanField(default=False, help_text="Add content editor for document")
    send_reject_email = models.BooleanField(default=True, help_text="Send email on document rejection for all steps")
    reject_email_subject = models.TextField(blank=True, help_text="Subject for rejection emails")
    reject_email_body = models.TextField(blank=True, help_text="Body template for rejection emails")

    # Withdraw email fields
    send_withdraw_email = models.BooleanField(default=True, help_text="Send email on document withdrawal")
    withdraw_email_subject = models.TextField(blank=True, help_text="Subject for withdrawal emails")
    withdraw_email_body = models.TextField(blank=True, help_text="Body template for withdrawal emails")

    # Email notification for all approve
    send_approved_email = models.BooleanField(default=False, help_text="This email is sent to pending approver and requestor when all approvers approve document")
    email_approved_subject = models.CharField(max_length=255, blank=True)
    email_approved_body_template = models.TextField(blank=True, help_text="Use {document}, {approver}, and {step} as placeholders")


    cc_emails = models.TextField(blank=True, help_text="Comma-separated email addresses for CC")

    def __str__(self):
        return self.name

    def get_cc_list(self):
        return [email.strip() for email in self.cc_emails.split(',') if email.strip()]

class DynamicField(models.Model):
    FIELD_TYPES = (
        ('text', 'Text'),
        ('textarea', 'Text Area'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Yes/No'),
        ('choice', 'Single Choice'),
        ('multiple_choice', 'Multiple Choice'),
        ('attachment', 'File Attachment'),
        ('product_list', 'Product List'),
        ('table_list', 'Table List'),
        ('tiptap_editor', 'Rich Text Editor'),
    )

    WIDTH_CHOICES = (
        ('quarter', 'Quarter Width'),
        ('half', 'Half Width'),
        ('three_quarter', 'Three Quarter Width'),
        ('full', 'Full Width'),
    )
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='dynamic_fields')
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    choices = models.TextField(blank=True, help_text="Comma-separated choices for 'choice' field type")

    # New fields for attachment type
    allowed_extensions = models.CharField(max_length=255, blank=True, help_text="Comma-separated list of allowed file extensions (e.g., .pdf,.doc,.jpg)")
    max_file_size = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Maximum file size in MB",
        validators=[MinValueValidator(1)]
    )
    multiple_files = models.BooleanField(default=False, help_text="Allow multiple file uploads for this field")
    textarea_rows = models.PositiveIntegerField(
        default=4,
        help_text="Number of rows for textarea fields",
        validators=[MinValueValidator(1), MaxValueValidator(20)]
    )
    input_width = models.CharField(max_length=15, choices=WIDTH_CHOICES, default='full', help_text="Width of the input field")
    table_columns = models.TextField(blank=True, help_text="Pipe-separated column names for 'table_list' field type (e.g., 'item|name|qty|invoice|reason|credit')")

    class Meta:
        ordering = ['order']

    def clean(self):
        super().clean()
        if self.field_type == 'textarea' and self.textarea_rows < 1:
            raise ValidationError({'textarea_rows': 'Number of rows must be at least 1.'})

    def get_choices(self):
        if self.field_type in ['choice', 'multiple_choice'] and self.choices:
            return [choice.strip() for choice in self.choices.split(',')]
        return []

    def __str__(self):
        return f"{self.workflow.name} - {self.name}"

    def get_allowed_extensions(self):
        if self.allowed_extensions:
            return [ext.strip() for ext in self.allowed_extensions.split(',')]
        return []

    def validate_file(self, file):
        if self.allowed_extensions:
            ext = os.path.splitext(file.name)[1]
            if ext.lower() not in self.get_allowed_extensions():
                raise ValidationError(f"File type {ext} is not allowed. Allowed types are: {self.allowed_extensions}")

        # if self.max_file_size and file.size > self.max_file_size:
        #     raise ValidationError(f"File size exceeds the maximum allowed size of {self.max_file_size} bytes")
        if self.max_file_size:
            max_size_bytes = self.max_file_size * 1024 * 1024  # Convert MB to bytes
            if file.size > max_size_bytes:
                raise ValidationError(f"File size exceeds the maximum allowed size of {self.max_file_size} MB")


class WorkflowSpecificManyToManyField(models.ManyToManyField):
    def formfield(self, **kwargs):
        from django.forms import ModelMultipleChoiceField
        defaults = {
            'form_class': ModelMultipleChoiceField,
            'queryset': self.remote_field.model.objects.none(),
        }
        defaults.update(kwargs)
        return super().formfield(**defaults)


class ApprovalStep(models.Model):
    INPUT_TYPES = (
        ('none', 'No Input Required'),
        ('text', 'Text Input'),
        ('number', 'Number Input'),
        ('date', 'Date Input'),
        ('choice', 'Multiple Choice'),
        ('file', 'File Upload'),  # New file input type
    )

    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='steps')
    name = models.CharField(max_length=100)
    order = models.PositiveIntegerField()
    # approvers = models.ManyToManyField(CustomUser, related_name='approval_steps', null=True, blank=True)
    approvers = models.ManyToManyField(User, related_name='approval_steps', blank=True)
    allow_custom_approver = models.BooleanField(default=False)
    approver_group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    approval_mode = models.CharField(
        max_length=10,
        choices=[('all', 'All Approvers Required'), ('any', 'Any Approver Sufficient')],
        default='all',
        help_text='Determines whether all approvers must approve or any single approver is sufficient'
    )
    # approvers = models.ManyToManyField(User, related_name='approval_steps', blank=True)

    # Fields for conditional logic
    is_conditional = models.BooleanField(default=False)
    move_to_next = models.BooleanField(
        default=True,
        help_text="If True, move to next step. If False, complete workflow after this step."
    )
    condition_field = models.ForeignKey(DynamicField, on_delete=models.SET_NULL, null=True, blank=True)
    condition_operator = models.CharField(max_length=10, choices=[
        ('eq', 'Equals'),
        ('ne', 'Not Equals'),
        ('gt', 'Greater Than'),
        ('lt', 'Less Than'),
        ('gte', 'Greater Than or Equal'),
        ('lte', 'Less Than or Equal'),
    ], null=True, blank=True)
    condition_value = models.CharField(max_length=255, null=True, blank=True)


    # input_type = models.CharField(max_length=10, choices=INPUT_TYPES, default='none')
    # input_choices = models.TextField(blank=True, help_text="Comma-separated choices for 'choice' input type")
    # allowed_file_extensions = models.CharField(max_length=255, blank=True, help_text="Comma-separated file extensions for 'file' input type")
    requires_edit = models.BooleanField(default=False, help_text="Enable approvers to edit field or upload file for particular step")
    editable_fields = models.ManyToManyField(DynamicField, blank=True, related_name='approval_steps')

    # Email notification fields removed - now using workflow-level email settings instead





    class Meta:
        ordering = ['workflow', 'order']


    def get_cc_list(self):
        return [email.strip() for email in self.cc_emails.split(',') if email.strip()]

    def __str__(self):
        return f"{self.workflow.name} - Step {self.order}: {self.name}"


    def evaluate_condition(self, document):
        if not self.is_conditional:
            return True

        dynamic_value = document.dynamic_values.filter(field=self.condition_field).first()
        if not dynamic_value:
            return False

        field_type = self.condition_field.field_type
        actual_value = dynamic_value.value
        condition_value = self.condition_value

        # Handle different field types based on FIELD_TYPES in DynamicField
        if field_type == 'text' or field_type == 'textarea':
            # Direct string comparison for text fields
            return self._compare_values(str(actual_value), str(condition_value))

        elif field_type == 'number':
            try:
                actual_value = float(actual_value)
                condition_value = float(condition_value)
                return self._compare_values(actual_value, condition_value)
            except (ValueError, TypeError):
                return False

        elif field_type == 'boolean':
            # Convert checkbox value to boolean
            actual_bool = actual_value == 'on'
            condition_bool = condition_value == 'on'
            return self._compare_values(actual_bool, condition_bool)

        elif field_type == 'choice':
            # Single choice comparison - direct string comparison
            actual_value = str(actual_value).strip()
            condition_value = str(condition_value).strip()
            return self._compare_values(actual_value, condition_value)

        elif field_type == 'multiple_choice':
            # Convert to sets for comparison, ignoring empty strings and whitespace
            actual_set = set(choice.strip() for choice in actual_value.split(',') if choice.strip())
            condition_set = set(choice.strip() for choice in condition_value.split(',') if choice.strip())

            if self.condition_operator in ['eq', 'ne']:
                # For eq/ne, compare the exact sets
                result = actual_set == condition_set
                return result if self.condition_operator == 'eq' else not result
            else:
                # For other operators, compare the number of selections
                return self._compare_values(len(actual_set), len(condition_set))

        return False

    def _compare_values(self, actual, condition):
        """Helper method to compare values based on the condition operator"""
        if self.condition_operator == 'eq':
            return actual == condition
        elif self.condition_operator == 'ne':
            return actual != condition
        elif self.condition_operator == 'gt':
            return actual > condition
        elif self.condition_operator == 'lt':
            return actual < condition
        elif self.condition_operator == 'gte':
            return actual >= condition
        elif self.condition_operator == 'lte':
            return actual <= condition
        return False

    class Meta:
        ordering = ['workflow', 'order']
        unique_together = ['workflow', 'order']

    def __str__(self):
        return f"{self.workflow.name} - {self.name}"

    def clean(self):
        if self.allow_custom_approver and not self.approver_group:
            raise ValidationError("Approver group must be set when custom approver is allowed.")


class ReferenceID(models.Model):
    year = models.IntegerField()
    last_number = models.IntegerField(default=0)

    @classmethod
    def get_next_reference(cls):
        from datetime import datetime
        current_year = int(datetime.now().year % 100)  # Get last two digits of current year

        # Get or create reference for the current year
        reference, created = cls.objects.get_or_create(year=current_year)

        # Increment the last number and format it
        reference.last_number += 1
        reference.save()

        # Return the new reference in the format YYNNN
        return f"{str(current_year).zfill(2)}{str(reference.last_number).zfill(5)}"

def editor_image_path(instance, filename):
    if instance.document and instance.document.document_reference:
        return f'documents/{instance.document.document_reference}/{filename}'
    else:
        # For images that don't have a document yet, use a temporary path
        # They will be moved to the correct location once the document is created
        return f'documents/temp/{filename}'

class EditorImage(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='editor_images', null=True)
    image = models.ImageField(upload_to=editor_image_path, storage=custom_storage)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    base_url = models.TextField(blank=True)

    def __str__(self):
        return f"Image for {self.document.document_reference if self.document and self.document.document_reference else 'new document'}"
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)  # Save first to ensure we have an ID
        if self.image and not self.base_url:
            # Set the base URL for referencing in HTML content
            self.base_url = f"/document/view-editor-image/{self.id}/"
            # Update with the base URL without triggering save() recursion
            EditorImage.objects.filter(id=self.id).update(base_url=self.base_url)
    
    @property
    def url(self):
        return self.base_url
    
    def delete(self, *args, **kwargs):
        # First delete the image file from storage
        if self.image:
            # Delete from storage
            self.image.delete(save=False)
        # Then delete the model instance
        super().delete(*args, **kwargs)
    
    def has_access(self, user):
        """Check if user has access to this image"""
        from .utils import get_allowed_document
        
        # If the image doesn't have a document yet, allow access
        # This is needed for images pasted into the editor before the form is submitted
        # if not self.document:
        #     return True
            
        # Otherwise, check if the user has access to the document
        document = get_allowed_document(user, self.document.document_reference)
        return document is not None and not isinstance(document, HttpResponse)



class Document(models.Model):
    STATUS_CHOICES = [
        ('cancel', 'Cancel'),
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    document_reference = models.CharField(max_length=7, unique=True, blank=True, null=True)
    title = models.CharField(max_length=200)
    content = models.TextField(null=True, blank=True)
    submitted_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='submitted_documents')
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE)
    current_step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    # important a lot mill
    last_submitted_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # First save to ensure we have a document_reference
        if not self.document_reference:
            self.document_reference = ReferenceID.get_next_reference()
        
        # Save document first to ensure it exists in database
        super().save(*args, **kwargs)
        
        # Then process images if there's content
        if self.content:
            import re
            import base64
            from django.core.files.base import ContentFile
            
            # Find all current image URLs in the content
            url_pattern = r'src="(/document/view-editor-image/\d+/)"'
            current_image_urls = set(re.findall(url_pattern, self.content))
            
            # Delete images that are no longer in the content
            for editor_image in self.editor_images.all():
                if editor_image.base_url not in current_image_urls:
                    editor_image.delete()  # This will delete both DB record and S3 file
            
            # Process new base64 images
            pattern = r'src="data:image/([a-zA-Z]+);base64,([^"]+)"'
            matches = re.finditer(pattern, self.content)
            content_updated = False
            processed_images = set()
        
            for match in matches:
                img_type = match.group(1).lower()  # Get the image type (png, jpeg, etc)
                base64_data = match.group(2)
                data_url = f'data:image/{img_type};base64,{base64_data}'
        
                if base64_data in processed_images:
                    continue
                    
                try:
                    image_data = base64.b64decode(base64_data)
                    file_content = ContentFile(image_data)
                    
                    # Create EditorImage instance
                    editor_image = EditorImage.objects.create(document=self)
                    
                    # Use proper extension based on image type
                    ext = 'jpg' if img_type in ['jpg', 'jpeg'] else img_type
                    filename = f'image.{ext}'
                    editor_image.image.save(filename, file_content, save=True)
                    
                    # The base_url is now automatically set in EditorImage.save()
                    image_url = editor_image.url
                    
                    # Replace the entire data URL with the base image URL
                    self.content = self.content.replace(data_url, image_url)
                    content_updated = True
                    processed_images.add(base64_data)
                except Exception as e:
                    logger.error(f"Error processing image: {str(e)}")
        
            # Only save again if we updated the content with image URLs
            if content_updated:
                super().save(update_fields=['content'])

    def is_favorited_by(self, user):
        return self.favorites.filter(user=user).exists()

    def resubmit(self, title, content):
        self.title = title
        self.content = content
        # self.status = 'in_review'
        # self.current_step = None
        self.last_submitted_at = timezone.now()
        self.approvals.filter(is_approved__isnull=True).delete()
        self.save()

    def create_approvals(self, custom_approvers=None):
        approvals_created = []
        last_conditional_step = None

        for step in self.workflow.steps.all():
            # Check if step condition is met
            if step.evaluate_condition(self):
                if step.allow_custom_approver and custom_approvers and step.id in custom_approvers:
                    approval = Approval.objects.create(
                        document=self,
                        step=step,
                        approver=custom_approvers[step.id]
                    )
                    approvals_created.append(approval)
              
                else:
                    for approver in step.approvers.all():
                        approval = Approval.objects.create(
                            document=self,
                            step=step,
                            approver=approver
                        )
                        approvals_created.append(approval)
                  

                # If this step has conditions and they're met, store it
                if step.is_conditional:
                    last_conditional_step = step

                # Only break if this is the conditional step that was met
                # and it's marked as not moving to next
                if step.is_conditional and not step.move_to_next:
                    break
            else:
                # If condition not met, continue creating next steps
                continue

        if approvals_created:
            # If we have a conditional step that was met and doesn't move to next,
            # filter out any approvals after that step
            if last_conditional_step and not last_conditional_step.move_to_next:
                approvals_created = [
                    approval for approval in approvals_created
                    if approval.step.order <= last_conditional_step.order
                ]

            
            self.status = 'in_review'
            self.current_step = approvals_created[0].step
            self.save()
            
            # Set can_approveAt for initial approvals of the first step
            current_time = timezone.now()
            first_step_approvals = [a for a in approvals_created if a.step == self.current_step]
            for approval in first_step_approvals:
                approval.can_approveAt = current_time
                approval.save(update_fields=['can_approveAt'])
                
            send_approved_document_email(approvals_created[0].document, approvals_created[0], status='pending')

        return approvals_created


    def handle_approval(self, user, is_approved, comment, uploaded_files, edited_values=None,):
        # TODO: Validate if user is the current approver

        approval = self.approvals.get(approver=user, step=self.current_step, is_approved__isnull=True)


        approval.is_approved = is_approved
        # Set the status field based on the is_approved value
        if is_approved:
            approval.status = 'approved'
        elif is_approved is False:  # Explicitly rejected
            approval.status = 'rejected'
        approval.comment = comment
        approval.recorded_at = timezone.now()


        if self.current_step.requires_edit:
                for field in self.current_step.editable_fields.all():
                    field_name = f'dynamic_{field.id}'
                    if field.field_type == 'attachment' and field_name in uploaded_files:
                        file = uploaded_files[field_name]
                        try:
                            field.validate_file(file)
                            DynamicFieldValue.objects.update_or_create(
                                document=self,
                                field=field,
                                defaults={'file': file}
                            )
                        except ValidationError as ve:
                            raise ValidationError(f"Error with {field.name}: {ve}")
                    elif field_name in edited_values:
                        DynamicFieldValue.objects.update_or_create(
                            document=self,
                            field=field,
                            defaults={'value': edited_values[field_name]}
                        )

        approval.save()


        if is_approved:
            # Check if we should move to the next step based on approval mode
            current_step = self.current_step
            
            if current_step.approval_mode == 'any':
                # If 'any approver' mode, we can move to the next step immediately
                # Cancel all other pending approvals for this step
                other_pending_approvals = self.approvals.filter(
                    step=current_step,
                    is_approved__isnull=True
                ).exclude(pk=approval.pk)
                
                # Delete other pending approvals instead of marking them as cancelled
                other_pending_approvals.delete()
                
                # Move to the next step
                self.move_to_next_step(approval)
            else:  # 'all' mode (default)
                # Check if all approvers have approved
                pending_approvals = self.approvals.filter(
                    step=current_step,
                    is_approved__isnull=True
                ).exists()
                
                # If no pending approvals remain, move to the next step
                if not pending_approvals:
                    self.move_to_next_step(approval)
        else:
            self.reject()
        return approval

    def can_withdraw(self, user):
        return (
            self.status == 'in_review' and
            self.submitted_by == user and
            not self.approvals.filter(is_approved__isnull=False, created_at__gt=self.last_submitted_at).exists()
        )

    def can_cancel(self, user):
        return (
            self.status == 'pending' or self.status == 'rejected' and
            self.submitted_by == user
        )

# The move_to_next_step method now uses a while loop to continue checking steps until either:

# A valid next step is found (conditions met)
# There are no more steps (document is approved)
# A step's conditions are not met (skip to next step)

# When a step's conditions are not met, it continues the loop to check the next step instead of immediately approving the document.

    def move_to_next_step(self, approval):
        current_step = approval.step

        # If current step condition met and move_to_next is False, complete workflow
        if current_step.evaluate_condition(self) and not current_step.move_to_next:            
            self.status = 'approved'
            self.save()
            send_approved_document_email(self, status='approved')
            return

        next_step = ApprovalStep.objects.filter(
            workflow=self.workflow,
            order__gt=approval.step.order
        ).order_by('order').first()

        if not next_step:
            # No more steps, document is approved
            self.status = 'approved'
            self.save()
            send_approved_document_email(self, status='approved')
            return

        if next_step.evaluate_condition(self):
            # Condition met, move to this step
            self.current_step = next_step
            self.status = 'in_review'
            self.save()

            # Send approval emails for the next step
            approvals = self.approvals.filter(step=next_step)
            current_time = timezone.now()
            for appr in approvals:
                # Set the can_approveAt timestamp
                appr.can_approveAt = current_time
                appr.save(update_fields=['can_approveAt'])
                send_approved_document_email(appr.document, appr, status='pending')
        else:
            # If condition not met for next step, recursively try next step
            dummy_approval = type('obj', (object,), {'step': next_step})()
            self.move_to_next_step(dummy_approval)

    def withdraw(self):
         #allow to withdraw for all next cycle if is_approved is null in next cycle
        if self.status != 'in_review' or self.approvals.filter(is_approved__isnull=False, created_at__gt=self.last_submitted_at).exists():
            raise ValidationError("This document cannot be withdrawn.")
        
        #send email before changing status
        send_withdraw_email(self)
        
        self.status = 'pending'
        self.current_step = None
        self.save()
        # Delete only the approvals from the current review cycle
        self.approvals.filter(created_at__gt=self.last_submitted_at).delete()


       # Delete only the approvals from the current review cycle
        self.approvals.filter(created_at__gt=self.last_submitted_at).delete()


    def reject(self):
        self.status = 'rejected'
        self.save()
        send_reject_email(self)

    def cancel(self):
        self.status = 'cancel'
        self.save()

    def save_draft(self):
        self.status = 'pending'
        self.current_step = None
        self.save()

    def get_current_approver(self):
        if not self.current_step:
            return None
        current_approval = self.approvals.filter(step=self.current_step, is_approved__isnull=True).first()
        return current_approval.approver if current_approval else None

    def get_rejector(self):
        # Find the most recent rejection
        rejection = self.approvals.filter(
            step=self.current_step,
            is_approved=False
        ).order_by('-updated_at').first()
        return rejection.approver if rejection else None

    def get_report_context(self):
        return {
            'document': self,
            'dynamic_fields': self.dynamic_values.all().select_related('field'),
            'approvals': self.approvals.all().select_related('step', 'approver').order_by('step__order'),
            'current_step': self.current_step,
            'workflow': self.workflow,
        }


    def get_dynamic_field_value(self, field_name):
        try:
            dynamic_field = self.workflow.dynamic_fields.get(name=field_name)
            value = self.dynamic_values.get(field=dynamic_field)
            if dynamic_field.field_type == 'product_list':
                return value.json_value
            return value.value
        except (DynamicField.DoesNotExist, DynamicFieldValue.DoesNotExist):
            return None


def user_directory_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.approver.id}/{filename}'

class Favorite(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='favorites')
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='favorites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'document')

class Approval(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('cancelled', 'Cancelled')
    )
    
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='approvals')
    step = models.ForeignKey(ApprovalStep, on_delete=models.CASCADE)
    approver = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    on_behalf_of = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='delegated_approvals', null=True, blank=True,
                                    help_text="If this approval was done on behalf of another user, this field indicates who")
    is_approved = models.BooleanField(null=True, default=None)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recorded_at = models.DateTimeField(null=True)
    can_approveAt = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the user became eligible to approve this document")

    def __str__(self):
        return f"{self.document.title} - {self.step.name} - {self.approver.username}"


    # class Meta:
    #     # This constraint ensures uniqueness, but it might not be enforced if it was added after data was inserted
    #     unique_together = ['document', 'step', 'approver', 'is_approved']


def dynamic_field_file_path(instance, filename):
    # return f'documents/{instance.document.id}/dynamic_fields/{filename}'

    return f'documents/{instance.document.document_reference}/{filename}'





def dynamic_file_upload_path(instance, filename):
    return custom_storage.generate_path(instance, filename)



from django.http import HttpResponse
class DynamicFieldValue(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='dynamic_values')
    field = models.ForeignKey('DynamicField', on_delete=models.CASCADE)
    value = models.TextField()
    file = models.FileField(storage=custom_storage, upload_to=dynamic_field_file_path, blank=True,
        null=True)
    json_value = JSONField(default=list, blank=True)


    @classmethod
    def update_or_create_values(cls, document, dynamic_fields, post_data):
        for field in dynamic_fields:
            value = post_data.get(f'dynamic_{field.id}')
            if field.required and not value:
                raise ValidationError(f"{field.name} is required.")
            cls.objects.update_or_create(
                document=document,
                field=field,
                defaults={'value': value or ''}
            )

    def has_access(self, user):
        """Check if user has access to this field value"""
        from .utils import get_allowed_document
        document = get_allowed_document(user, self.document.document_reference)
        return document is not None and not isinstance(document, HttpResponse)

    class Meta:
        unique_together = ('document', 'field')

    def __str__(self):

        if self.field.field_type == 'attachment':
            return f"{self.document.title} - {self.field.name}: {self.file.name if self.file else 'No file'}"
        if self.field.field_type == 'product_list':
            return f"{self.document.title} - {self.field.name}: {len(self.json_value)} product"

        return f"{self.document.title} - {self.field.name}: {self.value}"

    def clean(self):
        super().clean()
        if self.field.field_type == 'attachment' and self.file:
            self.field.validate_file(self.file)

    def get_value(self):
        if self.field.field_type == 'product_list':
            return self.json_value
        return self.value

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
        
        # Process base64 images in tiptap_editor fields
        if self.field.field_type == 'tiptap_editor' and self.value:
            import re
            import base64
            from django.core.files.base import ContentFile
            
            # Find all current image URLs in the content
            url_pattern = r'src="(/document/view-editor-image/\d+/)"'
            current_image_urls = set(re.findall(url_pattern, self.value))
            
            # Process new base64 images
            pattern = r'src="data:image/([a-zA-Z]+);base64,([^"]+)"'
            matches = re.finditer(pattern, self.value)
            content_updated = False
            processed_images = set()
        
            for match in matches:
                img_type = match.group(1).lower()  # Get the image type (png, jpeg, etc)
                base64_data = match.group(2)
                data_url = f'data:image/{img_type};base64,{base64_data}'
        
                if base64_data in processed_images:
                    continue
                    
                try:
                    image_data = base64.b64decode(base64_data)
                    file_content = ContentFile(image_data)
                    
                    # Create EditorImage instance
                    editor_image = EditorImage.objects.create(document=self.document)
                    
                    # Use proper extension based on image type
                    ext = 'jpg' if img_type in ['jpg', 'jpeg'] else img_type
                    filename = f'dynamic_field_{self.field.id}_image.{ext}'
                    editor_image.image.save(filename, file_content, save=True)
                    
                    # Get the image URL
                    image_url = editor_image.url
                    
                    # Replace the entire data URL with the base image URL
                    self.value = self.value.replace(data_url, image_url)
                    content_updated = True
                    processed_images.add(base64_data)
                except Exception as e:
                    logger.error(f"Error processing image in dynamic field: {str(e)}")
            
            # Only save again if we updated the content with image URLs
            if content_updated:
                # Use update to avoid recursion
                DynamicFieldValue.objects.filter(id=self.id).update(value=self.value)
