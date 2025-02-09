from .utils import get_user_bu_groups

def user_bu_groups(request):
    """Add user's BU groups to template context"""
    if request.user.is_authenticated:
        bu_groups = get_user_bu_groups(request.user)
        return {
            'user_bu_groups': ', '.join(sorted(bu_groups)) if bu_groups else ''
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
    if request.user.is_authenticated:
        from document.models import ApprovalWorkflow
        workflows = ApprovalWorkflow.objects.all()
        print(workflows)
        return {'workflows': workflows}
    return {'workflows': []}