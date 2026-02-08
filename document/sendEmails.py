from django.core.mail import EmailMultiAlternatives
from django.template import Template, Context
from django.utils.html import strip_tags
from django.conf import settings
import logging
import os
from django.template import Template, Context, TemplateSyntaxError
from django.urls import reverse
from .notification_service import send_approval_notification

logger = logging.getLogger(__name__)


def send_templated_email(subject_template, body_template, context_dict, recipient_list, cc_list=None, attachments=None, async_mode=True):
    """
    Send a templated email with optional attachments
    Args:
        subject_template: Template string for email subject
        body_template: Template string for email body
        context_dict: Dictionary of context variables for template rendering
        recipient_list: List of recipient email addresses
        cc_list: Optional list of CC email addresses
        attachments: Optional list of attachments (filename, content, mimetype)
        async_mode: If True, sends email asynchronously using Celery. If False, sends synchronously.
    Returns:
        If async_mode=True: Celery AsyncResult
        If async_mode=False: bool indicating success/failure
    """
    from document.tasks import send_templated_email_task, _serialize_context
    
    # Serialize context data for Celery
    serialized_context = _serialize_context(context_dict)
    
    if async_mode:
        # Use Celery task for asynchronous processing
        return send_templated_email_task.delay(
            subject_template,
            body_template,
            serialized_context,
            recipient_list,
            cc_list,
            attachments
        )
    
    # Call the task function directly for synchronous processing
    result = send_templated_email_task(
        subject_template,
        body_template,
        serialized_context,
        recipient_list,
        cc_list,
        attachments
    )
    return result.get('status') == 'success'


def send_reject_email(document):
    print('send email reject')
    workflow = document.workflow
    if not workflow.send_reject_email:

        return False

    rejector = document.get_rejector()
    context = {
        'document': document,
        'submitted_by': document.submitted_by,
        'rejector': rejector,
        'workflow': workflow,
    }
    recipient_list = [document.submitted_by.email]
    # cc_list = workflow.get_cc_list()
    cc_list = []

    return send_templated_email(
        workflow.reject_email_subject,
        workflow.reject_email_body,
        context,
        recipient_list,
        cc_list
    )


def send_void_email(document, voided_by):
    print('send email void')
    workflow = document.workflow
    if not workflow.send_reject_email:
        return False

    context = {
        'document': document,
        'submitted_by': document.submitted_by,
        'rejector': voided_by, # Using rejector context variable to match reject template
        'voider': voided_by,   # Adding specific voider context just in case
        'workflow': workflow,
        'reason': document.void_reason,
    }
    recipient_list = [document.submitted_by.email]
    # cc_list = workflow.get_cc_list()
    cc_list = []

    # Reuse reject email templates but maybe prefix subject or just use them as is since void is similar to reject
    # If we want specific void templates we would need to add them to ApprovalWorkflow model
    # For now, reusing reject templates as requested "apply the same case for void"
    
    return send_templated_email(
        workflow.reject_email_subject,
        workflow.reject_email_body,
        context,
        recipient_list,
        cc_list
    )


def send_withdraw_email(document):
    print('send email withdraw')
    workflow = document.workflow
    if not workflow.send_withdraw_email:
        logger.info(f"Withdraw email sending is disabled for document {document.id}")
        return False

    current_approver = document.get_current_approver()
    if not current_approver:
        logger.info(f"No current approver found for document {document.id}")
        return False

    logger.info(f"Sending withdraw email for document {document.id} to approver {current_approver.email}")
    
    context = {
        'document': document,
        'withdrawer': document.submitted_by,
        'workflow': workflow,
        'approver': current_approver,
    }

    recipient_list = [current_approver.email]
    # cc_list = workflow.get_cc_list()
    cc_list = []

    logger.info(f"Using email templates - Subject: {workflow.withdraw_email_subject}, Body: {workflow.withdraw_email_body}")

    return send_templated_email(
        workflow.withdraw_email_subject,
        workflow.withdraw_email_body,
        context,
        recipient_list,
        cc_list
    )


