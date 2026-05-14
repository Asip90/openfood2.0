# Order Notifications — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Déclencher une sonnerie + une notification push système dès qu'une nouvelle commande arrive, même si l'onglet dashboard est en arrière-plan ou fermé, et afficher un badge (1) sur le lien Commandes dans la sidebar et le bottom nav.

**Architecture:** Le serveur envoie un Web Push (VAPID / pywebpush) au navigateur du restaurateur immédiatement après la création d'une commande dans `checkout`. Le Service Worker reçoit l'événement `push`, affiche la notification OS et diffuse un message via `postMessage` aux onglets ouverts. Les onglets ouverts jouent le son et incrémentent le badge de notification en temps réel. Le badge est stocké dans l'état Alpine de `admin/base.html` et se réinitialise quand l'utilisateur visite la page Commandes.

**Tech Stack:** Django 6, pywebpush (VAPID), Web Push API, Service Worker, BroadcastChannel, Alpine.js 3.14, Tailwind CSS, existing `static/sounds/new-order.mp3`.

---

## Fichiers concernés

| Fichier | Action | Rôle |
|---------|--------|------|
| `requirements.txt` | Modifier | Ajouter pywebpush |
| `main/settings.py` | Modifier | Lire VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY, VAPID_EMAIL depuis `.env` |
| `.env` | Modifier | Stocker les clés VAPID générées |
| `base/models.py` | Modifier | Ajouter modèle `PushSubscription` |
| `base/migrations/XXXX_add_push_subscription.py` | Créer | Migration |
| `base/push_utils.py` | Créer | `send_push_to_restaurant(restaurant, title, body, url)` |
| `base/views.py` | Modifier | Vues `save_push_subscription` + `get_vapid_public_key` ; ajouter `pending_count` à `check_new_orders` |
| `base/urls.py` | Modifier | Ajouter 2 URLs push |
| `customer/views.py` | Modifier | Appeler `send_push_to_restaurant` après création de commande |
| `static/js/sw.js` | Modifier | Gérer événements `push` et `notificationclick` |
| `templates/admin_user/base.html` | Modifier | Enregistrer SW + push subscription, état Alpine `notifCount`, badge dans header |
| `templates/admin_user/sidebar.html` | Modifier | Badge rouge sur lien Commandes |
| `templates/admin_user/orders/list_orders.html` | Modifier | Réinitialiser badge au chargement |
| `templates/admin_user/index.html` | Modifier | Réinitialiser badge au chargement |

---

### Task 1 — Installer pywebpush et générer les clés VAPID

**Fichiers :** `requirements.txt`, `main/settings.py`, `.env`

- [ ] **Step 1 : Ajouter pywebpush à requirements.txt**

Ouvrir `requirements.txt` et ajouter à la fin :

```
pywebpush==2.0.0
```

- [ ] **Step 2 : Installer**

```bash
cd "/home/jey/Documents/projet /OpendFood" && pip install pywebpush==2.0.0
```

Résultat attendu : `Successfully installed pywebpush-2.0.0 ...`

- [ ] **Step 3 : Générer les clés VAPID**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python -c "
from py_vapid import Vapid
v = Vapid()
v.generate_keys()
print('VAPID_PUBLIC_KEY=', v.public_key.decode())
print('VAPID_PRIVATE_KEY=', v.private_key.decode())
"
```

Copier les deux valeurs affichées.

- [ ] **Step 4 : Ajouter les clés dans `.env`**

Ouvrir `.env` et ajouter (remplacer les valeurs par celles générées à l'étape précédente) :

```env
VAPID_PUBLIC_KEY=BExempleClePub...
VAPID_PRIVATE_KEY=ExemplePrivKey...
VAPID_EMAIL=jeremiebodjrenou1@gmail.com
```

- [ ] **Step 5 : Lire les clés dans `main/settings.py`**

Ouvrir `main/settings.py`. Après la ligne `FEDAPAY_SECRET_KEY = ...`, ajouter :

```python
VAPID_PUBLIC_KEY = os.environ.get('VAPID_PUBLIC_KEY', '')
VAPID_PRIVATE_KEY = os.environ.get('VAPID_PRIVATE_KEY', '')
VAPID_EMAIL = os.environ.get('VAPID_EMAIL', 'admin@example.com')
```

- [ ] **Step 6 : Vérifier le chargement**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python -c "
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'main.settings')
django.setup()
from django.conf import settings
print('PUB:', settings.VAPID_PUBLIC_KEY[:20])
print('PRIV:', settings.VAPID_PRIVATE_KEY[:10])
"
```

