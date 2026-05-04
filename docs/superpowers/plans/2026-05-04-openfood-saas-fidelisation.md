# OpenFood – SaaS Menu Digital & Fidélisation – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer le menu QR Code passif d'OpenFood en outil de fidélisation complet : capture client, ticket digital, PWA offline-first, re-engagement automatisé, parrainage et feedback.

**Architecture:** Full Django (pas de React/API séparé). Chaque feature est un module Django dans les apps existantes (`customer`, `base`). Les campagnes de re-engagement sont déclenchées par management command (cron). La PWA utilise les Service Workers natifs du navigateur.

**Tech Stack:** Django 4+, SQLite (dev) → PostgreSQL (prod), Django Email (SMTP Gmail existant), Service Workers (JS natif), qrcode (déjà installé), Pillow (déjà installé). Aucun nouveau package requis pour les Phases A–C. Phase D nécessite `celery` + `redis` optionnel (management command suffisant en attendant).

---

## État du codebase au démarrage

- `customer/models.py` : **vide** – CustomerProfile à créer
- `base/models.py` : Order existe avec `customer_name`, `customer_phone`, `customer_email` (champs texte libres, non reliés à un profil)
- `customer/views.py` : checkout existant ne capture PAS le nom/téléphone/email du client QR
- `base/views.py` : `check_new_orders` fait du polling (pas de WebSocket)
- `main/settings.py` : EMAIL_BACKEND Gmail SMTP déjà configuré

---

## Phase A : Capture Client & Ticket Digital

### Task 1 : Modèle CustomerProfile

**Files:**
- Create: `customer/models.py`
- Create: `customer/migrations/0001_customerprofile.py` (généré par makemigrations)

- [ ] **Step 1.1 : Écrire le test qui échoue**

```python
# customer/tests.py
from django.test import TestCase
from customer.models import CustomerProfile

class CustomerProfileTest(TestCase):
    def test_create_profile_with_phone(self):
        profile = CustomerProfile.objects.create(
            phone="0123456789",
            first_name="Jean",
            last_name="Dupont",
        )
        self.assertEqual(profile.phone, "0123456789")
        self.assertEqual(profile.visit_count, 0)
        self.assertIsNone(profile.last_visit)

    def test_phone_unique(self):
        CustomerProfile.objects.create(phone="0123456789")
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            CustomerProfile.objects.create(phone="0123456789")

    def test_record_visit_increments_count(self):
        profile = CustomerProfile.objects.create(phone="0123456789")
        profile.record_visit()
        profile.refresh_from_db()
        self.assertEqual(profile.visit_count, 1)
        self.assertIsNotNone(profile.last_visit)
```

- [ ] **Step 1.2 : Lancer le test pour vérifier qu'il échoue**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py test customer.tests.CustomerProfileTest -v 2
```

Expected: `ImportError: cannot import name 'CustomerProfile' from 'customer.models'`

- [ ] **Step 1.3 : Implémenter CustomerProfile**

Remplacer le contenu de `customer/models.py` :

```python
from django.db import models
from django.utils import timezone


class CustomerProfile(models.Model):
    phone = models.CharField(max_length=20, unique=True)
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    whatsapp_opted_in = models.BooleanField(default=False)
    email_opted_in = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_visit = models.DateTimeField(null=True, blank=True)
    visit_count = models.IntegerField(default=0)

    def record_visit(self):
        self.visit_count += 1
        self.last_visit = timezone.now()
        self.save(update_fields=["visit_count", "last_visit"])

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.phone})"
```

- [ ] **Step 1.4 : Générer et appliquer la migration**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py makemigrations customer
python manage.py migrate
```

Expected: `Applying customer.0001_customerprofile... OK`

- [ ] **Step 1.5 : Lancer les tests**

```bash
python manage.py test customer.tests.CustomerProfileTest -v 2
```

Expected: `Ran 3 tests ... OK`

- [ ] **Step 1.6 : Commit**

```bash
git add customer/models.py customer/migrations/
git commit -m "feat(customer): add CustomerProfile model with visit tracking"
```

---

### Task 2 : Relier Order à CustomerProfile

**Files:**
- Modify: `base/models.py` — ajouter FK CustomerProfile sur Order
- Create: migration dans `base/migrations/`

- [ ] **Step 2.1 : Écrire le test**

```python
# base/tests.py
from django.test import TestCase
from base.models import Order, Restaurant, SubscriptionPlan
from customer.models import CustomerProfile
from accounts.models import User

class OrderCustomerLinkTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@test.com",
            password="pass",
            first_name="O",
            last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        self.restaurant = Restaurant.objects.create(
            owner=self.user, name="Test Resto", address="1 rue Test",
            phone="0100000000", email="r@test.com",
            subscription_plan=plan,
        )

    def test_order_links_to_customer_profile(self):
        profile = CustomerProfile.objects.create(phone="0601020304")
        order = Order.objects.create(
            restaurant=self.restaurant,
            customer_profile=profile,
        )
        self.assertEqual(order.customer_profile.phone, "0601020304")

    def test_order_customer_profile_nullable(self):
        order = Order.objects.create(restaurant=self.restaurant)
        self.assertIsNone(order.customer_profile)
```

- [ ] **Step 2.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test base.tests.OrderCustomerLinkTest -v 2
```

Expected: `TypeError: Order.objects.create() got an unexpected keyword argument 'customer_profile'`

- [ ] **Step 2.3 : Ajouter le champ dans Order**

Dans `base/models.py`, dans la classe `Order`, après la ligne `notes = models.TextField(blank=True)` :

```python
    customer_profile = models.ForeignKey(
        'customer.CustomerProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='orders',
    )
```

- [ ] **Step 2.4 : Migration**

```bash
python manage.py makemigrations base
python manage.py migrate
```

Expected: `Applying base.0005_order_customer_profile... OK`

- [ ] **Step 2.5 : Tests**

```bash
python manage.py test base.tests.OrderCustomerLinkTest -v 2
```

Expected: `Ran 2 tests ... OK`

- [ ] **Step 2.6 : Commit**

```bash
git add base/models.py base/migrations/
git commit -m "feat(base): link Order to CustomerProfile (nullable FK)"
```

---

### Task 3 : Formulaire de checkout avec capture client

**Files:**
- Create: `customer/forms.py`
- Modify: `customer/views.py` — fonction `checkout`
- Modify: `templates/customer/checkout.html`

- [ ] **Step 3.1 : Écrire le test**

```python
# customer/tests.py  (ajouter après la classe existante)
from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from base.models import Restaurant, Table, SubscriptionPlan, Order
from customer.models import CustomerProfile
from accounts.models import User

