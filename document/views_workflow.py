from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.contrib.auth.models import Group
from django.http import JsonResponse
from .models import ApprovalWorkflow, ApprovalStep, DynamicField, Document
from accounts.models import CustomUser
from functools import wraps

# Custom decorator to check if user is superuser
def superuser_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_superuser:
            return render(request, '403.html', status=403)
        return view_func(request, *args, **kwargs)
    return _wrapped_view

@login_required
@superuser_required
def workflow_list(request):
    """List all workflows with filtering options"""
    workflows = ApprovalWorkflow.objects.all().order_by('-created_at')
    
    # Get stats for each workflow
    for workflow in workflows:
        workflow.step_count = workflow.steps.count()
        workflow.document_count = Document.objects.filter(workflow=workflow).count()
    
    return render(request, 'document/workflow/workflow_list.html', {
        'workflows': workflows
    })

@login_required
@superuser_required
def create_workflow(request):
    """Create a new workflow with basic information only"""
    # Get all available groups for authorization
    groups = Group.objects.all().order_by('name')
    
    if request.method == 'POST':
        try:
            # Get basic workflow data
            name = request.POST.get('name')
            content_editor = request.POST.get('content_editor') == 'true'
            
            # Create the workflow with basic information only
            workflow = ApprovalWorkflow.objects.create(
                name=name,
                created_by=request.user,
                content_editor=content_editor
            )
            
            # Handle authorized groups
            group_ids = request.POST.getlist('authorized_groups[]')
            if group_ids:
                workflow.authorized_groups.set(group_ids)
            
            # Set default email settings
            workflow.send_reject_email = True
            workflow.reject_email_subject = 'Your document has been rejected'
            workflow.reject_email_body = 'Your document has been rejected. Please review the comments and resubmit.'
            
            workflow.send_withdraw_email = True
            workflow.withdraw_email_subject = 'Document has been withdrawn'
            workflow.withdraw_email_body = 'The document has been withdrawn by the submitter.'
            
            workflow.send_approved_email = False
            workflow.email_approved_subject = 'Your document has been fully approved'
            workflow.email_approved_body_template = 'Congratulations! Your document has been approved by all required approvers.'
            
            workflow.save()
            
            messages.success(request, f'Workflow "{name}" created successfully! Now you can configure email settings and dynamic fields.')
            
            # Redirect to edit workflow page for further configuration
            return redirect('document_approval:edit_workflow', workflow_id=workflow.id)
            
        except Exception as e:
            messages.error(request, f'Error creating workflow: {str(e)}')
    
    return render(request, 'document/workflow/create_workflow.html', {
        'groups': groups
    })

@login_required
@superuser_required
def edit_workflow(request, workflow_id):
    """Edit an existing workflow"""
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    
    # Get all available groups for authorization
    groups = Group.objects.all().order_by('name')
    
    # Get only dynamic fields associated with this workflow, sorted by order
    dynamic_fields = workflow.dynamic_fields.all().order_by('order')
    
    if request.method == 'POST':
        try:
            # Update basic workflow data
            workflow.name = request.POST.get('name')
            workflow.content_editor = request.POST.get('content_editor') == 'true'
            
            # Handle authorized groups
            group_ids = request.POST.getlist('authorized_groups[]')
            workflow.authorized_groups.set(group_ids)
            
            # Handle email settings
            workflow.send_reject_email = request.POST.get('send_reject_email') == 'true'
            workflow.reject_email_subject = request.POST.get('reject_email_subject', '')
            workflow.reject_email_body = request.POST.get('reject_email_body', '')
            
            workflow.send_withdraw_email = request.POST.get('send_withdraw_email') == 'true'
            workflow.withdraw_email_subject = request.POST.get('withdraw_email_subject', '')
            workflow.withdraw_email_body = request.POST.get('withdraw_email_body', '')
            
            workflow.send_approved_email = request.POST.get('send_approved_email') == 'true'
            workflow.email_approved_subject = request.POST.get('email_approved_subject', '')
            workflow.email_approved_body_template = request.POST.get('email_approved_body_template', '')
            
            workflow.cc_emails = request.POST.get('cc_emails', '')
            
            workflow.save()
            
            # Handle dynamic fields
            field_ids = request.POST.getlist('dynamic_fields[]')
            workflow.dynamic_fields.set(field_ids)
            
            messages.success(request, f'Workflow "{workflow.name}" updated successfully!')
            return redirect('document_approval:workflow_list')
            
        except Exception as e:
            messages.error(request, f'Error updating workflow: {str(e)}')
    
    # Get field types and width choices for the inline editor
    field_types = DynamicField.FIELD_TYPES
    width_choices = DynamicField.WIDTH_CHOICES
    
    return render(request, 'document/workflow/edit_workflow.html', {
        'workflow': workflow,
        'groups': groups,
        'dynamic_fields': dynamic_fields,
        'field_types': field_types,
        'width_choices': width_choices,
    })

@login_required
@superuser_required
def delete_workflow(request, workflow_id):
    """Delete a workflow"""
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    
    # Count documents using this workflow
    document_count = Document.objects.filter(workflow=workflow).count()
    
    if request.method == 'POST':
        try:
            name = workflow.name
            workflow.delete()
            messages.success(request, f'Workflow "{name}" deleted successfully!')
        except Exception as e:
            messages.error(request, f'Error deleting workflow: {str(e)}')
        
        return redirect('document_approval:workflow_list')
    
    return render(request, 'document/workflow/delete_workflow.html', {
        'workflow': workflow,
        'document_count': document_count
    })

@login_required
def workflow_steps(request, workflow_id):
    """Display workflow steps with connecting dot lines"""
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    steps = workflow.steps.all().order_by('order')
    
    return render(request, 'document/workflow_steps.html', {
        'workflow': workflow,
        'steps': steps
    })

