from celery import shared_task
import logging
from .models import DynamicFieldValue, Document, ApprovalWorkflow, ApprovalStep, Approval
from .sendEmails import _generate_pdf_content, send_templated_email
from io import BytesIO
from django_project.celery import app
import tempfile
import os

# Set up logger
logger = logging.getLogger(__name__)

def _serialize_document(document):
    """Helper function to serialize document data"""
    return {
        'id': document.id,
        'document_reference': document.document_reference,
        'submitted_by_id': document.submitted_by.id,
        'workflow_id': document.workflow.id if document.workflow else None
    }

def _serialize_context(context_dict):
    """Helper function to serialize context data"""
    serialized = context_dict.copy()
    if 'document' in serialized:
        serialized['document_data'] = _serialize_document(serialized['document'])
        del serialized['document']
    if 'submitted_by' in serialized:
        serialized['submitted_by_id'] = serialized['submitted_by'].id
        del serialized['submitted_by']
    if 'workflow' in serialized:
        serialized['workflow_id'] = serialized['workflow'].id
        del serialized['workflow']
    if 'approval' in serialized:
        serialized['approval_id'] = serialized['approval'].id
        del serialized['approval']
    if 'step' in serialized:
        serialized['step_id'] = serialized['step'].id
        del serialized['step']
    if 'approver' in serialized:
        serialized['approver_id'] = serialized['approver'].id
        del serialized['approver']
    return serialized

@app.task(name='document.tasks.generate_pdf_task')
def generate_pdf_task(document_id):
    """
    Celery task to generate PDF asynchronously and store it temporarily
    Args:
        document_id: ID of the document to generate PDF for
    Returns:
        dict: Status and result of PDF generation
    """
    try:
        # Get document instance
        document = Document.objects.get(id=document_id)
        
        # Generate PDF using internal function
        pdf_content = _generate_pdf_content(document)
        
        if pdf_content:
            # Create a temporary file to store the PDF
            temp_dir = tempfile.gettempdir()
            temp_path = os.path.join(temp_dir, f"doc_{document_id}_temp.pdf")
            
            # Write PDF content to temporary file
            with open(temp_path, 'wb') as temp_file:
                temp_file.write(pdf_content.getvalue())
            
            # Return success with path to temporary file
            return {
                'status': 'success',
                'message': f'PDF generated successfully for document {document_id}',
                'document_reference': document.document_reference,
                'temp_pdf_path': temp_path
            }
        else:
            return {
                'status': 'error',
                'message': f'Failed to generate PDF for document {document_id}'
            }
            
    except Document.DoesNotExist:
        logger.error(f"Document with ID {document_id} not found")
        return {
            'status': 'error',
            'message': f'Document with ID {document_id} not found'
        }
    except Exception as e:
        logger.error(f"Error generating PDF for document {document_id}: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error generating PDF: {str(e)}'
        }

@app.task(name='document.tasks.send_approved_email_with_pdf_task')
def send_approved_email_with_pdf_task(pdf_result, document_id):
    """
    Celery task to send approved email with PDF attachment
    Args:
        pdf_result: Result from generate_pdf_task
        document_id: Document ID
    """
    logger = logging.getLogger(__name__)
    temp_path = None
    
    try:
        document = Document.objects.get(id=document_id)
        workflow = document.workflow
        
        if not workflow.send_approved_email:
            logger.info(f"Approved email sending is disabled for document {document_id}")
            return {
                'status': 'skipped',
                'message': 'Email sending is disabled'
            }
        
        context = {
            'document': document,
            'submitted_by': document.submitted_by,
            'workflow': workflow,
        }
        recipient_list = [document.submitted_by.email]
        cc_list = workflow.get_cc_list()
        
        attachments = None
        if pdf_result and pdf_result.get('status') == 'success':
            temp_path = pdf_result.get('temp_pdf_path')
            if temp_path and os.path.exists(temp_path):
                with open(temp_path, 'rb') as pdf_file:
                    filename = f"document_{document.document_reference}_report.pdf"
                    attachments = [(filename, pdf_file.read(), 'application/pdf')]
            else:
                logger.error(f"Temporary PDF file not found at {temp_path}")
                
        result = send_templated_email_task(
            workflow.email_approved_subject,
            workflow.email_approved_body_template,
            _serialize_context(context),
            recipient_list,
            cc_list,
            attachments=attachments
        )
        
        return {
            'status': 'success',
            'message': 'Approved email sent successfully'
        }
        
    except Document.DoesNotExist:
        logger.error(f"Document with ID {document_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending approved email: {str(e)}")
        raise
    finally:
        # Clean up temporary file
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Error cleaning up temporary PDF file: {str(e)}")

