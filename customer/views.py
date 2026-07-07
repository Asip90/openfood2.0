import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.contrib import messages
from django.db import transaction
from django.db.models import Avg, F, Prefetch, Sum

from base.models import Category, MenuItem, Order, OrderItem, RestaurantCustomization, AISettings, CustomerPushSubscription
from base.ratelimit import rate_limit
from base.services.ai.assistant import ask, is_assistant_available
from customer.utils import get_client_context


def client_menu(request, table_token):
    restaurant, table, customization, error = get_client_context(request, table_token)
    if error:
        return error

    categories = Category.objects.filter(
        restaurant=restaurant,
        is_active=True
    ).prefetch_related(
        Prefetch(
            "items",
            queryset=MenuItem.objects.filter(
                restaurant=restaurant,
                is_available=True
            ).prefetch_related('media')
        )
    ).order_by("order")

    categories = list(categories)  # evaluate queryset to allow reuse below
    has_active_items = any(list(cat.items.all()) for cat in categories)

    cart_key = f"cart_{restaurant.id}_{table_token}"
    cart = request.session.get(cart_key, {})

    cart_items = []
    cart_total = 0
    cart_count = 0

    for item_id, item_data in cart.items():
        try:
            MenuItem.objects.get(id=item_id, restaurant=restaurant)
            item_total = float(item_data["price"]) * item_data["quantity"]
            cart_total += item_total
            cart_count += item_data["quantity"]
            cart_items.append({
                "id": str(item_id),
                "name": item_data["name"],
                "price": float(item_data["price"]),
                "quantity": item_data["quantity"],
                "image": item_data.get("image"),
                "total": item_total
            })
        except MenuItem.DoesNotExist:
            continue

    # Top vendeurs du restaurant (badge « Populaire ») — 3 max, seuil 2 unités
    popular_ids = set(
        OrderItem.objects.filter(order__restaurant=restaurant)
        .values("menu_item_id")
        .annotate(qty=Sum("quantity"))
        .filter(qty__gte=2)
        .order_by("-qty")
        .values_list("menu_item_id", flat=True)[:3]
    )

    # Temps de préparation moyen des plats actifs (hero « Prêt en ~X min »)
    avg_prep = (
        MenuItem.objects.filter(
            restaurant=restaurant, is_available=True, preparation_time__gt=0
        ).aggregate(avg=Avg("preparation_time"))["avg"]
    )

    context = {
        "restaurant": restaurant,
        "table": table,
        "customization": customization,
        "categories": categories,
        "has_active_items": has_active_items,
        "cart": cart_items,
        "cart_total": cart_total,
        "cart_count": cart_count,
        "table_token": table_token,
        "cart_json": json.dumps(cart_items),
        "ai_enabled": is_assistant_available(),
        "popular_ids": popular_ids,
        "avg_prep": int(round(avg_prep)) if avg_prep else None,
        "opening_hours_json": json.dumps(restaurant.opening_hours or {}),
    }

    return render(request, "customer/menu.html", context)


