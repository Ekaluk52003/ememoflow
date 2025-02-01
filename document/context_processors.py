from .utils import get_user_bu_groups

def user_bu_groups(request):
    """Add user's BU groups to template context"""
    if request.user.is_authenticated:
        bu_groups = get_user_bu_groups(request.user)
        return {
            'user_bu_groups': ', '.join(sorted(bu_groups)) if bu_groups else ''
        }
    return {'user_bu_groups': ''}
