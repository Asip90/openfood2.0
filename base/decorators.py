# base/decorators.py
from functools import wraps
from django.shortcuts import redirect
from base.models import Restaurant


def get_user_restaurant(user):
    """
    Returns (restaurant, role) for a Django User.
    role is 'owner' for restaurant owners, or the StaffMember role string.
    Returns (None, None) if the user has no associated restaurant.
    """
    if hasattr(user, 'staff_profile') and user.staff_profile.is_active:
        sp = user.staff_profile
        return sp.restaurant, sp.role
    restaurant = Restaurant.objects.filter(owner=user).first()
    if restaurant:
        return restaurant, 'owner'
    return None, None


def restaurant_required(allowed_roles=None):
    """
    Decorator that:
    1. Requires authentication (redirects to 'connexion' if not).
    2. Resolves (restaurant, role) via get_user_restaurant.
    3. Redirects to 'create_restaurant' if no restaurant found.
    4. Redirects to 'dashboard' if role not in allowed_roles (when specified).
    5. Sets request.restaurant and request.user_role for the view.

    Usage:
        @restaurant_required()                          # any role
        @restaurant_required(['owner', 'coadmin'])      # restricted
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('connexion')
            restaurant, role = get_user_restaurant(request.user)
            if not restaurant:
                return redirect('create_restaurant')
            if allowed_roles and role not in allowed_roles:
                return redirect('dashboard')
            request.restaurant = restaurant
            request.user_role = role
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def owner_or_coadmin_required(view_func):
    """Shortcut decorator for owner + coadmin only views."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('connexion')
        restaurant, role = get_user_restaurant(request.user)
        if not restaurant:
            return redirect('create_restaurant')
        if role not in ('owner', 'coadmin'):
            return redirect('dashboard')
        request.restaurant = restaurant
        request.user_role = role
        return view_func(request, *args, **kwargs)
    return wrapper
