# Analytics par Plan & Impression de Reçus — Plan d'implémentation

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter une page d'analytiques complète avec accès par palier selon le plan d'abonnement, et permettre l'impression de reçus depuis la liste/détail des commandes.

**Architecture:** Une nouvelle vue `analytics_view` dans `base/views.py` calcule les métriques selon le plan (`analytics` = Pro, `advanced_analytics` = Max). Une vue `order_receipt` génère un template HTML imprimable. Les accès sont gardés par les champs booléens déjà présents sur `SubscriptionPlan`.

**Tech Stack:** Django ORM (aggregations), Chart.js (déjà utilisé dans le dashboard), CSS `@media print`, HTML template pour le reçu.

---

## Analytiques disponibles par plan

| Métrique | Gratuit | Pro (`analytics`) | Max (`advanced_analytics`) |
|---|---|---|---|
| KPIs du tableau de bord (déjà présents) | ✓ | ✓ | ✓ |
| Page analytiques dédiée | ✗ | ✓ | ✓ |
| Revenus des 30 derniers jours (courbe) | ✗ | ✓ | ✓ |
| Top 5 plats les plus commandés | ✗ | ✓ | ✓ |
| Valeur moyenne par commande | ✗ | ✓ | ✓ |
| Répartition par heure (heures de pointe) | ✗ | ✓ | ✓ |
| Tendance des revenus sur 12 mois | ✗ | ✗ | ✓ |
| Performance par catégorie | ✗ | ✗ | ✓ |
| Taux d'annulation | ✗ | ✗ | ✓ |
| Export CSV des commandes | ✗ | ✗ | ✓ |

---

## Structure des fichiers

| Fichier | Action | Rôle |
|---|---|---|
| `base/views.py` | Modifier | Ajouter `analytics_view`, `order_receipt`, `export_orders_csv` |
| `base/urls.py` | Modifier | Ajouter routes `/analytiques/`, `/orders/<pk>/recu/`, `/orders/export-csv/` |
| `templates/admin_user/analytics/index.html` | Créer | Page analytiques avec graphiques Chart.js |
| `templates/admin_user/orders/receipt.html` | Créer | Template de reçu imprimable |
| `templates/admin_user/sidebar.html` | Modifier | Ajouter lien "Analytiques" dans le menu |

---

## Tâche 1 : Vue et URL pour la page d'analytiques

**Files:**
- Modify: `base/views.py` (après la vue `dashboard`)
- Modify: `base/urls.py`

- [ ] **Étape 1 : Ajouter la vue `analytics_view` dans `base/views.py`**

Ajouter après la fonction `dashboard` (ligne ~257) :

