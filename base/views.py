from datetime import datetime, timedelta
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from base.decorators import get_user_restaurant, restaurant_required, owner_or_coadmin_required
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Sum, Avg, Prefetch, Q
from django.db.models.functions import TruncDate, TruncMonth, ExtractHour, ExtractWeekDay
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.utils import timezone
from base.models import Category, Table
from .forms import RestaurantCreateForm, OrderForm, OrderItemFormSet, TableForm, OrderItemForm, QRSettingsForm
from .models import SubscriptionPlan, PromoCode, PromoCodeUse, Restaurant, MenuItem, MenuItemMedia, Order, OrderItem, RestaurantCustomization, QRSettings
from django.forms import inlineformset_factory
from django.utils.text import slugify
from django.conf import settings
from .utils import generate_unique_subdomain
from django.views.decorators.http import require_GET
from base.services.subscription import get_effective_plan

FAQS = [
    {
        'question': 'Comment créer un menu QR code pour mon restaurant ?',
        'answer': 'Inscrivez-vous gratuitement sur Open Food, créez votre restaurant, ajoutez vos plats avec photos et prix, puis générez votre QR code. Imprimez-le et placez-le sur vos tables. Vos clients scannent et commandent directement depuis leur téléphone, sans application à installer.',
    },
    {
        'question': 'Faut-il une application mobile pour utiliser Open Food ?',
        'answer': 'Non. Open Food fonctionne entièrement dans le navigateur de vos clients. Aucun téléchargement requis. Votre menu est accessible instantanément après le scan du QR code.',
    },
    {
        'question': 'Open Food fonctionne-t-il au Bénin et en Afrique de l\'Ouest ?',
        'answer': 'Oui, Open Food est conçu pour les restaurateurs africains. L\'interface supporte le Franc CFA (FCFA) et est optimisée pour les connexions mobiles 3G/4G courantes en Afrique de l\'Ouest.',
    },
    {
        'question': 'Combien coûte Open Food ?',
        'answer': 'Open Food propose un plan gratuit pour démarrer sans carte bancaire. Des plans professionnels avec analytics avancés, domaine personnalisé et suppression du branding sont disponibles. Contactez-nous pour les tarifs.',
    },
    {
        'question': 'Puis-je personnaliser les couleurs de mon menu ?',
        'answer': 'Oui. Chaque restaurant peut personnaliser les couleurs, la police, le logo et la photo de couverture de son menu digital depuis le tableau de bord, sans aucune connaissance technique.',
    },
    {
        'question': 'Comment fonctionne la commande depuis le menu QR Code ?',
        'answer': 'Le client scanne le QR code posé sur sa table, parcourt le menu, ajoute des plats au panier et valide sa commande. La commande apparaît immédiatement dans votre tableau de bord avec une notification sonore.',
    },
]


def home(request):
    return render(request, 'home/index.html', {
        'faqs': FAQS,
        'canonical_url': request.build_absolute_uri('/'),
    })


@login_required
@require_GET
def check_new_orders(request):
    restaurant, role = get_user_restaurant(request.user)

    if not restaurant:
        return JsonResponse({"latest_order_id": None, "error": "Restaurant not found for user"}, status=404)

    latest_order_in_db = Order.objects.filter(restaurant=restaurant).order_by('-created_at', '-id').first()

    if latest_order_in_db:
        order_items_data = []
        for item in latest_order_in_db.items.all():
            order_items_data.append({
                'name': item.menu_item.name,
                'quantity': item.quantity,
                'price': str(item.price),
                'total': str(item.get_total()),
            })

        data = {
            'latest_order_id': latest_order_in_db.id,
            'customer_name': latest_order_in_db.customer_name or "Client",
            'table': {'number': latest_order_in_db.table.number} if latest_order_in_db.table else None,
            'total': str(latest_order_in_db.total),
            'status': latest_order_in_db.status,
            'created_at': latest_order_in_db.created_at.isoformat(),
            'notes': latest_order_in_db.notes or "",
            'items': order_items_data,
        }
    else:
        data = {'latest_order_id': None}

    return JsonResponse(data)