Résultat attendu : les deux clés s'affichent (non vides).

- [ ] **Step 7 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add requirements.txt main/settings.py && git commit -m "feat: add pywebpush + VAPID config"
```

---

### Task 2 — Modèle PushSubscription + migration

**Fichiers :** `base/models.py`

- [ ] **Step 1 : Ajouter le modèle à `base/models.py`**

Ouvrir `base/models.py`. À la fin du fichier, avant la dernière ligne (si vide) ou en fin de fichier, ajouter :

```python
class PushSubscription(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name="push_subscriptions"
    )
    endpoint = models.TextField(unique=True)
    p256dh = models.TextField()
    auth = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"PushSub {self.restaurant.name} — {self.endpoint[:40]}"
```

- [ ] **Step 2 : Créer la migration**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py makemigrations base --name add_push_subscription
```

Résultat attendu : `Migrations for 'base': base/migrations/XXXX_add_push_subscription.py`

- [ ] **Step 3 : Appliquer la migration**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py migrate
```

Résultat attendu : `Applying base.XXXX_add_push_subscription... OK`

- [ ] **Step 4 : Vérifier**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add base/models.py base/migrations/ && git commit -m "feat: add PushSubscription model"
```

---

### Task 3 — Utilitaire push + vues Django

**Fichiers :** `base/push_utils.py` (créer), `base/views.py`, `base/urls.py`

- [ ] **Step 1 : Créer `base/push_utils.py`**

```python
import json
from pywebpush import webpush, WebPushException
from django.conf import settings
from base.models import PushSubscription


def send_push_to_restaurant(restaurant, title, body, url="/orders/"):
    """Send a Web Push notification to all subscriptions of a restaurant."""
    subscriptions = PushSubscription.objects.filter(restaurant=restaurant)
    payload = json.dumps({"title": title, "body": body, "url": url})

    for sub in subscriptions:
        try:
            webpush(
                subscription_info={
                    "endpoint": sub.endpoint,
                    "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                },
                data=payload,
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={"sub": f"mailto:{settings.VAPID_EMAIL}"},
            )
        except WebPushException as e:
            if e.response is not None and e.response.status_code in (404, 410):
                sub.delete()
        except Exception:
            pass
```

- [ ] **Step 2 : Ajouter deux vues dans `base/views.py`**

Ouvrir `base/views.py`. Ajouter ces imports en haut si pas déjà présents :

```python
from django.conf import settings
```

Puis ajouter les deux vues à la fin du fichier (avant la dernière ligne ou à la fin) :

```python
@login_required
@require_GET
def get_vapid_public_key(request):
    return JsonResponse({"publicKey": settings.VAPID_PUBLIC_KEY})


@login_required
@csrf_exempt
def save_push_subscription(request):
    if request.method != "POST":
        return JsonResponse({"success": False}, status=405)

    restaurant, role = get_user_restaurant(request.user)
    if not restaurant:
        return JsonResponse({"success": False, "error": "No restaurant"}, status=400)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    endpoint = data.get("endpoint", "").strip()
    p256dh = data.get("keys", {}).get("p256dh", "").strip()
    auth = data.get("keys", {}).get("auth", "").strip()

    if not endpoint or not p256dh or not auth:
        return JsonResponse({"success": False, "error": "Missing fields"}, status=400)

    PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={"restaurant": restaurant, "p256dh": p256dh, "auth": auth},
    )
    return JsonResponse({"success": True})
```

- [ ] **Step 3 : Ajouter les imports manquants dans `base/views.py`**

En haut de `base/views.py`, vérifier/ajouter :

