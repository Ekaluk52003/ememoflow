
from django.db import models
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from .sendEmails import send_reject_email,  send_withdraw_email, send_approval_email



class ApprovalWorkflow(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    allow_custom_approvers = models.BooleanField(default=False)
    # Reject email fields
    send_reject_email = models.BooleanField(default=True, help_text="Send email on document rejection")
    reject_email_subject = models.TextField(blank=True, help_text="Subject for rejection emails")
    reject_email_body = models.TextField(blank=True, help_text="Body template for rejection emails")

    # Withdraw email fields
    send_withdraw_email = models.BooleanField(default=True, help_text="Send email on document withdrawal")
    withdraw_email_subject = models.TextField(blank=True, help_text="Subject for withdrawal emails")
    withdraw_email_body = models.TextField(blank=True, help_text="Body template for withdrawal emails")

    cc_emails = models.TextField(blank=True, help_text="Comma-separated email addresses for CC")

    def __str__(self):
        return self.name

    def get_cc_list(self):
        return [email.strip() for email in self.cc_emails.split(',') if email.strip()]

class DynamicField(models.Model):
    FIELD_TYPES = (
        ('text', 'Text'),
        ('number', 'Number'),
        ('date', 'Date'),
        ('boolean', 'Yes/No'),
        ('choice', 'Multiple Choice'),
    )
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE, related_name='dynamic_fields')
    name = models.CharField(max_length=100)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES)
    required = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)
    choices = models.TextField(blank=True, help_text="Comma-separated choices for 'choice' field type")

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.workflow.name} - {self.name}"



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
    approvers = models.ManyToManyField(CustomUser, related_name='approval_steps', null=True, blank=True)

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

    # Fields for user input
    requires_input = models.BooleanField(default=False)
    input_type = models.CharField(max_length=10, choices=INPUT_TYPES, default='none')
    input_prompt = models.CharField(max_length=255, blank=True)
    input_choices = models.TextField(blank=True, help_text="Comma-separated choices for 'choice' input type")
    allowed_file_extensions = models.CharField(max_length=255, blank=True, help_text="Comma-separated file extensions for 'file' input type")

    # Email notification fields
    send_email = models.BooleanField(default=False)
    email_subject = models.CharField(max_length=255, blank=True)
    email_body_template = models.TextField(blank=True, help_text="Use {document}, {approver}, and {step} as placeholders")
    cc_emails = models.TextField(blank=True, help_text="Comma-separated email addresses for CC")

    class Meta:
        ordering = ['workflow', 'order']

    def get_cc_list(self):
        return [email.strip() for email in self.cc_emails.split(',') if email.strip()]

    def __str__(self):
        return f"{self.workflow.name} - Step {self.order}: {self.name}"

    def clean(self):
        if self.is_conditional and (not self.condition_field or not self.condition_operator or self.condition_value is None):
            raise ValidationError("Conditional steps must have a condition field, operator, and value.")

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
        ordering = ['order']
        unique_together = ['workflow', 'order']

    def __str__(self):
        return f"{self.workflow.name} - {self.name}"

class Document(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('in_review', 'In Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    submitted_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='submitted_documents')
    workflow = models.ForeignKey(ApprovalWorkflow, on_delete=models.CASCADE)
    current_step = models.ForeignKey(ApprovalStep, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_submitted_at = models.DateTimeField(auto_now_add=True)


    def __str__(self):
        return self.title

    def move_to_next_step(self):
        # self.approvals.filter(step=None).delete()

        current_step_order = self.current_step.order
        next_step = ApprovalStep.objects.filter(
            workflow=self.workflow,
            order__gt=current_step_order
        ).order_by('order').first()

        if next_step:
            if next_step.evaluate_condition(self):
                self.current_step = next_step
                self.status = 'in_review'
                approval = self.approvals.get(step=next_step)
                send_approval_email(approval)
            else:
                print('no condition')
                self.status = 'approved'
                self.save()
        else:
            self.status = 'approved'
        self.save()

    def withdraw(self):
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


def user_directory_path(instance, filename):
    # File will be uploaded to MEDIA_ROOT/user_<id>/<filename>
    return f'user_{instance.approver.id}/{filename}'

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


class DynamicFieldValue(models.Model):
    document = models.ForeignKey('Document', on_delete=models.CASCADE, related_name='dynamic_values')
    field = models.ForeignKey('DynamicField', on_delete=models.CASCADE)
    value = models.TextField()

    class Meta:
        unique_together = ('document', 'field')

    def __str__(self):
        return f"{self.document.title} - {self.field.name}: {self.value}"