class CheckoutCaptureTest(TestCase):
    def setUp(self):
        self.client_http = Client()
        user = User.objects.create_user(
            email="owner@test.com", password="pass",
            first_name="O", last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        restaurant = Restaurant.objects.create(
            owner=user, name="Resto Test", address="1 rue",
            phone="0100000000", email="r@test.com",
            subscription_plan=plan,
        )
        self.table = Table.objects.create(
            restaurant=restaurant, number="1", capacity=4,
        )
        # Pré-remplir le panier dans la session
        session = self.client_http.session
        cart_key = f"cart_{restaurant.id}_{self.table.token}"
        session[cart_key] = {
            "1": {"name": "Burger", "price": "5.00", "quantity": 2}
        }
        session.save()
        self.table_token = str(self.table.token)
        self.restaurant = restaurant

    def test_checkout_creates_customer_profile(self):
        url = reverse("checkout", kwargs={"table_token": self.table_token})
        response = self.client_http.post(url, {
            "first_name": "Marie",
            "last_name": "Curie",
            "phone": "0601020304",
            "email": "marie@test.com",
            "receipt_method": "email",
        })
        self.assertEqual(CustomerProfile.objects.count(), 1)
        profile = CustomerProfile.objects.first()
        self.assertEqual(profile.phone, "0601020304")
        self.assertEqual(profile.visit_count, 1)

    def test_checkout_links_profile_to_order(self):
        url = reverse("checkout", kwargs={"table_token": self.table_token})
        self.client_http.post(url, {
            "first_name": "Marie",
            "last_name": "Curie",
            "phone": "0601020304",
            "email": "",
            "receipt_method": "none",
        })
        order = Order.objects.first()
        self.assertIsNotNone(order)
        self.assertIsNotNone(order.customer_profile)
        self.assertEqual(order.customer_profile.phone, "0601020304")
```

- [ ] **Step 3.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.CheckoutCaptureTest -v 2
```

Expected: FAIL (checkout ne capture pas les données client)

- [ ] **Step 3.3 : Créer le formulaire client**

Créer `customer/forms.py` :

```python
from django import forms


class CustomerInfoForm(forms.Form):
    first_name = forms.CharField(max_length=100, required=False, label="Prénom")
    last_name = forms.CharField(max_length=100, required=False, label="Nom")
    phone = forms.CharField(max_length=20, required=True, label="Téléphone")
    email = forms.EmailField(required=False, label="Email")
    receipt_method = forms.ChoiceField(
        choices=[
            ("none", "Pas de reçu"),
            ("email", "Reçu par email"),
            ("whatsapp", "Reçu par WhatsApp"),
        ],
        required=False,
        initial="none",
    )
```

- [ ] **Step 3.4 : Mettre à jour la vue checkout**

Remplacer la fonction `checkout` dans `customer/views.py` :

```python
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db import transaction
from base.models import Order, OrderItem
from customer.models import CustomerProfile
from customer.forms import CustomerInfoForm
from customer.utils import get_client_context
from customer.services.receipt import send_email_receipt, build_whatsapp_receipt_url


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
        form = CustomerInfoForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["phone"]
            first_name = form.cleaned_data.get("first_name", "")
            last_name = form.cleaned_data.get("last_name", "")
            email = form.cleaned_data.get("email", "")
            receipt_method = form.cleaned_data.get("receipt_method", "none")

            with transaction.atomic():
                profile, _ = CustomerProfile.objects.get_or_create(phone=phone)
                profile.first_name = profile.first_name or first_name
                profile.last_name = profile.last_name or last_name
                if email:
                    profile.email = email
                profile.email_opted_in = receipt_method == "email"
                profile.whatsapp_opted_in = receipt_method == "whatsapp"
                profile.save()
                profile.record_visit()

                order = Order.objects.create(
                    restaurant=restaurant,
                    table=table,
                    order_type="dine_in",
                    status="pending",
                    customer_profile=profile,
                    customer_name=f"{first_name} {last_name}".strip(),
                    customer_phone=phone,
                    customer_email=email,
                )

                for item_id, data in cart.items():
                    OrderItem.objects.create(
                        order=order,
                        menu_item_id=item_id,
                        quantity=data["quantity"],
                        price=data["price"],
                    )

                order.calculate_total()
                del request.session[cart_key]

            if receipt_method == "email" and email:
                send_email_receipt(order)

            return redirect("order_confirmation", order_id=order.id)
    else:
        form = CustomerInfoForm()

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
        "cart": cart_items,
        "cart_total": cart_total,
        "form": form,
    })
```

- [ ] **Step 3.5 : Créer le service de reçu**

Créer le dossier et fichier `customer/services/receipt.py` :

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/customer/services"
touch "/home/jey/Documents/projet /OpendFood/customer/services/__init__.py"
```

```python
# customer/services/receipt.py
from django.core.mail import send_mail
from django.conf import settings
import urllib.parse


def send_email_receipt(order):
    if not order.customer_email:
        return

    items_lines = "\n".join(
        f"  - {item.menu_item.name} x{item.quantity} : {item.get_total()} FCFA"
        for item in order.items.all()
    )

    body = (
        f"Bonjour {order.customer_name or 'cher client'},\n\n"
        f"Merci pour votre commande chez {order.restaurant.name} !\n\n"
        f"Commande n° {order.order_number}\n"
        f"Table : {order.table.number if order.table else 'N/A'}\n\n"
        f"Détail :\n{items_lines}\n\n"
        f"Total : {order.total} FCFA\n\n"
        f"À bientôt !"
    )

    send_mail(
        subject=f"Votre reçu – {order.restaurant.name}",
        message=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[order.customer_email],
        fail_silently=True,
    )


def build_whatsapp_receipt_url(order):
    if not order.customer_phone:
        return None

    items_lines = ", ".join(
        f"{item.menu_item.name} x{item.quantity}"
        for item in order.items.all()
    )

    message = (
        f"Votre reçu {order.restaurant.name} 🍽️\n"
        f"Commande #{order.order_number}\n"
        f"{items_lines}\n"
        f"Total: {order.total} FCFA\nMerci!"
    )

    phone = order.customer_phone.replace(" ", "").replace("+", "")
    encoded = urllib.parse.quote(message)
    return f"https://wa.me/{phone}?text={encoded}"
```

- [ ] **Step 3.6 : Mettre à jour le template checkout.html**

Remplacer le contenu de `templates/customer/checkout.html` par :

```html
{% extends 'customer/base.html' %}
{% block content %}
<div class="max-w-lg mx-auto p-4">
  <h1 class="text-2xl font-bold mb-4">Finaliser la commande</h1>

  <!-- Récapitulatif panier -->
  <div class="bg-white rounded-xl shadow p-4 mb-6">
    <h2 class="font-semibold text-lg mb-3">Votre commande</h2>
    {% for item in cart %}
    <div class="flex justify-between py-1 text-sm">
      <span>{{ item.name }} x{{ item.quantity }}</span>
      <span>{{ item.total }} FCFA</span>
    </div>
    {% endfor %}
    <div class="border-t mt-2 pt-2 font-bold flex justify-between">
      <span>Total</span>
      <span>{{ cart_total }} FCFA</span>
    </div>
  </div>

  <!-- Formulaire client -->
  <form method="POST">
    {% csrf_token %}
    <div class="bg-white rounded-xl shadow p-4 mb-6 space-y-4">
      <h2 class="font-semibold text-lg">Vos coordonnées</h2>

      <div>
        <label class="block text-sm font-medium text-gray-700">Prénom</label>
        <input type="text" name="first_name" value="{{ form.first_name.value|default:'' }}"
          class="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Nom</label>
        <input type="text" name="last_name" value="{{ form.last_name.value|default:'' }}"
          class="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Téléphone <span class="text-red-500">*</span></label>
        <input type="tel" name="phone" value="{{ form.phone.value|default:'' }}" required
          class="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
        {% if form.phone.errors %}
        <p class="text-red-500 text-xs mt-1">{{ form.phone.errors|join:", " }}</p>
        {% endif %}
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Email</label>
        <input type="email" name="email" value="{{ form.email.value|default:'' }}"
          class="mt-1 w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500">
      </div>

      <div>
        <label class="block text-sm font-medium text-gray-700">Recevoir mon reçu</label>
        <div class="mt-2 space-y-2">
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="receipt_method" value="none" checked class="accent-green-600">
            <span class="text-sm">Pas de reçu</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="receipt_method" value="email" class="accent-green-600">
            <span class="text-sm">Par email</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input type="radio" name="receipt_method" value="whatsapp" class="accent-green-600">
            <span class="text-sm">Par WhatsApp</span>
          </label>
        </div>
      </div>
    </div>

    <button type="submit"
      class="w-full bg-green-600 text-white font-semibold py-3 rounded-xl hover:bg-green-700 transition">
      Confirmer ma commande
    </button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 3.7 : Lancer les tests**

```bash
python manage.py test customer.tests.CheckoutCaptureTest -v 2
```

Expected: `Ran 2 tests ... OK`

- [ ] **Step 3.8 : Commit**

```bash
git add customer/forms.py customer/views.py customer/services/ templates/customer/checkout.html
git commit -m "feat(customer): capture client info at checkout, link to CustomerProfile"
```

---

### Task 4 : Page de confirmation avec options reçu WhatsApp

**Files:**
- Modify: `customer/views.py` — `order_confirmation`
- Modify: `templates/customer/confirmation.html`

- [ ] **Step 4.1 : Écrire le test**

```python
# customer/tests.py  (ajouter à la fin)
class OrderConfirmationWhatsAppTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="o2@test.com", password="pass",
            first_name="O", last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter2", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        restaurant = Restaurant.objects.create(
            owner=user, name="Resto2", address="1 rue",
            phone="0100000001", email="r2@test.com",
            subscription_plan=plan,
        )
        self.order = Order.objects.create(
            restaurant=restaurant,
            customer_phone="0601020304",
            customer_name="Jean Test",
        )

    def test_confirmation_page_returns_200(self):
        from django.test import Client
        c = Client()
        url = reverse("order_confirmation", kwargs={"order_id": self.order.id})
        response = c.get(url)
        self.assertEqual(response.status_code, 200)

    def test_whatsapp_url_in_context(self):
        from customer.services.receipt import build_whatsapp_receipt_url
        self.order.customer_phone = "22901020304"
        self.order.save()
        url = build_whatsapp_receipt_url(self.order)
        self.assertIn("wa.me/22901020304", url)
        self.assertIn("text=", url)
```

- [ ] **Step 4.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.OrderConfirmationWhatsAppTest -v 2
```

Expected: Tests échouent car `build_whatsapp_receipt_url` n'est pas encore accessible depuis le contexte de la vue.

- [ ] **Step 4.3 : Mettre à jour order_confirmation dans customer/views.py**

Remplacer la fonction `order_confirmation` :

```python
def order_confirmation(request, order_id):
    from customer.services.receipt import build_whatsapp_receipt_url
    order = get_object_or_404(Order, id=order_id)
    customization = RestaurantCustomization.objects.filter(
        restaurant=order.restaurant
    ).first()

    whatsapp_url = None
    if order.customer_profile and order.customer_profile.whatsapp_opted_in:
        whatsapp_url = build_whatsapp_receipt_url(order)

    return render(request, "customer/confirmation.html", {
        "order": order,
        "restaurant": order.restaurant,
        "customization": customization,
        "whatsapp_url": whatsapp_url,
    })
```

- [ ] **Step 4.4 : Mettre à jour templates/customer/confirmation.html**

```html
{% extends 'customer/base.html' %}
{% block content %}
<div class="max-w-lg mx-auto p-4 text-center">
  <div class="text-6xl mb-4">✅</div>
  <h1 class="text-2xl font-bold text-green-600 mb-2">Commande confirmée !</h1>
  <p class="text-gray-600 mb-6">Commande n° <strong>{{ order.order_number }}</strong></p>

  <div class="bg-white rounded-xl shadow p-4 text-left mb-6">
    <h2 class="font-semibold mb-3">Détail</h2>
    {% for item in order.items.all %}
    <div class="flex justify-between text-sm py-1">
      <span>{{ item.menu_item.name }} x{{ item.quantity }}</span>
      <span>{{ item.get_total }} FCFA</span>
    </div>
    {% endfor %}
    <div class="border-t mt-2 pt-2 font-bold flex justify-between">
      <span>Total</span>
      <span>{{ order.total }} FCFA</span>
    </div>
  </div>

  {% if whatsapp_url %}
  <a href="{{ whatsapp_url }}" target="_blank"
    class="inline-block w-full bg-green-500 text-white font-semibold py-3 rounded-xl mb-3 hover:bg-green-600 transition">
    📱 Recevoir mon reçu sur WhatsApp
  </a>
  {% endif %}

  <p class="text-sm text-gray-500 mt-4">
    Votre commande est en cours de préparation. Merci !
  </p>
</div>
{% endblock %}
```

- [ ] **Step 4.5 : Lancer les tests**

```bash
python manage.py test customer.tests.OrderConfirmationWhatsAppTest -v 2
```

Expected: `Ran 2 tests ... OK`

- [ ] **Step 4.6 : Commit**

```bash
git add customer/views.py templates/customer/confirmation.html
git commit -m "feat(customer): whatsapp receipt link on order confirmation page"
```

---

## Phase B : PWA Foundation (Offline-First)

### Task 5 : Manifeste PWA

**Files:**
- Create: `static/manifest.json`
- Modify: `templates/customer/base.html`

- [ ] **Step 5.1 : Écrire le test**

```python
# customer/tests.py  (ajouter)
class PWAManifestTest(TestCase):
    def test_manifest_accessible(self):
        from django.test import Client
        c = Client()
        response = c.get("/manifest.json")
        self.assertEqual(response.status_code, 200)
        import json
        data = json.loads(response.content)
        self.assertEqual(data["name"], "OpenFood")
        self.assertIn("icons", data)
        self.assertIn("start_url", data)
```

- [ ] **Step 5.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.PWAManifestTest -v 2
```

Expected: `404` pour `/manifest.json`

- [ ] **Step 5.3 : Créer le manifeste**

Créer `static/manifest.json` :

```json
{
  "name": "OpenFood",
  "short_name": "OpenFood",
  "description": "Menu digital et commande en ligne",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#16a34a",
  "orientation": "portrait",
  "icons": [
    {
      "src": "/static/img/logo.png",
      "sizes": "192x192",
      "type": "image/png"
    },
    {
      "src": "/static/img/logo.png",
      "sizes": "512x512",
      "type": "image/png"
    }
  ]
}
```

- [ ] **Step 5.4 : Ajouter la vue manifest dans base/urls.py**

Dans `base/urls.py`, ajouter :

```python
from django.views.generic import TemplateView
from django.urls import path

# Ajouter dans urlpatterns :
path("manifest.json", TemplateView.as_view(
    template_name="manifest.json",
    content_type="application/manifest+json",
), name="manifest"),
```

Créer `templates/manifest.json` :

```json
{
  "name": "OpenFood",
  "short_name": "OpenFood",
  "description": "Menu digital et commande en ligne",
  "start_url": "/",
  "display": "standalone",
  "background_color": "#ffffff",
  "theme_color": "#16a34a",
  "orientation": "portrait",
  "icons": [
    {"src": "/static/img/logo.png", "sizes": "192x192", "type": "image/png"},
    {"src": "/static/img/logo.png", "sizes": "512x512", "type": "image/png"}
  ]
}
```

- [ ] **Step 5.5 : Lancer le test**

```bash
python manage.py test customer.tests.PWAManifestTest -v 2
```

Expected: `Ran 1 test ... OK`

- [ ] **Step 5.6 : Ajouter le lien manifest dans templates/customer/base.html**

Dans le `<head>` de `templates/customer/base.html`, ajouter :

```html
<link rel="manifest" href="/manifest.json">
<meta name="theme-color" content="#16a34a">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
```

- [ ] **Step 5.7 : Commit**

```bash
git add static/manifest.json templates/manifest.json base/urls.py templates/customer/base.html
git commit -m "feat(pwa): add PWA manifest for installable menu"
```

---

### Task 6 : Service Worker (menu offline)

**Files:**
- Create: `static/js/sw.js`
- Modify: `templates/customer/base.html`

- [ ] **Step 6.1 : Créer le Service Worker**

Créer `static/js/sw.js` :

```javascript
const CACHE_NAME = "openfood-v1";
const OFFLINE_URLS = [
  "/offline/",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(OFFLINE_URLS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(
        names
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  // Stratégie : Network First, fallback cache
  if (event.request.method !== "GET") return;

  event.respondWith(
    fetch(event.request)
      .then((response) => {
        // Mettre en cache les pages menu et les images
        if (
          response.ok &&
          (event.request.url.includes("/t/") ||
            event.request.url.includes("/static/") ||
            event.request.url.includes("/media/"))
        ) {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
        }
        return response;
      })
      .catch(() =>
        caches.match(event.request).then(
          (cached) => cached || caches.match("/offline/")
        )
      )
  );
});
```

- [ ] **Step 6.2 : Créer la page offline**

Créer `templates/customer/offline.html` :

```html
{% extends 'customer/base.html' %}
{% block content %}
<div class="max-w-lg mx-auto p-4 text-center mt-16">
  <div class="text-6xl mb-4">📶</div>
  <h1 class="text-2xl font-bold mb-2">Pas de connexion</h1>
  <p class="text-gray-500">Le menu sera disponible dès que vous retrouvez Internet.<br>Vos articles ajoutés au panier sont conservés.</p>
</div>
{% endblock %}
```

- [ ] **Step 6.3 : Ajouter la vue offline dans customer/urls.py**

Dans `customer/urls.py` :

```python
from django.shortcuts import render
# Ajouter dans urlpatterns :
path("offline/", lambda r: render(r, "customer/offline.html"), name="offline"),
```

- [ ] **Step 6.4 : Enregistrer le SW dans templates/customer/base.html**

À la fin du `<body>` de `templates/customer/base.html`, avant `</body>` :

```html
<script>
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/static/js/sw.js')
        .catch(err => console.warn('SW registration failed:', err));
    });
  }
</script>
```

- [ ] **Step 6.5 : Tester manuellement**

```bash
python manage.py runserver
```

Ouvrir `http://localhost:8000/t/<un-token-de-table>`, vérifier dans DevTools → Application → Service Workers que le SW est enregistré. Mettre le navigateur en mode Offline et recharger la page — le menu doit s'afficher depuis le cache.

- [ ] **Step 6.6 : Commit**

```bash
git add static/js/sw.js templates/customer/offline.html templates/customer/base.html customer/urls.py
git commit -m "feat(pwa): add service worker for offline menu browsing"
```

---

## Phase C : Système de Feedback Post-Repas

### Task 7 : Modèle OrderFeedback

**Files:**
- Modify: `customer/models.py`
- Create: migration

- [ ] **Step 7.1 : Écrire le test**

```python
# customer/tests.py  (ajouter)
from customer.models import CustomerProfile, OrderFeedback

class OrderFeedbackTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="o3@test.com", password="pass",
            first_name="O", last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter3", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        self.restaurant = Restaurant.objects.create(
            owner=user, name="Resto3", address="1 rue",
            phone="0100000002", email="r3@test.com",
            subscription_plan=plan,
        )
        self.order = Order.objects.create(restaurant=self.restaurant)

    def test_create_positive_feedback(self):
        feedback = OrderFeedback.objects.create(
            order=self.order,
            rating=5,
            comment="Excellent !",
        )
        self.assertTrue(feedback.is_positive)

    def test_create_negative_feedback(self):
        feedback = OrderFeedback.objects.create(
            order=self.order,
            rating=2,
            comment="Trop long",
        )
        self.assertFalse(feedback.is_positive)

    def test_feedback_unique_per_order(self):
        OrderFeedback.objects.create(order=self.order, rating=4)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            OrderFeedback.objects.create(order=self.order, rating=3)
```

- [ ] **Step 7.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.OrderFeedbackTest -v 2
```

Expected: `ImportError: cannot import name 'OrderFeedback'`

- [ ] **Step 7.3 : Ajouter OrderFeedback à customer/models.py**

Ajouter à la fin de `customer/models.py` :

```python
class OrderFeedback(models.Model):
    order = models.OneToOneField(
        'base.Order',
        on_delete=models.CASCADE,
        related_name='feedback',
    )
    rating = models.IntegerField()  # 1 à 5
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    restaurant_alerted = models.BooleanField(default=False)

    @property
    def is_positive(self):
        return self.rating >= 4

    def __str__(self):
        return f"Feedback #{self.order.id} – {self.rating}/5"
```

- [ ] **Step 7.4 : Migration**

```bash
python manage.py makemigrations customer
python manage.py migrate
```

Expected: `Applying customer.0002_orderfeedback... OK`

- [ ] **Step 7.5 : Lancer les tests**

```bash
python manage.py test customer.tests.OrderFeedbackTest -v 2
```

Expected: `Ran 3 tests ... OK`

- [ ] **Step 7.6 : Commit**

```bash
git add customer/models.py customer/migrations/
git commit -m "feat(customer): add OrderFeedback model (rating 1-5, positive >= 4)"
```

---

### Task 8 : Vue feedback + alertes restaurateur

**Files:**
- Modify: `customer/views.py` — ajouter `submit_feedback`
- Modify: `customer/urls.py`
- Create: `templates/customer/feedback.html`
- Create: `customer/services/feedback.py`
- Modify: `templates/customer/confirmation.html` — ajouter lien feedback

- [ ] **Step 8.1 : Écrire le test**

```python
# customer/tests.py  (ajouter)
class FeedbackSubmitTest(TestCase):
    def setUp(self):
        self.client_http = Client()
        user = User.objects.create_user(
            email="o4@test.com", password="pass",
            first_name="O", last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter4", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        self.restaurant = Restaurant.objects.create(
            owner=user, name="Resto4", address="1 rue",
            phone="0100000003", email="owner@example.com",
            subscription_plan=plan,
        )
        self.order = Order.objects.create(restaurant=self.restaurant)

    def test_positive_feedback_submitted(self):
        url = reverse("submit_feedback", kwargs={"order_id": self.order.id})
        response = self.client_http.post(url, {"rating": 5, "comment": "Super !"})
        self.assertEqual(OrderFeedback.objects.count(), 1)
        self.assertEqual(response.status_code, 302)

    def test_negative_feedback_alerts_owner(self):
        from unittest.mock import patch
        url = reverse("submit_feedback", kwargs={"order_id": self.order.id})
        with patch("customer.services.feedback.alert_restaurant_negative") as mock_alert:
            self.client_http.post(url, {"rating": 2, "comment": "Mauvais"})
            mock_alert.assert_called_once()
```

- [ ] **Step 8.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.FeedbackSubmitTest -v 2
```

Expected: `NoReverseMatch: Reverse for 'submit_feedback' not found`

- [ ] **Step 8.3 : Créer customer/services/feedback.py**

```python
# customer/services/feedback.py
from django.core.mail import send_mail
from django.conf import settings


def alert_restaurant_negative(feedback):
    restaurant = feedback.order.restaurant
    owner_email = restaurant.email

    if not owner_email:
        return

    send_mail(
        subject=f"⚠️ Avis négatif reçu – {restaurant.name}",
        message=(
            f"Un client a laissé un avis de {feedback.rating}/5 pour la commande "
            f"#{feedback.order.order_number}.\n\n"
            f"Commentaire : {feedback.comment or '(aucun commentaire)'}\n\n"
            f"Connectez-vous à votre tableau de bord pour gérer cet avis."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[owner_email],
        fail_silently=True,
    )
    feedback.restaurant_alerted = True
    feedback.save(update_fields=["restaurant_alerted"])
```

- [ ] **Step 8.4 : Ajouter submit_feedback dans customer/views.py**

Ajouter à la fin de `customer/views.py` :

```python
from customer.models import OrderFeedback
from customer.services.feedback import alert_restaurant_negative

def submit_feedback(request, order_id):
    order = get_object_or_404(Order, id=order_id)

    if hasattr(order, 'feedback'):
        return redirect("order_confirmation", order_id=order.id)

    if request.method == "POST":
        rating = int(request.POST.get("rating", 0))
        comment = request.POST.get("comment", "").strip()

        if 1 <= rating <= 5:
            feedback = OrderFeedback.objects.create(
                order=order,
                rating=rating,
                comment=comment,
            )
            if not feedback.is_positive:
                alert_restaurant_negative(feedback)
            return redirect("feedback_thanks", order_id=order.id)

    return render(request, "customer/feedback.html", {
        "order": order,
        "restaurant": order.restaurant,
    })


def feedback_thanks(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    return render(request, "customer/feedback_thanks.html", {
        "order": order,
        "restaurant": order.restaurant,
        "is_positive": order.feedback.is_positive if hasattr(order, 'feedback') else False,
    })
```

- [ ] **Step 8.5 : Mettre à jour customer/urls.py**

Ajouter dans `customer/urls.py` :

```python
path("feedback/<int:order_id>/", views.submit_feedback, name="submit_feedback"),
path("feedback/<int:order_id>/merci/", views.feedback_thanks, name="feedback_thanks"),
```

- [ ] **Step 8.6 : Créer templates/customer/feedback.html**

```html
{% extends 'customer/base.html' %}
{% block content %}
<div class="max-w-lg mx-auto p-4">
  <h1 class="text-xl font-bold text-center mb-6">Comment s'est passé votre repas ?</h1>
  <form method="POST">
    {% csrf_token %}
    <!-- Étoiles -->
    <div class="flex justify-center gap-3 text-4xl mb-6" id="stars">
      {% for i in "12345" %}
      <label class="cursor-pointer">
        <input type="radio" name="rating" value="{{ forloop.counter }}" class="hidden star-radio"
          {% if forloop.counter == 5 %}checked{% endif %}>
        <span class="star text-gray-300 hover:text-yellow-400 transition" data-value="{{ forloop.counter }}">★</span>
      </label>
      {% endfor %}
    </div>
    <div class="mb-4">
      <textarea name="comment" rows="3" placeholder="Un commentaire ? (optionnel)"
        class="w-full border rounded-xl px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-500"></textarea>
    </div>
    <button type="submit"
      class="w-full bg-green-600 text-white font-semibold py-3 rounded-xl hover:bg-green-700 transition">
      Envoyer mon avis
    </button>
  </form>
</div>
<script>
  document.querySelectorAll('.star').forEach(star => {
    star.addEventListener('click', () => {
      const val = +star.dataset.value;
      document.querySelectorAll('.star').forEach((s, i) => {
        s.classList.toggle('text-yellow-400', i < val);
        s.classList.toggle('text-gray-300', i >= val);
      });
      document.querySelectorAll('.star-radio')[val - 1].checked = true;
    });
  });
  // Init: 5 étoiles jaunes par défaut
  document.querySelectorAll('.star').forEach(s => s.classList.add('text-yellow-400'));
</script>
{% endblock %}
```

- [ ] **Step 8.7 : Créer templates/customer/feedback_thanks.html**

```html
{% extends 'customer/base.html' %}
{% block content %}
<div class="max-w-lg mx-auto p-4 text-center mt-16">
  {% if is_positive %}
  <div class="text-6xl mb-4">⭐</div>
  <h1 class="text-2xl font-bold text-green-600 mb-2">Merci pour votre avis !</h1>
  <p class="text-gray-600 mb-6">Vous avez adoré ? Partagez votre expérience !</p>
  <a href="https://maps.google.com" target="_blank"
    class="inline-block bg-blue-500 text-white px-6 py-3 rounded-xl font-semibold hover:bg-blue-600 transition">
    Laisser un avis Google
  </a>
  {% else %}
  <div class="text-6xl mb-4">🙏</div>
  <h1 class="text-2xl font-bold mb-2">Merci pour votre retour</h1>
  <p class="text-gray-500">Nous en prenons bonne note pour nous améliorer.</p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 8.8 : Ajouter le lien feedback dans templates/customer/confirmation.html**

Après le bloc du total de commande, ajouter :

```html
<div class="mt-6 border-t pt-4">
  <p class="text-sm text-gray-600 mb-3">Comment s'est passé votre repas ?</p>
  <a href="{% url 'submit_feedback' order.id %}"
    class="inline-block w-full bg-yellow-400 text-gray-900 font-semibold py-3 rounded-xl text-center hover:bg-yellow-500 transition">
    ⭐ Donner mon avis
  </a>
</div>
```

- [ ] **Step 8.9 : Lancer les tests**

```bash
python manage.py test customer.tests.FeedbackSubmitTest -v 2
```

Expected: `Ran 2 tests ... OK`

- [ ] **Step 8.10 : Commit**

```bash
git add customer/views.py customer/urls.py customer/services/feedback.py templates/customer/
git commit -m "feat(customer): post-meal feedback with owner alert on negative reviews"
```

---

## Phase D : Re-engagement Client & Parrainage

### Task 9 : Commande de re-engagement automatisé

**Files:**
- Create: `customer/management/commands/send_reengagement.py`
- Create: `customer/services/campaigns.py`
- Create: `templates/email/reengagement.txt`

- [ ] **Step 9.1 : Écrire le test**

```python
# customer/tests.py  (ajouter)
from unittest.mock import patch

class ReEngagementCommandTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="o5@test.com", password="pass",
            first_name="O", last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter5", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        self.restaurant = Restaurant.objects.create(
            owner=user, name="Resto5", address="1 rue",
            phone="0100000004", email="r5@test.com",
            subscription_plan=plan,
        )

    def test_inactive_customers_detected(self):
        from django.utils import timezone
        from datetime import timedelta
        from customer.services.campaigns import get_inactive_customers

        # Client inactif depuis 30 jours
        inactive = CustomerProfile.objects.create(
            phone="0600000001",
            email="inactive@test.com",
            email_opted_in=True,
            last_visit=timezone.now() - timedelta(days=35),
        )
        Order.objects.create(
            restaurant=self.restaurant,
            customer_profile=inactive,
        )

        # Client actif récent
        active = CustomerProfile.objects.create(
            phone="0600000002",
            email="active@test.com",
            email_opted_in=True,
            last_visit=timezone.now() - timedelta(days=5),
        )
        Order.objects.create(
            restaurant=self.restaurant,
            customer_profile=active,
        )

        inactive_list = get_inactive_customers(self.restaurant, days=30)
        phones = [c.phone for c in inactive_list]
        self.assertIn("0600000001", phones)
        self.assertNotIn("0600000002", phones)

    def test_reengagement_email_sent(self):
        from django.utils import timezone
        from datetime import timedelta
        from customer.services.campaigns import send_reengagement_email

        profile = CustomerProfile.objects.create(
            phone="0600000003",
            email="re@test.com",
            email_opted_in=True,
            first_name="Alice",
            last_visit=timezone.now() - timedelta(days=35),
        )

        with patch("django.core.mail.send_mail") as mock_send:
            send_reengagement_email(profile, self.restaurant)
            mock_send.assert_called_once()
            args = mock_send.call_args
            self.assertIn("Alice", args[1]["message"])
