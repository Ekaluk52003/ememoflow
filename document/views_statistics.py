from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Avg, F, ExpressionWrapper, DurationField, Q
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta
from .models import Approval, Document, ApprovalWorkflow, CustomUser
from django.contrib.auth.models import Group

@login_required
def approval_statistics(request):
    """
    Display approval statistics for users and workflows
    """
    if not request.user.is_superuser:
        return render(request, '403.html', status=403)

    # Calculate user statistics
    user_stats = []
    
    # Get all users who have approvals
    users_with_approvals = CustomUser.objects.filter(
        approval__isnull=False
    ).distinct()
    
    for user in users_with_approvals:
        # Get all completed approvals (both approved and rejected)
        # Only select the fields we need to avoid querying non-existent columns
        completed_approvals = Approval.objects.filter(
            approver=user,
            recorded_at__isnull=False,
            can_approveAt__isnull=False
        ).only('id', 'document', 'recorded_at', 'can_approveAt')
        
        # Get pending approvals for this user
        pending_approvals = Approval.objects.filter(
            approver=user,
            is_approved__isnull=True,
            status='pending'
        ).only('id').count()
        
        # Calculate total decisions
        total_decisions = completed_approvals.count()
        
        # Calculate unique documents processed
        documents_processed = completed_approvals.values('document').distinct().count()
        
        # Calculate average response time
        # Only include approvals where both timestamps are available
        avg_response_time = None
        if total_decisions > 0:
            # Create a duration expression
            duration_expr = ExpressionWrapper(
                F('recorded_at') - F('can_approveAt'),
                output_field=DurationField()
            )
            
            # Calculate the average duration
            avg_duration = completed_approvals.annotate(
                duration=duration_expr
            ).aggregate(avg_duration=Avg('duration'))['avg_duration']
            
            if avg_duration:
                # Format the duration for display
                total_seconds = avg_duration.total_seconds()
                hours = int(total_seconds // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                
                if hours > 0:
                    avg_response_time = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    avg_response_time = f"{minutes}m {seconds}s"
                else:
                    avg_response_time = f"{seconds}s"
        
        user_stats.append({
            'user': user,
            'total_decisions': total_decisions,
            'pending_approvals': pending_approvals,
            'documents_processed': documents_processed,
            'avg_response_time': avg_response_time or 'N/A'
        })
    
    # Sort by total decisions (descending)
    user_stats.sort(key=lambda x: x['total_decisions'], reverse=True)
    
    # Calculate workflow statistics
    workflow_stats = []
    
    workflows = ApprovalWorkflow.objects.all()
    
    # Filter out workflows where the user is in a denied group
    if (not request.user.is_superuser) and request.user.groups.exists():
        workflows = workflows.exclude(denied_groups__in=request.user.groups.all())
    
    workflows = workflows.distinct()
    
    for workflow in workflows:
        # Get completed documents for this workflow
        # Only select the fields we need
        completed_docs = Document.objects.filter(
            workflow=workflow,
            status='approved'
        ).only('id', 'created_at', 'updated_at')
        
        document_count = completed_docs.count()
        
        # Calculate average completion time (from creation to approval)
        avg_completion_time = None
        if document_count > 0:
            # Create a duration expression
            duration_expr = ExpressionWrapper(
                F('updated_at') - F('created_at'),
                output_field=DurationField()
            )
            
            # Calculate the average duration
            avg_duration = completed_docs.annotate(
                duration=duration_expr
            ).aggregate(avg_duration=Avg('duration'))['avg_duration']
            
            if avg_duration:
                # Format the duration for display
                total_seconds = avg_duration.total_seconds()
                days = int(total_seconds // 86400)
                hours = int((total_seconds % 86400) // 3600)
                minutes = int((total_seconds % 3600) // 60)
                seconds = int(total_seconds % 60)
                
                if days > 0:
                    avg_completion_time = f"{days}d {hours}h {minutes}m {seconds}s"
                elif hours > 0:
                    avg_completion_time = f"{hours}h {minutes}m {seconds}s"
                elif minutes > 0:
                    avg_completion_time = f"{minutes}m {seconds}s"
                else:
                    avg_completion_time = f"{seconds}s"
        
        workflow_stats.append({
            'workflow': workflow,
            'document_count': document_count,
            'avg_completion_time': avg_completion_time or 'N/A'
        })
    
    # Sort by document count (descending)
    workflow_stats.sort(key=lambda x: x['document_count'], reverse=True)
    
    return render(request, 'document/approval_statistics.html', {
        'user_stats': user_stats,
        'workflow_stats': workflow_stats
    })
