from django.core.mail import EmailMultiAlternatives
from django.template import Template, Context
from django.utils.html import strip_tags
from django.conf import settings
import logging
from django.template import Template, Context, TemplateSyntaxError

logger = logging.getLogger(__name__)


def send_templated_email(subject_template, body_template, context_dict, recipient_list, cc_list=None):
    try:
        context = Context(context_dict)

        # Render the subject
        subject = strip_tags(
            Template(subject_template).render(context)).strip()[:255]

        # Render the body
        html_content = Template(body_template).render(context)
        text_content = strip_tags(html_content)

        # Create the email message
        msg = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            cc=cc_list
        )
        msg.attach_alternative(html_content, "text/html")

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
        logger.info(
            f"Withdraw email sending is disabled for workflow {workflow.id}")
        return False

    context = {
        'document': document,
        'submitted_by': document.submitted_by,
        'workflow': workflow,
    }
    recipient_list = [document.submitted_by.email]
    cc_list = workflow.get_cc_list()

    return send_templated_email(
        workflow.email_approved_subject,
        workflow.email_approved_body_template,
        context,
        recipient_list,
        cc_list
    )

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