```

- [ ] **Step 9.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.ReEngagementCommandTest -v 2
```

Expected: `ImportError: cannot import name 'get_inactive_customers'`

- [ ] **Step 9.3 : Créer customer/services/campaigns.py**

```python
# customer/services/campaigns.py
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta


def get_inactive_customers(restaurant, days=30):
    cutoff = timezone.now() - timedelta(days=days)
    return (
        restaurant.orders
        .filter(
            customer_profile__isnull=False,
            customer_profile__email_opted_in=True,
            customer_profile__email__gt="",
            customer_profile__last_visit__lt=cutoff,
        )
        .values_list("customer_profile", flat=True)
        .distinct()
        .order_by()
        .__class__._default_manager.filter(
            pk__in=restaurant.orders
            .filter(
                customer_profile__isnull=False,
                customer_profile__email_opted_in=True,
                customer_profile__last_visit__lt=cutoff,
            )
            .values_list("customer_profile__pk", flat=True)
            .distinct()
        )
    )


def get_inactive_customers(restaurant, days=30):
    from customer.models import CustomerProfile
    cutoff = timezone.now() - timedelta(days=days)
    profile_ids = (
        restaurant.orders
        .filter(
            customer_profile__isnull=False,
            customer_profile__email_opted_in=True,
            customer_profile__email__gt="",
            customer_profile__last_visit__lt=cutoff,
        )
        .values_list("customer_profile__pk", flat=True)
        .distinct()
    )
    return CustomerProfile.objects.filter(pk__in=profile_ids)


def send_reengagement_email(profile, restaurant):
    if not profile.email:
        return

    message = (
        f"Bonjour {profile.first_name or 'cher client'},\n\n"
        f"Vous nous manquez chez {restaurant.name} ! 🍽️\n\n"
        f"Votre dernier passage remonte à un moment et nous aimerions vous revoir.\n"
        f"Scannez à nouveau notre QR code à votre prochaine visite et profitez d'une"
        f" surprise !\n\n"
        f"À très bientôt,\nL'équipe {restaurant.name}"
    )

    send_mail(
        subject=f"Vous nous manquez, {profile.first_name or ''} ! – {restaurant.name}",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[profile.email],
        fail_silently=True,
    )
```