@login_required
def create_restaurant(request):
    promo_error = None
    if request.method == 'POST':
        form = RestaurantCreateForm(request.POST, request.FILES)
        if form.is_valid():
            restaurant = form.save(commit=False)
            restaurant.owner = request.user
            base_slug = slugify(restaurant.name)
            slug = base_slug
            counter = 1
            from base.models import Restaurant as _R
            while _R.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            restaurant.slug = slug
            restaurant.subdomain = generate_unique_subdomain(restaurant.name)

            plan = SubscriptionPlan.objects.filter(plan_type='gratuit', is_active=True).first()
            if not plan:
                plan = SubscriptionPlan.objects.filter(is_active=True).order_by('price').first()
            if plan is None:
                messages.error(request, "Aucun plan d'abonnement actif n'est disponible. Veuillez contacter le support.")
                return render(request, 'admin_user/create_restaurant.html', {'form': form})

            promo_code_input = request.POST.get('promo_code', '').strip().upper()
            promo = None
            if promo_code_input:
                try:
                    promo = PromoCode.objects.get(code=promo_code_input)
                    if not promo.is_valid():
                        promo_error = "Ce code promo n'est plus valide ou a expiré."
                        promo = None
                except PromoCode.DoesNotExist:
                    promo_error = "Code promo invalide."

            if promo_error:
                return render(request, 'admin_user/create_restaurant.html', {
                    'form': form,
                    'promo_error': promo_error,
                    'promo_code_value': promo_code_input,
                })

            if promo:
                plan = promo.plan
                duration = promo.duration_days
                promo.uses_count += 1
                promo.save(update_fields=['uses_count'])
            else:
                duration = plan.duration_days

            restaurant.subscription_plan = plan
            restaurant.subscription_start = timezone.now()
            restaurant.subscription_end = timezone.now() + timedelta(days=duration)
            restaurant.save()

            if promo:
                PromoCodeUse.objects.get_or_create(promo_code=promo, restaurant=restaurant)

            return redirect('dashboard')
    else:
        form = RestaurantCreateForm()

    return render(request, 'admin_user/create_restaurant.html', {'form': form})


@restaurant_required()
def dashboard(request):
    restaurant = request.restaurant
    role = request.user_role

    latest_order = Order.objects.filter(restaurant=restaurant).order_by('-created_at', '-id').first()
    latest_order_id = latest_order.id if latest_order else None

    if role == 'cuisinier':
        active_orders = Order.objects.filter(
            restaurant=restaurant,
            status__in=['pending', 'confirmed', 'preparing']
        ).order_by('-created_at').prefetch_related('items__menu_item')
        return render(request, "admin_user/index.html", {
            "restaurant": restaurant,
            "user_role": role,
            "active_orders": active_orders,
            "latest_order_id": latest_order_id,
        })

    if role == 'serveur':
        ready_orders = Order.objects.filter(
            restaurant=restaurant,
            status='ready'
        ).order_by('-created_at').prefetch_related('items__menu_item')
        tables = Table.objects.filter(restaurant=restaurant, is_active=True)
        return render(request, "admin_user/index.html", {
            "restaurant": restaurant,
            "user_role": role,
            "ready_orders": ready_orders,
            "tables": tables,
            "latest_order_id": latest_order_id,
        })

    # owner / coadmin — full dashboard
    today = timezone.now().date()
    last_7_days = today - timedelta(days=6)

    total_orders = Order.objects.filter(restaurant=restaurant).count()
    today_orders = Order.objects.filter(
        restaurant=restaurant,
        created_at__date=today
    ).count()

    total_revenue = Order.objects.filter(
        restaurant=restaurant,
        status__in=["confirmed", "preparing", "ready", "delivered"]
    ).aggregate(total=Sum("total"))["total"] or 0

    active_menu_items = MenuItem.objects.filter(
        restaurant=restaurant,
        is_available=True
    ).count()

    active_tables = Table.objects.filter(
        restaurant=restaurant,
        is_active=True
    ).count()

    orders_by_day = (
        Order.objects.filter(
            restaurant=restaurant,
            created_at__date__gte=last_7_days
        )
        .annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(count=Count('id'))
        .order_by('day')
    )

    days = []
    orders_count = []
    for item in orders_by_day:
        days.append(item['day'].strftime("%d/%m"))
        orders_count.append(item['count'])

    order_types = (
        Order.objects.filter(restaurant=restaurant)
        .values('order_type')
        .annotate(count=Count('id'))
    )

    type_labels = []
    type_values = []
    for o in order_types:
        type_labels.append(o['order_type'])
        type_values.append(o['count'])

    # URL de prévisualisation du menu client
    first_table = Table.objects.filter(restaurant=restaurant, is_active=True).first()
    if first_table:
        base = settings.FRONTEND_BASE_URL.rstrip('/')
        scheme = 'https' if base.startswith('https') else 'http'
        host = base.replace('https://', '').replace('http://', '')
        menu_url = f"{scheme}://{restaurant.subdomain}.{host}/t/{first_table.token}/"
    else:
        menu_url = None

    context = {
        "restaurant": restaurant,
        "user_role": role,
        "total_orders": total_orders,
        "today_orders": today_orders,
        "total_revenue": total_revenue,
        "active_menu_items": active_menu_items,
        "active_tables": active_tables,
        "days": days,
        "orders_count": orders_count,
        "type_labels": type_labels,
        "type_values": type_values,
        "latest_order_id": latest_order_id,
        "menu_url": menu_url,
    }

    return render(request, "admin_user/index.html", context)


