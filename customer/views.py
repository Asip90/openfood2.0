import json
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET
from django.contrib import messages
from django.db import transaction
from django.db.models import Prefetch

from base.models import Category, MenuItem, Order, OrderItem, RestaurantCustomization
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
            )
        )
    ).order_by("order")

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

    context = {
        "restaurant": restaurant,
        "table": table,
        "customization": customization,
        "categories": categories,
        "cart": cart_items,
        "cart_total": cart_total,
        "cart_count": cart_count,
        "table_token": table_token,
        "cart_json": json.dumps(cart_items),
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

    if not cart:
        messages.error(request, "Votre panier est vide")
        return redirect("client_menu", table_token=table_token)

    if request.method == "POST":
        with transaction.atomic():
            order = Order.objects.create(
                restaurant=restaurant,
                table=table,
                order_type="dine_in",
                status="pending",
                customer_name=request.POST.get("customer_name", "").strip(),
                customer_phone=request.POST.get("customer_phone", "").strip(),
                notes=request.POST.get("notes", "").strip(),
            )

            for item_id, data in cart.items():
                OrderItem.objects.create(
                    order=order,
                    menu_item_id=item_id,
                    quantity=data["quantity"],
                    price=data["price"]
                )

            order.calculate_total()
            del request.session[cart_key]

            return redirect("order_confirmation", order_id=order.id)

    cart_items = []
    cart_total = 0
    for item_id, data in cart.items():
        item_total = float(data["price"]) * data["quantity"]
        cart_total += item_total
        cart_items.append({
            "name": data["name"],
            "price": float(data["price"]),
            "quantity": data["quantity"],
            "total": item_total,
        })

    return render(request, "customer/checkout.html", {
        "restaurant": restaurant,
        "customization": customization,
        "table": table,
        "table_token": table_token,
        "cart": cart_items,
        "cart_total": int(cart_total),
    })


def order_confirmation(request, order_id):
    order = get_object_or_404(Order, id=order_id)
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


@csrf_exempt
def get_item_details(request, item_id):
    if request.method != 'GET':
        return JsonResponse({'success': False})

    try:
        item = MenuItem.objects.get(id=item_id, is_available=True)
        MenuItem.objects.filter(pk=item.pk).update(view_count=item.view_count + 1)
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
