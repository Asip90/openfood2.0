import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from base.decorators import get_user_restaurant
from base.models import PushSubscription
from base.push import get_vapid_public_key, push_enabled


@require_GET
def vapid_public_key(request):
    return JsonResponse({"publicKey": get_vapid_public_key(), "enabled": push_enabled()})


@login_required
@require_POST
def push_subscribe(request):
    try:
        data = json.loads(request.body.decode() or '{}')
        sub = data.get('subscription') or data
        endpoint = sub['endpoint']
        keys = sub['keys']
        p256dh = keys['p256dh']
        auth = keys['auth']
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False, "error": "invalid payload"}, status=400)

    restaurant, _role = get_user_restaurant(request.user)
    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "restaurant": restaurant,
            "p256dh": p256dh,
            "auth": auth,
            "user_agent": request.META.get('HTTP_USER_AGENT', '')[:300],
        },
    )
    return JsonResponse({"ok": True})


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        data = json.loads(request.body.decode() or '{}')
        endpoint = data.get('endpoint')
    except ValueError:
        endpoint = None
    if endpoint:
        PushSubscription.objects.filter(endpoint=endpoint, user=request.user).delete()
    return JsonResponse({"ok": True})