@restaurant_required()
@owner_or_coadmin_required
def analytics_view(request):
    restaurant = request.restaurant
    plan = get_effective_plan(restaurant)

    if not plan or not plan.analytics:
        return render(request, "admin_user/analytics/index.html", {
            "restaurant": restaurant,
            "access_denied": True,
        })

    today = timezone.now().date()
    last_30_days = today - timedelta(days=29)
    last_12_months = today - timedelta(days=364)

    # Revenus par jour sur 30 jours
    revenue_by_day = (
        Order.objects.filter(
            restaurant=restaurant,
            status__in=["confirmed", "preparing", "ready", "delivered"],
            created_at__date__gte=last_30_days,
        )
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"))
        .order_by("day")
    )
    revenue_labels, revenue_values = [], []
    for item in revenue_by_day:
        day_obj = item["day"]
        revenue_labels.append(day_obj.strftime("%d/%m"))
        revenue_values.append(float(item["revenue"] or 0))

    # Top 5 plats les plus commandés
    top_items = list(
        OrderItem.objects.filter(order__restaurant=restaurant)
        .values("menu_item__name")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:5]
    )

    # Top 5 menus les plus consultés (view_count)
    top_viewed = list(
        MenuItem.objects.filter(restaurant=restaurant)
        .order_by("-view_count")
        .values("name", "view_count")[:5]
    )

    # Valeur moyenne par commande
    avg_order = (
        Order.objects.filter(
            restaurant=restaurant,
            status__in=["confirmed", "preparing", "ready", "delivered"],
        ).aggregate(avg=Avg("total"))["avg"] or 0
    )

    # Heures de pointe (0–23)
    orders_by_hour = (
        Order.objects.filter(restaurant=restaurant)
        .annotate(hour=ExtractHour("created_at"))
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hour_map = {row["hour"]: row["count"] for row in orders_by_hour}
    peak_labels = [f"{h:02d}h" for h in range(24)]
    peak_values = [hour_map.get(h, 0) for h in range(24)]

    # Jours de la semaine les plus chargés (0=lundi … 6=dimanche)
    DAY_NAMES = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    orders_by_dow = (
        Order.objects.filter(restaurant=restaurant)
        .annotate(dow=ExtractWeekDay("created_at"))
        .values("dow")
        .annotate(count=Count("id"))
        .order_by("dow")
    )
    # Django ExtractWeekDay: 1=dimanche … 7=samedi
    dow_map_raw = {row["dow"]: row["count"] for row in orders_by_dow}
    # Réordonne en lundi-dimanche (index 0..6)
    # Django: 2=lundi…7=samedi, 1=dimanche
    dow_reordered = [dow_map_raw.get(i, 0) for i in range(2, 8)]  # lun→sam
    dow_reordered.append(dow_map_raw.get(1, 0))  # dimanche
    dow_labels = DAY_NAMES
    dow_values = dow_reordered

    # Tables les plus utilisées (top 5)
    top_tables = list(
        Order.objects.filter(restaurant=restaurant, table__isnull=False)
        .values("table__number")
        .annotate(count=Count("id"))
        .order_by("-count")[:5]
    )

    context = {
        "restaurant": restaurant,
        "access_denied": False,
        "has_advanced": plan.advanced_analytics,
        "revenue_labels": revenue_labels,
        "revenue_values": revenue_values,
        "top_items": top_items,
        "top_viewed": top_viewed,
        "avg_order": round(avg_order, 0),
        "peak_labels": peak_labels,
        "peak_values": peak_values,
        "dow_labels": dow_labels,
        "dow_values": dow_values,
        "top_tables": top_tables,
    }

    if plan.advanced_analytics:
        # Revenus par mois sur 12 mois
        monthly_revenue = (
            Order.objects.filter(
                restaurant=restaurant,
                status__in=["confirmed", "preparing", "ready", "delivered"],
                created_at__date__gte=last_12_months,
            )
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(revenue=Sum("total"))
            .order_by("month")
        )
        context["monthly_labels"] = [r["month"].strftime("%Y-%m") for r in monthly_revenue]
        context["monthly_values"] = [float(r["revenue"] or 0) for r in monthly_revenue]

        # Performance par catégorie
        context["category_perf"] = list(
            OrderItem.objects.filter(order__restaurant=restaurant)
            .values("menu_item__category__name")
            .annotate(total_qty=Sum("quantity"), total_rev=Sum("price"))
            .order_by("-total_rev")
        )

        # Taux d'annulation
        total = Order.objects.filter(restaurant=restaurant).count()
        cancelled = Order.objects.filter(restaurant=restaurant, status="cancelled").count()
        context["cancellation_rate"] = round((cancelled / total * 100) if total else 0, 1)

    return render(request, "admin_user/analytics/index.html", context)


@restaurant_required()
@owner_or_coadmin_required
def export_orders_csv(request):
    import csv
    restaurant = request.restaurant
    plan = get_effective_plan(restaurant)

    if not plan or not plan.advanced_analytics:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès réservé au plan Max.")

    from django.http import HttpResponse
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="commandes_{restaurant.slug}.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Numéro", "Date", "Type", "Statut", "Client", "Téléphone",
        "Table", "Sous-total", "Total", "Notes"
    ])

    orders = Order.objects.filter(restaurant=restaurant).select_related("table").order_by("-created_at")
    for order in orders:
        writer.writerow([
            order.order_number,
            order.created_at.strftime("%Y-%m-%d %H:%M"),
            order.get_order_type_display(),
            order.get_status_display(),
            order.customer_name,
            order.customer_phone,
            order.table.number if order.table else "",
            order.subtotal,
            order.total,
            order.notes,
        ])

    return response