@app.task(name='document.tasks.send_approval_notification_task')
def send_approval_notification_task(email_result, document_id):
    """
    Celery task to send approval notification email
    Args:
        email_result: Result from previous email task (unused but required for chaining)
        document_id: Document ID
    """
    logger = logging.getLogger(__name__)
    
    try:
        document = Document.objects.get(id=document_id)
        
        # Get all approvals that need notification
        for approval in document.approvals.all():
            if not approval.step.send_email:
                logger.info(
                    f"Email sending is disabled for step {approval.step.id} of document {approval.document.id}"
                )
                continue

            context = {
                'document': document,
                'submitted_by': document.submitted_by,
                'approval': approval,
                'step': approval.step,
                'approver': approval.approver,
            }

            recipient_list = [approval.approver.email]

            send_templated_email_task(
                approval.step.email_subject,
                approval.step.email_body_template,
                _serialize_context(context),
                recipient_list
            )
            
        return {
            'status': 'success',
            'message': f'Approval notifications sent for document {document_id}'
        }
            
    except Document.DoesNotExist:
        logger.error(f"Document with ID {document_id} not found")
        raise
    except Exception as e:
        logger.error(f"Error sending approval notifications: {str(e)}")
        raise

@app.task
def upload_file_task(document_id, field_id, file_path):
    from django.core.files import File
    with open(file_path, 'rb') as file:
        DynamicFieldValue.objects.create(
            document_id=document_id,
            field_id=field_id,
            file=File(file)
        )

@app.task
def test_task(message="Hello, this is a test of the Celery task system!"):
    logger = logging.getLogger(__name__)
    logger.info(message)
    return message

@app.task(name='document.tasks.send_templated_email_task')
def send_templated_email_task(subject_template, body_template, context_dict, recipient_list, cc_list=None, attachments=None):
    """
    Celery task to send templated email
    Args:
        subject_template: Template string for email subject
        body_template: Template string for email body
        context_dict: Dictionary of context variables for template rendering
        recipient_list: List of recipient email addresses
        cc_list: Optional list of CC email addresses
        attachments: Optional list of attachments (filename, content, mimetype)
    Returns:
        dict: Status and message of the operation
    """
    try:
        from django.urls import reverse
        from django.template import Template, Context
        from django.conf import settings
        from django.utils.html import strip_tags
        from django.core.mail import EmailMultiAlternatives
        from accounts.models import CustomUser
        from document.models import Document, ApprovalWorkflow, Approval, ApprovalStep
        import re
        
        # Deserialize context data
        context = context_dict.copy()
        if 'document_data' in context:
            document = Document.objects.get(id=context['document_data']['id'])
            context['document'] = document
            del context['document_data']
        if 'submitted_by_id' in context:
            context['submitted_by'] = CustomUser.objects.get(id=context['submitted_by_id'])
        if 'workflow_id' in context:
            context['workflow'] = ApprovalWorkflow.objects.get(id=context['workflow_id'])
        if 'approval_id' in context:
            context['approval'] = Approval.objects.get(id=context['approval_id'])
        if 'step_id' in context:
            context['step'] = ApprovalStep.objects.get(id=context['step_id'])
        if 'approver_id' in context:
            context['approver'] = CustomUser.objects.get(id=context['approver_id'])
        
        # Add document_url tag to the template if document exists
        if 'document' in context:
            document = context['document']
            host = settings.ALLOWED_HOSTS[3] if settings.ALLOWED_HOSTS else 'localhost:8000'
            document_url = reverse('document_approval:document_detail', args=[document.document_reference])
            full_url = f"https://{host}{document_url}"
            # Add the URL as a clickable link, only replace the template tag
            html_link = f'<a href="{full_url}">{full_url}</a>'
            body_template = body_template.replace('{{document_url}}', html_link)
        
        django_context = Context(context)

        # Render subject
        subject = Template(subject_template).render(django_context)
        # Remove newlines and tags from subject
        subject = strip_tags(''.join(subject.splitlines()))[:255]

        # Convert Windows-style line endings to Unix-style
        body_template = body_template.replace('\r\n', '\n')
        
        # Convert line breaks to HTML breaks before rendering
        body_template = body_template.replace('\n', '<br>\n')
        
        # Render body
        html_content = Template(body_template).render(django_context)
        
        # For plain text, convert <br> back to newlines, convert HTML link to plain URL, and strip other HTML
        text_content = html_content
        text_content = text_content.replace('<br>', '\n')
        
        # Extract URLs from HTML links for plain text version
        def replace_link_with_url(match):
            url = match.group(1)
            return url
        text_content = re.sub(r'<a href="([^"]+)">[^<]+</a>', replace_link_with_url, text_content)
        text_content = strip_tags(text_content)

        # Create email message
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            cc=cc_list if cc_list else None,
        )
        msg.attach_alternative(html_content, "text/html")

        # Add attachment if present
        if attachments:
            filename, content, mimetype = attachments[0]  # We only have one attachment
            msg.attach(filename, content, mimetype)

        # Send the email
        msg.send()
        
        # Send notification if requested and we have the necessary context
        if 'document' in context and len(recipient_list) > 0:
            document = context['document']
            # Get the user from the first recipient email
            user = CustomUser.objects.filter(email=recipient_list[0]).first()
            if user:
                from document.sendEmails import send_approval_notification
                send_approval_notification(document, user)

        return {
            'status': 'success',
            'message': f'Email sent successfully to {", ".join(recipient_list)}'
        }
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return {
            'status': 'error',
            'message': f'Error sending email: {str(e)}'
        }