```python
@restaurant_required()
@owner_or_coadmin_required
def analytics_view(request):
    restaurant = request.restaurant
    plan = restaurant.subscription_plan

    if not plan or not plan.analytics:
        return render(request, "admin_user/analytics/index.html", {
            "restaurant": restaurant,
            "access_denied": True,
        })

    today = timezone.now().date()
    last_30_days = today - timedelta(days=29)
    last_12_months = today - timedelta(days=364)

    # --- Métriques Pro (analytics=True) ---

    # Revenus par jour sur 30 jours
    revenue_by_day = (
        Order.objects.filter(
            restaurant=restaurant,
            status__in=["confirmed", "preparing", "ready", "delivered"],
            created_at__date__gte=last_30_days,
        )
        .extra(select={"day": "date(created_at)"})
        .values("day")
        .annotate(revenue=Sum("total"))
        .order_by("day")
    )
    revenue_labels = []
    revenue_values = []
    for item in revenue_by_day:
        day = item["day"]
        if isinstance(day, str):
            day_obj = datetime.strptime(day, "%Y-%m-%d").date()
        else:
            day_obj = day
        revenue_labels.append(day_obj.strftime("%d/%m"))
        revenue_values.append(float(item["revenue"] or 0))

    # Top 5 plats les plus commandés
    top_items = (
        OrderItem.objects.filter(order__restaurant=restaurant)
        .values("menu_item__name")
        .annotate(total_qty=Sum("quantity"))
        .order_by("-total_qty")[:5]
    )

    # Valeur moyenne par commande
    avg_order = (
        Order.objects.filter(
            restaurant=restaurant,
            status__in=["confirmed", "preparing", "ready", "delivered"],
        ).aggregate(avg=Avg("total"))["avg"] or 0
    )

    # Répartition par heure (heures de pointe, 0–23)
    orders_by_hour = (
        Order.objects.filter(restaurant=restaurant)
        .extra(select={"hour": "EXTRACT(HOUR FROM created_at)"})
        .values("hour")
        .annotate(count=Count("id"))
        .order_by("hour")
    )
    hour_map = {int(row["hour"]): row["count"] for row in orders_by_hour}
    peak_labels = [f"{h:02d}h" for h in range(24)]
    peak_values = [hour_map.get(h, 0) for h in range(24)]

    context = {
        "restaurant": restaurant,
        "access_denied": False,
        "has_advanced": plan.advanced_analytics,
        # Pro
        "revenue_labels": revenue_labels,
        "revenue_values": revenue_values,
        "top_items": list(top_items),
        "avg_order": round(avg_order, 0),
        "peak_labels": peak_labels,
        "peak_values": peak_values,
    }

    # --- Métriques Max (advanced_analytics=True) ---
    if plan.advanced_analytics:
        # Revenus par mois sur 12 mois
        monthly_revenue = (
            Order.objects.filter(
                restaurant=restaurant,
                status__in=["confirmed", "preparing", "ready", "delivered"],
                created_at__date__gte=last_12_months,
            )
            .extra(select={"month": "strftime('%Y-%m', created_at)"})
            .values("month")
            .annotate(revenue=Sum("total"))
            .order_by("month")
        )
        context["monthly_labels"] = [r["month"] for r in monthly_revenue]
        context["monthly_values"] = [float(r["revenue"] or 0) for r in monthly_revenue]

        # Performance par catégorie
        category_perf = (
            OrderItem.objects.filter(order__restaurant=restaurant)
            .values("menu_item__category__name")
            .annotate(total_qty=Sum("quantity"), total_rev=Sum("price"))
            .order_by("-total_rev")
        )
        context["category_perf"] = list(category_perf)

        # Taux d'annulation
        total = Order.objects.filter(restaurant=restaurant).count()
        cancelled = Order.objects.filter(restaurant=restaurant, status="cancelled").count()
        context["cancellation_rate"] = round((cancelled / total * 100) if total else 0, 1)

    return render(request, "admin_user/analytics/index.html", context)
```

- [ ] **Étape 2 : Ajouter l'import `Avg` dans `base/views.py`**

Trouver la ligne d'import existante (en haut du fichier) :
```python
from django.db.models import Sum, Count
```
La remplacer par :
```python
from django.db.models import Sum, Count, Avg
```

- [ ] **Étape 3 : Ajouter la route dans `base/urls.py`**

Ajouter après la ligne `path("dashboard/", dashboard, name="dashboard"),` :
```python
path("analytiques/", analytics_view, name="analytics"),
```

Ajouter `analytics_view` à l'import en haut de `base/urls.py` :
```python
from .views import (
    home, create_restaurant, dashboard, analytics_view,
    # ... reste des imports existants
)
```

- [ ] **Étape 4 : Vérifier que la vue s'importe sans erreur**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py check
```
Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Étape 5 : Commit**

```bash
git add base/views.py base/urls.py
git commit -m "feat: add analytics_view with Pro/Max plan gating"
```

---

## Tâche 2 : Template de la page d'analytiques

**Files:**
- Create: `templates/admin_user/analytics/index.html`

- [ ] **Étape 1 : Créer le répertoire et le template**

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/templates/admin_user/analytics"
```