@restaurant_required()
def order_receipt(request, pk):
    restaurant = request.restaurant
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    items = order.items.select_related("menu_item").all()
    return render(request, "admin_user/orders/receipt.html", {
        "order": order,
        "items": items,
        "restaurant": restaurant,
    })


@restaurant_required()
def create_manual_order(request):
    restaurant = request.restaurant

    categories = Category.objects.filter(
        restaurant=restaurant,
        is_active=True
    ).prefetch_related(
        Prefetch(
            "items",
            queryset=MenuItem.objects.filter(is_available=True, restaurant=restaurant)
        )
    )

    if request.method == "POST":
        order_form = OrderForm(request.POST, restaurant=restaurant)
        formset = OrderItemFormSet(request.POST, prefix='items')

        if order_form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    order = order_form.save(commit=False)
                    order.restaurant = restaurant
                    order.save()

                    formset.instance = order
                    instances = formset.save(commit=False)

                    for instance in instances:
                        instance.price = instance.menu_item.discount_price or instance.menu_item.price
                        instance.save()

                    order.calculate_total()
                    order.save()

                messages.success(request, f"Commande #{order.id} créée avec succès.")
                return redirect("orders_list")

            except Exception as e:
                messages.error(request, f"Erreur lors de la création de la commande: {str(e)}")
        else:
            for field, errors in order_form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")

            for form in formset:
                for field, errors in form.errors.items():
                    for error in errors:
                        messages.error(request, f"Article: {error}")
    else:
        order_form = OrderForm(restaurant=restaurant)
        formset = OrderItemFormSet(prefix='items')

    return render(request, "admin_user/orders/create_manual_order.html", {
        "order_form": order_form,
        "formset": formset,
        "categories": categories,
        "restaurant": restaurant,
    })


@owner_or_coadmin_required
def update_order(request, order_id):
    restaurant = request.restaurant
    order = get_object_or_404(Order, id=order_id, restaurant=restaurant)

    categories = Category.objects.filter(
        restaurant=restaurant,
        is_active=True
    ).prefetch_related(
        Prefetch(
            "items",
            queryset=MenuItem.objects.filter(is_available=True, restaurant=restaurant)
        )
    )

    OrderItemFormSetLocal = inlineformset_factory(
        Order,
        OrderItem,
        form=OrderItemForm,
        extra=0,
        can_delete=True,
        fields=['menu_item', 'quantity']
    )

    if request.method == "POST":
        order_form = OrderForm(request.POST, instance=order, restaurant=restaurant)
        formset = OrderItemFormSetLocal(request.POST, instance=order, prefix='items')

        if order_form.is_valid() and formset.is_valid():
            try:
                with transaction.atomic():
                    order = order_form.save()
                    formset.save()

                    new_items_count = int(request.POST.get('new-items-TOTAL_FORMS', 0))
                    for i in range(new_items_count):
                        menu_item_id = request.POST.get(f'new-items-{i}-menu_item')
                        quantity = request.POST.get(f'new-items-{i}-quantity')

                        if menu_item_id and quantity:
                            menu_item = MenuItem.objects.get(id=menu_item_id, restaurant=restaurant)
                            OrderItem.objects.create(
                                order=order,
                                menu_item=menu_item,
                                quantity=quantity,
                                price=menu_item.discount_price or menu_item.price
                            )

                    order.calculate_total()
                    order.save()

                messages.success(request, f"Commande #{order.id} mise à jour avec succès.")
                return redirect("orders_list")

            except Exception as e:
                messages.error(request, f"Erreur lors de la mise à jour: {str(e)}")
        else:
            messages.error(request, "Veuillez corriger les erreurs ci-dessous.")
    else:
        order_form = OrderForm(instance=order, restaurant=restaurant)
        formset = OrderItemFormSetLocal(instance=order, prefix='items')

    existing_items = []
    for item in order.items.all():
        existing_items.append({
            'id': item.id,
            'menu_item_id': item.menu_item.id,
            'name': item.menu_item.name,
            'price': float(item.price),
            'quantity': item.quantity,
            'image_url': item.menu_item.image.url if item.menu_item.image else '',
            'subtotal': float(item.get_total())
        })

    return render(request, "admin_user/orders/update_order.html", {
        "order": order,
        "order_form": order_form,
        "formset": formset,
        "categories": categories,
        "restaurant": restaurant,
        "existing_items": existing_items,
    })


