from django.conf import settings as _settings

from base.decorators import get_user_restaurant


def restaurant_context(request):
    user = getattr(request, 'user', None)
    ctx = {
        'GA_MEASUREMENT_ID': getattr(_settings, 'GA_MEASUREMENT_ID', ''),
    }
    if user is None or not user.is_authenticated:
        return ctx
    restaurant, role = get_user_restaurant(user)
    ctx.update({
        'restaurant': restaurant,
        'user_role': role,
    })
    return ctx
