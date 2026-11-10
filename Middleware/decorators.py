from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def admin_required(min_weight=2):
    """
    Custom decorator to block users whose role weight is below the required threshold.
    min_weight = 2 (Checkers/Staff), 3 (Admins), 4 (Super Admins)
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('portal_login')
            
            profile = getattr(request.user, 'profile', None)
            from Middleware.views import get_role_weight
            weight = get_role_weight(profile.user_role if profile else None)
            
            if weight < min_weight:
                messages.error(request, "Access Denied: You do not have the required permissions to view this page.")
                return redirect('dashboard') # Or a generic 403 page
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator


def auth_manager_access_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied

        from Middleware.models import Permission, Profile

        # 1. Check Permission table for active, approved AUTH_MANAGER assignment
        has_app_perm = Permission.objects.filter(
            user=request.user,
            application__app_id__iexact='AUTH_MANAGER',
            permission_type__in=['maker', 'checker', 'admin'],
            is_active=True,
            approval_status__iexact='approved'
        ).exists()

        if has_app_perm:
            return view_func(request, *args, **kwargs)

        # 2. Fallback check for Profile user_role
        try:
            profile = Profile.objects.get(username=request.user)
            if profile.user_role and profile.user_role.strip().lower() in ['maker', 'checker', 'admin']:
                return view_func(request, *args, **kwargs)
        except Profile.DoesNotExist:
            pass

        raise PermissionDenied
        
    return _wrapped_view