@owner_or_coadmin_required
def delete_order(request, order_id):
    restaurant = request.restaurant

    try:
        order = Order.objects.get(id=order_id, restaurant=restaurant)

        if request.method == "POST":
            order_number = order.id
            order.delete()
            messages.success(request, f"Commande #{order_number} supprimée avec succès.")
            return redirect("orders_list")

    except Order.DoesNotExist:
        messages.error(request, "Commande non trouvée.")

    return redirect("orders_list")


def _orders_queryset(restaurant, status_filter, q):
    qs = Order.objects.filter(restaurant=restaurant).order_by("-created_at")
    if status_filter:
        qs = qs.filter(status=status_filter)
    if q:
        qs = qs.filter(
            Q(customer_name__icontains=q) |
            Q(order_number__icontains=q) |
            Q(table__number__icontains=q)
        ).distinct()
    return qs


@restaurant_required()
def orders_list(request):
    restaurant = request.restaurant
    status_filter = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()

    orders_qs = _orders_queryset(restaurant, status_filter, q)
    paginator = Paginator(orders_qs, 10)
    orders = paginator.get_page(request.GET.get("page"))

    latest_order = Order.objects.filter(restaurant=restaurant).order_by('-created_at', '-id').first()
    latest_order_id = latest_order.id if latest_order else None

    return render(request, "admin_user/orders/list_orders.html", {
        "restaurant": restaurant,
        "orders": orders,
        "current_status": status_filter,
        "current_q": q,
        "status_choices": Order.STATUS_CHOICES,
        "pending_count": Order.objects.filter(restaurant=restaurant, status="pending").count(),
        "latest_order_id": latest_order_id,
    })


@restaurant_required()
def orders_partial(request):
    """Renders only the orders feed fragment (list + pagination) for AJAX refresh."""
    restaurant = request.restaurant
    status_filter = request.GET.get("status", "")
    q = request.GET.get("q", "").strip()

    orders_qs = _orders_queryset(restaurant, status_filter, q)
    paginator = Paginator(orders_qs, 10)
    orders = paginator.get_page(request.GET.get("page", 1))

    return render(request, "admin_user/orders/_orders_feed.html", {
        "orders": orders,
        "current_status": status_filter,
        "current_q": q,
        "status_choices": Order.STATUS_CHOICES,
    })


@restaurant_required()
def order_change_status(request, pk):
    restaurant = request.restaurant
    role = request.user_role
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    new_status = request.POST.get("status")

    # Role-based allowed status transitions
    if role in ('owner', 'coadmin'):
        allowed = {s[0] for s in Order.STATUS_CHOICES}
    elif role == 'cuisinier':
        allowed = {'confirmed', 'preparing', 'ready', 'cancelled'}
    elif role == 'serveur':
        allowed = {'delivered'}
    else:
        allowed = set()

    if new_status not in allowed:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Action non autorisée.'}, status=403)
        messages.error(request, "Action non autorisée.")
        return redirect("orders_list")

    order.status = new_status
    if new_status == 'preparing':
        u = request.user
        order.preparing_by_name = f"{u.first_name} {u.last_name}".strip() or u.email
    order.save()

    status_display = dict(Order.STATUS_CHOICES).get(new_status, new_status)

    if is_ajax:
        return JsonResponse({'ok': True, 'status': new_status, 'status_display': status_display})

    messages.success(request, f"Statut de la commande #{order.order_number} mis à jour : {status_display}")
    return redirect("orders_list")


