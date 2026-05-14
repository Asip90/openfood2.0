from base.decorators import get_user_restaurant


def restaurant_context(request):
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {}
    restaurant, role = get_user_restaurant(user)
    return {
        'restaurant': restaurant,
        'user_role': role,
    }