- [ ] **Étape 2 : Créer `templates/admin_user/analytics/index.html`**

```html
{% extends "admin_user/base.html" %}
{% load i18n %}

{% block title %}{% trans "Analytiques" %}{% endblock %}

{% block content %}
<div class="container-fluid py-4">

  {% if access_denied %}
  <!-- Paywall -->
  <div class="row justify-content-center mt-5">
    <div class="col-md-6 text-center">
      <div class="card shadow-sm border-0 p-5">
        <div class="mb-3" style="font-size:3rem;">📊</div>
        <h4 class="fw-bold mb-2">{% trans "Analytiques avancées" %}</h4>
        <p class="text-muted mb-4">
          {% trans "Accédez aux rapports de revenus, aux plats les plus commandés, aux heures de pointe et bien plus encore avec le plan Pro." %}
        </p>
        <a href="{% url 'pricing' %}" class="btn btn-primary btn-lg rounded-pill px-5">
          {% trans "Passer au plan Pro" %}
        </a>
      </div>
    </div>
  </div>

  {% else %}

  <div class="d-flex justify-content-between align-items-center mb-4">
    <h2 class="fw-bold mb-0">{% trans "Analytiques" %}</h2>
    {% if has_advanced %}
    <a href="{% url 'export_orders_csv' %}" class="btn btn-outline-secondary btn-sm">
      <i class="bi bi-download me-1"></i>{% trans "Exporter CSV" %}
    </a>
    {% endif %}
  </div>

  <!-- KPIs Pro -->
  <div class="row g-3 mb-4">
    <div class="col-6 col-md-3">
      <div class="card border-0 shadow-sm text-center p-3">
        <div class="text-muted small mb-1">{% trans "Valeur moyenne / commande" %}</div>
        <div class="fw-bold fs-4">{{ avg_order }} FCFA</div>
      </div>
    </div>
    {% if has_advanced %}
    <div class="col-6 col-md-3">
      <div class="card border-0 shadow-sm text-center p-3">
        <div class="text-muted small mb-1">{% trans "Taux d'annulation" %}</div>
        <div class="fw-bold fs-4">{{ cancellation_rate }}%</div>
      </div>
    </div>
    {% endif %}
  </div>

  <!-- Revenus 30 jours -->
  <div class="row g-3 mb-4">
    <div class="col-12 col-lg-8">
      <div class="card border-0 shadow-sm p-3">
        <h6 class="fw-semibold mb-3">{% trans "Revenus — 30 derniers jours" %}</h6>
        <canvas id="revenueChart" height="100"></canvas>
      </div>
    </div>
    <div class="col-12 col-lg-4">
      <div class="card border-0 shadow-sm p-3">
        <h6 class="fw-semibold mb-3">{% trans "Top 5 plats commandés" %}</h6>
        {% for item in top_items %}
        <div class="d-flex justify-content-between align-items-center py-1 border-bottom">
          <span class="text-truncate me-2" style="max-width:160px;">{{ item.menu_item__name }}</span>
          <span class="badge bg-primary rounded-pill">{{ item.total_qty }}x</span>
        </div>
        {% empty %}
        <p class="text-muted small">{% trans "Aucune donnée." %}</p>
        {% endfor %}
      </div>
    </div>
  </div>

  <!-- Heures de pointe -->
  <div class="row g-3 mb-4">
    <div class="col-12">
      <div class="card border-0 shadow-sm p-3">
        <h6 class="fw-semibold mb-3">{% trans "Heures de pointe" %}</h6>
        <canvas id="peakChart" height="60"></canvas>
      </div>
    </div>
  </div>

  {% if has_advanced %}
  <!-- Revenus 12 mois -->
  <div class="row g-3 mb-4">
    <div class="col-12 col-lg-7">
      <div class="card border-0 shadow-sm p-3">
        <h6 class="fw-semibold mb-3">{% trans "Revenus — 12 derniers mois" %}</h6>
        <canvas id="monthlyChart" height="100"></canvas>
      </div>
    </div>
    <div class="col-12 col-lg-5">
      <div class="card border-0 shadow-sm p-3">
        <h6 class="fw-semibold mb-3">{% trans "Performance par catégorie" %}</h6>
        <div class="table-responsive">
          <table class="table table-sm mb-0">
            <thead><tr><th>{% trans "Catégorie" %}</th><th class="text-end">{% trans "Qté" %}</th><th class="text-end">{% trans "Revenus" %}</th></tr></thead>
            <tbody>
              {% for c in category_perf %}
              <tr>
                <td>{{ c.menu_item__category__name|default:"—" }}</td>
                <td class="text-end">{{ c.total_qty }}</td>
                <td class="text-end">{{ c.total_rev }} FCFA</td>
              </tr>
              {% empty %}
              <tr><td colspan="3" class="text-muted">{% trans "Aucune donnée." %}</td></tr>
              {% endfor %}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
  {% endif %}

  {% endif %}{# end access_denied #}
</div>

{% if not access_denied %}
<script>
const primaryColor = getComputedStyle(document.documentElement).getPropertyValue('--bs-primary').trim() || '#0d6efd';

// Revenus 30j
new Chart(document.getElementById('revenueChart'), {
  type: 'line',
  data: {
    labels: {{ revenue_labels|safe }},
    datasets: [{
      label: 'FCFA',
      data: {{ revenue_values|safe }},
      borderColor: primaryColor,
      backgroundColor: primaryColor + '22',
      fill: true,
      tension: 0.4,
      pointRadius: 3,
    }]
  },
  options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
});

// Heures de pointe
new Chart(document.getElementById('peakChart'), {
  type: 'bar',
  data: {
    labels: {{ peak_labels|safe }},
    datasets: [{
      label: '{% trans "Commandes" %}',
      data: {{ peak_values|safe }},
      backgroundColor: primaryColor + 'bb',
    }]
  },
  options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { stepSize: 1 } } } }
});

{% if has_advanced %}
// Revenus 12 mois
new Chart(document.getElementById('monthlyChart'), {
  type: 'bar',
  data: {
    labels: {{ monthly_labels|safe }},
    datasets: [{
      label: 'FCFA',
      data: {{ monthly_values|safe }},
      backgroundColor: primaryColor + 'cc',
    }]
  },
  options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true } } }
});
{% endif %}
</script>
{% endif %}
{% endblock %}
```