@restaurant_required()
def order_detail(request, pk):
    restaurant = request.restaurant
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        items = [
            {
                'name': item.menu_item.name,
                'quantity': item.quantity,
                'price': float(item.price),
                'total': float(item.price * item.quantity),
            }
            for item in order.items.select_related('menu_item').all()
        ]
        return JsonResponse({
            'ok': True,
            'order_number': order.order_number,
            'status': order.status,
            'status_display': order.get_status_display(),
            'table': f"Table {order.table.number}" if order.table else "À emporter",
            'customer_name': order.customer_name or '',
            'customer_phone': order.customer_phone or '',
            'notes': order.notes or '',
            'subtotal': float(order.subtotal),
            'tax': float(order.tax),
            'total': float(order.total),
            'items': items,
            'created_at': order.created_at.strftime('%d/%m/%Y %H:%M'),
        })

    return render(request, "admin_user/orders/detail_orders.html", {
        "order": order,
        "restaurant": restaurant
    })


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menus_list(request):
    restaurant = request.restaurant
    categories = Category.objects.filter(
        restaurant=restaurant
    ).prefetch_related('items__media')

    return render(request, "admin_user/menus/list_menu.html", {
        "restaurant": restaurant,
        "categories": categories
    })


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_create(request):
    restaurant = request.restaurant
    categories = Category.objects.filter(restaurant=restaurant)

    if request.method == "POST":
        plan = restaurant.subscription_plan
        if plan and plan.max_menu_items > 0:
            current_count = MenuItem.objects.filter(restaurant=restaurant).count()
            if current_count >= plan.max_menu_items:
                messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_menu_items} plats. Passez au plan supérieur pour en ajouter davantage.")
                return redirect("menus_list")

        menu_item = MenuItem.objects.create(
            restaurant=restaurant,
            category_id=request.POST.get("category"),
            name=request.POST.get("name"),
            price=request.POST.get("price"),
            description=request.POST.get("description"),
            is_available=True,
        )

        for i in range(1, 4):
            f = request.FILES.get(f"image_{i}")
            if f:
                MenuItemMedia.objects.create(
                    menu_item=menu_item, file=f, media_type='image', order=i
                )

        video_f = request.FILES.get("video")
        if video_f:
            MenuItemMedia.objects.create(
                menu_item=menu_item, file=video_f, media_type='video', order=0
            )

        return redirect("menus_list")

    return render(request, "admin_user/menus/create_menus.html", {
        "restaurant": restaurant,
        "categories": categories
    })


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_update(request, pk):
    restaurant = request.restaurant
    menu_item = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)

    if request.method == "POST":
        menu_item.name = request.POST.get("name")
        menu_item.price = request.POST.get("price")
        menu_item.description = request.POST.get("description")

        category_id = request.POST.get("category")
        if category_id:
            menu_item.category_id = category_id

        menu_item.save()

        any_new_image = any(request.FILES.get(f"image_{i}") for i in range(1, 4))
        if any_new_image:
            menu_item.media.filter(media_type='image').delete()
            for i in range(1, 4):
                f = request.FILES.get(f"image_{i}")
                if f:
                    MenuItemMedia.objects.create(
                        menu_item=menu_item, file=f, media_type='image', order=i
                    )

        video_f = request.FILES.get("video")
        if video_f:
            menu_item.media.filter(media_type='video').delete()
            MenuItemMedia.objects.create(
                menu_item=menu_item, file=video_f, media_type='video', order=0
            )

        return redirect("menus_list")

    categories = Category.objects.filter(restaurant=restaurant)
    existing_images = list(menu_item.media.filter(media_type='image').order_by('order'))
    existing_video = menu_item.media.filter(media_type='video').first()

    return render(request, "admin_user/menus/update_menu.html", {
        "restaurant": restaurant,
        "menu_item": menu_item,
        "categories": categories,
        "existing_images": existing_images,
        "existing_video": existing_video,
    })


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def change_menu_status(request, pk):
    restaurant = request.restaurant
    menu_item = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)
    menu_item.is_available = not menu_item.is_available
    menu_item.save()
    return redirect("menus_list")


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_delete(request, pk):
    restaurant = request.restaurant
    menu_item = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)
    menu_item.delete()
    return redirect("menus_list")


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def create_category(request):
    restaurant = request.restaurant

    if request.method == "POST":
        name = request.POST.get("name")
        description = request.POST.get("description")
        image = request.FILES.get("image")

        if not name:
            return render(request, "admin_user/menus/create_category.html", {
                "restaurant": restaurant,
                "error": "Le nom de la catégorie est obligatoire"
            })

        if not description:
            return render(request, "admin_user/menus/create_category.html", {
                "restaurant": restaurant,
                "error": "La description de la catégorie est obligatoire"
            })

        if not image:
            return render(request, "admin_user/menus/create_category.html", {
                "restaurant": restaurant,
                "error": "L'image de la catégorie est obligatoire"
            })

        if Category.objects.filter(restaurant=restaurant, name=name).exists():
            return render(request, "admin_user/menus/create_category.html", {
                "restaurant": restaurant,
                "error": "La catégorie existe déjà"
            })

        Category.objects.create(
            restaurant=restaurant,
            name=name,
            description=description,
            image=image,
        )
        return redirect("menus_list")

    return render(request, "admin_user/menus/create_category.html", {
        "restaurant": restaurant
    })


