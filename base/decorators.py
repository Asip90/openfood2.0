# base/decorators.py
from functools import wraps
from django.shortcuts import redirect
from base.models import StaffMember, Restaurant


def get_staff_from_session(request):
    """Return the active StaffMember from session, or None."""
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return None
    try:
        return StaffMember.objects.select_related('restaurant').get(
            id=staff_id, is_active=True
        )
    except StaffMember.DoesNotExist:
        return None


def staff_required(roles=None):
    """
    Decorator for views accessible only to active StaffMembers.
    roles: list of allowed roles e.g. ['cuisinier', 'serveur']; None = all roles.
    Attaches request.staff_member on success.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            staff = get_staff_from_session(request)
            if staff is None:
                return redirect('staff_login')
            if roles and staff.role not in roles:
                return redirect('staff_orders')
            request.staff_member = staff
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_or_coadmin_required(view_func):
    """
    Decorator for staff management views.
    Accepts Django-authenticated owner OR coadmin via staff session.
    Attaches request.managing_restaurant and request.staff_member (None for owner).
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Case 1: Django-authenticated restaurant owner
        if request.user.is_authenticated:
            restaurant = Restaurant.objects.filter(owner=request.user).first()
            if restaurant:
                request.managing_restaurant = restaurant
                request.staff_member = None
                return view_func(request, *args, **kwargs)
        # Case 2: coadmin via staff session
        staff = get_staff_from_session(request)
        if staff and staff.role == 'coadmin':
            request.managing_restaurant = staff.restaurant
            request.staff_member = staff
            return view_func(request, *args, **kwargs)
        return redirect('connexion')
    return wrapper