- [ ] **Step 9.4 : Créer la management command**

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/customer/management/commands"
touch "/home/jey/Documents/projet /OpendFood/customer/management/__init__.py"
touch "/home/jey/Documents/projet /OpendFood/customer/management/commands/__init__.py"
```

Créer `customer/management/commands/send_reengagement.py` :

```python
from django.core.management.base import BaseCommand
from base.models import Restaurant
from customer.services.campaigns import get_inactive_customers, send_reengagement_email


class Command(BaseCommand):
    help = "Envoie des emails de re-engagement aux clients inactifs depuis N jours"

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30,
                            help="Nombre de jours d'inactivité (défaut: 30)")
        parser.add_argument("--restaurant-id", type=int, default=None,
                            help="Limiter à un restaurant (optionnel)")

    def handle(self, *args, **options):
        days = options["days"]
        restaurant_id = options.get("restaurant_id")

        restaurants = Restaurant.objects.filter(is_active=True)
        if restaurant_id:
            restaurants = restaurants.filter(pk=restaurant_id)

        total_sent = 0
        for restaurant in restaurants:
            inactive = get_inactive_customers(restaurant, days=days)
            for profile in inactive:
                send_reengagement_email(profile, restaurant)
                total_sent += 1
                self.stdout.write(f"  → Email envoyé à {profile.email}")

        self.stdout.write(self.style.SUCCESS(
            f"Re-engagement terminé : {total_sent} email(s) envoyé(s)."
        ))
