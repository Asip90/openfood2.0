"""Logique carte de fidélité (tampons)."""
from django.db import transaction
from django.db.models import F
from base.models import LoyaltyProgram, LoyaltyCard, Order


def program_for(restaurant):
    if not restaurant.is_pro():
        return None
    prog = LoyaltyProgram.objects.filter(restaurant=restaurant).first()
    if prog is None or not prog.is_enabled:
        return None
    return prog


def award_for_order(order):
    """Crédite 1 tampon pour une commande payée. Idempotent."""
    if order.loyalty_awarded or not order.customer_phone:
        return None
    prog = program_for(order.restaurant)
    if prog is None:
        return None
    claimed = Order.objects.filter(pk=order.pk, loyalty_awarded=False).update(loyalty_awarded=True)
    if not claimed:
        return None
    order.loyalty_awarded = True
    card, _ = LoyaltyCard.objects.get_or_create(
        restaurant=order.restaurant, phone=order.customer_phone)
    LoyaltyCard.objects.filter(pk=card.pk).update(stamps=F('stamps') + 1)
    card.refresh_from_db()
    return card


def redeem(card):
    with transaction.atomic():
        card = LoyaltyCard.objects.select_for_update().get(pk=card.pk)
        prog = LoyaltyProgram.objects.filter(restaurant=card.restaurant).first()
        required = prog.stamps_required if prog else 0
        if not required or card.stamps < required:
            return False
        card.stamps -= required
        card.rewards_redeemed += 1
        card.save(update_fields=["stamps", "rewards_redeemed", "updated_at"])
    return True


def progress(restaurant, phone):
    prog = program_for(restaurant)
    if prog is None or not phone:
        return None
    card = LoyaltyCard.objects.filter(restaurant=restaurant, phone=phone).first()
    stamps = card.stamps if card else 0
    return {
        "stamps": stamps,
        "required": prog.stamps_required,
        "remaining": max(0, prog.stamps_required - stamps),
        "reward_available": stamps >= prog.stamps_required,
        "reward_label": prog.reward_label,
    }