- [ ] **Étape 3 : Tester la page en naviguant vers `/analytiques/`**

Démarrer le serveur :
```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py runserver
```
- Avec un compte sur plan **Gratuit** → doit afficher le paywall
- Avec un compte sur plan **Pro** → doit afficher les graphiques Pro
- Avec un compte sur plan **Max** → doit afficher tous les graphiques y compris les 12 mois

- [ ] **Étape 4 : Commit**

```bash
git add templates/admin_user/analytics/
git commit -m "feat: add analytics page template with Pro/Max sections"
```

---

## Tâche 3 : Lien "Analytiques" dans la sidebar

**Files:**
- Modify: `templates/admin_user/sidebar.html`

- [ ] **Étape 1 : Ouvrir la sidebar et repérer le lien "Dashboard"**

```bash
grep -n "dashboard\|Tableau de bord\|analytique" "/home/jey/Documents/projet /OpendFood/templates/admin_user/sidebar.html"
```

- [ ] **Étape 2 : Ajouter le lien après le lien dashboard**

Trouver le bloc `<li>` correspondant au lien "Tableau de bord" / dashboard dans la sidebar.
Après ce bloc, ajouter (en suivant le même style HTML existant) :

```html
{% if user_role == 'owner' or user_role == 'coadmin' %}
<li class="nav-item">
  <a href="{% url 'analytics' %}" class="nav-link {% if request.resolver_match.url_name == 'analytics' %}active{% endif %}">
    <i class="nav-icon bi bi-bar-chart-line"></i>
    <span>{% trans "Analytiques" %}</span>
  </a>
</li>
{% endif %}
```