```

- [ ] **Step 9.5 : Lancer les tests**

```bash
python manage.py test customer.tests.ReEngagementCommandTest -v 2
```

Expected: `Ran 2 tests ... OK`

- [ ] **Step 9.6 : Tester la commande manuellement**

```bash
python manage.py send_reengagement --days 30 --help
python manage.py send_reengagement --days 30
```

Expected: Affiche le nombre d'emails envoyés.

- [ ] **Step 9.7 : Commit**

```bash
git add customer/management/ customer/services/campaigns.py
git commit -m "feat(customer): re-engagement management command for inactive customers"
```

> **Note cron :** Ajouter `0 9 * * 1 cd /path/to/project && python manage.py send_reengagement --days 30` dans crontab pour exécution hebdomadaire le lundi à 9h.

---

### Task 10 : Programme de parrainage

**Files:**
- Modify: `customer/models.py` — ajouter ReferralCode
- Create: migration
- Modify: `customer/views.py` — générer et suivre les liens de parrainage
- Modify: `customer/urls.py`
- Create: `templates/customer/referral.html`

- [ ] **Step 10.1 : Écrire le test**

```python
# customer/tests.py  (ajouter)
from customer.models import CustomerProfile, ReferralCode

class ReferralCodeTest(TestCase):
    def test_create_referral_code_for_profile(self):
        profile = CustomerProfile.objects.create(phone="0700000001")
        code = ReferralCode.objects.create(owner=profile)
        self.assertEqual(len(code.code), 8)
        self.assertTrue(code.code.isupper())

    def test_referral_code_unique(self):
        profile = CustomerProfile.objects.create(phone="0700000002")
        code = ReferralCode.generate_for(profile)
        self.assertIsNotNone(code.code)

    def test_get_or_create_referral(self):
        profile = CustomerProfile.objects.create(phone="0700000003")
        code1 = ReferralCode.generate_for(profile)
        code2 = ReferralCode.generate_for(profile)
        self.assertEqual(code1.pk, code2.pk)