@csrf_exempt
def update_cart(request, table_token):
    if request.method != "POST":
        return JsonResponse({"success": False})

    restaurant, table, _, error = get_client_context(request, table_token)
    if error:
        return JsonResponse({"success": False, "error": "Contexte invalide"})

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "JSON invalide"})

    cart_key = f"cart_{restaurant.id}_{table_token}"

    # Format full-cart : {"cart": [{id, name, price, image, quantity}, ...]}
    if "cart" in data:
        new_cart = {}
        for item in data["cart"]:
            item_id = str(item.get("id", "")).strip()
            quantity = int(item.get("quantity", 1))
            if not item_id or quantity <= 0:
                continue
            try:
                menu_item = MenuItem.objects.get(
                    id=item_id, restaurant=restaurant, is_available=True
                )
                new_cart[item_id] = {
                    "name": menu_item.name,
                    "price": str(menu_item.discount_price or menu_item.price),
                    "quantity": quantity,
                    "image": menu_item.image.url if menu_item.image else None,
                }
            except MenuItem.DoesNotExist:
                continue
        request.session[cart_key] = new_cart
        request.session.modified = True

    else:
        # Format legacy : {"action": "add"|"update"|"remove", "item_id": "12"}
        action = data.get("action")
        item_id = str(data.get("item_id", "")).strip()
        cart = request.session.get(cart_key, {})

        if action == "add" and item_id:
            try:
                item = MenuItem.objects.get(
                    id=item_id, restaurant=restaurant, is_available=True
                )
                if item_id in cart:
                    cart[item_id]["quantity"] += 1
                else:
                    cart[item_id] = {
                        "name": item.name,
                        "price": str(item.discount_price or item.price),
                        "quantity": 1,
                        "image": item.image.url if item.image else None,
                    }
            except MenuItem.DoesNotExist:
                pass

        elif action == "update" and item_id:
            qty = int(data.get("quantity", 1))
            if item_id in cart:
                if qty > 0:
                    cart[item_id]["quantity"] = qty
                else:
                    del cart[item_id]

        elif action == "remove" and item_id:
            cart.pop(item_id, None)

        request.session[cart_key] = cart
        request.session.modified = True

    cart = request.session.get(cart_key, {})
    total = sum(float(i["price"]) * i["quantity"] for i in cart.values())
    count = sum(i["quantity"] for i in cart.values())

    return JsonResponse({
        "success": True,
        "cart_total": total,
        "cart_count": count,
    })


def checkout(request, table_token):
    restaurant, table, customization, error = get_client_context(request, table_token)
    if error:
        return error

    cart_key = f"cart_{restaurant.id}_{table_token}"
    cart = request.session.get(cart_key, {})

    # Panier éventuellement modifié sur la page de finalisation (steppers)
    if request.method == "POST" and request.POST.get("cart_data"):
        try:
            edited = json.loads(request.POST["cart_data"])
        except (json.JSONDecodeError, TypeError):
            edited = []
        new_cart = {}
        for it in edited:
            iid = str(it.get("id", "")).strip()
            qty = int(it.get("quantity", 0) or 0)
            if not iid or qty <= 0:
                continue
            try:
                mi = MenuItem.objects.get(id=iid, restaurant=restaurant, is_available=True)
            except MenuItem.DoesNotExist:
                continue
            new_cart[iid] = {
                "name": mi.name,
                "price": str(mi.discount_price or mi.price),
                "quantity": qty,
                "image": mi.image.url if mi.image else None,
            }
        cart = new_cart
        request.session[cart_key] = new_cart
        request.session.modified = True

    if not cart:
        messages.error(request, "Votre panier est vide")
        return redirect("client_menu", table_token=table_token)

    if request.method == "POST":
        raw_type = request.POST.get("order_type", "dine_in")
        order_type = raw_type if raw_type in ("dine_in", "takeaway") else "dine_in"
        with transaction.atomic():
            order = Order.objects.create(
                restaurant=restaurant,
                table=table,
                order_type=order_type,
                status="pending",
                customer_name=request.POST.get("customer_name", "").strip(),
                customer_phone=request.POST.get("customer_phone", "").strip(),
                notes=request.POST.get("notes", "").strip(),
            )

            for item_id, data in cart.items():
                # Prix relu en BDD au moment de la commande : le prix stocké en
                # session peut être périmé si le restaurateur l'a modifié.
                try:
                    menu_item = MenuItem.objects.get(id=item_id, restaurant=restaurant)
                except MenuItem.DoesNotExist:
                    continue
                OrderItem.objects.create(
                    order=order,
                    menu_item=menu_item,
                    quantity=data["quantity"],
                    price=menu_item.discount_price or menu_item.price,
                )

            order.calculate_total()
            del request.session[cart_key]

            return redirect("order_confirmation", public_token=order.public_token)

    cart_items = []
    cart_total = 0
    for item_id, data in cart.items():
        item_total = float(data["price"]) * data["quantity"]
        cart_total += item_total
        cart_items.append({
            "id": str(item_id),
            "name": data["name"],
            "price": float(data["price"]),
            "quantity": data["quantity"],
            "image": data.get("image"),
            "total": item_total,
        })

    return render(request, "customer/checkout.html", {
        "restaurant": restaurant,
        "customization": customization,
        "table": table,
        "table_token": table_token,
        "cart": cart_items,
        "cart_total": int(cart_total),
        "cart_json": json.dumps(cart_items),
    })


