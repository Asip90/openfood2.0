# base/cashier_views.py — Caisse : addition + encaissement (option A, paiement manuel)
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.shortcuts import redirect, render, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from base.decorators import restaurant_required
from base.models import Order, Table

# Statuts considérés comme « à encaisser » (une commande annulée ne se paie pas)
BILLABLE_STATUSES = ("pending", "confirmed", "preparing", "ready", "delivered")
CASHIER_ROLES = ("owner", "coadmin", "serveur")


def _paid_by_name(user):
    return f"{user.first_name} {user.last_name}".strip() or user.email


@restaurant_required(allowed_roles=CASHIER_ROLES)
def cashier(request):
    """Page Caisse : tables ouvertes (impayées) du jour + recherche + total encaissé."""
    restaurant = request.restaurant
    today = timezone.localdate()

    # Recherche libre : n° de table, n° de commande, ou téléphone
    q = request.GET.get("q", "").strip()
    results = None
    if q:
        digits = "".join(c for c in q if c.isdigit())
        # L'UI affiche « #83C0C1 » : on ignore le # pour matcher ORD-8B83C0C1
        q_num = q.lstrip("#").strip()
        filters = Q(order_number__icontains=q_num) if q_num else Q(pk__in=[])
        if digits:
            filters |= Q(customer_phone__icontains=digits) | Q(table__number__icontains=digits)
        results = list(
            Order.objects.filter(
                restaurant=restaurant, status__in=BILLABLE_STATUSES, is_paid=False
            ).filter(filters).select_related("table").order_by("-created_at")[:40]
        )

    # Tables avec des commandes impayées, regroupées (une table impayée reste
    # due même après minuit — pas de filtre de date ici)
    open_orders = (
        Order.objects.filter(
            restaurant=restaurant,
            status__in=BILLABLE_STATUSES,
            is_paid=False,
            table__isnull=False,
        )
        .values("table_id", "table__number")
        .annotate(total=Sum("total"), n=Count("id"))
        .order_by("table__number")
    )

    # Commandes impayées sans table (à emporter)
    takeaway = list(
        Order.objects.filter(
            restaurant=restaurant,
            status__in=BILLABLE_STATUSES,
            is_paid=False,
            table__isnull=True,
        ).order_by("-created_at")
    )

    collected_today = (
        Order.objects.filter(
            restaurant=restaurant, is_paid=True, paid_at__date=today
        ).aggregate(t=Sum("total"))["t"] or 0
    )

    return render(request, "admin_user/cashier/index.html", {
        "restaurant": restaurant,
        "q": q,
        "results": results,
        "open_tables": open_orders,
        "takeaway": takeaway,
        "collected_today": collected_today,
    })


@restaurant_required(allowed_roles=CASHIER_ROLES)
def cashier_table(request, table_id):
    """Détail d'une table : toutes les commandes impayées + total dû."""
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    orders = list(
        Order.objects.filter(
            restaurant=restaurant, table=table,
            status__in=BILLABLE_STATUSES, is_paid=False,
        ).prefetch_related("items__menu_item").order_by("created_at")
    )
    total_due = sum((o.total or 0) for o in orders)
    return render(request, "admin_user/cashier/table.html", {
        "restaurant": restaurant,
        "table": table,
        "orders": orders,
        "total_due": total_due,
    })


@require_POST
@restaurant_required(allowed_roles=CASHIER_ROLES)
def mark_order_paid(request, order_id):
    restaurant = request.restaurant
    order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
    if not order.is_paid and order.status in BILLABLE_STATUSES:
        order.is_paid = True
        order.paid_at = timezone.now()
        order.paid_by_name = _paid_by_name(request.user)
        order.save(update_fields=["is_paid", "paid_at", "paid_by_name"])
        messages.success(request, f"Commande #{order.order_number[-6:]} encaissée ({int(order.total)} FCFA).")
    return redirect(request.META.get("HTTP_REFERER") or "cashier")


@require_POST
@restaurant_required(allowed_roles=("owner", "coadmin"))
def mark_order_unpaid(request, order_id):
    """Annule un encaissement fait par erreur (owner/coadmin seulement)."""
    restaurant = request.restaurant
    order = get_object_or_404(Order, id=order_id, restaurant=restaurant)
    if order.is_paid:
        order.is_paid = False
        order.paid_at = None
        order.paid_by_name = ""
        order.save(update_fields=["is_paid", "paid_at", "paid_by_name"])
        messages.success(request, f"Commande #{order.order_number[-6:]} remise en non payée.")
    return redirect(request.META.get("HTTP_REFERER") or "cashier")


@require_POST
@restaurant_required(allowed_roles=CASHIER_ROLES)
def mark_table_paid(request, table_id):
    restaurant = request.restaurant
    table = get_object_or_404(Table, id=table_id, restaurant=restaurant)
    orders = Order.objects.filter(
        restaurant=restaurant, table=table,
        status__in=BILLABLE_STATUSES, is_paid=False,
    )
    now = timezone.now()
    name = _paid_by_name(request.user)
    total = 0
    n = 0
    for o in orders:
        o.is_paid = True
        o.paid_at = now
        o.paid_by_name = name
        o.save(update_fields=["is_paid", "paid_at", "paid_by_name"])
        total += int(o.total or 0)
        n += 1
    if n:
        messages.success(request, f"Table {table.number} encaissée : {n} commande(s), {total} FCFA.")
    else:
        messages.info(request, f"Aucune commande à encaisser sur la table {table.number}.")
    return redirect("cashier")
