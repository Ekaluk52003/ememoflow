
from django.db import models
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from .sendEmails import send_reject_email,  send_withdraw_email, send_approval_email, send_approved_email
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

User = get_user_model()

class ReportConfiguration(models.Model):
    company_name = models.CharField(max_length=200)
    company_address = models.TextField()
    company_logo = models.ImageField(upload_to='report_logos/', storage=FileSystemStorage(location=settings.MEDIA_ROOT))
    footer_text = models.TextField()

    @property
    def logo_data_uri(self):
        import base64
        with open(self.company_logo.path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        return f"data:image/png;base64,{encoded_string}"

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
    # allow_custom_approvers = models.BooleanField(default=False)
    # Reject email fields
    send_reject_email = models.BooleanField(default=True, help_text="Send email on document rejection")
    reject_email_subject = models.TextField(blank=True, help_text="Subject for rejection emails")
    reject_email_body = models.TextField(blank=True, help_text="Body template for rejection emails")

    # Withdraw email fields
    send_withdraw_email = models.BooleanField(default=True, help_text="Send email on document withdrawal")
    withdraw_email_subject = models.TextField(blank=True, help_text="Subject for withdrawal emails")
    withdraw_email_body = models.TextField(blank=True, help_text="Body template for withdrawal emails")

    # Email notification for all approve
    send_approved_email = models.BooleanField(default=False)
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
    )

    WIDTH_CHOICES = (
        ('half', 'Half Width'),
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
    input_width = models.CharField(max_length=4, choices=WIDTH_CHOICES, default='full', help_text="Width of the input field")

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
    # approvers = models.ManyToManyField(User, related_name='approval_steps', blank=True)

    # Fields for conditional logic
    is_conditional = models.BooleanField(default=False)
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


    input_type = models.CharField(max_length=10, choices=INPUT_TYPES, default='none')
    input_choices = models.TextField(blank=True, help_text="Comma-separated choices for 'choice' input type")
    allowed_file_extensions = models.CharField(max_length=255, blank=True, help_text="Comma-separated file extensions for 'file' input type")
    requires_edit = models.BooleanField(default=False)
    editable_fields = models.ManyToManyField(DynamicField, blank=True, related_name='approval_steps')

    # Email notification fields
    send_email = models.BooleanField(default=False)
    email_subject = models.CharField(max_length=255, blank=True)
    email_body_template = models.TextField(blank=True, help_text="Use {document}, {approver}, and {step} as placeholders")
    cc_emails = models.TextField(blank=True, help_text="Comma-separated email addresses for CC for")





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

        actual_value = dynamic_value.value
        condition_value = self.condition_value

        if self.condition_field.field_type == 'number':
            try:
                actual_value = float(actual_value)
                condition_value = float(condition_value)
            except ValueError:
                return False

        if self.condition_operator == 'eq':
            return actual_value == condition_value
        elif self.condition_operator == 'ne':
            return actual_value != condition_value
        elif self.condition_operator == 'gt':
            return actual_value > condition_value
        elif self.condition_operator == 'lt':
            return actual_value < condition_value
        elif self.condition_operator == 'gte':
            return actual_value >= condition_value
        elif self.condition_operator == 'lte':
            return actual_value <= condition_value

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
    content = models.TextField()
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
        if not self.document_reference:
            # Fetch the reference from the Reference table (explained below)
            self.document_reference = ReferenceID.get_next_reference()
        super().save(*args, **kwargs)

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
        for step in self.workflow.steps.all():
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

        if approvals_created:
            send_approval_email(approvals_created[0])
            self.status = 'in_review'
            self.current_step = approvals_created[0].step
            self.save()

        return approvals_created

    def handle_approval(self, user, is_approved, comment, uploaded_files, edited_values=None,):

        approval = self.approvals.get(approver=user, step=self.current_step, is_approved__isnull=True)


        approval.is_approved = is_approved
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
            self.status == 'pending' and
            self.submitted_by == user
        )


    def move_to_next_step(self, approval):
    # Determine the next step based on the current approval's step
        next_step = ApprovalStep.objects.filter(
            workflow=self.workflow,
            order__gt=approval.step.order  # Use the order from the current approval's step
        ).order_by('order').first()

        if next_step:
            if next_step.evaluate_condition(self):
                print('next step true ?', next_step)
                self.current_step = next_step
                self.status = 'in_review'
                self.save()

                # Send approval emails for the next step
                approvals = self.approvals.filter(step=next_step)
                for appr in approvals:
                    send_approval_email(appr)
            else:
                send_approved_email(self)
                self.status = 'approved'
                self.save()
        else:
            send_approved_email(self)
            self.status = 'approved'

        self.save()

    def withdraw(self):
         #allow to withdraw for all next cycle if is_approved is null in next cycle
        if self.status != 'in_review' or self.approvals.filter(is_approved__isnull=False, created_at__gt=self.last_submitted_at).exists():
            raise ValidationError("This document cannot be withdrawn.")
        #send email before change systus
        send_withdraw_email(self)
        self.status = 'pending'
        self.current_step = None
        self.save()


       # Delete only the approvals from the current review cycle
        self.approvals.filter(created_at__gt=self.last_submitted_at).delete()


    def reject(self):
        self.status = 'rejected'
        self.save()
        send_reject_email(self)

    def cancel(self):
        self.status = 'cancel'
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
    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='approvals')
    step = models.ForeignKey(ApprovalStep, on_delete=models.CASCADE)
    approver = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    is_approved = models.BooleanField(null=True, default=None)
    comment = models.TextField(blank=True)
    user_input = models.TextField(blank=True)
    uploaded_file = models.FileField(upload_to=user_directory_path, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    recorded_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.document.title} - {self.step.name} - {self.approver.username}"


    # class Meta:
    #     # This constraint ensures uniqueness, but it might not be enforced if it was added after data was inserted
    #     unique_together = ['document', 'step', 'approver', 'is_approved']


def dynamic_field_file_path(instance, filename):
    return f'documents/{instance.document.id}/dynamic_fields/{filename}'

class DynamicFieldValue(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='dynamic_values')
    field = models.ForeignKey('DynamicField', on_delete=models.CASCADE)
    value = models.TextField()
    file = models.FileField(upload_to=dynamic_field_file_path, blank=True, null=True)
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