def order_confirmation(request, public_token):
    order = get_object_or_404(Order, public_token=public_token)
    customization = RestaurantCustomization.objects.filter(
        restaurant=order.restaurant
    ).first()

    table_token = order.table.token if order.table else None

    return render(request, "customer/confirmation.html", {
        "order": order,
        "restaurant": order.restaurant,
        "customization": customization,
        "table": order.table,
        "table_token": table_token,
    })


@require_GET
def order_status(request, public_token):
    """Suivi du statut par le client (page de confirmation)."""
    order = get_object_or_404(Order, public_token=public_token)
    return JsonResponse({
        "status": order.status,
        "status_display": order.get_status_display(),
    })


@csrf_exempt
@require_POST
def customer_push_subscribe(request, public_token):
    """Abonne l'appareil du client au push pour suivre CETTE commande (sans compte)."""
    order = get_object_or_404(Order, public_token=public_token)
    try:
        data = json.loads(request.body)
        sub = data.get("subscription") or data
        endpoint = sub["endpoint"]
        keys = sub["keys"]
        p256dh, auth = keys["p256dh"], keys["auth"]
    except (ValueError, KeyError, TypeError):
        return JsonResponse({"ok": False, "error": "payload invalide"}, status=400)

    CustomerPushSubscription.objects.update_or_create(
        order=order,
        endpoint=endpoint,
        defaults={"p256dh": p256dh, "auth": auth},
    )
    return JsonResponse({"ok": True})


def my_orders(request):
    """Page « Mes commandes du jour » — la liste vit dans le localStorage de l'appareil,
    les statuts sont rafraîchis via order_status. Aucun compte requis."""
    restaurant = getattr(request, "restaurant", None)
    if not restaurant:
        return render(request, "customer/error.html", {"message": "Restaurant non disponible"})
    customization, _ = RestaurantCustomization.objects.get_or_create(restaurant=restaurant)
    return render(request, "customer/my_orders.html", {
        "restaurant": restaurant,
        "customization": customization,
    })


@csrf_exempt
@require_POST
@rate_limit("orders-by-phone", max_requests=8, window_seconds=300, json_response=True)
def my_orders_by_phone(request):
    """Retrouve les commandes du jour par numéro de téléphone (résumé + statut only,
    pas le jeton d'accès : évite l'énumération et l'accès au détail complet)."""
    from django.utils import timezone
    restaurant = getattr(request, "restaurant", None)
    if not restaurant:
        return JsonResponse({"orders": []})
    try:
        phone = str(json.loads(request.body).get("phone", "")).strip()
    except (json.JSONDecodeError, TypeError):
        phone = ""
    digits = "".join(c for c in phone if c.isdigit())
    if len(digits) < 6:
        return JsonResponse({"error": "Numéro invalide.", "orders": []}, status=400)

    today = timezone.localdate()
    qs = Order.objects.filter(
        restaurant=restaurant,
        customer_phone__icontains=digits,
        created_at__date=today,
    ).select_related("table").order_by("-created_at")[:20]

    orders = [{
        "number": o.order_number[-6:] if o.order_number else str(o.id),
        "total": int(o.total or 0),
        "table": o.table.number if o.table else None,
        "status": o.status,
        "status_display": o.get_status_display(),
    } for o in qs]
    return JsonResponse({"orders": orders})