#for sending email when document is approved
def send_approved_document_email(document, approval=None, status=None):
    """
    Combined function to handle both approval request emails and approved notification emails
    
    Args:
        document: Document instance
        approval: Approval instance (optional, only for approval request emails)
        status: Document status (optional, defaults to document.status if not provided)
    
    Returns:
        Task result or None
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Determine the status if not explicitly provided
    if status is None and document:
        status = document.status
    
    # Handle approved email with PDF generation
    if status == 'approved':
        try:
            from celery import chain
            from document.tasks import (
                generate_pdf_task,
                send_approved_email_with_pdf_task,
                send_approval_notification_task
            )
            
            workflow = document.workflow
            if not workflow.send_approved_email:
                # If approved email is disabled, only send approval notifications
                return send_approval_notification_task.delay(None, document.id)

            # Create a chain of tasks:
            # 1. Generate PDF
            # 2. Send approved email with the generated PDF
            # 3. Send approval notifications
            task_chain = chain(
                generate_pdf_task.s(document.id),
                send_approved_email_with_pdf_task.s(document.id),
                send_approval_notification_task.s(document.id)
            )
            
            # Execute the chain
            return task_chain()
            
        except Exception as e:
            logger.error(f"Error initiating approved email chain: {str(e)}")
            raise
    
    # Handle pending approval email
    elif status == 'pending' and approval:
        try:
            workflow = document.workflow
            if not workflow.send_approved_email:  # Using the same setting as approved emails
                logger.info(
                    f"Email sending is disabled for document {document.id}"
                )
                return
                
            context_dict = {
                'document': document,
                'approver': approval.approver,
                'step': approval.step,
                'workflow': workflow,
            }

            # Get email templates from workflow instead of step
            subject_template = workflow.email_approved_subject
            body_template = workflow.email_approved_body_template

            # Get CC list from workflow
            # cc_list = workflow.get_cc_list()
            cc_list = []
            
            # Get list of recipients (primary approver + authorized users)
            recipients = [approval.approver.email]
            
            # Add authorized users who can approve on behalf of this approver
            from .models_authorization import ApprovalAuthorization
            from django.utils import timezone
            
            now = timezone.now()
            authorized_users = ApprovalAuthorization.objects.filter(
                authorizer=approval.approver,
                valid_from__lte=now,
                valid_until__gte=now,
                is_active=True
            )
            
            # Create a serializable list of authorized user info
            authorized_user_info = []
            
            for auth in authorized_users:
                if auth.authorized_user.email and auth.authorized_user.email not in recipients:
                    recipients.append(auth.authorized_user.email)
                    # Add serializable user info (not the actual User object)
                    authorized_user_info.append({
                        'id': auth.authorized_user.id,
                        'username': auth.authorized_user.username,
                        'email': auth.authorized_user.email,
                        'full_name': auth.authorized_user.get_full_name() or auth.authorized_user.username
                    })
            
            # Only add to context if we have authorized users
            if authorized_user_info:
                context_dict['authorized_users'] = authorized_user_info
            
            # Send email using the common function
            success = send_templated_email(
                subject_template,
                body_template,
                context_dict,
                recipients,
                cc_list
            )

            if success:
                logger.info(
                    f"Approval email sent for document {approval.document.id} to {approval.approver.email}"
                )
            else:
                logger.error(
                    f"Failed to send approval email for document {approval.document.id}"
                )

        except Exception as e:
            logger.error(
                f"Error in send_approval_email for document {approval.document.id}: {str(e)}"
            )
    
    else:
        logger.warning(f"Invalid status '{status}' or missing required parameters for document email")


# Legacy functions removed - using combined function directly


def _generate_pdf_content(document):
    """
    Internal function to generate PDF content
    Args:
        document: Document instance
    Returns:
        BytesIO: PDF content or None if generation fails
    """
    from document.views import generate_pdf_report
    from django.http import HttpResponse
    from io import BytesIO
    from document.models import PDFTemplate
    from django.conf import settings

    try:
        # Get the default template
        template = PDFTemplate.objects.first()
        if not template:
            return None

        # Create a mock request object with user and build_absolute_uri method
        class MockRequest:
            def __init__(self, user):
                self.user = user
                self.scheme = 'http'
                self.META = {'HTTP_HOST': os.environ.get('DOMAIN', 'localhost:8000')}

            def build_absolute_uri(self, path=''):
                return f"{self.scheme}://{self.META['HTTP_HOST']}{path}"

        mock_request = MockRequest(document.submitted_by)
        
        # Call generate_pdf_report
        response = generate_pdf_report(mock_request, document.document_reference, template.id)
        
        if isinstance(response, HttpResponse):
            # Get the content from the response
            pdf_content = BytesIO(response.content)
            pdf_content.seek(0)
            return pdf_content
            
        return None

    except Exception as e:
        print(f"Error generating PDF: {str(e)}")
        return None

def generate_email_pdf(document, async_mode=True):
    """
    Generate PDF for a document, with option for synchronous or asynchronous processing
    Args:
        document: Document instance to generate PDF for
        async_mode: If True, uses Celery task for async processing. If False, generates PDF synchronously
    Returns:
        If async_mode=True: Celery AsyncResult object
        If async_mode=False: BytesIO object containing PDF or None if generation fails
    """
    from document.tasks import generate_pdf_task

    if async_mode:
        # Use Celery task for asynchronous processing
        return generate_pdf_task.delay(document.id)

    # Generate PDF synchronously
    return _generate_pdf_content(document)
