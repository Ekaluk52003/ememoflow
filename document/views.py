from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import Document, Approval, ApprovalWorkflow, ApprovalStep, DynamicField, DynamicFieldValue
from accounts.models import CustomUser
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib import messages
import os
from .sendEmails import send_reject_email,  send_withdraw_email, send_approval_email


@login_required
def workflow_list(request):
    workflows = ApprovalWorkflow.objects.all()
    return render(request, 'document/workflow_list.html', {'workflows': workflows})

@login_required
def document_list(request):
    documents = Document.objects.all().order_by('-created_at')
    return render(request, 'document/document_list.html', {'documents': documents})

@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    dynamic_field_values = document.dynamic_values.all()
    user_approval = document.approvals.filter(approver=request.user, step=document.current_step, is_approved__isnull=True).first()

    if request.method == 'POST' and user_approval and document.status == 'in_review':
        try:
            document.handle_approval(
                user=request.user,
                is_approved=request.POST.get('is_approved') == 'true',
                comment=request.POST.get('comment', ''),
                user_input=request.POST.get('user_input', ''),
                uploaded_file=request.FILES.get('user_input_file')
            )
            messages.success(request, "Approval decision recorded successfully.")
        except ValidationError as e:
            messages.error(request, str(e))
        return redirect('document_approval:document_detail', pk=document.pk)

    context = {
        'document': document,
        'dynamic_field_values': dynamic_field_values,
        'user_approval': user_approval,
        'can_approve': user_approval and document.status == 'in_review',
        'can_resubmit': document.status in ['rejected','pending'] and request.user == document.submitted_by,
        'can_draw' : document.can_withdraw(request.user)
    }

    # for field in dynamic_field_values :
    #     print(field.field.field_type )
    #     # print(field.value )

    return render(request, 'document/document_detail.html', context)



@login_required
def resubmit_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    workflow = document.workflow
    dynamic_fields = workflow.dynamic_fields.all()

    for field in dynamic_fields:
        if field.field_type == 'choice':
            field.choice_list = [choice.strip() for choice in field.choices.split(',') if choice.strip()]

        # Get existing value for this field
        existing_value = document.dynamic_values.filter(field=field).first()
        field.existing_value = existing_value.value if existing_value else ''

    if request.user != document.submitted_by or document.status not in ['pending', 'rejected']:
        return HttpResponseForbidden("You don't have permission to resubmit this document.")

    if request.method == 'POST':
        try:
            document.resubmit(request.POST.get('title'), request.POST.get('content'))
            DynamicFieldValue.update_or_create_values(document, document.workflow.dynamic_fields.all(), request.POST)

            custom_approvers = {}
            if workflow.allow_custom_approvers:
                for step in workflow.steps.all():
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if approver_id:
                        custom_approvers[step.id] = CustomUser.objects.get(id=approver_id)

            document.create_approvals(custom_approvers)
            messages.success(request, "Document submitted successfully, but no approver was found for the first step.")

            return redirect('document_approval:document_detail', pk=document.pk)
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'document': document,
        'workflow': document.workflow,
        'dynamic_fields': dynamic_fields,
        'potential_approvers': CustomUser.objects.all(),
    }
    return render(request, 'document/resubmit_document.html', context)



@login_required
def withdraw_document(request, document_id):
    document = get_object_or_404(Document, id=document_id, submitted_by=request.user)

    if request.method == 'POST':
        try:
            document.withdraw()
            messages.success(request, "Document has been successfully withdrawn.")
        except ValidationError as e:
            messages.error(request, str(e))

    return redirect('document_approval:document_detail', pk=document.pk)


@login_required
#done upadte
def submit_document(request, workflow_id):
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    dynamic_fields = workflow.dynamic_fields.all()

    for field in dynamic_fields:
        if field.field_type == 'choice':
            field.choice_list = [choice.strip() for choice in field.choices.split(',') if choice.strip()]
        else:
            field.choice_list = []

    if request.method == 'POST':
        try:
            document = Document.objects.create(
                title=request.POST.get('title'),
                content=request.POST.get('content'),
                submitted_by=request.user,
                workflow=workflow,
                status='in_review',
                current_step=workflow.steps.first()
            )
            DynamicFieldValue.update_or_create_values(document, workflow.dynamic_fields.all(), request.POST)

            custom_approvers = {}
            if workflow.allow_custom_approvers:
                for step in workflow.steps.all():
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if approver_id:
                        custom_approvers[step.id] = CustomUser.objects.get(id=approver_id)

            document.create_approvals(custom_approvers)

            messages.success(request, "Document submitted successfully, but no approver was found for the first step.")

            return redirect('document_approval:document_detail', pk=document.pk)
        except ValidationError as e:
            messages.error(request, str(e))

    context = {
        'workflow': workflow,
        'dynamic_fields': dynamic_fields,
        'potential_approvers': CustomUser.objects.all(),
    }
    return render(request, 'document/submit_document.html', context)


@login_required
def documents_to_approve_to_resubmit(request):
    # This Django ORM query is fetching a specific set of documents based on certain conditions. Let's break it down:

# Document.objects.filter(...): This starts a query on the Document model.
# Q(current_step__approval__approver=request.user):
# This looks for documents where the current step has an approval assigned to the current user.
# Q(current_step__approval__is_approved=None):
# This further filters to only include documents where that approval is pending (not yet approved or rejected).
# Q(status='in_review'):
# This ensures only documents with the status 'in_review' are included.
# .distinct():
# This removes any duplicate results that might occur due to the nature of the query joins.
# .order_by('-created_at'):
# This orders the results by the creation date in descending order (newest first).
# Putting it all together, this query is finding:
# "All documents that are currently in review, where the current step has a pending approval assigned to the current user, ordered from newest to oldest."
# This query would typically be used to show a user all the documents that are waiting for their approval. It ensures that:

# The document is in the review process.
# The current user is responsible for the next approval.
# That approval hasn't been made yet (it's still pending).

# The distinct() call is important because without it, you might get duplicate documents if a user has multiple approvals on different steps of the same document.
    documents_to_approve = Document.objects.filter(
        Q(current_step__approval__approver=request.user) &
        Q(current_step__approval__is_approved=None) &
        Q(status='in_review')
    )

    # Documents rejected that the user can resubmit
    documents_to_resubmit = Document.objects.filter(
        Q(submitted_by=request.user) &
        Q(status='rejected')
    )

    # Combine both querysets
    documents = (documents_to_approve | documents_to_resubmit).distinct().order_by('-updated_at')

    context = {
        'documents': documents,

    }
    return render(request, 'document/documents_to_action.html', context)