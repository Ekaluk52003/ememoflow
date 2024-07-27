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
    user_approval = document.approvals.filter(
        approver=request.user,
        step=document.current_step,
        is_approved__isnull=True
    ).first()

    if request.method == 'POST' and user_approval and document.status == 'in_review':
        # Handle approval submission
        is_approved = request.POST.get('is_approved') == 'true'
        comment = request.POST.get('comment', '')
        user_input = request.POST.get('user_input', '')
        uploaded_file = request.FILES.get('user_input_file')




        if user_approval.step.requires_input:
            if user_approval.step.input_type == 'file':
                if not uploaded_file:
                        print('not uploaded_filee',  uploaded_file)
                        messages.error(request, "File upload is required for this step.")
                        return redirect('document_approval:document_detail', pk=document.pk)

                # Validate file extension
                # allowed_extensions = [ext.strip() for ext in  user_approval.step.allowed_file_extensions.split(',')]
                # file_extension = os.path.splitext(uploaded_file.name)
                # if file_extension[1:] not in allowed_extensions:
                #     messages.error(request, f"Invalid file type. Allowed types are: {', '.join(allowed_extensions)}")
                #     return redirect('document_approval:document_detail', pk=document.pk)
                print('uploading the file')
                user_approval.uploaded_file = uploaded_file

            elif not user_input:
                    messages.error(request, "User input is required for this step.")
                    return redirect('document_detail', pk=document.pk)
            else:
                user_approval.user_input = user_input

        user_approval.is_approved = is_approved
        user_approval.comment = comment
        user_approval.recorded_at = timezone.now()
        user_approval.save()

        if is_approved:
            document.move_to_next_step()
        else:
            document.reject()

        return redirect('document_approval:document_detail', pk=document.pk)

    can_withdraw = (
        document.status == 'in_review' and
        document.submitted_by == request.user and
        not document.approvals.filter(is_approved__isnull=False, created_at__gt=document.last_submitted_at).exists()
    # There do not exist any approvals for this document that have been decided (approved or rejected) and were created after the document was last submitted or resubmitted.
    )

    context = {
        'document': document,
        'dynamic_field_values': dynamic_field_values,
        'user_approval': user_approval,
        'can_approve': user_approval and document.status == 'in_review',
        'can_resubmit': document.status in ['rejected','pending'] and request.user == document.submitted_by,
        'can_draw' : can_withdraw
    }
    return render(request, 'document/document_detail.html', context)

@login_required
def resubmit_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    workflow = document.workflow
    dynamic_fields = workflow.dynamic_fields.all()

    # Pre-process choices for each field and get existing values
    for field in dynamic_fields:
        if field.field_type == 'choice':
            field.choice_list = [choice.strip() for choice in field.choices.split(',') if choice.strip()]

        # Get existing value for this field
        existing_value = document.dynamic_values.filter(field=field).first()
        field.existing_value = existing_value.value if existing_value else ''
    un_authorize = request.user != document.submitted_by or document.status not in ['pending', 'rejected']
    if (un_authorize):
        (print(document.status))
        return HttpResponseForbidden("You don't have permission to resubmit this document.")

    if request.method == 'POST':
        document.title = request.POST.get('title')
        document.content = request.POST.get('content')
        document.status = 'in_review'
        document.current_step = workflow.steps.first()
        document.last_submitted_at = timezone.now()
        # Delete all pending approvals
        document.approvals.filter(is_approved=None).delete()
        document.save()

        for field in dynamic_fields:
            value = request.POST.get(f'dynamic_{field.id}')
            if field.required and not value:
                messages.error(request, f"{field.name} is required.")
                return render(request, 'resubmit_document.html',
                              {'document': document, 'workflow': workflow, 'dynamic_fields': dynamic_fields})

            DynamicFieldValue.objects.update_or_create(
                document=document,
                field=field,
                defaults={'value': value or ''}
            )


        for step in workflow.steps.all():
            if step.evaluate_condition(document):
                if not workflow.allow_custom_approvers:
                    for approver in step.approvers.all():
                        Approval.objects.create(
                            document=document,
                            step=step,
                            approver=approver
                        )

                else :
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if  approver_id:
                        approver = CustomUser.objects.get(id=approver_id)
                        Approval.objects.create(
                        document=document,
                        step=step,
                        approver=approver,
                        is_approved=None
                )


        return redirect('document_approval:document_detail', pk=document.pk)

    context = {
        'document': document,
        'workflow': workflow,
        'dynamic_fields': dynamic_fields,
        'potential_approvers': CustomUser.objects.all(),  # Or a more specific queryset
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
def submit_document(request, workflow_id):
    workflow = ApprovalWorkflow.objects.get(id=workflow_id)  # Hardcoded to workflow with ID 1
    dynamic_fields = workflow.dynamic_fields.all()

     # Process choices for each field
    for field in dynamic_fields:
        if field.field_type == 'choice':
            field.choice_list = [choice.strip() for choice in field.choices.split(',') if choice.strip()]
        else:
            field.choice_list = []

    if request.method == 'POST':
        value = request.POST.get(f'dynamic_{field.id}')
        title = request.POST.get('title')
        content = request.POST.get('content')

        document = Document.objects.create(
            title=title,
            content=content,
            submitted_by=request.user,
            workflow=workflow,
            status='in_review'
        )

        # Save dynamic field values
        for field in dynamic_fields:
            value = request.POST.get(f'dynamic_{field.id}')
            if field.required and not value:
                messages.error(request, f"{field.name} is required.")
                document.delete()
                return render(request, 'submit_document.html', {'workflow': workflow, 'dynamic_fields': dynamic_fields})

            # Each dynamic file should be added
            DynamicFieldValue.objects.create(
                document=document,
                field=field,
                value=value or ''
            )

        for step in workflow.steps.all():
            if step.evaluate_condition(document):
                if not workflow.allow_custom_approvers:
                    for approver in step.approvers.all():
                        Approval.objects.create(
                            document=document,
                            step=step,
                            approver=approver                        )

                else :
                    approver_id = request.POST.get(f'approver_{step.id}')
                    if  approver_id:
                        approver = CustomUser.objects.get(id=approver_id)
                        Approval.objects.create(
                        document=document,
                        step=step,
                        approver=approver,
                        is_approved=None
                )

        # Set the current step to the first step of the workflow
        document.current_step = workflow.steps.first()
        document.save()

        return redirect('document_approval:document_detail', pk=document.pk)

    potential_approvers = CustomUser.objects.all()  # Or a more specific queryset

    context = {
        'workflow': workflow,
        'potential_approvers': potential_approvers,
        'dynamic_fields': dynamic_fields
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