@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def create_category_modale(request):
    restaurant = request.restaurant

    if request.method == "POST":
        name = request.POST.get("name")

        if not name:
            return JsonResponse({"error": "Nom requis"}, status=400)

        if Category.objects.filter(restaurant=restaurant, name__iexact=name).exists():
            return JsonResponse({"error": "Cette catégorie existe déjà"}, status=400)

        category = Category.objects.create(restaurant=restaurant, name=name)

        return JsonResponse({"id": category.id, "name": category.name})

    return JsonResponse({"error": "Méthode non autorisée"}, status=405)


@owner_or_coadmin_required
def customization(request):
    restaurant = request.restaurant

    customization_obj, created = RestaurantCustomization.objects.get_or_create(
        restaurant=restaurant
    )

    if request.method == "POST":
        customization_obj.primary_color = request.POST.get("primary_color")
        customization_obj.secondary_color = request.POST.get("secondary_color")
        customization_obj.font_family = request.POST.get("font_family", "poppins")

        if request.FILES.get("logo"):
            customization_obj.logo = request.FILES["logo"]

        if request.FILES.get("cover_image"):
            customization_obj.cover_image = request.FILES["cover_image"]

        if request.POST.get("remove_logo") == "true":
            customization_obj.logo.delete(save=False)
            customization_obj.logo = None

        if request.POST.get("remove_cover") == "true":
            customization_obj.cover_image.delete(save=False)
            customization_obj.cover_image = None

        customization_obj.save()
        messages.success(request, "Personnalisation mise à jour avec succès.")
        return redirect("customization")

    return render(request, "admin_user/customization.html", {
        "restaurant": restaurant,
        "customization": customization_obj
    })


@owner_or_coadmin_required
def reset_customization(request):
    restaurant = request.restaurant

    if RestaurantCustomization.objects.filter(restaurant=restaurant).exists():
        customization_obj = restaurant.customization
        customization_obj.primary_color = '#16a34a'
        customization_obj.secondary_color = '#f97316'
        customization_obj.font_family = 'poppins'

        if customization_obj.logo:
            customization_obj.logo.delete(save=False)
            customization_obj.logo = None
        if customization_obj.cover_image:
            customization_obj.cover_image.delete(save=False)
            customization_obj.cover_image = None

        customization_obj.save()
        messages.info(request, "Personnalisations réinitialisées aux valeurs par défaut.")

    return redirect("customization")


@owner_or_coadmin_required
def restaurant_settings(request):
    restaurant = request.restaurant

    days_of_week = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    schedules = {}

    for day in days_of_week:
        schedules[day] = {
            'ouverture': restaurant.opening_hours.get(f'{day}_open', '09:00'),
            'fermeture': restaurant.opening_hours.get(f'{day}_close', '22:00'),
        }

    hours = []
    for hour in range(0, 24):
        for minute in [0, 30]:
            hours.append(f"{hour:02d}:{minute:02d}")

    if request.method == "POST":
        restaurant.name = request.POST.get("name", restaurant.name)
        restaurant.description = request.POST.get("description", restaurant.description)
        restaurant.phone = request.POST.get("phone", restaurant.phone)
        restaurant.email = request.POST.get("email", restaurant.email)
        restaurant.address = request.POST.get("address", restaurant.address)

        opening_hours = {}
        for day in days_of_week:
            open_key = f"{day}_ouverture"
            close_key = f"{day}_fermeture"
            if open_key in request.POST and close_key in request.POST:
                opening_hours[f"{day}_open"] = request.POST.get(open_key)
                opening_hours[f"{day}_close"] = request.POST.get(close_key)

        if opening_hours:
            restaurant.opening_hours = opening_hours

        try:
            restaurant.save()
            messages.success(request, "Les paramètres ont été mis à jour avec succès !")
            return redirect("restaurant_settings")
        except Exception as e:
            messages.error(request, f"Une erreur est survenue : {str(e)}")

    context = {
        "restaurant": restaurant,
        "schedules": schedules,
        "hours": hours,
    }

    return render(request, "admin_user/settings.html", context)


