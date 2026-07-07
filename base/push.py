"""Web Push (VAPID) helpers.

Keys are read from environment variables (loaded from main/.env), so this module
never touches settings.py:

    VAPID_PRIVATE_KEY   absolute path to the PEM private key (or the raw key string)
    VAPID_PUBLIC_KEY    application server key (base64url) exposed to the browser
    VAPID_CLAIMS_EMAIL  contact, e.g. "mailto:admin@openfood.site"

Sending is done in a background thread so it never blocks the request that
created the order / waiter call (e.g. a customer checkout).
"""
import json
import logging
import os
import threading

from django.db import connections

logger = logging.getLogger(__name__)


def get_vapid_private_key():
    return (os.getenv('VAPID_PRIVATE_KEY') or '').strip()


def get_vapid_public_key():
    return (os.getenv('VAPID_PUBLIC_KEY') or '').strip()


def get_vapid_claims_email():
    return (os.getenv('VAPID_CLAIMS_EMAIL') or 'mailto:admin@openfood.site').strip()


def push_enabled():
    return bool(get_vapid_private_key() and get_vapid_public_key())


def send_web_push(subscription, payload):
    """Send to a single PushSubscription. Removes the subscription if it is gone."""
    try:
        from pywebpush import webpush, WebPushException
    except Exception as e:  # pragma: no cover - dependency missing
        logger.warning("pywebpush not available: %s", e)
        return False
    try:
        webpush(
            subscription_info=subscription.as_subscription_info(),
            data=json.dumps(payload),
            vapid_private_key=get_vapid_private_key(),
            vapid_claims={"sub": get_vapid_claims_email()},
            timeout=10,
        )
        return True
    except WebPushException as e:
        status = getattr(getattr(e, 'response', None), 'status_code', None)
        if status in (404, 410):
            # Subscription expired / unsubscribed — clean it up.
            subscription.delete()
        else:
            logger.warning("WebPush failed (%s): %s", status, e)
        return False
    except Exception as e:
        logger.warning("WebPush error: %s", e)
        return False


def _send_to_roles(restaurant, roles, payload):
    from base.models import PushSubscription, StaffMember
    user_ids = set()
    if 'owner' in roles and getattr(restaurant, 'owner_id', None):
        user_ids.add(restaurant.owner_id)
    staff_roles = [r for r in roles if r != 'owner']
    if staff_roles:
        user_ids.update(
            StaffMember.objects.filter(
                restaurant=restaurant, is_active=True, role__in=staff_roles
            ).values_list('user_id', flat=True)
        )
    if not user_ids:
        return
    for sub in PushSubscription.objects.filter(user_id__in=user_ids):
        send_web_push(sub, payload)


def _worker_new_order(order_id):
    from base.models import Order
    order = Order.objects.select_related('restaurant', 'table').filter(id=order_id).first()
    if not order:
        return
    where = f"Table {order.table.number}" if order.table else (order.customer_name or "Client")
    total = int(order.total) if order.total else 0
    _send_to_roles(order.restaurant, ['owner', 'coadmin', 'cuisinier', 'serveur'], {
        "title": "Nouvelle commande",
        "body": f"{where} · {total} FCFA",
        "tag": f"order-{order.id}",
        "url": "/orders/",
    })


def _worker_waiter_call(call_id):
    from base.models import WaiterCall
    call = WaiterCall.objects.select_related('restaurant', 'table').filter(id=call_id).first()
    if not call:
        return
    _send_to_roles(call.restaurant, ['owner', 'coadmin', 'serveur'], {
        "title": "Appel serveur",
        "body": f"Table {call.table.number} demande un serveur",
        "tag": f"call-{call.id}",
        "url": "/orders/",
    })


def _worker_order_ready(order_id):
    from base.models import Order
    order = Order.objects.select_related('restaurant', 'table').filter(id=order_id).first()
    if not order:
        return
    where = f"Table {order.table.number}" if order.table else (order.customer_name or "À emporter")
    number = order.order_number[-6:] if order.order_number else str(order.id)
    _send_to_roles(order.restaurant, ['owner', 'coadmin', 'serveur'], {
        "title": "Commande prête 🛎️",
        "body": f"#{number} · {where} — à servir",
        "tag": f"ready-{order.id}",
        "url": "/dashboard/",
    })


CUSTOMER_STATUS_MESSAGES = {
    'confirmed': "Votre commande est confirmée 👍",
    'preparing': "Votre commande est en préparation 🍳",
    'ready':     "Votre commande est prête ! 🎉",
    'delivered': "Bon appétit ! 😋",
    'cancelled': "Votre commande a été annulée.",
}


def _worker_customer_status(order_id, status):
    from base.models import Order, CustomerPushSubscription
    order = Order.objects.select_related('restaurant').filter(id=order_id).first()
    if not order:
        return
    body = CUSTOMER_STATUS_MESSAGES.get(status)
    if not body:
        return
    number = order.order_number[-6:] if order.order_number else str(order.id)
    payload = {
        "title": f"{order.restaurant.name} · Commande #{number}",
        "body": body,
        "tag": f"orderstatus-{order.id}",
        "url": "/mes-commandes/",
    }
    for sub in CustomerPushSubscription.objects.filter(order=order):
        send_web_push(sub, payload)


def notify_customer_status(order_id, status):
    _run_async(_worker_customer_status, order_id, status)


def _run_async(fn, *args):
    if not push_enabled():
        return

    def _target():
        try:
            fn(*args)
        except Exception as e:
            logger.warning("push worker error: %s", e)
        finally:
            connections.close_all()

    threading.Thread(target=_target, daemon=True).start()


def notify_new_order(order_id):
    _run_async(_worker_new_order, order_id)


def notify_waiter_call(call_id):
    _run_async(_worker_waiter_call, call_id)


def notify_order_ready(order_id):
    _run_async(_worker_order_ready, order_id)
