from django.core.mail import EmailMultiAlternatives
from django.template import Template, Context
from django.utils.html import strip_tags
from django.conf import settings
import logging
from django.template import Template, Context, TemplateSyntaxError

logger = logging.getLogger(__name__)


def send_templated_email(subject_template, body_template, context_dict, recipient_list, cc_list=None, attachments=None):
    try:
        context = Context(context_dict)

        # Render subject
        subject = Template(subject_template).render(context)
        # Remove newlines and tags from subject
        subject = strip_tags(''.join(subject.splitlines()))[:255]

        # Render body
        html_content = Template(body_template).render(context)
        text_content = strip_tags(html_content)

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

        logger.info(f"Email sent to {', '.join(recipient_list)}")
        return True
    except Exception as e:
        logger.error(f"Error sending email: {str(e)}")
        return False


def send_reject_email(document):
    print('send email reject')
    workflow = document.workflow
    if not workflow.send_reject_email:
        logger.info(
            f"Reject email sending is disabled for workflow {workflow.id}")
        return False

    rejector = document.get_rejector()
    context = {
        'document': document,
        'rejector': rejector,
        'workflow': workflow,
    }
    recipient_list = [document.submitted_by.email]
    cc_list = workflow.get_cc_list()

    return send_templated_email(
        workflow.reject_email_subject,
        workflow.reject_email_body,
        context,
        recipient_list,
        cc_list
    )


def send_withdraw_email(document):
    workflow = document.workflow
    if not workflow.send_withdraw_email:
        logger.info(
            f"Withdraw email sending is disabled for workflow {workflow.id}")
        return False

    current_approver = document.get_current_approver()
    if not current_approver:
        logger.warning(f"No current approver found for document {document.id}")
        return False

    context = {
        'document': document,
        'withdrawer': document.submitted_by,
        'workflow': workflow,
        'approver': current_approver,
    }
    recipient_list = [current_approver.email]
    cc_list = workflow.get_cc_list()

    return send_templated_email(
        workflow.withdraw_email_subject,
        workflow.withdraw_email_body,
        context,
        recipient_list,
        cc_list
    )


def send_approved_email(document):
    workflow = document.workflow
    if not workflow.send_approved_email:
        return False

    context = {
        'document': document,
        'submitted_by': document.submitted_by,
        'workflow': workflow,
    }
    recipient_list = [document.submitted_by.email]
    cc_list = workflow.get_cc_list()

    # Generate PDF attachment
    pdf_file = generate_email_pdf(document)
    attachments = None
    if pdf_file:
        filename = f"document_{document.document_reference}_report.pdf"
        attachments = [(filename, pdf_file.getvalue(), 'application/pdf')]

    return send_templated_email(
        workflow.email_approved_subject,
        workflow.email_approved_body_template,
        context,
        recipient_list,
        cc_list,
        attachments=attachments
    )


# notify to approver for up coming document to approve
def send_approval_email(approval):
    if not approval.step.send_email:
        logger.info(
            f"Email sending is disabled for step {approval.step.id} of document {approval.document.id}"
        )
        return

    try:
        context = Context({
            'document': approval.document,
            'approver': approval.approver,
            'step': approval.step,
        })

        # Render the subject
        subject_template = Template(approval.step.email_subject)
        subject = strip_tags(subject_template.render(context)).strip()[:255]

        # Render the body
        body_template = Template(approval.step.email_body_template)
        html_content = body_template.render(context)
        text_content = strip_tags(html_content)

        # Get CC list
        cc_list = approval.step.get_cc_list()

        # Create the email message
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [approval.approver.email],
            cc=cc_list
        )
        msg.attach_alternative(html_content, "text/html")

        # Send the email
        msg.send()

        logger.info(
            f"Approval email sent for document {approval.document.id} to {approval.approver.email}"
        )

    except TemplateSyntaxError as e:
        logger.error(
            f"Template syntax error in send_approval_email for document {approval.document.id}: {str(e)}"
        )
    except AttributeError as e:
        logger.error(
            f"Attribute error in send_approval_email for document {approval.document.id}: {str(e)}"
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in send_approval_email for document {approval.document.id}: {str(e)}"
        )


def generate_email_pdf(document):
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
                self.META = {'HTTP_HOST': settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost:8000'}

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
