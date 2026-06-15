from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from base.models import Order, WaiterCall
from base import push


@receiver(post_save, sender=Order)
def _push_on_new_order(sender, instance, created, **kwargs):
    """Web Push staff when a new order is created (after the tx commits, so the
    total computed by calculate_total() is available)."""
    if not created:
        return
    order_id = instance.id
    transaction.on_commit(lambda: push.notify_new_order(order_id))


@receiver(post_save, sender=WaiterCall)
def _push_on_waiter_call(sender, instance, created, **kwargs):
    if not created:
        return
    call_id = instance.id
    transaction.on_commit(lambda: push.notify_waiter_call(call_id))
