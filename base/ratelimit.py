# base/ratelimit.py
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse, JsonResponse


def get_client_ip(request):
    """IP réelle du client (derrière nginx, REMOTE_ADDR est le proxy)."""
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def rate_limit(key_prefix, max_requests, window_seconds, methods=('POST',), json_response=False):
    """
    Limite le nombre de requêtes par IP sur une fenêtre glissante approximative.

    Basé sur le cache Django (LocMem par défaut : compteur par worker gunicorn,
    donc la limite effective est max_requests × nb_workers — suffisant contre
    le brute-force et le spam).
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.method in methods:
                key = f"rl:{key_prefix}:{get_client_ip(request)}"
                cache.add(key, 0, timeout=window_seconds)
                try:
                    count = cache.incr(key)
                except ValueError:
                    # La clé a expiré entre add et incr
                    cache.add(key, 1, timeout=window_seconds)
                    count = 1
                if count > max_requests:
                    if json_response:
                        return JsonResponse(
                            {"error": "Trop de requêtes. Réessayez dans quelques instants."},
                            status=429,
                        )
                    return HttpResponse(
                        "Trop de requêtes. Réessayez dans quelques instants.",
                        status=429,
                    )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator
