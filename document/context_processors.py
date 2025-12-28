from .utils import get_user_bu_groups

def user_bu_groups(request):
    """Add user's groups to template context"""
    if request.user.is_authenticated:
        # Get all user groups instead of just BU groups
        user_groups = [group.name for group in request.user.groups.all()]
        return {
            'user_bu_groups': ', '.join(sorted(user_groups)) if user_groups else ''
        }
    return {'user_bu_groups': ''}

def pending_documents_count(request):
    if not request.user.is_authenticated:
        return {'pending_count': 0}
        
    from document.models import Document
    from django.db.models import Q, F

    count = Document.objects.filter(
        Q(status='in_review', current_step__isnull=False,
          approvals__step=F('current_step'),
          approvals__approver=request.user,
          approvals__is_approved__isnull=True) |
        Q(submitted_by=request.user, status__in=['rejected', 'pending'])
    ).distinct().count()

    return {'pending_count': count}

def workflows_list(request):
    """Add available workflows to template context"""
    # Skip loading workflows for admin pages to improve performance
    if request.user.is_authenticated and not request.path.startswith('/admin/'):
        from document.models import ApprovalWorkflow
        # Cache the workflows to avoid repeated queries
        workflows = ApprovalWorkflow.objects.select_related('created_by').all()
        
        # Exclude workflows where the user is in a denied group
        if (not request.user.is_superuser) and request.user.groups.exists():
            workflows = workflows.exclude(
                denied_groups__in=request.user.groups.all()
            )
            
        return {'workflows': workflows.distinct()}
    return {'workflows': []}