- [ ] **Étape 3 : Vérifier visuellement que le lien apparaît dans la sidebar**

Naviguer vers le dashboard → le lien "Analytiques" doit être visible dans la barre latérale.

- [ ] **Étape 4 : Commit**

```bash
git add templates/admin_user/sidebar.html
git commit -m "feat: add Analytics link in sidebar for owner/coadmin"
```

---

## Tâche 4 : Export CSV des commandes (plan Max)

**Files:**
- Modify: `base/views.py`
- Modify: `base/urls.py`

- [ ] **Étape 1 : Ajouter la vue `export_orders_csv` dans `base/views.py`**

Ajouter après `analytics_view` :

```python
@restaurant_required()
@owner_or_coadmin_required
def export_orders_csv(request):
    import csv
    restaurant = request.restaurant
    plan = restaurant.subscription_plan

    if not plan or not plan.advanced_analytics:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès réservé au plan Max.")

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
```

- [ ] **Étape 2 : Ajouter la route dans `base/urls.py`**

```python
path("orders/export-csv/", export_orders_csv, name="export_orders_csv"),
```

Ajouter `export_orders_csv` à l'import en haut de `base/urls.py`.

- [ ] **Étape 3 : Vérifier que le CSV se télécharge correctement**

Avec un compte Max, cliquer sur "Exporter CSV" depuis `/analytiques/` → un fichier `.csv` doit se télécharger avec les colonnes correctes.

- [ ] **Étape 4 : Commit**

```bash
git add base/views.py base/urls.py
git commit -m "feat: add CSV export for Max plan subscribers"
```

---

## Tâche 5 : Vue et template du reçu d'impression

**Files:**
- Modify: `base/views.py`
- Modify: `base/urls.py`
- Create: `templates/admin_user/orders/receipt.html`

- [ ] **Étape 1 : Ajouter la vue `order_receipt` dans `base/views.py`**

Ajouter après `export_orders_csv` (ou après `order_detail`) :

```python
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
```

- [ ] **Étape 2 : Ajouter la route dans `base/urls.py`**

```python
path("orders/<int:pk>/recu/", order_receipt, name="order_receipt"),
```

Ajouter `order_receipt` à l'import en haut de `base/urls.py`.