```python
import json
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from base.models import PushSubscription
```

- [ ] **Step 4 : Ajouter les URLs dans `base/urls.py`**

Ouvrir `base/urls.py`. Ajouter dans `urlpatterns` :

```python
# Push notifications
path("push/vapid-public-key/", get_vapid_public_key, name="vapid_public_key"),
path("push/subscribe/", save_push_subscription, name="save_push_subscription"),
```

- [ ] **Step 5 : Ajouter `pending_count` dans `check_new_orders`**

Ouvrir `base/views.py`. Dans la vue `check_new_orders`, remplacer la réponse finale :

```python
    return JsonResponse(data)
```

Par :

```python
    pending_count = Order.objects.filter(
        restaurant=restaurant, status="pending"
    ).count()
    data["pending_count"] = pending_count
    return JsonResponse(data)
```

- [ ] **Step 6 : Vérifier**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 7 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add base/push_utils.py base/views.py base/urls.py && git commit -m "feat: add push subscription views and utility"
```

---

### Task 4 — Mettre à jour le Service Worker

**Fichier :** `static/js/sw.js`

- [ ] **Step 1 : Remplacer entièrement `static/js/sw.js`**

```javascript
// Open Food PWA Service Worker
const CACHE_NAME = 'openfood-v2';
const STATIC_ASSETS = [
  '/static/sounds/new-order.mp3',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS).catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    )
  );
  self.clients.claim();
});

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  if (event.request.url.includes('/api/') || event.request.url.includes('/admin/')) return;

  if (event.request.url.includes('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(c => c.put(event.request, clone));
          return resp;
        });
      })
    );
  }
});

// ── Push notifications ──────────────────────────────────────
self.addEventListener('push', event => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch(e) {}

  const title = data.title || 'Nouvelle commande';
  const options = {
    body: data.body || 'Une nouvelle commande vient d\'être passée.',
    icon: '/static/logo/logo_open_food.png',
    badge: '/static/logo/logo_open_food.png',
    tag: 'new-order',
    renotify: true,
    requireInteraction: false,
    data: { url: data.url || '/orders/' },
  };

  event.waitUntil(
    Promise.all([
      self.registration.showNotification(title, options),
      // Notify all open tabs so they can play sound and update badge
      self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
        clients.forEach(client => client.postMessage({ type: 'NEW_ORDER', ...data }));
      }),
    ])
  );
});