@csrf_exempt
def get_item_details(request, item_id):
    if request.method != 'GET':
        return JsonResponse({'success': False})

    # Scopé au restaurant du sous-domaine : pas de fuite inter-restaurants
    restaurant = getattr(request, "restaurant", None)
    if restaurant is None:
        return JsonResponse({'success': False, 'error': 'Restaurant non disponible'}, status=404)

    try:
        item = MenuItem.objects.get(id=item_id, restaurant=restaurant, is_available=True)
        MenuItem.objects.filter(pk=item.pk).update(view_count=F('view_count') + 1)
        return JsonResponse({
            'success': True,
            'item': {
                'id': str(item.id),
                'name': item.name,
                'description': item.description,
                'price': str(item.price),
                'discount_price': str(item.discount_price) if item.discount_price else None,
                'image_url': item.image.url if item.image else None,
                'ingredients': item.ingredients,
                'allergens': item.allergens,
                'is_vegetarian': item.is_vegetarian,
                'is_vegan': item.is_vegan,
                'is_spicy': item.is_spicy,
                'preparation_time': item.preparation_time,
                'category': item.category.name if item.category else '',
            }
        })
    except MenuItem.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Article non trouvé'})


MAX_USER_MESSAGE_LEN = 500


@csrf_exempt
@require_POST
@rate_limit("chat", max_requests=15, window_seconds=60, json_response=True)
def chat_assistant(request, table_token):
    restaurant, table, customization, error = get_client_context(request, table_token)
    if error:
        return JsonResponse({"reply": "Session invalide.", "actions": []}, status=400)

    settings = AISettings.load()
    if not settings.is_enabled or not settings.api_key:
        return JsonResponse(
            {"reply": "L'assistant n'est pas disponible.", "actions": [], "unavailable": True}
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"reply": "Requête invalide.", "actions": []}, status=400)

    user_message = str(data.get("message", "")).strip()[:MAX_USER_MESSAGE_LEN]
    if not user_message:
        return JsonResponse({"reply": "Posez-moi une question sur le menu.", "actions": []})

    hist_key = f"chat_{restaurant.id}_{table_token}"
    history = request.session.get(hist_key, [])

    user_turns = sum(1 for m in history if m.get("role") == "user")
    if user_turns >= settings.max_messages_per_session:
        return JsonResponse({
            "reply": "Vous avez atteint la limite de messages. Appelez un serveur pour plus d'aide.",
            "actions": [{"type": "call_waiter", "label": "Appeler un serveur"}],
            "limit_reached": True,
        })

    result = ask(restaurant, history, user_message)

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": result["reply"]})
    request.session[hist_key] = history[-(settings.max_messages_per_session * 2):]
    request.session.modified = True

    return JsonResponse({"reply": result["reply"], "actions": result.get("actions", [])})


@require_GET
def menu_api(request, table_token):
    restaurant, table, customization, error = get_client_context(request, table_token)
    if error:
        return JsonResponse({"error": "Restaurant non disponible"}, status=404)

    categories = Category.objects.filter(
        restaurant=restaurant,
        is_active=True
    ).prefetch_related("items")

    categories_data = []
    for category in categories:
        items = category.items.filter(is_available=True)
        categories_data.append({
            "id": category.id,
            "name": category.name,
            "items": [
                {
                    "id": item.id,
                    "name": item.name,
                    "price": str(item.discount_price or item.price),
                    "image": item.image.url if item.image else None,
                }
                for item in items
            ]
        })

    return JsonResponse({
        "restaurant": {
            "id": restaurant.id,
            "name": restaurant.name,
            "logo": restaurant.logo.url if restaurant.logo else None,
        },
        "customization": {
            "primary_color": customization.primary_color,
            "secondary_color": customization.secondary_color,
        },
        "categories": categories_data
    })
