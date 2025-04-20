from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from django.http import HttpResponseForbidden, JsonResponse
from django.db.models import Q

from .models_authorization import ApprovalAuthorization
from .forms_authorization import ApprovalAuthorizationForm
from .direct_authorization import create_direct_authorization

# Direct authorization view that uses a custom form approach
def direct_create_authorization(request):
    return create_direct_authorization(request)

# API endpoint to fetch users for the dropdown
@login_required
def api_users(request):
    """API endpoint to fetch users for the dropdown"""
    from accounts.models import CustomUser
    from django.contrib.auth.models import Group
    from .utils import get_user_bu_groups
    
    # Get current user's groups
    current_user_groups = request.user.groups.all()
    current_user_group_names = set(group.name for group in current_user_groups)
    
    # Extract BU manager groups and non-BU groups
    current_user_bu_manager_groups = []
    current_user_non_bu_groups = []
    
    for group_name in current_user_group_names:
        if group_name.startswith('BU') and group_name.endswith('_Manager'):
            current_user_bu_manager_groups.append(group_name)
        elif not (group_name.startswith('BU') and not group_name.endswith('_Manager')):
            # This is not a direct BU group (like 'BU1'), so it's a non-BU group (like 'Middle_Management')
            current_user_non_bu_groups.append(group_name)
    
    # Get all active users
    all_users = CustomUser.objects.filter(is_active=True)
    
    # Filter users based on current user's groups
    filtered_users = []
    for user in all_users:
        user_groups = set(group.name for group in user.groups.all())
        
        # Check if user should be included based on our filtering rules
        should_include = False
        
        # If current user is in any BU manager group (e.g., BU1_Manager)
        if current_user_bu_manager_groups:
            # Include users who are in the same BU manager groups
            if any(group in current_user_bu_manager_groups for group in user_groups):
                should_include = True
            # Exclude users who are in different BU manager groups
            elif any(group.startswith('BU') and group.endswith('_Manager') for group in user_groups):
                # If user is in a different BU manager group, explicitly exclude them
                should_include = False
                # Skip to the next user
                continue
        
        # Include users who share any non-BU group with current user (e.g., Middle_Management)
        if current_user_non_bu_groups and any(group in current_user_non_bu_groups for group in user_groups):
            should_include = True
            
        # If user should be included, add them to the filtered list
        if should_include:
            filtered_users.append(user)
        # If current user has no BU manager groups and no non-BU groups, fall back to showing users who share any group
        elif not current_user_bu_manager_groups and not current_user_non_bu_groups and user_groups.intersection(current_user_group_names):
            filtered_users.append(user)
    
    # Sort the filtered users by username
    filtered_users.sort(key=lambda user: user.username)
    
    # Convert to a list of dictionaries with group names
    user_list = []
    for user in filtered_users:
        # Get user's groups as a comma-separated string
        group_names = ', '.join(sorted([group.name for group in user.groups.all()]))
        user_list.append({
            'id': user.id, 
            'username': f"{user.username} ({group_names})"
        })
    
    return JsonResponse(user_list, safe=False)


@login_required
def authorization_list(request):
    """View to list all authorizations for the current user"""
    # Authorizations given by the current user
    given_authorizations = ApprovalAuthorization.objects.filter(
        authorizer=request.user
    ).select_related('authorized_user')
    
    # Authorizations received by the current user
    received_authorizations = ApprovalAuthorization.objects.filter(
        authorized_user=request.user
    ).select_related('authorizer')
    
    # Active authorizations where the current user can approve on behalf of others
    now = timezone.now()
    active_received = received_authorizations.filter(
        valid_from__lte=now,
        valid_until__gte=now,
        is_active=True
    )
    
    context = {
        'given_authorizations': given_authorizations,
        'received_authorizations': received_authorizations,
        'active_received': active_received,
        'now': now,  # Pass the current time to the template
    }
    
    return render(request, 'document/authorization_list.html', context)