self.addEventListener('notificationclick', event => {
  event.notification.close();
  const targetUrl = (event.notification.data && event.notification.data.url) || '/orders/';

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(clients => {
      // Focus an existing tab if possible
      for (const client of clients) {
        if (client.url.includes('/orders/') && 'focus' in client) {
          return client.focus();
        }
      }
      // Otherwise navigate first available tab or open a new window
      if (clients[0] && 'navigate' in clients[0]) {
        return clients[0].navigate(targetUrl).then(c => c && c.focus());
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
```

- [ ] **Step 2 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add static/js/sw.js && git commit -m "feat: service worker handles push events and notification clicks"
```

---

### Task 5 — Enregistrement SW + subscription push dans admin/base.html

**Fichier :** `templates/admin_user/base.html`

- [ ] **Step 1 : Étendre l'état Alpine du body**

Dans `templates/admin_user/base.html`, remplacer :

```html
<body class="font-sans bg-slate-50 h-full antialiased overflow-x-hidden" x-data="{ sidebarOpen: true }">
```

Par :

```html
<body class="font-sans bg-slate-50 h-full antialiased overflow-x-hidden"
      x-data="{ sidebarOpen: true, notifCount: 0 }"
      @reset-notif.window="notifCount = 0">
```

- [ ] **Step 2 : Ajouter l'enregistrement SW + push subscription dans `{% block extra_js %}` en bas de base.html**

Juste avant `</body>` (après `{% block extra_js %}{% endblock %}`), ajouter un bloc script permanent (en dehors du block extra_js pour qu'il soit toujours présent) :

```html
<script>
(function() {
  const VAPID_PUBLIC_KEY = '{{ VAPID_PUBLIC_KEY|default:"" }}';
  const SUBSCRIBE_URL = '{% url "save_push_subscription" %}';
  const CSRF = '{{ csrf_token }}';

  if (!('serviceWorker' in navigator) || !('PushManager' in window) || !VAPID_PUBLIC_KEY) return;

  function urlBase64ToUint8Array(base64String) {
    const padding = '='.repeat((4 - base64String.length % 4) % 4);
    const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    const raw = atob(base64);
    return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
  }

  async function subscribePush(registration) {
    try {
      let sub = await registration.pushManager.getSubscription();
      if (!sub) {
        sub = await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
        });
      }
      const subJson = sub.toJSON();
      await fetch(SUBSCRIBE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CSRF },
        body: JSON.stringify(subJson),
      });
    } catch(e) {}
  }

  navigator.serviceWorker.register('/static/js/sw.js').then(reg => {
    // Ask push permission only on user gesture — we request on first load quietly
    if (Notification.permission === 'granted') {
      subscribePush(reg);
    } else if (Notification.permission !== 'denied') {
      Notification.requestPermission().then(p => {
        if (p === 'granted') subscribePush(reg);
      });
    }
  });

  // Listen for NEW_ORDER messages from SW (push received while tab is open)
  navigator.serviceWorker.addEventListener('message', event => {
    if (event.data && event.data.type === 'NEW_ORDER') {
      // Play sound
      const audio = new Audio('/static/sounds/new-order.mp3');
      audio.play().catch(() => {});
      // Increment Alpine badge
      const body = document.body;
      if (body._x_dataStack && body._x_dataStack[0]) {
        body._x_dataStack[0].notifCount = (body._x_dataStack[0].notifCount || 0) + 1;
      }
    }
  });
})();
</script>
```

- [ ] **Step 3 : Passer VAPID_PUBLIC_KEY dans le contexte Django via context processor**

La vue base n'a pas accès directe à `settings.VAPID_PUBLIC_KEY` dans le template. Le plus simple : ajouter un context processor.

Créer `base/context_processors.py` :

```python
from django.conf import settings


def vapid_key(request):
    return {"VAPID_PUBLIC_KEY": getattr(settings, "VAPID_PUBLIC_KEY", "")}
```

Dans `main/settings.py`, dans la liste `TEMPLATES[0]['OPTIONS']['context_processors']`, ajouter :

```python
'base.context_processors.vapid_key',
```

- [ ] **Step 4 : Vérifier**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add templates/admin_user/base.html base/context_processors.py main/settings.py && git commit -m "feat: register push subscription in admin dashboard"
```

---

### Task 6 — Déclencher le push depuis la vue checkout

**Fichier :** `customer/views.py`

- [ ] **Step 1 : Ajouter l'import de `send_push_to_restaurant`**

En haut de `customer/views.py`, après les imports existants, ajouter :

```python
from base.push_utils import send_push_to_restaurant
```

- [ ] **Step 2 : Appeler `send_push_to_restaurant` après la création de commande**

Dans la vue `checkout`, après `order.calculate_total()` et avant `del request.session[cart_key]`, ajouter :

```python
            # Notify restaurant staff via Web Push
            table_label = f"Table {table.number}" if table else "Commande"
            customer = order.customer_name or "Client"
            send_push_to_restaurant(
                restaurant=restaurant,
                title=f"🛎 Nouvelle commande — {table_label}",
                body=f"{customer} • {int(order.total)} FCFA",
                url="/orders/",
            )
```

Le bloc complet devient :

```python
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

            # Notify restaurant staff via Web Push
            table_label = f"Table {table.number}" if table else "Commande"
            customer = order.customer_name or "Client"
            send_push_to_restaurant(
                restaurant=restaurant,
                title=f"🛎 Nouvelle commande — {table_label}",
                body=f"{customer} • {int(order.total)} FCFA",
                url="/orders/",
            )

            del request.session[cart_key]
            return redirect("order_confirmation", order_id=order.id)
```

- [ ] **Step 3 : Vérifier**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add customer/views.py && git commit -m "feat: trigger Web Push on new order creation"
```

---

### Task 7 — Badge de notification dans sidebar et bottom nav

**Fichiers :** `templates/admin_user/sidebar.html`, `templates/admin_user/base.html`, `templates/admin_user/orders/list_orders.html`, `templates/admin_user/index.html`

Le badge compte les nouvelles commandes détectées depuis le dernier passage sur la page Commandes. Il utilise `notifCount` dans Alpine (défini à Task 5).

La mise à jour du badge vient :
1. Des messages SW (push reçu → `notifCount++`)
2. Du polling existant (modifié pour incrémenter aussi le badge)

- [ ] **Step 1 : Ajouter le badge sur "Commandes" dans `sidebar.html`**

Dans `templates/admin_user/sidebar.html`, remplacer le bloc lien Commandes :

```html
<!-- Commandes — tous les rôles -->
<a href="{{ url_orders }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_orders %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-shopping-bag-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Commandes
  </span>
</a>
```

Par :

```html
<!-- Commandes — tous les rôles -->
<a href="{{ url_orders }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_orders %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <div class="relative flex-shrink-0">
    <i class="ri-shopping-bag-line text-lg"></i>
    <span x-show="notifCount > 0" x-cloak
          class="absolute -top-1.5 -right-1.5 bg-red-500 text-white text-[9px] font-bold rounded-full min-w-[1.1rem] h-[1.1rem] flex items-center justify-center leading-none px-0.5"
          x-text="notifCount > 9 ? '9+' : notifCount"></span>
  </div>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Commandes
  </span>
</a>
```

- [ ] **Step 2 : Ajouter le badge sur "Commandes" dans le bottom nav de `base.html`**

Dans `templates/admin_user/base.html`, dans le `<nav>` bottom nav, remplacer le lien Commandes :

```html
    <!-- Commandes — tous -->
    <a href="{{ url_orders }}"
       class="flex-1 flex flex-col items-center justify-center gap-1 transition-colors
              {% if current == url_orders %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}">
      <div class="relative w-7 h-7 flex items-center justify-center">
        {% if current == url_orders %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
        <i class="ri-shopping-bag-line text-[1.15rem] leading-none relative"></i>
      </div>
      <span class="text-[9.5px] font-semibold leading-none">Commandes</span>
    </a>
```

Par :

```html
    <!-- Commandes — tous -->
    <a href="{{ url_orders }}"
       class="flex-1 flex flex-col items-center justify-center gap-1 transition-colors
              {% if current == url_orders %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}">
      <div class="relative w-7 h-7 flex items-center justify-center">
        {% if current == url_orders %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
        <i class="ri-shopping-bag-line text-[1.15rem] leading-none relative"></i>
        <span x-show="notifCount > 0" x-cloak
              class="absolute -top-1 -right-1 bg-red-500 text-white text-[8px] font-bold rounded-full w-4 h-4 flex items-center justify-center leading-none"
              x-text="notifCount > 9 ? '9+' : notifCount"></span>
      </div>
      <span class="text-[9.5px] font-semibold leading-none">Commandes</span>
    </a>
```

- [ ] **Step 3 : Réinitialiser `notifCount` sur la page Commandes**

Dans `templates/admin_user/orders/list_orders.html`, dans le bloc `{% block extra_js %}`, ajouter au début du script :

```javascript
  // Réinitialiser le badge de notification
  window.dispatchEvent(new CustomEvent('reset-notif'));
```

- [ ] **Step 4 : Réinitialiser `notifCount` sur le dashboard**

Dans `templates/admin_user/index.html`, dans le bloc `{% block extra_js %}`, ajouter au début du script :

```javascript
  // Réinitialiser le badge de notification
  window.dispatchEvent(new CustomEvent('reset-notif'));
```

- [ ] **Step 5 : Incrémenter le badge depuis le polling existant**

Dans `templates/admin_user/orders/list_orders.html`, dans le polling `setInterval`, remplacer :

```javascript
      if (d.latest_order_id && d.latest_order_id !== lastOrderId) {
        audio.play().catch(() => {});
        lastOrderId = d.latest_order_id;
        location.reload();
      }
```

Par :

```javascript
      if (d.latest_order_id && d.latest_order_id !== lastOrderId) {
        audio.play().catch(() => {});
        lastOrderId = d.latest_order_id;
        // Incrémenter le badge Alpine
        const body = document.body;
        if (body._x_dataStack && body._x_dataStack[0]) {
          body._x_dataStack[0].notifCount = (body._x_dataStack[0].notifCount || 0) + 1;
        }
        location.reload();
      }
```

Dans `templates/admin_user/index.html`, dans le polling `checkNewOrders`, remplacer :

```javascript
      if (d.latest_order_id && d.latest_order_id !== lastOrderId) {
        orderSound.play().catch(() => {});
        lastOrderId = d.latest_order_id;
        location.reload();
      }
```

Par :

```javascript
      if (d.latest_order_id && d.latest_order_id !== lastOrderId) {
        orderSound.play().catch(() => {});
        lastOrderId = d.latest_order_id;
        // Incrémenter le badge Alpine
        const body = document.body;
        if (body._x_dataStack && body._x_dataStack[0]) {
          body._x_dataStack[0].notifCount = (body._x_dataStack[0].notifCount || 0) + 1;
        }
        location.reload();
      }
```

- [ ] **Step 6 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood" && git add templates/admin_user/sidebar.html templates/admin_user/base.html templates/admin_user/orders/list_orders.html templates/admin_user/index.html && git commit -m "feat: notification badge on orders nav link"
```

---

### Task 8 — Test du flux complet

- [ ] **Step 1 : Démarrer le serveur**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py runserver
```

- [ ] **Step 2 : Ouvrir le dashboard dans Chrome**

URL : `http://le-festival-des-rois.localhost:8000/dashboard/`

- [ ] **Step 3 : Autoriser les notifications**

Chrome affiche un popup demandant la permission → cliquer "Autoriser".

Vérifier dans DevTools → Application → Service Workers → le SW est actif.
Vérifier dans DevTools → Application → Push Messaging → une subscription existe.

- [ ] **Step 4 : Vérifier que la subscription est sauvegardée en base**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py shell -c "
from base.models import PushSubscription
print(PushSubscription.objects.count(), 'subscription(s)')
"
```

Résultat attendu : `1 subscription(s)`

- [ ] **Step 5 : Passer une commande client**

Ouvrir dans un autre onglet ou appareil : `http://le-festival-des-rois.localhost:8000/t/1b7632b9-3e2c-42f3-946a-09fd57fb5ffb/`

Ajouter un article au panier → Checkout → Soumettre.

- [ ] **Step 6 : Vérifier la notification**

Sur le dashboard (même si l'onglet est en arrière-plan) :
- La notification OS doit apparaître avec le titre `🛎 Nouvelle commande — Table X`
- Le son `new-order.mp3` doit jouer
- Le badge rouge `1` doit apparaître sur "Commandes" dans la sidebar et le bottom nav

- [ ] **Step 7 : Vérifier le click sur notification**

Cliquer sur la notification OS → le navigateur doit naviguer vers `/orders/` et le badge doit disparaître.

- [ ] **Step 8 : Vérifier la réinitialisation du badge**

Naviguer vers `/orders/` → le badge `1` disparaît (reset-notif event dispatché).

---

## Checklist de vérification finale

- [ ] `python manage.py check` — aucune erreur
- [ ] `PushSubscription` créée en base après ouverture du dashboard
- [ ] Notification OS reçue après passage d'une commande
- [ ] Son joué à la réception de la notification
- [ ] Badge `1` visible sur "Commandes" dans sidebar (desktop) et bottom nav (mobile)
- [ ] Badge disparaît en visitant `/orders/` ou `/dashboard/`
- [ ] Click sur notification OS → navigation vers `/orders/`
- [ ] Aucune double-notification (push + polling) grâce au `renotify: true` et `tag: 'new-order'`
- [ ] Subscriptions expirées supprimées automatiquement (404/410)
