from django.utils import timezone
from .models_authorization import ApprovalAuthorization


def get_authorized_approvers(user):
    """
    Get all users that the current user is authorized to approve on behalf of.
    
    Args:
        user: The user who might be authorized to approve on behalf of others
        
    Returns:
        A list of user IDs that the current user is authorized to approve for
    """
    now = timezone.now()
    authorizations = ApprovalAuthorization.objects.filter(
        authorized_user=user,
        valid_from__lte=now,
        valid_until__gte=now,
        is_active=True
    )
    return [auth.authorizer.id for auth in authorizations]


def is_authorized_approver(document, user):
    """
    Check if a user is an authorized approver for the current step of a document.
    This includes both direct approvers and users authorized to approve on behalf of others.
    
    Args:
        document: The document being approved
        user: The user attempting to approve
        
    Returns:
        A tuple (is_authorized, original_approver) where:
        - is_authorized: Boolean indicating if the user is authorized
        - original_approver: The original approver if user is acting on behalf, otherwise None
    """
    # Check if user is a direct approver
    direct_approval = document.approvals.filter(
        approver=user,
        step=document.current_step,
        is_approved__isnull=True
    ).exists()
    
    if direct_approval:
        return True, None
    
    # Check if user is authorized to approve on behalf of someone else
    authorized_for = get_authorized_approvers(user)
    if not authorized_for:
        return False, None
    
    # Check if any of the users the current user is authorized for
    # are approvers for the current step
    authorized_approval = document.approvals.filter(
        approver_id__in=authorized_for,
        step=document.current_step,
        is_approved__isnull=True
    ).first()
    
    if authorized_approval:
        return True, authorized_approval.approver
    
    return False, None
