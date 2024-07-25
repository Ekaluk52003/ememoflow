from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Q
from .models import Document, Approval, ApprovalWorkflow, ApprovalStep
from accounts.models import CustomUser
from django.core.exceptions import ValidationError

@login_required
def document_list(request):
    documents = Document.objects.all().order_by('-created_at')
    return render(request, 'document/document_list.html', {'documents': documents})

@login_required
def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    user_approval = document.approvals.filter(
        approver=request.user,
        step=document.current_step,
        is_approved__isnull=True
    ).first()

    if request.method == 'POST' and user_approval and document.status == 'in_review':
        # Handle approval submission
        is_approved = request.POST.get('is_approved') == 'true'
        comment = request.POST.get('comment', '')

        user_approval.is_approved = is_approved
        user_approval.comment = comment
        user_approval.save()

        if is_approved:
            document.move_to_next_step()
        else:
            document.reject()

        return redirect('document_approval:document_detail', pk=document.pk)

    context = {
        'document': document,
        'user_approval': user_approval,
        'can_approve': user_approval and document.status == 'in_review',
        'can_resubmit': document.status == 'rejected' and request.user == document.submitted_by,
    }
    return render(request, 'document/document_detail.html', context)

@login_required
def resubmit_document(request, pk):
    document = get_object_or_404(Document, pk=pk)
    workflow = document.workflow

    if request.user != document.submitted_by or document.status != 'rejected':
        return HttpResponseForbidden("You don't have permission to resubmit this document.")

    if request.method == 'POST':
        document.title = request.POST.get('title')
        document.content = request.POST.get('content')
        document.status = 'in_review'
        document.current_step = workflow.steps.first()
        # Delete all pending approvals
        document.approvals.filter(is_approved=None).delete()
        document.save()

        for step in workflow.steps.all():
            approver_id = request.POST.get(f'approver_{step.id}')
            if approver_id:
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
        'potential_approvers': CustomUser.objects.all(),  # Or a more specific queryset
    }
    return render(request, 'document/resubmit_document.html', context)

@login_required
def submit_document(request):
    workflow = ApprovalWorkflow.objects.get(id=1)  # Hardcoded to workflow with ID 1

    if request.method == 'POST':
        title = request.POST.get('title')
        content = request.POST.get('content')

        document = Document.objects.create(
            title=title,
            content=content,
            submitted_by=request.user,
            workflow=workflow,
            status='in_review'
        )

        # Create approval records for each step
        for step in workflow.steps.all():
            approver_id = request.POST.get(f'approver_{step.id}')
            if approver_id:
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
        'documents_to_approve': documents_to_approve,
        'documents_to_resubmit': documents_to_resubmit,
    }
    return render(request, 'document/documents_to_action.html', context)