```

- [ ] **Step 10.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.ReferralCodeTest -v 2
```

Expected: `ImportError: cannot import name 'ReferralCode'`

- [ ] **Step 10.3 : Ajouter ReferralCode à customer/models.py**

Ajouter à la fin de `customer/models.py` :

```python
import random
import string


class ReferralCode(models.Model):
    owner = models.OneToOneField(
        CustomerProfile,
        on_delete=models.CASCADE,
        related_name='referral_code',
    )
    code = models.CharField(max_length=8, unique=True)
    uses = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    @classmethod
    def generate_for(cls, profile):
        obj, created = cls.objects.get_or_create(owner=profile)
        if created:
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            while cls.objects.filter(code=code).exists():
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            obj.code = code
            obj.save()
        return obj

    def __str__(self):
        return f"{self.code} ({self.owner.phone})"
```

- [ ] **Step 10.4 : Migration**

```bash
python manage.py makemigrations customer
python manage.py migrate
```

Expected: `Applying customer.0003_referralcode... OK`

- [ ] **Step 10.5 : Ajouter la vue referral dans customer/views.py**

```python
from customer.models import ReferralCode

def referral_page(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    profile = order.customer_profile

    if not profile:
        return redirect("order_confirmation", order_id=order_id)

    ref_code = ReferralCode.generate_for(profile)
    restaurant = order.restaurant

    referral_url = (
        f"{request.scheme}://{request.get_host()}"
        f"/t/{order.table.token}?ref={ref_code.code}"
        if order.table else "#"
    )

    whatsapp_message = (
        f"J'ai mangé chez {restaurant.name} et c'était top ! 🍽️\n"
        f"Scanne ce QR code avec mon code promo {ref_code.code} pour ta prochaine visite."
    )
    import urllib.parse
    whatsapp_url = f"https://wa.me/?text={urllib.parse.quote(whatsapp_message)}"

    return render(request, "customer/referral.html", {
        "order": order,
        "restaurant": restaurant,
        "ref_code": ref_code,
        "referral_url": referral_url,
        "whatsapp_url": whatsapp_url,
    })
```

