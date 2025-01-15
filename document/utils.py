
from .models import Document, Approval
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import render

def get_allowed_documents(user):
    # Check if the user is in the "super user" group
    if user.is_superuser:
        return Document.objects.all().order_by('-created_at')


    is_super_user = user.groups.filter(name='super user').exists()

    # Base queryset
    documents = Document.objects.all()

    if not is_super_user:
        # If not a superuser, filter documents where the user is an approver or the submitter
        approver_documents = Approval.objects.filter(
            document=OuterRef('pk'),
            approver=user
        )
        documents = documents.filter(
            Q(Exists(approver_documents)) |  # User is an approver
            Q(submitted_by=user)  # User is the submitter
        )

    # Order the documents by creation date, most recent first
    return documents.order_by('-created_at')


def get_allowed_document(user, reference_id):
    allowed_documents = get_allowed_documents(user)
    try:
        document = allowed_documents.get(document_reference=reference_id)
    except Document.DoesNotExist:
        return render(None, 'error.html', {
            'message': "Document not found or you don't have permission to access it."
        })
    return document
