from base.decorators import get_user_restaurant


def restaurant_context(request):
    if not request.user.is_authenticated:
        return {}
    restaurant, role = get_user_restaurant(request.user)
    return {
        'restaurant': restaurant,
        'user_role': role,
    }