- [ ] **Step 10.6 : Ajouter la route dans customer/urls.py**

```python
path("referral/<int:order_id>/", views.referral_page, name="referral_page"),
```

- [ ] **Step 10.7 : Créer templates/customer/referral.html**

```html
{% extends 'customer/base.html' %}
{% block content %}
<div class="max-w-lg mx-auto p-4 text-center">
  <div class="text-5xl mb-4">🎁</div>
  <h1 class="text-2xl font-bold mb-2">Parrainez vos amis !</h1>
  <p class="text-gray-600 mb-6">
    Partagez votre code à un ami. Lorsqu'il vient chez {{ restaurant.name }}, vous recevez tous les deux une récompense.
  </p>

  <div class="bg-green-50 border-2 border-green-500 rounded-xl p-4 mb-6">
    <p class="text-sm text-gray-500 mb-1">Votre code de parrainage</p>
    <p class="text-4xl font-black text-green-600 tracking-widest">{{ ref_code.code }}</p>
  </div>

  <a href="{{ whatsapp_url }}" target="_blank"
    class="block w-full bg-green-500 text-white font-semibold py-3 rounded-xl mb-3 hover:bg-green-600 transition">
    📲 Partager sur WhatsApp
  </a>

  <button onclick="navigator.clipboard.writeText('{{ referral_url }}')"
    class="block w-full border border-gray-300 text-gray-700 font-semibold py-3 rounded-xl hover:bg-gray-50 transition">
    🔗 Copier le lien
  </button>
</div>
{% endblock %}
```

- [ ] **Step 10.8 : Ajouter le lien parrainage dans templates/customer/feedback_thanks.html**

Dans le bloc positif de `feedback_thanks.html`, après le bouton Google :

```html
<div class="mt-4">
  <a href="{% url 'referral_page' order.id %}"
    class="inline-block w-full border border-green-500 text-green-600 font-semibold py-3 rounded-xl hover:bg-green-50 transition">
    🎁 Parrainer un ami
  </a>
</div>
```

- [ ] **Step 10.9 : Lancer les tests**

```bash
python manage.py test customer.tests.ReferralCodeTest -v 2
```

Expected: `Ran 3 tests ... OK`

- [ ] **Step 10.10 : Commit**

```bash
git add customer/models.py customer/views.py customer/urls.py customer/migrations/ templates/customer/
git commit -m "feat(customer): referral program with unique code and WhatsApp sharing"
```

---

## Phase E : Upselling Intelligent

### Task 11 : Suggestions d'accompagnements dans le panier

**Files:**
- Modify: `customer/views.py` — enrichir `client_menu` avec suggestions upsell
- Modify: `templates/customer/cart_sidebar.html` — afficher les suggestions

- [ ] **Step 11.1 : Écrire le test**

```python
# customer/tests.py  (ajouter)
from customer.services.upsell import get_upsell_suggestions
from base.models import Category, MenuItem

class UpsellTest(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="o6@test.com", password="pass",
            first_name="O", last_name="W",
        )
        plan = SubscriptionPlan.objects.create(
            name="Starter6", plan_type="starter", price=0,
            max_menu_items=50, max_tables=10,
        )
        self.restaurant = Restaurant.objects.create(
            owner=user, name="Resto6", address="1 rue",
            phone="0100000005", email="r6@test.com",
            subscription_plan=plan,
        )
        self.cat_plats = Category.objects.create(
            restaurant=self.restaurant, name="Plats"
        )
        self.cat_boissons = Category.objects.create(
            restaurant=self.restaurant, name="Boissons"
        )
        self.burger = MenuItem.objects.create(
            restaurant=self.restaurant, category=self.cat_plats,
            name="Burger", price=5, is_available=True,
        )
        self.coca = MenuItem.objects.create(
            restaurant=self.restaurant, category=self.cat_boissons,
            name="Coca", price=2, is_available=True,
        )

    def test_upsell_returns_items_from_other_categories(self):
        cart_item_ids = [self.burger.id]
        suggestions = get_upsell_suggestions(self.restaurant, cart_item_ids)
        suggestion_ids = [s.id for s in suggestions]
        self.assertIn(self.coca.id, suggestion_ids)
        self.assertNotIn(self.burger.id, suggestion_ids)

    def test_upsell_returns_max_3_items(self):
        for i in range(5):
            MenuItem.objects.create(
                restaurant=self.restaurant, category=self.cat_boissons,
                name=f"Boisson {i}", price=2, is_available=True,
            )
        suggestions = get_upsell_suggestions(self.restaurant, [self.burger.id])
        self.assertLessEqual(len(suggestions), 3)
```

