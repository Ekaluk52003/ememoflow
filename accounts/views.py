from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.db.models import Q, Prefetch
from django.http import HttpResponse

from .models import CustomUser

@login_required
def user_list(request):
    """
    View to display all active users grouped by their groups.
    Includes filtering functionality by group using HTMX.
    """
    # Get all groups
    groups = Group.objects.all().order_by('name')
    
    # Get filter parameter
    filter_group = request.GET.get('group', None)
    
    # Base query for active users
    users_query = CustomUser.objects.filter(is_active=True).prefetch_related('groups')
    
    # Apply group filter if specified
    if filter_group and filter_group != 'all':
        users_query = users_query.filter(groups__name=filter_group)
        
        # When filtering by a specific group, we only show that group
        users = users_query.order_by('username')
        users_by_group = {filter_group: list(users)}
        users_with_no_group = []
    else:
        # Get all users when not filtering
        users = users_query.order_by('username')
        
        # Organize users by group
        users_by_group = {}
        
        # Users with no group
        users_with_no_group = []
        
        for user in users:
            user_groups = list(user.groups.all())
            
            if not user_groups:
                users_with_no_group.append(user)
                continue
                
            for group in user_groups:
                if group.name not in users_by_group:
                    users_by_group[group.name] = []
                users_by_group[group.name].append(user)
    
    context = {
        'groups': groups,
        'users_by_group': users_by_group,
        'users_with_no_group': users_with_no_group,
        'filter_group': filter_group,
    }
    
    # Check if this is an HTMX request
    if request.headers.get('HX-Request'):
        # For HTMX requests with push-url, we only need to return the partial content
        # The URL will be updated in the browser automatically by HTMX
        return render(request, 'accounts/partials/user_list_content.html', context)
    
    # Return the full page for regular requests
    return render(request, 'accounts/user_list.html', context)