- [ ] **Étape 3 : Créer `templates/admin_user/orders/receipt.html`**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reçu {{ order.order_number }}</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: 'Courier New', monospace; font-size: 13px; color: #000; background: #fff; padding: 20px; max-width: 380px; margin: 0 auto; }
    .header { text-align: center; border-bottom: 2px dashed #000; padding-bottom: 12px; margin-bottom: 12px; }
    .header h1 { font-size: 18px; font-weight: bold; text-transform: uppercase; }
    .header p { font-size: 11px; color: #444; }
    .section { margin-bottom: 10px; }
    .section-title { font-weight: bold; text-transform: uppercase; font-size: 11px; letter-spacing: 1px; border-bottom: 1px dashed #000; padding-bottom: 4px; margin-bottom: 6px; }
    .row { display: flex; justify-content: space-between; margin-bottom: 3px; }
    .row .label { color: #555; }
    table { width: 100%; border-collapse: collapse; margin-bottom: 10px; }
    table th { font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #000; padding: 4px 0; text-align: left; }
    table th:last-child, table td:last-child { text-align: right; }
    table td { padding: 4px 0; vertical-align: top; }
    .totals { border-top: 2px dashed #000; padding-top: 8px; }
    .totals .row { font-weight: bold; font-size: 15px; }
    .footer { text-align: center; border-top: 1px dashed #000; margin-top: 14px; padding-top: 10px; font-size: 11px; color: #555; }
    .badge { display: inline-block; padding: 2px 8px; border: 1px solid #000; border-radius: 3px; font-size: 11px; font-weight: bold; }
    @media print {
      body { padding: 0; }
      .no-print { display: none !important; }
      @page { margin: 8mm; size: 80mm auto; }
    }
  </style>
</head>
<body>

<!-- Bouton d'impression (masqué à l'impression) -->
<div class="no-print" style="text-align:center; margin-bottom: 16px;">
  <button onclick="window.print()" style="padding: 8px 24px; font-size: 14px; cursor: pointer; background: #000; color: #fff; border: none; border-radius: 4px;">
    🖨 Imprimer
  </button>
  <a href="javascript:history.back()" style="margin-left: 12px; font-size: 13px; color: #555;">← Retour</a>
</div>

<div class="header">
  {% if restaurant.logo %}
    <img src="{{ restaurant.logo.url }}" alt="{{ restaurant.name }}" style="max-height:50px; max-width:120px; margin-bottom:6px;">
  {% endif %}
  <h1>{{ restaurant.name }}</h1>
  {% if restaurant.address %}<p>{{ restaurant.address }}</p>{% endif %}
  {% if restaurant.phone %}<p>{{ restaurant.phone }}</p>{% endif %}
</div>

<div class="section">
  <div class="section-title">Commande</div>
  <div class="row">
    <span class="label">Numéro :</span>
    <span><strong>{{ order.order_number }}</strong></span>
  </div>
  <div class="row">
    <span class="label">Date :</span>
    <span>{{ order.created_at|date:"d/m/Y H:i" }}</span>
  </div>
  <div class="row">
    <span class="label">Type :</span>
    <span>{{ order.get_order_type_display }}</span>
  </div>
  {% if order.table %}
  <div class="row">
    <span class="label">Table :</span>
    <span>{{ order.table.number }}</span>
  </div>
  {% endif %}
  <div class="row">
    <span class="label">Statut :</span>
    <span class="badge">{{ order.get_status_display }}</span>
  </div>
</div>

{% if order.customer_name %}
<div class="section">
  <div class="section-title">Client</div>
  <div class="row">
    <span class="label">Nom :</span>
    <span>{{ order.customer_name }}</span>
  </div>
  {% if order.customer_phone %}
  <div class="row">
    <span class="label">Tél :</span>
    <span>{{ order.customer_phone }}</span>
  </div>
  {% endif %}
</div>
{% endif %}

<div class="section">
  <div class="section-title">Articles</div>
  <table>
    <thead>
      <tr>
        <th>Article</th>
        <th style="text-align:center">Qté</th>
        <th>Prix</th>
      </tr>
    </thead>
    <tbody>
      {% for item in items %}
      <tr>
        <td>{{ item.menu_item.name }}{% if item.notes %}<br><small style="color:#666">{{ item.notes }}</small>{% endif %}</td>
        <td style="text-align:center">{{ item.quantity }}</td>
        <td>{{ item.get_total }} F</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>

<div class="totals">
  {% if order.tax > 0 %}
  <div class="row" style="font-weight:normal; font-size:13px;">
    <span>Sous-total</span>
    <span>{{ order.subtotal }} FCFA</span>
  </div>
  <div class="row" style="font-weight:normal; font-size:13px;">
    <span>Taxes</span>
    <span>{{ order.tax }} FCFA</span>
  </div>
  {% endif %}
  <div class="row">
    <span>TOTAL</span>
    <span>{{ order.total }} FCFA</span>
  </div>
</div>

{% if order.notes %}
<div class="section" style="margin-top:10px;">
  <div class="section-title">Notes</div>
  <p>{{ order.notes }}</p>
</div>
{% endif %}

<div class="footer">
  <p>Merci de votre visite !</p>
  <p style="margin-top:4px; font-size:10px;">Propulsé par OpenFood</p>
</div>

</body>
</html>
```

- [ ] **Étape 4 : Vérifier le rendu du reçu**

Naviguer vers `/orders/1/recu/` (remplacer 1 par un ID réel).
- Le reçu doit s'afficher avec les informations du restaurant, la commande, les articles et le total.
- Cliquer sur "Imprimer" → la boîte de dialogue d'impression du navigateur s'ouvre.
- Dans l'aperçu d'impression, le bouton "Imprimer" et le lien "Retour" ne doivent pas apparaître.

- [ ] **Étape 5 : Commit**

```bash
git add base/views.py base/urls.py templates/admin_user/orders/receipt.html
git commit -m "feat: add printable order receipt view and template"
```

---

## Tâche 6 : Boutons "Imprimer le reçu" sur la liste et la page de modification des commandes

**Files:**
- Modify: `templates/admin_user/orders/list_orders.html`
- Modify: `templates/admin_user/orders/update_order.html`

- [ ] **Étape 1 : Repérer l'emplacement du bouton dans la liste des commandes**

```bash
grep -n "order_detail\|update_order\|order\.pk\|order\.id\|btn" "/home/jey/Documents/projet /OpendFood/templates/admin_user/orders/list_orders.html" | head -20
```

- [ ] **Étape 2 : Ajouter le bouton reçu dans `list_orders.html`**

Dans le bloc qui affiche les actions par commande (là où se trouvent les boutons de détail/modification), ajouter :

```html
<a href="{% url 'order_receipt' order.pk %}" 
   target="_blank" 
   class="btn btn-sm btn-outline-secondary" 
   title="Imprimer le reçu">
  <i class="bi bi-printer"></i>
</a>
```

- [ ] **Étape 3 : Ajouter le bouton reçu dans `update_order.html`**

```bash
grep -n "btn\|Enregistrer\|Annuler\|delete_order" "/home/jey/Documents/projet /OpendFood/templates/admin_user/orders/update_order.html" | head -20
```

Dans le bas du formulaire (près du bouton "Enregistrer"), ajouter :

```html
<a href="{% url 'order_receipt' order.pk %}" 
   target="_blank" 
   class="btn btn-outline-secondary">
  <i class="bi bi-printer me-1"></i>{% trans "Imprimer le reçu" %}
</a>
```

- [ ] **Étape 4 : Vérifier les boutons visuellement**

- Liste des commandes : chaque ligne doit avoir une icône imprimante.
- Page de modification : le bouton "Imprimer le reçu" doit apparaître à côté de "Enregistrer".
- Cliquer sur le bouton → le reçu s'ouvre dans un nouvel onglet.

- [ ] **Étape 5 : Commit**

```bash
git add templates/admin_user/orders/list_orders.html templates/admin_user/orders/update_order.html
git commit -m "feat: add print receipt buttons to order list and update pages"
```

---

## Révision du plan

### Couverture des exigences

| Exigence | Tâche |
|---|---|
| Analytiques basiques (gratuit) | Déjà en place sur le dashboard |
| Page analytiques Pro (revenus 30j, top plats, valeur moy., heures de pointe) | Tâches 1 + 2 |
| Page analytiques Max (12 mois, catégories, taux annulation) | Tâches 1 + 2 |
| Export CSV (Max seulement) | Tâche 4 |
| Paywall pour plan Gratuit | Tâche 2 (bloc `access_denied`) |
| Lien dans la sidebar | Tâche 3 |
| Impression de reçu (template) | Tâche 5 |
| Bouton imprimer sur liste et édition | Tâche 6 |

### Scan des placeholders

Aucun "TBD" ou "TODO" dans le plan — chaque étape contient le code complet.

### Cohérence des types

- `order_receipt` → paramètre `pk` (int) cohérent avec `orders/<int:pk>/recu/`
- `analytics_view` → utilise `OrderItem` (déjà importé dans `base/views.py`)
- `export_orders_csv` → utilise `Order.objects.filter(restaurant=restaurant)` cohérent avec le reste des vues
