import hashlib
import hmac
import json
import logging
from datetime import timedelta

import requests as http_requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from base.decorators import get_user_restaurant
from base.models import PromoCode, PromoCodeUse, SubscriptionPlan

logger = logging.getLogger(__name__)

from django.conf import settings as _settings
FEDAPAY_BASE = (
    'https://api.fedapay.com/v1'
    if getattr(_settings, 'FEDAPAY_ENV', 'sandbox') == 'live'
    else 'https://sandbox-api.fedapay.com/v1'
)


def _fedapay_headers():
    return {
        'Authorization': f'Bearer {settings.FEDAPAY_SECRET_KEY}',
        'Content-Type': 'application/json',
    }


def pricing(request):
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    restaurant = None
    current_plan = None
    if request.user.is_authenticated:
        restaurant, _ = get_user_restaurant(request.user)
        if restaurant:
            current_plan = restaurant.subscription_plan
    return render(request, 'home/pricing.html', {
        'plans': plans,
        'current_plan': current_plan,
        'restaurant': restaurant,
    })


@login_required
def subscribe_initiate(request, plan_type):
    restaurant, role = get_user_restaurant(request.user)
    if not restaurant:
        messages.error(request, "Aucun restaurant trouvé.")
        return redirect('create_restaurant')

    if role not in ('owner', 'coadmin'):
        messages.error(request, "Seul le propriétaire peut gérer l'abonnement.")
        return redirect('dashboard')

    plan = SubscriptionPlan.objects.filter(plan_type=plan_type, is_active=True).first()
    if not plan:
        messages.error(request, "Plan introuvable.")
        return redirect('pricing')

    # Free plan — apply directly without payment
    if plan.price == 0:
        restaurant.subscription_plan = plan
        restaurant.subscription_start = timezone.now()
        restaurant.subscription_end = timezone.now() + timedelta(days=plan.duration_days)
        restaurant.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_end'])
        messages.success(request, f"Vous êtes maintenant sur le plan {plan.name}.")
        return redirect('dashboard')

    # Check promo code
    promo_code_input = request.POST.get('promo_code', '').strip().upper()
    if promo_code_input:
        try:
            promo = PromoCode.objects.get(code=promo_code_input)
            if promo.is_valid():
                promo.uses_count += 1
                promo.save(update_fields=['uses_count'])
                PromoCodeUse.objects.get_or_create(promo_code=promo, restaurant=restaurant)
                restaurant.subscription_plan = promo.plan
                restaurant.subscription_start = timezone.now()
                restaurant.subscription_end = timezone.now() + timedelta(days=promo.duration_days)
                restaurant.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_end'])
                messages.success(request, f"Code appliqué ! Plan {promo.plan.name} actif pendant {promo.duration_days} jours.")
                return redirect('dashboard')
            else:
                messages.error(request, "Ce code promo n'est plus valide.")
                return redirect('pricing')
        except PromoCode.DoesNotExist:
            messages.error(request, "Code promo invalide.")
            return redirect('pricing')

    # Initiate FedaPay payment
    callback_url = request.build_absolute_uri(f'/abonnement/callback/{plan_type}/')
    payload = {
        'description': f'OpenFood — Plan {plan.name} (1 mois)',
        'amount': int(plan.price),
        'currency': {'iso': 'XOF'},
        'callback_url': callback_url,
        'customer': {
            'email': request.user.email,
            'firstname': request.user.first_name or 'Client',
            'lastname': request.user.last_name or 'OpenFood',
        },
        'metadata': {
            'restaurant_id': restaurant.pk,
            'plan_type': plan_type,
        },
    }
    try:
        resp = http_requests.post(
            f'{FEDAPAY_BASE}/transactions',
            json=payload,
            headers=_fedapay_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        transaction_id = data.get('v1/transaction', {}).get('id') or data.get('id')

        # Generate payment token/URL
        token_resp = http_requests.post(
            f'{FEDAPAY_BASE}/transactions/{transaction_id}/token',
            headers=_fedapay_headers(),
            timeout=10,
        )
        token_resp.raise_for_status()
        token_data = token_resp.json()
        payment_url = token_data.get('url') or token_data.get('token', {}).get('url')

        if payment_url:
            return redirect(payment_url)
        raise ValueError("No payment URL in FedaPay response")

    except Exception as e:
        logger.error("FedaPay initiate failed: %s", e)
        messages.error(request, "Erreur lors de la création du paiement. Vérifiez votre connexion et réessayez.")
        return redirect('pricing')


@login_required
def subscribe_callback(request, plan_type):
    restaurant, role = get_user_restaurant(request.user)
    if not restaurant:
        return redirect('create_restaurant')

    transaction_id = request.GET.get('id') or request.GET.get('transaction_id')
    if not transaction_id:
        messages.error(request, "Référence de paiement introuvable.")
        return redirect('pricing')

    try:
        resp = http_requests.get(
            f'{FEDAPAY_BASE}/transactions/{transaction_id}',
            headers=_fedapay_headers(),
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        transaction = data.get('v1/transaction', data)
        status = transaction.get('status')
    except Exception as e:
        logger.error("FedaPay retrieve failed: %s", e)
        messages.error(request, "Impossible de vérifier le paiement.")
        return redirect('pricing')

    if status == 'approved':
        plan = SubscriptionPlan.objects.filter(plan_type=plan_type, is_active=True).first()
        if plan:
            now = timezone.now()
            if (restaurant.subscription_plan == plan
                    and restaurant.subscription_end
                    and restaurant.subscription_end > now):
                new_end = restaurant.subscription_end + timedelta(days=plan.duration_days)
            else:
                new_end = now + timedelta(days=plan.duration_days)

            restaurant.subscription_plan = plan
            restaurant.subscription_start = now
            restaurant.subscription_end = new_end
            restaurant.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_end'])
            messages.success(request, f"Paiement confirmé ! Plan {plan.name} actif jusqu'au {new_end.strftime('%d/%m/%Y')}.")
            return redirect('dashboard')

    messages.error(request, "Le paiement n'a pas été confirmé. Veuillez réessayer.")
    return redirect('pricing')


@login_required
def subscription_status(request):
    restaurant, role = get_user_restaurant(request.user)
    if not restaurant:
        return redirect('create_restaurant')
    plan = restaurant.subscription_plan
    is_expired = bool(restaurant.subscription_end and restaurant.subscription_end < timezone.now())
    days_left = None
    if restaurant.subscription_end and not is_expired:
        days_left = (restaurant.subscription_end - timezone.now()).days
    return render(request, 'admin_user/subscription/status.html', {
        'restaurant': restaurant,
        'plan': plan,
        'is_expired': is_expired,
        'days_left': days_left,
        'all_plans': SubscriptionPlan.objects.filter(is_active=True).order_by('price'),
    })


@csrf_exempt
def fedapay_webhook(request):
    if request.method != 'POST':
        return HttpResponse(status=405)

    secret = getattr(settings, 'FEDAPAY_WEBHOOK_SECRET', '')
    sig = request.headers.get('X-Fedapay-Signature', '')

    if secret:
        expected = hmac.new(secret.encode(), request.body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return HttpResponse('Invalid signature', status=400)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponse('Bad JSON', status=400)

    event = payload.get('name', '')
    obj = payload.get('data', {}).get('object', {})

    if event == 'transaction.approved' and obj.get('status') == 'approved':
        meta = obj.get('metadata') or {}
        restaurant_id = meta.get('restaurant_id')
        plan_type = meta.get('plan_type')

        if restaurant_id and plan_type:
            from base.models import Restaurant
            try:
                restaurant = Restaurant.objects.get(pk=restaurant_id)
                plan = SubscriptionPlan.objects.filter(plan_type=plan_type, is_active=True).first()
                if plan:
                    now = timezone.now()
                    if (restaurant.subscription_plan == plan
                            and restaurant.subscription_end
                            and restaurant.subscription_end > now):
                        new_end = restaurant.subscription_end + timedelta(days=plan.duration_days)
                    else:
                        new_end = now + timedelta(days=plan.duration_days)
                    restaurant.subscription_plan = plan
                    restaurant.subscription_start = now
                    restaurant.subscription_end = new_end
                    restaurant.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_end'])
            except Restaurant.DoesNotExist:
                logger.warning("Webhook: restaurant %s not found", restaurant_id)

    return JsonResponse({'received': True})