@login_required
def create_authorization(request):
    """View to create a new authorization without using Django forms"""
    from accounts.models import CustomUser
    from django.utils import timezone
    import datetime
    
    # Get all active users for the dropdown
    users = CustomUser.objects.filter(is_active=True).order_by('username')
    print(f"Found {users.count()} active users")
    
    # Debug: Print the first 5 users
    for user in users[:5]:
        print(f"User: {user.username} (ID: {user.id})")
    
    if request.method == 'POST':
        try:
            # Get form data directly from POST
            authorized_user_id = request.POST.get('authorized_user')
            valid_from_str = request.POST.get('valid_from')
            valid_until_str = request.POST.get('valid_until')
            reason = request.POST.get('reason')
            
            # Validate required fields
            error_message = None
            if not authorized_user_id:
                error_message = "Please select a user to authorize."
            elif not valid_from_str:
                error_message = "Please specify when the authorization becomes active."
            elif not valid_until_str:
                error_message = "Please specify when the authorization expires."
            elif not reason:
                error_message = "Please provide a reason for the authorization."
            
            if error_message:
                return render(request, 'document/authorization_form.html', {
                    'error_message': error_message,
                    'users': users
                })
            
            # Convert string dates to timezone-aware datetime objects
            try:
                # Parse the datetime strings
                naive_valid_from = datetime.datetime.fromisoformat(valid_from_str.replace('T', ' '))
                naive_valid_until = datetime.datetime.fromisoformat(valid_until_str.replace('T', ' '))
                
                # Make them timezone-aware
                valid_from = timezone.make_aware(naive_valid_from)
                valid_until = timezone.make_aware(naive_valid_until)
            except ValueError:
                return render(request, 'document/authorization_form.html', {
                    'error_message': "Invalid date format.",
                    'users': users
                })
            
            # Validate dates
            now = timezone.now()
            if valid_from >= valid_until:
                return render(request, 'document/authorization_form.html', {
                    'error_message': "End date must be after start date.",
                    'users': users
                })
            
            if valid_until <= now:
                return render(request, 'document/authorization_form.html', {
                    'error_message': "End date must be in the future.",
                    'users': users
                })
            
            # Get the authorized user
            try:
                authorized_user = CustomUser.objects.get(id=authorized_user_id)
            except CustomUser.DoesNotExist:
                return render(request, 'document/authorization_form.html', {
                    'error_message': "Selected user does not exist.",
                    'users': users
                })
            
            # Prevent self-authorization
            if authorized_user.id == request.user.id:
                return render(request, 'document/authorization_form.html', {
                    'error_message': "You cannot authorize yourself.",
                    'users': users
                })
            
            # Check for overlapping authorizations
            overlapping = ApprovalAuthorization.objects.filter(
                authorizer=request.user,
                authorized_user=authorized_user,
                valid_from__lt=valid_until,
                valid_until__gt=valid_from,
                is_active=True
            )
            
            if overlapping.exists():
                return render(request, 'document/authorization_form.html', {
                    'error_message': "There is already an overlapping authorization for this user.",
                    'users': users
                })
            
            # Create the authorization directly
            authorization = ApprovalAuthorization(
                authorizer=request.user,
                authorized_user=authorized_user,
                valid_from=valid_from,
                valid_until=valid_until,
                reason=reason,
                is_active=True
            )
            
            # Save the authorization
            authorization.save()
            
            messages.success(
                request, 
                f"Successfully authorized {authorized_user.username} to approve documents on your behalf."
            )
            return redirect('document_approval:authorization_list')
            
        except Exception as e:
            print(f"Error creating authorization: {str(e)}")
            return render(request, 'document/authorization_form.html', {
                'error_message': f"Error creating authorization: {str(e)}",
                'users': users
            })
    
    # GET request - show the form
    return render(request, 'document/authorization_form.html', {
        'users': users
    })


@login_required
def edit_authorization(request, pk):
    """View to edit an existing authorization"""
    authorization = get_object_or_404(ApprovalAuthorization, pk=pk)
    
    # Only the authorizer can edit their authorizations
    if authorization.authorizer != request.user:
        return HttpResponseForbidden("You don't have permission to edit this authorization.")
    
    if request.method == 'POST':
        form = ApprovalAuthorizationForm(
            request.POST, 
            instance=authorization
        )
        if form.is_valid():
            authorization = form.save(commit=False)
            # The authorizer should already be set, but we'll ensure it's correct
            authorization.authorizer = request.user
            authorization.save()
            messages.success(request, "Authorization updated successfully.")
            return redirect('document_approval:authorization_list')
    else:
        form = ApprovalAuthorizationForm(
            instance=authorization
        )
    
    return render(request, 'document/authorization_form.html', {
        'form': form,
        'title': 'Edit Authorization',
        'authorization': authorization,
    })


@login_required
def delete_authorization(request, pk):
    """View to delete an authorization"""
    authorization = get_object_or_404(ApprovalAuthorization, pk=pk)
    
    # Only the authorizer can delete their authorizations
    if authorization.authorizer != request.user:
        return HttpResponseForbidden("You don't have permission to delete this authorization.")
    
    if request.method == 'POST':
        authorization.delete()
        messages.success(request, "Authorization deleted successfully.")
        return redirect('document_approval:authorization_list')
    
    return render(request, 'document/authorization_confirm_delete.html', {
        'authorization': authorization,
    })


@login_required
def toggle_authorization(request, pk):
    """View to activate/deactivate an authorization"""
    authorization = get_object_or_404(ApprovalAuthorization, pk=pk)
    
    # Only the authorizer can toggle their authorizations
    if authorization.authorizer != request.user:
        return HttpResponseForbidden("You don't have permission to modify this authorization.")
    
    if request.method == 'POST':
        authorization.is_active = not authorization.is_active
        authorization.save()
        
        status = "activated" if authorization.is_active else "deactivated"
        messages.success(request, f"Authorization {status} successfully.")
        
        return redirect('document_approval:authorization_list')
    
    return render(request, 'document/authorization_toggle.html', {
        'authorization': authorization,
    })
