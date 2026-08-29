from django.db.models import Q

from .models import Project

def experiments_for_user(request):
    """Context processor that injects a group-scoped 'experiments' queryset for the sidebar.

    Returns an 'experiments' variable containing experiments whose project.group matches
    the logged-in user's research group. If the user is anonymous or has no group, returns an empty queryset.
    """
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {'experiments': Project.objects.none(), 'page_obj': None, 'search_query': ''}

    profile = getattr(user, 'profile', None)
    rg = getattr(profile, 'research_group', None)
    filters = Q(authorized_users=user)
    if rg:
        filters |= Q(project__group=rg)
    qs = Project.objects.filter(filters).distinct().order_by('-created_on')
    # We return the full queryset here; views can still override via context if needed.
    return {'experiments': qs, 'page_obj': None, 'search_query': ''}