@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def tables_list(request):
    restaurant = request.restaurant
    tables = Table.objects.filter(restaurant=restaurant)
    active_count = tables.filter(is_active=True).count()
    return render(request, "admin_user/tables/table_list.html", {
        'active_count': active_count,
        "restaurant": restaurant,
        "tables": tables
    })


@owner_or_coadmin_required
def table_create(request):
    restaurant = request.restaurant

    if request.method == 'POST':
        plan = restaurant.subscription_plan
        if plan and plan.max_tables > 0:
            current_count = Table.objects.filter(restaurant=restaurant).count()
            if current_count >= plan.max_tables:
                messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_tables} tables. Passez au plan supérieur pour en créer davantage.")
                return redirect('tables_list')

        form = TableForm(request.POST)
        if form.is_valid():
            number = form.cleaned_data['number']

            if Table.objects.filter(restaurant=restaurant, number=number).exists():
                messages.error(request, "Cette table existe déjà.")
            else:
                table = form.save(commit=False)
                table.restaurant = restaurant
                table.save()
                messages.success(request, f"Table {table.number} créée avec succès.")
                return redirect('tables_list')
    else:
        form = TableForm()

    return render(request, 'admin_user/tables/table_create.html', {
        'restaurant': restaurant,
        'form': form
    })


@owner_or_coadmin_required
def table_delete(request, table_id):
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    table.delete()
    messages.success(request, f"Table {table.number} supprimée.")
    return redirect('tables_list')


@owner_or_coadmin_required
def table_toggle_active(request, table_id):
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    table.is_active = not table.is_active
    table.save(update_fields=['is_active'])
    messages.success(request, f"Table {table.number} {'activée' if table.is_active else 'désactivée'}.")
    return redirect(request.META.get('HTTP_REFERER', 'tables_list'))


@owner_or_coadmin_required
def table_regenerate_qr(request, table_id):
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    table.generate_qr_code()
    messages.success(request, f"QR Code de la table {table.number} régénéré.")
    return redirect(request.META.get('HTTP_REFERER', 'tables_list'))


@restaurant_required(allowed_roles=['owner', 'coadmin'])
def qr_settings_view(request):
    restaurant = request.restaurant
    qr_settings, _ = QRSettings.objects.get_or_create(restaurant=restaurant)

    if request.method == 'POST':
        form = QRSettingsForm(request.POST, request.FILES, instance=qr_settings)
        if form.is_valid():
            form.save()
            # Régénérer tous les QR des tables actives
            tables = restaurant.tables.filter(is_active=True)
            for table in tables:
                table.generate_qr_code()
                table.save(update_fields=['qr_code'])
            count = tables.count()
            messages.success(request, f"Paramètres sauvegardés. {count} QR code(s) régénéré(s).")
            return redirect('qr_settings')
    else:
        form = QRSettingsForm(instance=qr_settings)

    first_table = restaurant.tables.filter(is_active=True, qr_code__isnull=False).exclude(qr_code='').first()
    return render(request, 'admin_user/tables/qr_settings.html', {
        'form': form,
        'qr_settings': qr_settings,
        'first_table': first_table,
    })


@owner_or_coadmin_required
def table_update(request, table_id):
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)

    if request.method == 'POST':
        form = TableForm(request.POST, instance=table)
        if form.is_valid():
            form.save()
            messages.success(request, f"Table {table.number} mise à jour avec succès.")
            return redirect('tables_list')
    else:
        form = TableForm(instance=table)

    return render(request, 'admin_user/tables/table_update.html', {
        'table': table,
        'form': form
    })


from django.views.decorators.cache import cache_control

@cache_control(max_age=86400)
def pwa_manifest(request, slug):
    try:
        restaurant = Restaurant.objects.get(slug=slug, is_active=True)
        customization = RestaurantCustomization.objects.filter(restaurant=restaurant).first()
        primary_color = customization.primary_color if customization and customization.primary_color else '#f97316'
    except Restaurant.DoesNotExist:
        restaurant = None
        primary_color = '#f97316'

    manifest = {
        "name": restaurant.name if restaurant else "Open Food",
        "short_name": restaurant.name[:12] if restaurant else "Menu",
        "description": (restaurant.description or "Menu digital par QR Code") if restaurant else "Menu digital par QR Code",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": primary_color,
        "orientation": "portrait",
        "icons": [
            {"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
            {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
        "categories": ["food", "shopping"],
        "lang": "fr"
    }
    return JsonResponse(manifest, content_type='application/manifest+json')


@owner_or_coadmin_required
def settings_hub(request):
    restaurant = request.restaurant
    return render(request, "admin_user/settings_hub.html", {
        "restaurant": restaurant,
        "plan": restaurant.subscription_plan,
    })
