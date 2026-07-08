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
    unread_feedback_count = 0
    if restaurant is not None:
        unread_feedback_count = restaurant.feedbacks.filter(is_read=False).count()
    ctx.update({
        'restaurant': restaurant,
        'user_role': role,
        'unread_feedback_count': unread_feedback_count,
    })
    return ctx


def canonical_url(request):
    return {
        'canonical_url': request.build_absolute_uri(request.path),
    }