- [ ] **Step 11.2 : Lancer le test pour vérifier qu'il échoue**

```bash
python manage.py test customer.tests.UpsellTest -v 2
```

Expected: `ImportError: cannot import name 'get_upsell_suggestions'`

- [ ] **Step 11.3 : Créer customer/services/upsell.py**

```python
# customer/services/upsell.py
from base.models import MenuItem, Category


def get_upsell_suggestions(restaurant, cart_item_ids, max_suggestions=3):
    if not cart_item_ids:
        return []

    cart_categories = (
        MenuItem.objects.filter(pk__in=cart_item_ids)
        .values_list("category_id", flat=True)
        .distinct()
    )

    suggestions = (
        MenuItem.objects.filter(
            restaurant=restaurant,
            is_available=True,
        )
        .exclude(pk__in=cart_item_ids)
        .exclude(category_id__in=cart_categories)
        .order_by("?")[:max_suggestions]
    )

    return list(suggestions)
```

- [ ] **Step 11.4 : Enrichir l'API cart pour inclure les suggestions**

Dans `customer/views.py`, mettre à jour `update_cart` pour retourner les suggestions :

```python
from customer.services.upsell import get_upsell_suggestions

# Dans update_cart, avant return JsonResponse, ajouter :
cart_item_ids = [int(k) for k in cart.keys()]
suggestions = get_upsell_suggestions(restaurant, cart_item_ids)
suggestions_data = [
    {
        "id": s.id,
        "name": s.name,
        "price": str(s.discount_price or s.price),
        "image": s.image.url if s.image else None,
        "category": s.category.name,
    }
    for s in suggestions
]

return JsonResponse({
    "success": True,
    "total": total,
    "count": len(cart),
    "upsell": suggestions_data,
})
```

- [ ] **Step 11.5 : Afficher les suggestions dans le template cart**

Dans `templates/customer/cart_sidebar.html`, ajouter après la liste des articles du panier :

```html
<div id="upsell-zone" class="mt-4 hidden">
  <p class="text-sm font-semibold text-gray-600 mb-2">Vous aimerez aussi :</p>
  <div id="upsell-items" class="space-y-2"></div>
</div>

<script>
function renderUpsell(items) {
  const zone = document.getElementById('upsell-zone');
  const container = document.getElementById('upsell-items');
  if (!items || items.length === 0) { zone.classList.add('hidden'); return; }

  zone.classList.remove('hidden');
  container.innerHTML = items.map(item => `
    <div class="flex items-center justify-between bg-gray-50 rounded-lg p-2">
      <div class="flex items-center gap-2">
        ${item.image ? `<img src="${item.image}" class="w-10 h-10 rounded object-cover">` : ''}
        <div>
          <p class="text-sm font-medium">${item.name}</p>
          <p class="text-xs text-gray-500">${item.price} FCFA</p>
        </div>
      </div>
      <button onclick="addToCartUpsell(${item.id})"
        class="text-xs bg-green-600 text-white px-2 py-1 rounded hover:bg-green-700">
        + Ajouter
      </button>
    </div>
  `).join('');
}

// Appeler renderUpsell(data.upsell) après chaque réponse de update_cart
// (intégrer dans le JS existant du cart)
</script>
```

- [ ] **Step 11.6 : Lancer les tests**

```bash
python manage.py test customer.tests.UpsellTest -v 2
```

Expected: `Ran 2 tests ... OK`

- [ ] **Step 11.7 : Lancer tous les tests**

```bash
python manage.py test customer base -v 2
```

Expected: Tous les tests passent.

- [ ] **Step 11.8 : Commit final**

```bash
git add customer/services/upsell.py customer/views.py templates/customer/cart_sidebar.html
git commit -m "feat(customer): intelligent upsell suggestions from other categories in cart"
```

---

## Récapitulatif des fichiers modifiés/créés

| Fichier | Action | Phase |
|---------|--------|-------|
| `customer/models.py` | Create: CustomerProfile, OrderFeedback, ReferralCode | A, C, D |
| `customer/forms.py` | Create: CustomerInfoForm | A |
| `customer/views.py` | Modify: checkout, order_confirmation + add submit_feedback, referral_page | A, C, D, E |
| `customer/urls.py` | Modify: ajouter routes feedback, referral, offline | B, C, D |
| `customer/services/receipt.py` | Create: email + WhatsApp receipt | A |
| `customer/services/feedback.py` | Create: alert_restaurant_negative | C |
| `customer/services/campaigns.py` | Create: get_inactive_customers, send_reengagement_email | D |
| `customer/services/upsell.py` | Create: get_upsell_suggestions | E |
| `customer/management/commands/send_reengagement.py` | Create: management command | D |
| `base/models.py` | Modify: Order.customer_profile FK | A |
| `static/js/sw.js` | Create: service worker | B |
| `static/manifest.json` | Create: PWA manifest | B |
| `templates/customer/checkout.html` | Modify: customer info form | A |
| `templates/customer/confirmation.html` | Modify: WhatsApp receipt + feedback link | A, C |
| `templates/customer/feedback.html` | Create: star rating form | C |
| `templates/customer/feedback_thanks.html` | Create: positive/negative thank you | C |
| `templates/customer/referral.html` | Create: referral share page | D |
| `templates/customer/offline.html` | Create: offline fallback | B |
| `templates/customer/base.html` | Modify: manifest link + SW registration | B |
| `templates/manifest.json` | Create: PWA manifest template | B |

---

## Tests à exécuter en fin de chaque phase

```bash
# Phase A
python manage.py test customer.tests.CustomerProfileTest customer.tests.CheckoutCaptureTest customer.tests.OrderConfirmationWhatsAppTest base.tests.OrderCustomerLinkTest

# Phase B
python manage.py test customer.tests.PWAManifestTest

# Phase C
python manage.py test customer.tests.OrderFeedbackTest customer.tests.FeedbackSubmitTest

# Phase D
python manage.py test customer.tests.ReEngagementCommandTest customer.tests.ReferralCodeTest

# Phase E
python manage.py test customer.tests.UpsellTest

# Tous les tests
python manage.py test customer base
```

---

## Vérification du spec

| Exigence spec | Couvert par |
|---------------|-------------|
| Ticket digital WhatsApp/Email | Task 3 (capture) + Task 4 (confirmation) + receipt.py |
| Relances automatisées | Task 9 (campaigns.py + management command) |
| Programme de parrainage | Task 10 (ReferralCode + referral_page) |
| Feedback Loop (positif → partager, négatif → alerte privée) | Task 7 + Task 8 |
| Mode Offline-First (Service Worker) | Task 6 |
| PWA installable | Task 5 (manifest) |
| Upselling intelligent | Task 11 |
| Gestion stocks dynamique | Déjà existant (`MenuItem.is_available` + `change_menu_status`) |
