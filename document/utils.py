from .models import Document, Approval, User
from django.db.models import Q, Exists, OuterRef
from django.shortcuts import render

def get_user_bu_groups(user):
    """Get all BU groups the user belongs to"""
    all_groups = user.groups.all()
    bu_groups = set()
    
    for group in all_groups:
        if group.name.endswith('_Manager'):
            # If user is BU1_Manager, add 'BU1' to their BUs
            bu_name = group.name.replace('_Manager', '')
            bu_groups.add(bu_name)
        elif group.name.startswith('BU') and not group.name.endswith('_Manager'):
            # Direct BU group membership
            bu_groups.add(group.name)

    return bu_groups

def is_bu_manager(user):
    """Check if the user is a manager in any of their BUs"""
    return user.groups.filter(name__endswith='_Manager').exists()

def get_allowed_documents(user):
    # Check if the user is superuser or in Director group
    if user.is_superuser or user.groups.filter(name='Director').exists():
        return Document.objects.all().order_by('-created_at')
    
    # Get documents where the workflow has authorized groups that include the user's groups
    authorized_workflow_docs = Document.objects.filter(
        workflow__authorized_groups__in=user.groups.all()
    )
    
    # Get documents where the user is an authorized user
    # Use try/except to handle the case when the relation doesn't exist yet
    try:
        cc_authorized_docs = Document.objects.filter(
            authorized_users=user
        )
    except Exception:
        # If the relation doesn't exist yet, use an empty queryset
        cc_authorized_docs = Document.objects.none()

    # Get user's BU groups
    bu_groups = get_user_bu_groups(user)
    if not bu_groups:
        # If user is not in any BU group, they can only see their submitted documents,
        # documents from workflows where they're in an authorized group,
        # and documents where they are authorized as a CC recipient
        return (Document.objects.filter(
            Q(submitted_by=user) |
            Q(id__in=authorized_workflow_docs) |
            Q(id__in=cc_authorized_docs)
        )).distinct().order_by('-created_at')

    # Get all users who are either in these BU groups or are managers of these BUs
    users_in_same_bus = User.objects.filter(
        Q(groups__name__in=bu_groups) |  # Users in BU groups
        Q(groups__name__in=[f"{bu}_Manager" for bu in bu_groups])  # Users who are managers
    ).distinct()  
    
    # Base queryset - documents submitted by the user themselves,
    # documents submitted by users in the same BUs,
    # documents from workflows where the user's group is authorized,
    # or documents where the user is authorized as a CC recipient
    documents = Document.objects.filter(
        Q(submitted_by=user) |  # Always include user's own documents
        Q(submitted_by__in=users_in_same_bus) |
        Q(id__in=authorized_workflow_docs) |
        Q(id__in=cc_authorized_docs)
    )

    # If user is not a BU manager, they can only see their submitted documents,
    # documents from authorized workflows, and documents where they are CC'd
    if not is_bu_manager(user):
        documents = documents.filter(
            Q(submitted_by=user) |
            Q(id__in=authorized_workflow_docs) |
            Q(id__in=cc_authorized_docs)
        )

    # Order the documents by creation date, most recent first
    return documents.distinct().order_by('-created_at')

def get_allowed_document(user, reference_id):
    allowed_documents = get_allowed_documents(user)
    try:
        document = allowed_documents.get(document_reference=reference_id)
    except Document.DoesNotExist:
        return render(None, 'error.html', {
            'message': "Document not found or you don't have permission to access it."
        })
    return document