@login_required
@superuser_required
def create_workflow_step(request, workflow_id):
    """Create a new workflow step using Alpine.js dynamic form"""
    workflow = get_object_or_404(ApprovalWorkflow, id=workflow_id)
    
    # Get all users for approver selection
    users = CustomUser.objects.all().order_by('first_name', 'last_name')
    
    # Get all groups for approver group selection
    groups = Group.objects.all().order_by('name')
    
    # Get only dynamic fields associated with this workflow for conditional logic
    dynamic_fields = workflow.dynamic_fields.all().order_by('name')
    
    # Handle form submission
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            order = request.POST.get('order')
            approval_mode = request.POST.get('approval_mode')
            requires_edit = request.POST.get('requires_edit') == 'true'
            
            # Create the step
            step = ApprovalStep.objects.create(
                workflow=workflow,
                name=name,
                order=order,
                approval_mode=approval_mode,
                requires_edit=requires_edit
            )
            
            # Handle editable fields if requires_edit is enabled
            if requires_edit:
                editable_field_ids = request.POST.getlist('editable_fields[]')
                step.editable_fields.set(editable_field_ids)
            
            # Handle approvers
            approver_ids = request.POST.getlist('approvers[]')
            if approver_ids:
                step.approvers.set(approver_ids)
            
            # Handle approver group
            approver_group_id = request.POST.get('approver_group')
            if approver_group_id and approver_group_id != 'none':
                step.approver_group_id = approver_group_id
                step.save()
            
            # Handle conditional logic
            is_conditional = request.POST.get('is_conditional') == 'true'
            if is_conditional:
                step.is_conditional = True
                step.condition_field_id = request.POST.get('condition_field')
                step.condition_operator = request.POST.get('condition_operator')
                step.condition_value = request.POST.get('condition_value')
                step.save()
            
            # Input type handling removed
            
            messages.success(request, f'Step "{name}" created successfully!')
            return redirect('document_approval:workflow_steps', workflow_id=workflow.id)
            
        except Exception as e:
            messages.error(request, f'Error creating step: {str(e)}')
    
    # Get condition operators from the model field choices
    condition_operators = ApprovalStep._meta.get_field('condition_operator').choices
    
    return render(request, 'document/create_workflow_step.html', {
        'workflow': workflow,
        'users': users,
        'groups': groups,
        'dynamic_fields': dynamic_fields,
        'condition_operators': condition_operators
    })

@login_required
@superuser_required
def edit_workflow_step(request, step_id):
    """Edit an existing workflow step using Alpine.js dynamic form"""
    step = get_object_or_404(ApprovalStep, id=step_id)
    workflow = step.workflow
    
    # Get all users for approver selection
    users = CustomUser.objects.all().order_by('first_name', 'last_name')
    
    # Get all groups for approver group selection
    groups = Group.objects.all().order_by('name')
    
    # Get only dynamic fields associated with this workflow for conditional logic
    dynamic_fields = workflow.dynamic_fields.all().order_by('name')
    
    if request.method == 'POST':
        try:
            # Get form data
            name = request.POST.get('name')
            order = request.POST.get('order')
            approval_mode = request.POST.get('approval_mode')
            requires_edit = request.POST.get('requires_edit') == 'true'
            
            # Update the step
            step.name = name
            step.order = order
            step.approval_mode = approval_mode
            step.requires_edit = requires_edit
            step.save()
            
            # Handle editable fields if requires_edit is enabled
            if requires_edit:
                editable_field_ids = request.POST.getlist('editable_fields[]')
                step.editable_fields.set(editable_field_ids)
            else:
                step.editable_fields.clear()
            
            # Handle approvers
            approver_ids = request.POST.getlist('approvers[]')
            if request.POST.get('approverType') == 'specific':
                step.approvers.set(approver_ids)
                step.approver_group = None
            elif request.POST.get('approverType') == 'group':
                step.approvers.clear()
                approver_group_id = request.POST.get('approver_group')
                if approver_group_id and approver_group_id != 'none':
                    step.approver_group_id = approver_group_id
            else:
                # No specific approvers
                step.approvers.clear()
                step.approver_group = None
            
            step.save()
            
            # Handle conditional logic
            is_conditional = request.POST.get('is_conditional') == 'true'
            step.is_conditional = is_conditional
            if is_conditional:
                step.condition_field_id = request.POST.get('condition_field')
                step.condition_operator = request.POST.get('condition_operator')
                step.condition_value = request.POST.get('condition_value')
                # Process move_to_next field
                step.move_to_next = request.POST.get('move_to_next') == 'true'
            else:
                step.condition_field = None
                step.condition_operator = None
                step.condition_value = None
                # Default to True for move_to_next when not conditional
                step.move_to_next = True
            
            step.save()
            
            # Input type handling removed
            
            messages.success(request, f'Step "{name}" updated successfully!')
            return redirect('document_approval:workflow_steps', workflow_id=workflow.id)
            
        except Exception as e:
            messages.error(request, f'Error updating step: {str(e)}')
    
    # Get condition operators from the model field choices
    condition_operators = ApprovalStep._meta.get_field('condition_operator').choices
    
    # Determine approver type for the form
    if step.approvers.exists():
        approver_type = 'specific'
    elif step.approver_group:
        approver_type = 'group'
    else:
        approver_type = 'none'
    
    return render(request, 'document/edit_workflow_step.html', {
        'step': step,
        'workflow': workflow,
        'users': users,
        'groups': groups,
        'dynamic_fields': dynamic_fields,
        'condition_operators': condition_operators,
        'approver_type': approver_type,
        'selected_approvers': [str(a.id) for a in step.approvers.all()]
    })
