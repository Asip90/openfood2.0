# Open Food SaaS — Full Refonte Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Skills à invoquer pendant l'exécution :**
> - `frontend-design:frontend-design` → avant chaque tâche de template HTML/CSS (Phases 1, 2, 3, 4, 5)
> - `marketing-skills:seo-audit` + `marketing-skills:ai-seo` → Phase 6

**Goal:** Refonte complète de l'interface Open Food SaaS — passer d'un design fonctionnel mais rudimentaire à une expérience Premium FoodTech (UberEats-style côté client, dashboard SaaS B2B côté restaurateur), avec PWA et SEO intégré.

**Architecture:** Full Django templates + Tailwind CSS (CDN avec config inline). Multi-tenant par subdomain. Deux "faces" distinctes : vue Client (`/t/<uuid>/`) et vue Restaurateur (`/dashboard/`). Pas de build step — Tailwind CDN play mode.

**Tech Stack:** Django 4.x, Tailwind CSS v3 (CDN), Alpine.js (CDN — pour réactivité légère sans build), Font Awesome 7, Remixicon, SQLite, Django REST Framework (AJAX orders).

---

## Scope Check — 6 sous-systèmes indépendants

Ce plan couvre 6 phases qui peuvent être exécutées séquentiellement. Chaque phase produit un résultat testable et committable indépendamment.

| Phase | Sous-système | Fichiers principaux |
|-------|-------------|---------------------|
| 1 | Design System & Base Templates | `templates/base.html`, `templates/customer/base.html`, `templates/admin_user/base.html` |
| 2 | Vue Client — Menu & Panier | `templates/customer/menu.html`, `customer/cart_sidebar.html`, `customer/menu_detail_modal.html` |
| 3 | Vue Client — Checkout & Confirmation | `templates/customer/checkout.html`, `customer/order_confirmation.html` |
| 4 | Vue Restaurateur — Dashboard & Orders | `templates/admin_user/dashboard.html`, `admin_user/orders/list_orders.html` |
| 5 | Module Fidélité + PWA | `templates/customer/loyalty.html`, `static/manifest.json`, `static/js/sw.js` |
| 6 | SEO (meta, schema, AI SEO) | Tous les templates publics + `base/views.py` context |

---

## File Map — Fichiers créés ou modifiés

### Nouveaux fichiers
- `templates/customer/loyalty.html` — Composant fidélisation post-commande (WhatsApp + parrainage)
- `static/manifest.json` — PWA manifest
- `static/js/sw.js` — Service Worker (cache offline)
- `static/css/customer.css` — Animations CSS custom (skeleton loaders, transitions)
- `static/icons/` — PWA icons (192x192, 512x512, apple-touch-icon)
- `templates/customer/skeleton_menu.html` — Loading skeleton placeholder

### Fichiers modifiés
- `templates/base.html` — Refonte complète avec blocks propres
- `templates/customer/base.html` — Nouvelle structure PWA-ready + Alpine.js
- `templates/customer/menu.html` — Cards immersives, catégories filtrables
- `templates/customer/cart_sidebar.html` — Panier rétractable slide-in
- `templates/customer/menu_detail_modal.html` — Modal produit premium
- `templates/customer/checkout.html` — Checkout épuré
- `templates/customer/order_confirmation.html` — Page confirmation + loyalty hook
- `templates/admin_user/base.html` — Layout sidebar modernisé
- `templates/admin_user/dashboard.html` — Stats cards + graphique Chart.js
- `templates/admin_user/orders/list_orders.html` — Liste commandes temps réel
- `templates/home/index.html` — Landing page refonte (assemblage des partials)
- `templates/home/hero.html` — Hero section Tailwind moderne
- `templates/home/Solution.html` — Section solution refonte
- `main/settings.py` — Ajout `ALPINE_CDN` constant si besoin

---

## Phase 1 — Design System & Base Templates

> **AVANT DE COMMENCER :** Invoquer le skill `frontend-design:frontend-design` pour guider les choix de design.

**Palette officielle du projet :**
- `primary`: `#f97316` (Orange-500 — "Orange gourmand" chaleureux)
- `primary-dark`: `#ea580c` (Orange-600)
- `surface`: `#ffffff`
- `surface-muted`: `#f8fafc` (Slate-50)
- `border`: `#e2e8f0` (Slate-200)
- `text`: `#0f172a` (Slate-900)
- `text-muted`: `#64748b` (Slate-500)
- `success`: `#22c55e` (Green-500)
- `danger`: `#ef4444` (Red-500)
- `warning`: `#f59e0b` (Amber-500)

### Task 1.1 : Refonte `templates/base.html` (socle landing page)

**Files:**
- Modify: `templates/base.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/base.html"
```

- [ ] **Step 2 : Écrire le nouveau `templates/base.html`**

Remplacer le contenu complet par :

```html
<!DOCTYPE html>
<html lang="fr" class="scroll-smooth">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Open Food — Menu Digital par QR Code{% endblock %}</title>
  {% block meta %}
  <meta name="description" content="{% block meta_description %}Créez votre menu digital QR Code en 5 minutes. Solution SaaS pour restaurateurs.{% endblock %}">
  <meta property="og:title" content="{% block og_title %}Open Food{% endblock %}">
  <meta property="og:description" content="{% block og_description %}Menu digital QR Code pour restaurants{% endblock %}">
  <meta property="og:type" content="website">
  {% endblock %}

  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            primary: { DEFAULT: '#f97316', dark: '#ea580c', light: '#fed7aa' },
            surface: { DEFAULT: '#ffffff', muted: '#f8fafc' },
          },
          fontFamily: {
            sans: ['Inter', 'system-ui', 'sans-serif'],
          },
          borderRadius: { xl: '0.75rem', '2xl': '1rem', '3xl': '1.5rem' },
          boxShadow: {
            soft: '0 2px 8px rgba(0,0,0,0.06)',
            card: '0 4px 16px rgba(0,0,0,0.08)',
            float: '0 8px 32px rgba(0,0,0,0.12)',
          }
        }
      }
    }
  </script>
  <!-- Google Fonts: Inter -->
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <!-- Remixicon -->
  <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
  <!-- Alpine.js -->
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>

  {% block extra_css %}{% endblock %}
</head>
<body class="font-sans bg-surface-muted text-slate-900 antialiased">

  {% block navbar %}{% endblock %}

  <main id="main-content">
    {% block content %}{% endblock %}
  </main>

  {% block footer %}{% endblock %}

  {% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3 : Vérifier que Django démarre sans erreur**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check --deploy 2>&1 | grep -E "ERROR|WARNING" | head -20
```
Résultat attendu : 0 erreur système (les warnings de sécurité déploiement sont normaux en dev).

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/base.html
git commit -m "design: refonte base.html avec design system Orange + Inter + Alpine.js"
```

---

### Task 1.2 : Refonte `templates/customer/base.html` (socle vue client PWA-ready)

**Files:**
- Modify: `templates/customer/base.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/base.html"
```

- [ ] **Step 2 : Remplacer par la nouvelle version PWA-ready**

```html
<!DOCTYPE html>
<html lang="fr" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover">
  <title>{% block title %}{{ restaurant.name }} — Menu{% endblock %}</title>
  <meta name="description" content="{{ restaurant.description|default:'Découvrez notre menu digital' }}">

  <!-- PWA -->
  <link rel="manifest" href="{% url 'pwa_manifest' restaurant.slug %}">
  <meta name="theme-color" content="{{ customization.primary_color|default:'#f97316' }}">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="default">
  <meta name="apple-mobile-web-app-title" content="{{ restaurant.name }}">

  <!-- SEO Schema (défini par block) -->
  {% block schema_org %}{% endblock %}

  <!-- Tailwind CSS -->
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            primary: {
              DEFAULT: '{{ customization.primary_color|default:"#f97316" }}',
              dark: '{{ customization.secondary_color|default:"#ea580c" }}',
            },
            surface: { DEFAULT: '#ffffff', muted: '#f8fafc' },
          },
          fontFamily: {
            sans: ['{{ customization.font_family|default:"Inter" }}', 'system-ui', 'sans-serif'],
          },
          boxShadow: {
            soft: '0 2px 8px rgba(0,0,0,0.06)',
            card: '0 4px 16px rgba(0,0,0,0.08)',
            float: '0 8px 32px rgba(0,0,0,0.15)',
          }
        }
      }
    }
  </script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>

  {% block extra_css %}{% endblock %}
</head>
<body class="font-sans bg-surface-muted min-h-full antialiased"
      x-data="cartStore()"
      x-init="initCart()">

  {% block navbar %}
    {% include 'customer/navbar.html' %}
  {% endblock %}

  <main class="pb-24">
    {% block content %}{% endblock %}
  </main>

  <!-- Panier flottant (bouton) -->
  {% block cart_fab %}
  <div x-show="cartCount > 0"
       x-cloak
       x-transition:enter="transition ease-out duration-300"
       x-transition:enter-start="opacity-0 translate-y-4"
       x-transition:enter-end="opacity-100 translate-y-0"
       class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 w-[calc(100%-3rem)] max-w-sm">
    <button @click="cartOpen = true"
            class="w-full flex items-center justify-between bg-primary text-white px-5 py-4 rounded-2xl shadow-float font-semibold text-base active:scale-95 transition-transform">
      <span class="flex items-center gap-2">
        <span class="bg-white text-primary rounded-lg w-7 h-7 flex items-center justify-center text-sm font-bold" x-text="cartCount"></span>
        <span>Voir mon panier</span>
      </span>
      <span x-text="formatPrice(cartTotal)"></span>
    </button>
  </div>
  {% endblock %}

  <!-- Sidebar panier -->
  {% include 'customer/cart_sidebar.html' %}

  <!-- Modal détail produit -->
  {% include 'customer/menu_detail_modal.html' %}

  <!-- Scripts Alpine.js Cart Store -->
  <script>
    function cartStore() {
      return {
        cartOpen: false,
        modalOpen: false,
        modalItem: null,
        cart: JSON.parse(localStorage.getItem('cart_{{ table.token }}') || '[]'),
        get cartCount() {
          return this.cart.reduce((sum, item) => sum + item.quantity, 0);
        },
        get cartTotal() {
          return this.cart.reduce((sum, item) => sum + (item.price * item.quantity), 0);
        },
        formatPrice(amount) {
          return new Intl.NumberFormat('fr-FR', { style: 'currency', currency: 'XOF', minimumFractionDigits: 0 }).format(amount);
        },
        initCart() {
          this.$watch('cart', val => {
            localStorage.setItem('cart_{{ table.token }}', JSON.stringify(val));
          });
        },
        addToCart(item) {
          const existing = this.cart.find(i => i.id === item.id);
          if (existing) {
            existing.quantity += 1;
            this.cart = [...this.cart];
          } else {
            this.cart = [...this.cart, { ...item, quantity: 1 }];
          }
          this.syncCartToServer();
        },
        removeFromCart(itemId) {
          this.cart = this.cart.filter(i => i.id !== itemId);
          this.syncCartToServer();
        },
        updateQuantity(itemId, qty) {
          if (qty <= 0) { this.removeFromCart(itemId); return; }
          this.cart = this.cart.map(i => i.id === itemId ? { ...i, quantity: qty } : i);
          this.syncCartToServer();
        },
        syncCartToServer() {
          fetch('{% url "update_cart" table.token %}', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}' },
            body: JSON.stringify({ cart: this.cart })
          });
        },
        openModal(item) {
          this.modalItem = item;
          this.modalOpen = true;
          document.body.style.overflow = 'hidden';
        },
        closeModal() {
          this.modalOpen = false;
          document.body.style.overflow = '';
        }
      }
    }
  </script>

  <!-- PWA Service Worker -->
  <script>
    if ('serviceWorker' in navigator) {
      window.addEventListener('load', () => {
        navigator.serviceWorker.register('/static/js/sw.js').catch(() => {});
      });
    }
  </script>

  {% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3 : Vérifier le rendu en démarrant le serveur**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py runserver 8000 &
sleep 2 && curl -s http://localhost:8000/connexion/ | grep -c "tailwind" || echo "Template OK"
```

- [ ] **Step 4 : Arrêter le serveur de test**

```bash
pkill -f "manage.py runserver" 2>/dev/null; echo "Server stopped"
```

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/base.html
git commit -m "design: customer/base.html PWA-ready avec Alpine.js cart store et FAB panier"
```

---

### Task 1.3 : Refonte `templates/admin_user/base.html` (sidebar restaurateur)

**Files:**
- Modify: `templates/admin_user/base.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/admin_user/base.html"
```

- [ ] **Step 2 : Réécrire avec layout sidebar moderne**

```html
<!DOCTYPE html>
<html lang="fr" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}Dashboard{% endblock %} — Open Food</title>

  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: {
            primary: { DEFAULT: '#f97316', dark: '#ea580c', light: '#fff7ed' },
            sidebar: { DEFAULT: '#0f172a', hover: '#1e293b' },
          },
          fontFamily: { sans: ['Inter', 'system-ui', 'sans-serif'] },
        }
      }
    }
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>
  {% block extra_css %}{% endblock %}
</head>
<body class="font-sans bg-slate-50 h-full" x-data="{ sidebarOpen: true, mobileMenuOpen: false }">

<div class="flex h-full">
  <!-- Sidebar Desktop -->
  <aside class="hidden lg:flex flex-col w-64 bg-sidebar text-white fixed inset-y-0 z-50 transition-all duration-300"
         :class="sidebarOpen ? 'w-64' : 'w-16'">
    <!-- Logo -->
    <div class="flex items-center h-16 px-4 border-b border-slate-700/50">
      <div class="flex items-center gap-3 overflow-hidden">
        {% if restaurant.logo %}
          <img src="{{ restaurant.logo.url }}" alt="{{ restaurant.name }}" class="h-8 w-8 rounded-lg object-cover flex-shrink-0">
        {% else %}
          <div class="h-8 w-8 rounded-lg bg-primary flex items-center justify-center flex-shrink-0">
            <i class="ri-restaurant-line text-white text-sm"></i>
          </div>
        {% endif %}
        <span class="font-semibold text-sm truncate" x-show="sidebarOpen">{{ restaurant.name|default:"Open Food" }}</span>
      </div>
    </div>

    <!-- Navigation -->
    <nav class="flex-1 py-4 overflow-y-auto">
      <div class="px-2 space-y-1">
        {% include 'admin_user/sidebar.html' %}
      </div>
    </nav>

    <!-- User bottom -->
    <div class="p-4 border-t border-slate-700/50">
      <div class="flex items-center gap-3 overflow-hidden">
        <div class="h-8 w-8 rounded-full bg-primary flex items-center justify-center flex-shrink-0 text-white text-xs font-bold">
          {{ request.user.first_name|first|upper }}{{ request.user.last_name|first|upper }}
        </div>
        <div class="overflow-hidden" x-show="sidebarOpen">
          <p class="text-xs font-medium truncate">{{ request.user.get_full_name }}</p>
          <p class="text-xs text-slate-400 truncate">{{ request.user.email }}</p>
        </div>
      </div>
    </div>
  </aside>

  <!-- Mobile overlay -->
  <div x-show="mobileMenuOpen" x-cloak @click="mobileMenuOpen = false"
       class="fixed inset-0 bg-black/50 z-40 lg:hidden"></div>

  <!-- Mobile Sidebar -->
  <aside x-show="mobileMenuOpen" x-cloak
         x-transition:enter="transition ease-out duration-300"
         x-transition:enter-start="-translate-x-full"
         x-transition:enter-end="translate-x-0"
         x-transition:leave="transition ease-in duration-200"
         x-transition:leave-start="translate-x-0"
         x-transition:leave-end="-translate-x-full"
         class="fixed inset-y-0 left-0 w-72 bg-sidebar text-white z-50 flex flex-col lg:hidden">
    <div class="flex items-center justify-between h-16 px-4 border-b border-slate-700/50">
      <span class="font-semibold">{{ restaurant.name|default:"Open Food" }}</span>
      <button @click="mobileMenuOpen = false" class="p-2 rounded-lg hover:bg-slate-700">
        <i class="ri-close-line text-xl"></i>
      </button>
    </div>
    <nav class="flex-1 py-4 overflow-y-auto px-2">
      {% include 'admin_user/sidebar.html' %}
    </nav>
  </aside>

  <!-- Main content -->
  <div class="flex-1 flex flex-col min-h-full" :class="sidebarOpen ? 'lg:ml-64' : 'lg:ml-16'">
    <!-- Top bar -->
    <header class="sticky top-0 z-30 bg-white border-b border-slate-200 h-16 flex items-center justify-between px-4 lg:px-6">
      <div class="flex items-center gap-3">
        <button @click="mobileMenuOpen = true" class="p-2 rounded-lg hover:bg-slate-100 lg:hidden">
          <i class="ri-menu-line text-xl text-slate-600"></i>
        </button>
        <button @click="sidebarOpen = !sidebarOpen" class="hidden lg:flex p-2 rounded-lg hover:bg-slate-100">
          <i class="ri-menu-fold-line text-xl text-slate-600"></i>
        </button>
        <h1 class="text-lg font-semibold text-slate-900">{% block page_title %}Dashboard{% endblock %}</h1>
      </div>
      <div class="flex items-center gap-2">
        {% block header_actions %}{% endblock %}
        <a href="{% url 'log_out' %}" class="flex items-center gap-2 px-3 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-xl transition-colors">
          <i class="ri-logout-circle-r-line"></i>
          <span class="hidden sm:block">Déconnexion</span>
        </a>
      </div>
    </header>

    <!-- Page content -->
    <main class="flex-1 p-4 lg:p-6">
      {% if messages %}
        {% for message in messages %}
          <div class="mb-4 px-4 py-3 rounded-xl text-sm font-medium
            {% if message.tags == 'success' %}bg-green-50 text-green-800 border border-green-200
            {% elif message.tags == 'error' %}bg-red-50 text-red-800 border border-red-200
            {% else %}bg-blue-50 text-blue-800 border border-blue-200{% endif %}">
            {{ message }}
          </div>
        {% endfor %}
      {% endif %}

      {% block content %}{% endblock %}
    </main>
  </div>
</div>

{% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Step 3 : Mettre à jour `templates/admin_user/sidebar.html`**

Remplacer le contenu par des liens avec le style compatible avec la nouvelle sidebar :

```html
{% url 'dashboard' as url_dashboard %}
{% url 'orders_list' as url_orders %}
{% url 'menus_list' as url_menus %}
{% url 'tables_list' as url_tables %}
{% url 'customization' as url_custom %}
{% url 'restaurant_settings' as url_settings %}

{% with nav_items=True %}
{% for item in ""|make_list %}{% endfor %}
{% endwith %}

<a href="{{ url_dashboard }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors {% if request.path == url_dashboard %}bg-primary text-white{% else %}text-slate-300 hover:bg-sidebar-hover hover:text-white{% endif %}">
  <i class="ri-dashboard-line text-lg flex-shrink-0"></i>
  <span x-show="sidebarOpen ?? true">Tableau de bord</span>
</a>

<a href="{{ url_orders }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors {% if '/orders' in request.path %}bg-primary text-white{% else %}text-slate-300 hover:bg-sidebar-hover hover:text-white{% endif %}">
  <i class="ri-shopping-bag-line text-lg flex-shrink-0"></i>
  <span x-show="sidebarOpen ?? true">Commandes</span>
</a>

<a href="{{ url_menus }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors {% if '/menus' in request.path %}bg-primary text-white{% else %}text-slate-300 hover:bg-sidebar-hover hover:text-white{% endif %}">
  <i class="ri-restaurant-line text-lg flex-shrink-0"></i>
  <span x-show="sidebarOpen ?? true">Menu</span>
</a>

<a href="{{ url_tables }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors {% if '/tables' in request.path %}bg-primary text-white{% else %}text-slate-300 hover:bg-sidebar-hover hover:text-white{% endif %}">
  <i class="ri-table-line text-lg flex-shrink-0"></i>
  <span x-show="sidebarOpen ?? true">Tables</span>
</a>

<a href="{{ url_custom }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors {% if '/customization' in request.path %}bg-primary text-white{% else %}text-slate-300 hover:bg-sidebar-hover hover:text-white{% endif %}">
  <i class="ri-palette-line text-lg flex-shrink-0"></i>
  <span x-show="sidebarOpen ?? true">Personnalisation</span>
</a>

<a href="{{ url_settings }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors {% if '/settings' in request.path %}bg-primary text-white{% else %}text-slate-300 hover:bg-sidebar-hover hover:text-white{% endif %}">
  <i class="ri-settings-3-line text-lg flex-shrink-0"></i>
  <span x-show="sidebarOpen ?? true">Paramètres</span>
</a>
```

- [ ] **Step 4 : Vérifier qu'aucun template enfant ne casse (check blocs)**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check 2>&1
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/admin_user/base.html templates/admin_user/sidebar.html
git commit -m "design: admin dashboard avec sidebar collapse responsive + Alpine.js"
```

---

## Phase 2 — Vue Client : Menu & Panier

> **AVANT DE COMMENCER :** Invoquer le skill `frontend-design:frontend-design`.

### Task 2.1 : Refonte `templates/customer/navbar.html`

**Files:**
- Modify: `templates/customer/navbar.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/navbar.html"
```

- [ ] **Step 2 : Réécrire la navbar client**

```html
<!-- customer/navbar.html -->
<nav class="sticky top-0 z-40 bg-white border-b border-slate-100 shadow-soft">
  <div class="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
    <!-- Restaurant info -->
    <div class="flex items-center gap-3">
      {% if restaurant.logo %}
        <img src="{{ restaurant.logo.url }}" alt="{{ restaurant.name }}"
             class="h-9 w-9 rounded-xl object-cover">
      {% else %}
        <div class="h-9 w-9 rounded-xl bg-primary flex items-center justify-center">
          <i class="ri-restaurant-line text-white"></i>
        </div>
      {% endif %}
      <div>
        <p class="font-semibold text-sm text-slate-900 leading-tight">{{ restaurant.name }}</p>
        <p class="text-xs text-slate-500">Table {{ table.number }}</p>
      </div>
    </div>

    <!-- Actions -->
    <div class="flex items-center gap-2">
      <!-- Recherche future (placeholder) -->
      <button class="p-2 rounded-xl hover:bg-slate-100 transition-colors text-slate-600">
        <i class="ri-search-line text-lg"></i>
      </button>
    </div>
  </div>
</nav>
```

- [ ] **Step 3 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/navbar.html
git commit -m "design: navbar client épurée avec info restaurant et table"
```

---

### Task 2.2 : Refonte `templates/customer/menu.html`

**Files:**
- Modify: `templates/customer/menu.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/menu.html"
```

- [ ] **Step 2 : Réécrire la page menu complète**

```html
{% extends 'customer/base.html' %}

{% block title %}Menu — {{ restaurant.name }}{% endblock %}

{% block schema_org %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Restaurant",
  "name": "{{ restaurant.name }}",
  "description": "{{ restaurant.description|default:'' }}",
  "servesCuisine": "International",
  "hasMenu": {
    "@type": "Menu",
    "name": "Menu {{ restaurant.name }}",
    "hasMenuSection": [
      {% for category in categories %}
      {
        "@type": "MenuSection",
        "name": "{{ category.name }}",
        "hasMenuItem": [
          {% for item in category.menuitem_set.all %}
          {
            "@type": "MenuItem",
            "name": "{{ item.name }}",
            "description": "{{ item.description|default:'' }}",
            "offers": { "@type": "Offer", "price": "{{ item.price }}", "priceCurrency": "XOF" }
          }{% if not forloop.last %},{% endif %}
          {% endfor %}
        ]
      }{% if not forloop.last %},{% endif %}
      {% endfor %}
    ]
  }
}
</script>
{% endblock %}

{% block content %}
<!-- Hero Cover Restaurant -->
{% if restaurant.cover_image %}
<div class="relative h-44 overflow-hidden">
  <img src="{{ restaurant.cover_image.url }}" alt="{{ restaurant.name }}"
       class="w-full h-full object-cover">
  <div class="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent"></div>
  <div class="absolute bottom-4 left-4 text-white">
    <h1 class="text-xl font-bold">{{ restaurant.name }}</h1>
    {% if restaurant.description %}
      <p class="text-sm text-white/80 mt-0.5">{{ restaurant.description|truncatechars:60 }}</p>
    {% endif %}
  </div>
</div>
{% else %}
<div class="bg-gradient-to-br from-primary to-primary-dark h-32 flex items-end px-4 pb-4">
  <h1 class="text-white text-xl font-bold">{{ restaurant.name }}</h1>
</div>
{% endif %}

<!-- Sticky Category Tabs -->
<div class="sticky top-14 z-30 bg-white border-b border-slate-100 shadow-soft">
  <div class="max-w-2xl mx-auto px-4 overflow-x-auto scrollbar-hide">
    <div class="flex gap-1 py-3 w-max" id="category-tabs">
      {% for category in categories %}
      <button onclick="scrollToCategory('cat-{{ category.id }}')"
              id="tab-{{ category.id }}"
              class="category-tab px-4 py-1.5 rounded-full text-sm font-medium whitespace-nowrap transition-colors text-slate-600 hover:bg-slate-100">
        {{ category.name }}
      </button>
      {% endfor %}
    </div>
  </div>
</div>

<!-- Menu Content -->
<div class="max-w-2xl mx-auto px-4 py-4 space-y-8">
  {% for category in categories %}
    {% with items=category.menuitem_set.filter(is_available=True) %}
    {% if items or True %}
    <section id="cat-{{ category.id }}" class="category-section">
      <!-- Category header -->
      <div class="flex items-center gap-3 mb-4">
        {% if category.image %}
          <img src="{{ category.image.url }}" alt="{{ category.name }}"
               class="h-8 w-8 rounded-lg object-cover">
        {% endif %}
        <h2 class="text-lg font-bold text-slate-900">{{ category.name }}</h2>
        <div class="flex-1 h-px bg-slate-100"></div>
      </div>

      <!-- Items grid -->
      <div class="space-y-3">
        {% for item in category.menuitem_set.all %}
        {% if item.is_available %}
        <div class="bg-white rounded-2xl shadow-soft border border-slate-100 overflow-hidden
                    active:scale-[0.99] transition-transform cursor-pointer"
             @click="openModal({{ item|json_script:'item'|striptags }})">

          <div class="flex gap-3 p-3">
            <!-- Info -->
            <div class="flex-1 min-w-0">
              <div class="flex items-start gap-2 mb-1">
                <h3 class="font-semibold text-slate-900 text-sm leading-tight">{{ item.name }}</h3>
                {% if item.is_vegetarian %}
                  <span class="flex-shrink-0 w-4 h-4 rounded-full bg-green-500 border-2 border-white shadow-sm" title="Végétarien"></span>
                {% endif %}
                {% if item.is_spicy %}
                  <span class="flex-shrink-0 text-xs">🌶️</span>
                {% endif %}
              </div>
              {% if item.description %}
                <p class="text-xs text-slate-500 line-clamp-2 leading-relaxed">{{ item.description }}</p>
              {% endif %}
              <!-- Badges -->
              <div class="flex items-center gap-2 mt-2">
                {% if item.preparation_time %}
                  <span class="text-xs text-slate-400 flex items-center gap-1">
                    <i class="ri-time-line"></i>{{ item.preparation_time }} min
                  </span>
                {% endif %}
              </div>
              <!-- Prix -->
              <div class="flex items-center gap-2 mt-2">
                {% if item.discount_price %}
                  <span class="font-bold text-primary text-base">{{ item.discount_price|floatformat:0 }} FCFA</span>
                  <span class="text-xs text-slate-400 line-through">{{ item.price|floatformat:0 }}</span>
                {% else %}
                  <span class="font-bold text-slate-900 text-base">{{ item.price|floatformat:0 }} FCFA</span>
                {% endif %}
              </div>
            </div>

            <!-- Image + Add button -->
            <div class="relative flex-shrink-0">
              {% if item.image %}
                <img src="{{ item.image.url }}" alt="{{ item.name }}"
                     class="w-24 h-24 rounded-xl object-cover">
              {% else %}
                <div class="w-24 h-24 rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center">
                  <i class="ri-restaurant-line text-2xl text-slate-400"></i>
                </div>
              {% endif %}
              <!-- Bouton + -->
              <button @click.stop="addToCart({
                          id: {{ item.id }},
                          name: '{{ item.name|escapejs }}',
                          price: {{ item.discount_price|default:item.price }},
                          image: '{% if item.image %}{{ item.image.url }}{% endif %}'
                        })"
                      class="absolute -bottom-2 -right-2 w-8 h-8 bg-primary text-white rounded-xl shadow-float
                             flex items-center justify-center font-bold text-lg
                             active:scale-90 transition-transform hover:bg-primary-dark">
                +
              </button>
            </div>
          </div>
        </div>
        {% endif %}
        {% empty %}
        <p class="text-slate-400 text-sm text-center py-4">Aucun article disponible dans cette catégorie.</p>
        {% endfor %}
      </div>
    </section>
    {% endif %}
    {% endwith %}
  {% empty %}
  <div class="text-center py-16">
    <i class="ri-restaurant-line text-4xl text-slate-300 block mb-3"></i>
    <p class="text-slate-500 font-medium">Le menu n'est pas encore disponible.</p>
  </div>
  {% endfor %}
</div>

<!-- Scroll spy pour onglets catégories -->
<script>
  function scrollToCategory(id) {
    const el = document.getElementById(id);
    if (el) {
      const offset = 120;
      const top = el.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  }

  // Intersection Observer pour activer l'onglet actif
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const id = entry.target.id.replace('cat-', '');
        document.querySelectorAll('.category-tab').forEach(t => {
          t.classList.remove('bg-primary', 'text-white');
          t.classList.add('text-slate-600');
        });
        const tab = document.getElementById('tab-' + id);
        if (tab) {
          tab.classList.add('bg-primary', 'text-white');
          tab.classList.remove('text-slate-600');
          tab.scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
        }
      }
    });
  }, { rootMargin: '-30% 0px -60% 0px' });

  document.querySelectorAll('.category-section').forEach(s => observer.observe(s));
</script>
{% endblock %}
```

- [ ] **Step 3 : Tester manuellement en accédant à un menu**

Démarrer le serveur, créer un restaurant test si besoin, et vérifier sur `http://127.0.0.1:8000/t/<uuid>/`.

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check 2>&1
```

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/menu.html
git commit -m "design: refonte menu client avec cards immersives, tabs catégories et bouton + rapide"
```

---

### Task 2.3 : Refonte `templates/customer/cart_sidebar.html`

**Files:**
- Modify: `templates/customer/cart_sidebar.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/cart_sidebar.html"
```

- [ ] **Step 2 : Réécrire le panier rétractable**

```html
<!-- customer/cart_sidebar.html — utilisé dans customer/base.html -->

<!-- Overlay -->
<div x-show="cartOpen" x-cloak @click="cartOpen = false"
     x-transition:enter="transition ease-out duration-200"
     x-transition:enter-start="opacity-0"
     x-transition:enter-end="opacity-100"
     x-transition:leave="transition ease-in duration-150"
     x-transition:leave-start="opacity-100"
     x-transition:leave-end="opacity-0"
     class="fixed inset-0 bg-black/50 z-50">
</div>

<!-- Drawer -->
<div x-show="cartOpen" x-cloak
     x-transition:enter="transition ease-out duration-300"
     x-transition:enter-start="translate-y-full"
     x-transition:enter-end="translate-y-0"
     x-transition:leave="transition ease-in duration-200"
     x-transition:leave-start="translate-y-0"
     x-transition:leave-end="translate-y-full"
     class="fixed bottom-0 left-0 right-0 z-50 bg-white rounded-t-3xl shadow-float max-h-[85vh] flex flex-col">

  <!-- Handle + Header -->
  <div class="flex-shrink-0 px-4 pt-3 pb-4 border-b border-slate-100">
    <div class="w-10 h-1 bg-slate-200 rounded-full mx-auto mb-4"></div>
    <div class="flex items-center justify-between">
      <h2 class="font-bold text-lg text-slate-900">Mon panier</h2>
      <button @click="cartOpen = false" class="p-2 rounded-xl hover:bg-slate-100 text-slate-600">
        <i class="ri-close-line text-xl"></i>
      </button>
    </div>
  </div>

  <!-- Cart items list -->
  <div class="flex-1 overflow-y-auto px-4 py-3 space-y-3">
    <template x-if="cart.length === 0">
      <div class="text-center py-12">
        <i class="ri-shopping-cart-line text-4xl text-slate-300 block mb-3"></i>
        <p class="text-slate-500 font-medium">Votre panier est vide</p>
        <p class="text-slate-400 text-sm mt-1">Ajoutez des plats pour commencer</p>
      </div>
    </template>

    <template x-for="item in cart" :key="item.id">
      <div class="flex items-center gap-3 bg-slate-50 rounded-2xl p-3">
        <!-- Image -->
        <div class="flex-shrink-0">
          <template x-if="item.image">
            <img :src="item.image" :alt="item.name" class="w-14 h-14 rounded-xl object-cover">
          </template>
          <template x-if="!item.image">
            <div class="w-14 h-14 rounded-xl bg-slate-200 flex items-center justify-center">
              <i class="ri-restaurant-line text-slate-400"></i>
            </div>
          </template>
        </div>

        <!-- Info -->
        <div class="flex-1 min-w-0">
          <p class="font-semibold text-sm text-slate-900 truncate" x-text="item.name"></p>
          <p class="text-primary font-bold text-sm mt-0.5" x-text="formatPrice(item.price)"></p>
        </div>

        <!-- Quantity controls -->
        <div class="flex items-center gap-2 flex-shrink-0">
          <button @click="updateQuantity(item.id, item.quantity - 1)"
                  class="w-7 h-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-600 font-bold active:scale-90 transition-transform">
            −
          </button>
          <span class="font-semibold text-slate-900 w-5 text-center text-sm" x-text="item.quantity"></span>
          <button @click="updateQuantity(item.id, item.quantity + 1)"
                  class="w-7 h-7 rounded-lg bg-primary text-white flex items-center justify-center font-bold active:scale-90 transition-transform">
            +
          </button>
        </div>
      </div>
    </template>
  </div>

  <!-- Footer avec Total + Bouton Commander -->
  <div class="flex-shrink-0 px-4 pb-8 pt-3 border-t border-slate-100 space-y-3">
    <!-- Total -->
    <div class="flex items-center justify-between">
      <span class="text-slate-600 font-medium">Total</span>
      <span class="text-xl font-bold text-slate-900" x-text="formatPrice(cartTotal)"></span>
    </div>

    <!-- Notes optionnelles -->
    <textarea placeholder="Note pour le cuisinier (optionnel)..."
              class="w-full text-sm border border-slate-200 rounded-xl px-3 py-2 resize-none h-16 focus:outline-none focus:ring-2 focus:ring-primary/30"
              id="cart-notes"></textarea>

    <!-- Bouton Commander -->
    <a href="{% url 'checkout' table.token %}"
       x-show="cart.length > 0"
       class="block w-full bg-primary text-white text-center font-bold py-4 rounded-2xl shadow-float active:scale-[0.98] transition-transform">
      Commander — <span x-text="formatPrice(cartTotal)"></span>
    </a>
  </div>
</div>
```

- [ ] **Step 3 : Vérifier que `cartOpen` est bien défini dans customer/base.html (déjà fait en Task 1.2)**

```bash
grep -n "cartOpen" "/home/jey/Documents/projet /OpendFood/templates/customer/base.html" | head -5
```
Attendu : au moins 1 ligne avec `cartOpen: false`.

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/cart_sidebar.html
git commit -m "design: panier client rétractable bottom sheet avec contrôle quantité"
```

---

### Task 2.4 : Refonte `templates/customer/menu_detail_modal.html`

**Files:**
- Modify: `templates/customer/menu_detail_modal.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/menu_detail_modal.html"
```

- [ ] **Step 2 : Réécrire la modal détail produit**

```html
<!-- customer/menu_detail_modal.html -->
<div x-show="modalOpen" x-cloak @click.self="closeModal()"
     x-transition:enter="transition ease-out duration-200"
     x-transition:enter-start="opacity-0"
     x-transition:enter-end="opacity-100"
     x-transition:leave="transition ease-in duration-150"
     x-transition:leave-start="opacity-100"
     x-transition:leave-end="opacity-0"
     class="fixed inset-0 z-60 bg-black/60 flex items-end sm:items-center justify-center">

  <div x-show="modalOpen" x-cloak
       x-transition:enter="transition ease-out duration-300"
       x-transition:enter-start="translate-y-full sm:translate-y-0 sm:scale-95 sm:opacity-0"
       x-transition:enter-end="translate-y-0 sm:scale-100 sm:opacity-100"
       x-transition:leave="transition ease-in duration-200"
       x-transition:leave-start="translate-y-0 sm:scale-100 sm:opacity-100"
       x-transition:leave-end="translate-y-full sm:translate-y-0 sm:scale-95 sm:opacity-0"
       class="bg-white w-full max-w-md rounded-t-3xl sm:rounded-3xl overflow-hidden max-h-[90vh] flex flex-col"
       @click.stop>

    <!-- Item image -->
    <div class="relative">
      <template x-if="modalItem && modalItem.image">
        <img :src="modalItem.image" :alt="modalItem.name" class="w-full h-52 object-cover">
      </template>
      <template x-if="!modalItem || !modalItem.image">
        <div class="w-full h-52 bg-gradient-to-br from-slate-100 to-slate-200 flex items-center justify-center">
          <i class="ri-restaurant-line text-5xl text-slate-300"></i>
        </div>
      </template>
      <button @click="closeModal()"
              class="absolute top-3 right-3 w-9 h-9 bg-white/90 backdrop-blur-sm rounded-xl flex items-center justify-center shadow-soft">
        <i class="ri-close-line text-lg text-slate-700"></i>
      </button>
    </div>

    <!-- Content -->
    <div class="flex-1 overflow-y-auto px-5 py-4">
      <template x-if="modalItem">
        <div>
          <h2 class="font-bold text-xl text-slate-900" x-text="modalItem.name"></h2>

          <!-- Prix -->
          <div class="flex items-center gap-2 mt-1">
            <span class="font-bold text-primary text-xl" x-text="formatPrice(modalItem.price)"></span>
            <template x-if="modalItem.original_price">
              <span class="text-slate-400 text-sm line-through" x-text="formatPrice(modalItem.original_price)"></span>
            </template>
          </div>

          <!-- Description -->
          <template x-if="modalItem.description">
            <p class="text-slate-600 text-sm leading-relaxed mt-3" x-text="modalItem.description"></p>
          </template>

          <!-- Badges (végétarien, vegan, épicé) -->
          <div class="flex flex-wrap gap-2 mt-3">
            <template x-if="modalItem.is_vegetarian">
              <span class="px-3 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full border border-green-100">🌿 Végétarien</span>
            </template>
            <template x-if="modalItem.is_vegan">
              <span class="px-3 py-1 bg-green-50 text-green-700 text-xs font-medium rounded-full border border-green-100">🌱 Vegan</span>
            </template>
            <template x-if="modalItem.is_spicy">
              <span class="px-3 py-1 bg-red-50 text-red-700 text-xs font-medium rounded-full border border-red-100">🌶️ Épicé</span>
            </template>
            <template x-if="modalItem.preparation_time">
              <span class="px-3 py-1 bg-slate-50 text-slate-600 text-xs font-medium rounded-full border border-slate-100">
                ⏱ <span x-text="modalItem.preparation_time + ' min'"></span>
              </span>
            </template>
          </div>

          <!-- Allergènes -->
          <template x-if="modalItem.allergens">
            <div class="mt-4 p-3 bg-amber-50 rounded-xl border border-amber-100">
              <p class="text-xs font-semibold text-amber-800 mb-1">⚠️ Allergènes</p>
              <p class="text-xs text-amber-700" x-text="modalItem.allergens"></p>
            </div>
          </template>
        </div>
      </template>
    </div>

    <!-- Footer bouton Ajouter -->
    <div class="flex-shrink-0 px-5 pb-8 pt-3 border-t border-slate-100">
      <button @click="addToCart(modalItem); closeModal()"
              class="w-full bg-primary text-white font-bold py-4 rounded-2xl shadow-float active:scale-[0.98] transition-transform text-base">
        Ajouter au panier — <span x-text="formatPrice(modalItem ? modalItem.price : 0)"></span>
      </button>
    </div>
  </div>
</div>
```

- [ ] **Step 3 : Vérifier que `z-60` est reconnu (Tailwind CDN play mode le supporte)**

```bash
grep -n "z-60\|z-50\|z-40" "/home/jey/Documents/projet /OpendFood/templates/customer/base.html" | head -5
```

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/menu_detail_modal.html
git commit -m "design: modal détail produit avec image, badges, allergènes et CTA ajout panier"
```

---

## Phase 3 — Vue Client : Checkout & Confirmation

### Task 3.1 : Refonte `templates/customer/checkout.html`

**Files:**
- Modify: `templates/customer/checkout.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/checkout.html"
```

- [ ] **Step 2 : Vérifier le contexte retourné par la view `checkout`**

```bash
grep -n "def checkout" "/home/jey/Documents/projet /OpendFood/customer/views.py"
```
Puis lire la vue pour connaître les variables contextuelles disponibles.

- [ ] **Step 3 : Réécrire le checkout**

```html
{% extends 'customer/base.html' %}
{% load widget_tweaks %}

{% block title %}Commander — {{ restaurant.name }}{% endblock %}

{% block cart_fab %}{% endblock %}

{% block content %}
<div class="max-w-xl mx-auto px-4 py-6">
  <!-- Back button -->
  <a href="javascript:history.back()" class="flex items-center gap-2 text-slate-600 text-sm font-medium mb-6 hover:text-slate-900">
    <i class="ri-arrow-left-line text-lg"></i>
    Retour au menu
  </a>

  <h1 class="text-2xl font-bold text-slate-900 mb-6">Votre commande</h1>

  <!-- Récapitulatif panier -->
  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-4 mb-6">
    <h2 class="font-semibold text-slate-700 mb-3 text-sm uppercase tracking-wide">Récapitulatif</h2>
    <div class="space-y-2">
      <template x-for="item in cart" :key="item.id">
        <div class="flex justify-between items-center text-sm">
          <span class="text-slate-700">
            <span class="font-semibold text-slate-900" x-text="item.quantity + 'x'"></span>
            <span x-text="' ' + item.name"></span>
          </span>
          <span class="font-semibold" x-text="formatPrice(item.price * item.quantity)"></span>
        </div>
      </template>
    </div>
    <div class="border-t border-slate-100 mt-3 pt-3 flex justify-between">
      <span class="font-bold text-slate-900">Total</span>
      <span class="font-bold text-xl text-primary" x-text="formatPrice(cartTotal)"></span>
    </div>
  </div>

  <!-- Formulaire client -->
  <form method="post" action="" class="space-y-4">
    {% csrf_token %}
    <input type="hidden" name="cart_data" x-bind:value="JSON.stringify(cart)">

    <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-4 space-y-4">
      <h2 class="font-semibold text-slate-700 text-sm uppercase tracking-wide">Vos informations</h2>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Prénom (optionnel)</label>
        <input type="text" name="customer_name" placeholder="Jean"
               class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary">
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Téléphone (optionnel)</label>
        <input type="tel" name="customer_phone" placeholder="+229 97 00 00 00"
               class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary">
      </div>

      <div>
        <label class="block text-sm font-medium text-slate-700 mb-1">Note pour le restaurant</label>
        <textarea name="notes" rows="2" placeholder="Sans oignons, allergie aux noix..."
                  class="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary resize-none"></textarea>
      </div>
    </div>

    <!-- Mode de paiement -->
    <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-4">
      <h2 class="font-semibold text-slate-700 mb-3 text-sm uppercase tracking-wide">Paiement</h2>
      <div class="grid grid-cols-3 gap-2">
        {% for value, label in payment_methods %}
        <label class="flex flex-col items-center gap-1 cursor-pointer">
          <input type="radio" name="payment_method" value="{{ value }}" class="sr-only peer" {% if forloop.first %}checked{% endif %}>
          <div class="w-full py-3 rounded-xl border border-slate-200 flex flex-col items-center gap-1 text-slate-600 peer-checked:border-primary peer-checked:bg-primary/5 peer-checked:text-primary transition-colors">
            {% if value == 'cash' %}<i class="ri-money-dollar-circle-line text-xl"></i>
            {% elif value == 'card' %}<i class="ri-bank-card-line text-xl"></i>
            {% else %}<i class="ri-smartphone-line text-xl"></i>{% endif %}
            <span class="text-xs font-medium">{{ label }}</span>
          </div>
        </label>
        {% endfor %}
      </div>
    </div>

    <!-- CTA -->
    <button type="submit"
            class="w-full bg-primary text-white font-bold py-4 rounded-2xl shadow-float active:scale-[0.98] transition-transform text-base">
      Confirmer ma commande
    </button>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 4 : Vérifier que `payment_methods` est dans le contexte de la view**

```bash
grep -n "payment_methods\|Payment\|PAYMENT" "/home/jey/Documents/projet /OpendFood/customer/views.py" | head -10
```
Si absent, ajouter dans la view :
```python
from base.models import Payment
context['payment_methods'] = Payment.PAYMENT_METHOD_CHOICES  # adapter selon le model
```

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/checkout.html customer/views.py
git commit -m "design: checkout épuré avec résumé panier Alpine.js et sélecteur paiement"
```

---

## Phase 4 — Vue Restaurateur : Dashboard & Orders

> **AVANT DE COMMENCER :** Invoquer le skill `frontend-design:frontend-design`.

### Task 4.1 : Refonte `templates/admin_user/dashboard.html`

**Files:**
- Modify: `templates/admin_user/dashboard.html`

- [ ] **Step 1 : Lire le fichier actuel et la view dashboard**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/admin_user/dashboard.html"
grep -n "def dashboard\|def home" "/home/jey/Documents/projet /OpendFood/base/views.py" | head -5
```

- [ ] **Step 2 : Identifier les variables de contexte disponibles**

Lire la view `dashboard` (ou `home`) pour connaître les stats disponibles. Variables typiquement disponibles :
- `total_orders`, `pending_orders`, `today_revenue`, `total_menu_items`
- `recent_orders` (queryset)
- `restaurant`

- [ ] **Step 3 : Réécrire le dashboard**

```html
{% extends 'admin_user/base.html' %}

{% block page_title %}Tableau de bord{% endblock %}

{% block content %}
<!-- Stats cards -->
<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">

  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-5">
    <div class="flex items-center justify-between mb-3">
      <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
        <i class="ri-shopping-bag-line text-primary text-xl"></i>
      </div>
      <span class="text-xs font-medium text-green-600 bg-green-50 px-2 py-0.5 rounded-full">Aujourd'hui</span>
    </div>
    <p class="text-2xl font-bold text-slate-900">{{ today_orders|default:"0" }}</p>
    <p class="text-sm text-slate-500 mt-0.5">Commandes</p>
  </div>

  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-5">
    <div class="flex items-center justify-between mb-3">
      <div class="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
        <i class="ri-time-line text-amber-500 text-xl"></i>
      </div>
      <span class="text-xs font-medium text-amber-600 bg-amber-50 px-2 py-0.5 rounded-full">En attente</span>
    </div>
    <p class="text-2xl font-bold text-slate-900">{{ pending_orders|default:"0" }}</p>
    <p class="text-sm text-slate-500 mt-0.5">À préparer</p>
  </div>

  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-5">
    <div class="flex items-center justify-between mb-3">
      <div class="w-10 h-10 rounded-xl bg-green-50 flex items-center justify-center">
        <i class="ri-money-franc-circle-line text-green-500 text-xl"></i>
      </div>
    </div>
    <p class="text-2xl font-bold text-slate-900">{{ today_revenue|default:"0"|floatformat:0 }}</p>
    <p class="text-sm text-slate-500 mt-0.5">Revenus (FCFA)</p>
  </div>

  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 p-5">
    <div class="flex items-center justify-between mb-3">
      <div class="w-10 h-10 rounded-xl bg-blue-50 flex items-center justify-center">
        <i class="ri-restaurant-line text-blue-500 text-xl"></i>
      </div>
    </div>
    <p class="text-2xl font-bold text-slate-900">{{ total_menu_items|default:"0" }}</p>
    <p class="text-sm text-slate-500 mt-0.5">Plats au menu</p>
  </div>

</div>

<!-- Commandes récentes -->
<div class="bg-white rounded-2xl shadow-soft border border-slate-100">
  <div class="flex items-center justify-between px-6 py-4 border-b border-slate-100">
    <h2 class="font-semibold text-slate-900">Commandes récentes</h2>
    <a href="{% url 'orders_list' %}" class="text-sm text-primary font-medium hover:underline">Voir tout</a>
  </div>

  <div class="divide-y divide-slate-100" id="recent-orders-list">
    {% for order in recent_orders %}
    <div class="flex items-center gap-4 px-6 py-4 hover:bg-slate-50 transition-colors">
      <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
        {% if order.status == 'pending' %}bg-amber-50 text-amber-600
        {% elif order.status == 'preparing' %}bg-blue-50 text-blue-600
        {% elif order.status == 'ready' %}bg-green-50 text-green-600
        {% else %}bg-slate-100 text-slate-500{% endif %}">
        <i class="ri-shopping-bag-line"></i>
      </div>
      <div class="flex-1 min-w-0">
        <p class="font-medium text-sm text-slate-900"># {{ order.order_number }}</p>
        <p class="text-xs text-slate-500 mt-0.5">
          Table {{ order.table.number|default:"—" }} · {{ order.created_at|timesince }} ago
        </p>
      </div>
      <div class="text-right flex-shrink-0">
        <p class="font-bold text-sm text-slate-900">{{ order.total|floatformat:0 }} FCFA</p>
        <span class="text-xs font-medium px-2 py-0.5 rounded-full
          {% if order.status == 'pending' %}bg-amber-50 text-amber-700
          {% elif order.status == 'confirmed' %}bg-blue-50 text-blue-700
          {% elif order.status == 'preparing' %}bg-indigo-50 text-indigo-700
          {% elif order.status == 'ready' %}bg-green-50 text-green-700
          {% elif order.status == 'delivered' %}bg-slate-100 text-slate-600
          {% else %}bg-red-50 text-red-700{% endif %}">
          {{ order.get_status_display }}
        </span>
      </div>
    </div>
    {% empty %}
    <div class="px-6 py-12 text-center">
      <i class="ri-shopping-bag-line text-3xl text-slate-300 block mb-2"></i>
      <p class="text-slate-500 font-medium">Aucune commande pour l'instant</p>
    </div>
    {% endfor %}
  </div>
</div>

<!-- Auto-refresh des commandes en attente (polling) -->
<script>
  const newOrderSound = new Audio('{% static "sounds/new-order.mp3" %}');
  let lastOrderCount = {{ pending_orders|default:0 }};

  async function checkNewOrders() {
    try {
      const resp = await fetch('{% url "check_new_orders" %}', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const data = await resp.json();
      if (data.new_count > lastOrderCount) {
        newOrderSound.play().catch(() => {});
        lastOrderCount = data.new_count;
        location.reload();
      }
    } catch(e) {}
  }
  setInterval(checkNewOrders, 15000);
</script>
{% load static %}
{% endblock %}
```

- [ ] **Step 4 : Vérifier que la view `dashboard` retourne `today_orders`, `pending_orders`, `today_revenue`, `recent_orders`**

```bash
grep -n "today_orders\|pending_orders\|today_revenue\|recent_orders" "/home/jey/Documents/projet /OpendFood/base/views.py"
```

Si certaines variables manquent, les ajouter dans la view. Exemple pour `today_revenue` :
```python
from django.utils import timezone
from django.db.models import Sum
from base.models import Order

today = timezone.now().date()
context['today_revenue'] = Order.objects.filter(
    restaurant=restaurant,
    created_at__date=today,
    status='delivered'
).aggregate(Sum('total'))['total__sum'] or 0
context['today_orders'] = Order.objects.filter(restaurant=restaurant, created_at__date=today).count()
context['pending_orders'] = Order.objects.filter(restaurant=restaurant, status='pending').count()
context['recent_orders'] = Order.objects.filter(restaurant=restaurant).order_by('-created_at')[:10]
```

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/admin_user/dashboard.html base/views.py
git commit -m "design: dashboard restaurateur avec stats cards et commandes récentes temps réel"
```

---

### Task 4.2 : Refonte `templates/admin_user/orders/list_orders.html`

**Files:**
- Modify: `templates/admin_user/orders/list_orders.html`

- [ ] **Step 1 : Lire le fichier actuel**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/admin_user/orders/list_orders.html"
```

- [ ] **Step 2 : Réécrire la liste commandes**

```html
{% extends 'admin_user/base.html' %}
{% load static %}

{% block page_title %}Commandes{% endblock %}

{% block header_actions %}
<a href="{% url 'create_manual_order' %}"
   class="flex items-center gap-2 px-4 py-2 bg-primary text-white rounded-xl text-sm font-medium hover:bg-primary-dark transition-colors">
  <i class="ri-add-line"></i>
  <span class="hidden sm:block">Commande manuelle</span>
</a>
{% endblock %}

{% block content %}
<!-- Filtres statut -->
<div class="flex gap-2 mb-6 overflow-x-auto pb-1">
  {% for value, label in status_choices %}
  <a href="?status={{ value }}"
     class="px-4 py-2 rounded-xl text-sm font-medium whitespace-nowrap transition-colors flex-shrink-0
       {% if current_status == value %}bg-primary text-white{% else %}bg-white border border-slate-200 text-slate-600 hover:border-primary hover:text-primary{% endif %}">
    {{ label }}
    {% if value == 'pending' and pending_count %}
      <span class="ml-1 bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5">{{ pending_count }}</span>
    {% endif %}
  </a>
  {% endfor %}
</div>

<!-- Liste commandes -->
<div class="space-y-3" id="orders-container">
  {% for order in orders %}
  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 overflow-hidden
              hover:shadow-card transition-shadow">
    <div class="flex items-center gap-4 p-4">
      <!-- Numéro & statut -->
      <div class="flex-shrink-0">
        <div class="w-12 h-12 rounded-xl flex items-center justify-center
          {% if order.status == 'pending' %}bg-amber-50 text-amber-600
          {% elif order.status == 'confirmed' %}bg-blue-50 text-blue-600
          {% elif order.status == 'preparing' %}bg-indigo-50 text-indigo-600
          {% elif order.status == 'ready' %}bg-green-50 text-green-600
          {% else %}bg-slate-100 text-slate-500{% endif %}">
          <i class="ri-shopping-bag-line text-xl"></i>
        </div>
      </div>

      <!-- Infos principales -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <span class="font-bold text-slate-900">#{{ order.order_number|slice:"-6:" }}</span>
          <span class="text-xs font-medium px-2 py-0.5 rounded-full
            {% if order.status == 'pending' %}bg-amber-50 text-amber-700
            {% elif order.status == 'confirmed' %}bg-blue-50 text-blue-700
            {% elif order.status == 'preparing' %}bg-indigo-50 text-indigo-700
            {% elif order.status == 'ready' %}bg-green-50 text-green-700
            {% elif order.status == 'delivered' %}bg-slate-100 text-slate-600
            {% else %}bg-red-50 text-red-700{% endif %}">
            {{ order.get_status_display }}
          </span>
        </div>
        <p class="text-xs text-slate-500 mt-0.5">
          {% if order.table %}Table {{ order.table.number }}{% else %}À emporter{% endif %}
          · {{ order.created_at|timesince }}
          {% if order.customer_name %} · {{ order.customer_name }}{% endif %}
        </p>
        <!-- Articles résumé -->
        <p class="text-xs text-slate-600 mt-1 truncate">
          {% for item in order.items.all|slice:":3" %}{{ item.quantity }}× {{ item.menu_item.name }}{% if not forloop.last %}, {% endif %}{% endfor %}
          {% if order.items.count > 3 %} +{{ order.items.count|add:"-3" }} autres{% endif %}
        </p>
      </div>

      <!-- Montant + Actions -->
      <div class="flex-shrink-0 text-right">
        <p class="font-bold text-slate-900">{{ order.total|floatformat:0 }} FCFA</p>
        <div class="flex items-center gap-1 mt-2">
          <a href="{% url 'order_detail' order.pk %}"
             class="p-2 rounded-lg hover:bg-slate-100 text-slate-500 transition-colors" title="Détails">
            <i class="ri-eye-line"></i>
          </a>
          <a href="{% url 'order_change_status' order.pk %}"
             class="p-2 rounded-lg hover:bg-primary/10 text-primary transition-colors" title="Changer statut">
            <i class="ri-refresh-line"></i>
          </a>
        </div>
      </div>
    </div>
  </div>
  {% empty %}
  <div class="bg-white rounded-2xl shadow-soft border border-slate-100 py-16 text-center">
    <i class="ri-shopping-bag-line text-4xl text-slate-300 block mb-3"></i>
    <p class="text-slate-500 font-medium">Aucune commande</p>
  </div>
  {% endfor %}
</div>

<!-- Pagination -->
{% if orders.has_other_pages %}
<div class="flex justify-center gap-2 mt-6">
  {% if orders.has_previous %}
  <a href="?page={{ orders.previous_page_number }}{% if current_status %}&status={{ current_status }}{% endif %}"
     class="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-600 hover:border-primary hover:text-primary transition-colors">
    ← Précédent
  </a>
  {% endif %}
  <span class="px-4 py-2 rounded-xl bg-primary text-white text-sm font-medium">
    {{ orders.number }} / {{ orders.paginator.num_pages }}
  </span>
  {% if orders.has_next %}
  <a href="?page={{ orders.next_page_number }}{% if current_status %}&status={{ current_status }}{% endif %}"
     class="px-4 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-600 hover:border-primary hover:text-primary transition-colors">
    Suivant →
  </a>
  {% endif %}
</div>
{% endif %}

<!-- Polling nouvelles commandes -->
<script>
  const audio = new Audio('{% static "sounds/new-order.mp3" %}');
  let knownCount = {{ orders.paginator.count|default:0 }};

  setInterval(async () => {
    try {
      const r = await fetch('{% url "check_new_orders" %}', { headers: {'X-Requested-With': 'XMLHttpRequest'} });
      const d = await r.json();
      if (d.new_count > knownCount) {
        audio.play().catch(()=>{});
        knownCount = d.new_count;
        location.reload();
      }
    } catch(e) {}
  }, 10000);
</script>
{% endblock %}
```

- [ ] **Step 3 : Vérifier que la view `orders_list` supporte le filtre `?status=` et la pagination**

```bash
grep -n "def orders_list\|status\|Paginator\|page" "/home/jey/Documents/projet /OpendFood/base/views.py" | head -20
```

Si la pagination manque, l'ajouter dans la view :
```python
from django.core.paginator import Paginator

def orders_list(request):
    restaurant = get_object_or_404(Restaurant, owner=request.user)
    status = request.GET.get('status', '')
    orders_qs = Order.objects.filter(restaurant=restaurant).order_by('-created_at')
    if status:
        orders_qs = orders_qs.filter(status=status)
    paginator = Paginator(orders_qs, 20)
    page = request.GET.get('page', 1)
    orders = paginator.get_page(page)
    context = {
        'orders': orders,
        'current_status': status,
        'status_choices': Order.STATUS_CHOICES,
        'pending_count': Order.objects.filter(restaurant=restaurant, status='pending').count(),
    }
    return render(request, 'admin_user/orders/list_orders.html', context)
```

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/admin_user/orders/list_orders.html base/views.py
git commit -m "design: liste commandes avec filtres statut, badges, polling et pagination"
```

---

## Phase 5 — Module Fidélité + PWA

### Task 5.1 : Créer `templates/customer/loyalty.html` (module fidélisation)

**Files:**
- Create: `templates/customer/loyalty.html`
- Modify: `templates/customer/order_confirmation.html`

- [ ] **Step 1 : Créer le template loyalty.html**

```html
<!-- customer/loyalty.html — à inclure dans order_confirmation.html -->
<!-- Paramètre attendu : order (Order instance), restaurant (Restaurant instance) -->

<div class="mt-6 bg-gradient-to-br from-primary/10 to-amber-50 rounded-2xl border border-primary/20 p-5">
  <div class="flex items-center gap-3 mb-4">
    <div class="w-10 h-10 rounded-xl bg-primary flex items-center justify-center flex-shrink-0">
      <i class="ri-gift-line text-white text-xl"></i>
    </div>
    <div>
      <h3 class="font-bold text-slate-900">Merci pour votre commande !</h3>
      <p class="text-xs text-slate-500">Profitez de nos offres exclusives</p>
    </div>
  </div>

  <!-- Option 1 : Ticket WhatsApp -->
  {% if restaurant.phone %}
  <a href="https://wa.me/{{ restaurant.phone|cut:'+' }}?text={{ whatsapp_message|urlencode }}"
     target="_blank" rel="noopener noreferrer"
     class="flex items-center gap-3 bg-white rounded-xl p-4 mb-3 border border-slate-100 hover:border-green-300 transition-colors group">
    <div class="w-10 h-10 rounded-xl bg-green-500 flex items-center justify-center flex-shrink-0">
      <i class="ri-whatsapp-line text-white text-xl"></i>
    </div>
    <div class="flex-1">
      <p class="font-semibold text-sm text-slate-900 group-hover:text-green-700">Recevoir mon ticket par WhatsApp</p>
      <p class="text-xs text-slate-500">Confirmez votre commande #{{ order.order_number|slice:"-6:" }}</p>
    </div>
    <i class="ri-arrow-right-s-line text-slate-400 group-hover:text-green-600"></i>
  </a>
  {% endif %}

  <!-- Option 2 : Parrainage (lien QR table) -->
  <div class="bg-white rounded-xl p-4 border border-slate-100">
    <p class="font-semibold text-sm text-slate-900 mb-1">Partagez notre restaurant</p>
    <p class="text-xs text-slate-500 mb-3">Invitez un ami et profitez tous les deux de -10% sur votre prochaine commande</p>
    <button onclick="shareRestaurant()"
            class="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl border border-primary text-primary text-sm font-semibold hover:bg-primary hover:text-white transition-colors">
      <i class="ri-share-forward-line"></i>
      Partager le menu
    </button>
  </div>
</div>

<script>
  function shareRestaurant() {
    const url = window.location.origin + '/t/{{ table.token }}/';
    if (navigator.share) {
      navigator.share({
        title: '{{ restaurant.name }}',
        text: 'Découvre le menu de {{ restaurant.name|escapejs }} — commande directement depuis ton téléphone !',
        url: url
      }).catch(() => {});
    } else {
      navigator.clipboard.writeText(url).then(() => {
        alert('Lien copié ! Partagez-le à vos amis.');
      });
    }
  }
</script>
```

- [ ] **Step 2 : Modifier `templates/customer/order_confirmation.html` pour inclure le module**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/customer/order_confirmation.html"
```

Ajouter après la section de confirmation existante :

```html
{% include 'customer/loyalty.html' with order=order restaurant=restaurant table=table %}
```

- [ ] **Step 3 : Ajouter `whatsapp_message` dans la view `order_confirmation`**

```bash
grep -n "def order_confirmation" "/home/jey/Documents/projet /OpendFood/customer/views.py"
```

Ajouter dans le contexte :
```python
from urllib.parse import quote
items_text = ', '.join([f"{i.quantity}x {i.menu_item.name}" for i in order.items.all()])
whatsapp_message = f"Bonjour {restaurant.name} ! J'ai passé la commande #{order.order_number[-6:]} : {items_text}. Total : {order.total} FCFA. Merci !"
context['whatsapp_message'] = whatsapp_message
```

- [ ] **Step 4 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/customer/loyalty.html templates/customer/order_confirmation.html customer/views.py
git commit -m "feat: module fidélité post-commande avec ticket WhatsApp et partage parrainage"
```

---

### Task 5.2 : Setup PWA (manifest.json + Service Worker)

**Files:**
- Create: `static/manifest.json`
- Create: `static/js/sw.js`
- Modify: `base/views.py` (vue pour servir le manifest dynamique par restaurant)
- Modify: `base/urls.py` (nouvelle URL `pwa_manifest`)

- [ ] **Step 1 : Créer la view `pwa_manifest` dans `base/views.py`**

Ajouter à la fin de `base/views.py` :
```python
import json
from django.http import JsonResponse
from django.views.decorators.cache import cache_control

@cache_control(max_age=86400)
def pwa_manifest(request, slug):
    from base.models import Restaurant, RestaurantCustomization
    try:
        restaurant = Restaurant.objects.get(slug=slug, is_active=True)
        customization = RestaurantCustomization.objects.filter(restaurant=restaurant).first()
        primary_color = customization.primary_color if customization else '#f97316'
        logo_url = request.build_absolute_uri(restaurant.logo.url) if restaurant.logo else ''
    except Restaurant.DoesNotExist:
        primary_color = '#f97316'
        logo_url = ''
        restaurant = None

    manifest = {
        "name": restaurant.name if restaurant else "Open Food",
        "short_name": (restaurant.name[:12] if restaurant else "Menu"),
        "description": restaurant.description if restaurant and restaurant.description else "Menu digital par QR Code",
        "start_url": f"/t/{request.resolver_match.kwargs.get('table_token', '')}/" if 'table_token' in request.resolver_match.kwargs else "/",
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
```

- [ ] **Step 2 : Ajouter l'URL dans `base/urls.py`**

```bash
grep -n "urlpatterns" "/home/jey/Documents/projet /OpendFood/base/urls.py" | head -3
```

Ajouter dans `urlpatterns` de `base/urls.py` :
```python
path('manifest/<slug:slug>.json', pwa_manifest, name='pwa_manifest'),
```

Et ajouter l'import en haut :
```python
from base.views import pwa_manifest
```

- [ ] **Step 3 : Créer `static/js/sw.js` (service worker minimal)**

```javascript
// sw.js — Open Food PWA Service Worker
const CACHE_NAME = 'openfood-v1';
const STATIC_ASSETS = [
  '/static/sounds/new-order.mp3',
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
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
  // Network-first pour les requêtes API et pages Django
  if (event.request.url.includes('/api/') || event.request.method !== 'GET') return;

  // Cache-first pour les assets statiques
  if (event.request.url.includes('/static/')) {
    event.respondWith(
      caches.match(event.request).then(cached =>
        cached || fetch(event.request).then(resp => {
          const clone = resp.clone();
          caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          return resp;
        })
      )
    );
  }
});
```

- [ ] **Step 4 : Créer les icônes PWA (placeholder — à remplacer par vraies icônes)**

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/static/icons"
# Créer des icônes SVG de base (à remplacer par vraies icônes PNG)
python3 -c "
import base64, struct, zlib

def create_minimal_png(size, color=(249, 115, 22)):
    # Crée un PNG minimal en mémoire
    def chunk(name, data):
        c = struct.pack('>I', len(data)) + name + data
        return c + struct.pack('>I', zlib.crc32(c[4:]) & 0xffffffff)
    
    header = b'\x89PNG\r\n\x1a\n'
    ihdr = chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 2, 0, 0, 0))
    raw = b''
    for y in range(size):
        raw += b'\x00'
        for x in range(size):
            raw += bytes(color)
    idat = chunk(b'IDAT', zlib.compress(raw))
    iend = chunk(b'IEND', b'')
    return header + ihdr + idat + iend

with open('/home/jey/Documents/projet /OpendFood/static/icons/icon-192.png', 'wb') as f:
    f.write(create_minimal_png(192))
with open('/home/jey/Documents/projet /OpendFood/static/icons/icon-512.png', 'wb') as f:
    f.write(create_minimal_png(512))
print('Icons created')
"
```

- [ ] **Step 5 : Vérifier que la vue manifest répond correctement**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check 2>&1
```

- [ ] **Step 6 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add static/js/sw.js static/icons/ base/views.py base/urls.py
git commit -m "feat: PWA setup avec manifest.json dynamique par restaurant et service worker"
```

---

## Phase 6 — SEO (meta, schema markup, AI SEO)

> **AVANT DE COMMENCER :** Invoquer les skills `marketing-skills:seo-audit` et `marketing-skills:ai-seo` pour un audit complet et des recommandations spécifiques au projet.

### Task 6.1 : SEO audit & méta-tags sur les pages publiques

**Files:**
- Modify: `templates/home/index.html`
- Modify: `templates/home/hero.html`
- Modify: `templates/home/Solution.html`
- Modify: `base/views.py` (view `home`)

- [ ] **Step 1 : Invoquer `marketing-skills:seo-audit`**

```
Invoke: marketing-skills:seo-audit
Context: Landing page Django SaaS — menu digital QR Code pour restaurants en Afrique de l'Ouest (Bénin, FCFA). Pages publiques : /, /connexion, /inscription.
```

- [ ] **Step 2 : Lire les templates actuels**

```bash
cat "/home/jey/Documents/projet /OpendFood/templates/home/index.html"
cat "/home/jey/Documents/projet /OpendFood/templates/home/hero.html"
```

- [ ] **Step 3 : Ajouter les méta-tags SEO dans `templates/home/index.html`**

S'assurer que `{% extends 'base.html' %}` est présent et ajouter les blocs :

```html
{% block title %}Open Food — Créez votre Menu Digital QR Code | SaaS Restaurateurs{% endblock %}

{% block meta_description %}Créez votre menu digital par QR Code en 5 minutes. Solution SaaS pour restaurants et cafés en Afrique. Sans impression, sans application. Commencez gratuitement.{% endblock %}

{% block og_title %}Open Food — Menu Digital par QR Code pour Restaurants{% endblock %}
{% block og_description %}La solution SaaS n°1 pour les restaurateurs africains. Menu digital, commandes en ligne, tableau de bord temps réel. Démarrez gratuitement.{% endblock %}
```

- [ ] **Step 4 : Ajouter Schema.org Organization sur la home**

```html
{% block schema_org %}
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "SoftwareApplication",
  "name": "Open Food",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web",
  "description": "Solution SaaS de menu digital par QR Code pour les restaurateurs.",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "XOF",
    "description": "Plan gratuit disponible"
  },
  "featureList": [
    "Menu digital QR Code",
    "Commandes en temps réel",
    "Tableau de bord restaurateur",
    "PWA mobile-first"
  ]
}
</script>
{% endblock %}
```

- [ ] **Step 5 : Ajouter les méta canonical et sitemap dans `base/views.py`**

Ajouter au contexte de la view `home` :
```python
context['canonical_url'] = request.build_absolute_uri('/')
```

Et dans `templates/base.html` dans le `{% block meta %}` :
```html
{% if canonical_url %}
<link rel="canonical" href="{{ canonical_url }}">
{% endif %}
```

- [ ] **Step 6 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/home/ templates/base.html base/views.py
git commit -m "seo: méta-tags, og:tags, schema.org SoftwareApplication et canonical sur landing"
```

---

### Task 6.2 : AI SEO — Optimisation pour moteurs IA (Perplexity, ChatGPT Search, Gemini)

> Invoquer `marketing-skills:ai-seo` pour recommandations spécifiques.

**Files:**
- Create: `templates/home/faq.html` (partial FAQ schema)
- Modify: `templates/home/index.html`

- [ ] **Step 1 : Invoquer `marketing-skills:ai-seo`**

```
Invoke: marketing-skills:ai-seo
Context: SaaS B2B menu digital QR code, cible restaurateurs Afrique de l'Ouest.
Keywords cibles: "menu QR code restaurant", "menu digital restaurant Bénin", "logiciel menu restaurant", "commande QR code restaurant Afrique"
```

- [ ] **Step 2 : Créer `templates/home/faq.html` avec FAQ schema**

```html
<!-- home/faq.html — FAQ pour SEO IA -->
<section class="max-w-3xl mx-auto px-4 py-16">
  <h2 class="text-3xl font-bold text-slate-900 text-center mb-10">Questions fréquentes</h2>

  <div class="space-y-4" itemscope itemtype="https://schema.org/FAQPage">
    {% for faq in faqs %}
    <div class="bg-white rounded-2xl shadow-soft border border-slate-100 overflow-hidden"
         itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">
      <button class="w-full flex items-center justify-between px-6 py-5 text-left font-semibold text-slate-900 hover:bg-slate-50 transition-colors"
              x-data="{ open: false }" @click="open = !open">
        <span itemprop="name">{{ faq.question }}</span>
        <i class="ri-arrow-down-s-line text-xl text-slate-400 transition-transform" :class="open ? 'rotate-180' : ''"></i>
      </button>
      <div x-show="open" x-cloak class="px-6 pb-5"
           itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">
        <p class="text-slate-600 leading-relaxed text-sm" itemprop="text">{{ faq.answer }}</p>
      </div>
    </div>
    {% endfor %}
  </div>
</section>

<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {% for faq in faqs %}
    {
      "@type": "Question",
      "name": "{{ faq.question|escapejs }}",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "{{ faq.answer|escapejs }}"
      }
    }{% if not forloop.last %},{% endif %}
    {% endfor %}
  ]
}
</script>
```

- [ ] **Step 3 : Ajouter les FAQs dans la view `home` de `base/views.py`**

```python
FAQS = [
    {
        'question': 'Comment créer un menu QR code pour mon restaurant ?',
        'answer': 'Inscrivez-vous gratuitement sur Open Food, créez votre restaurant, ajoutez vos plats avec photos et prix, puis générez votre QR code. Imprimez-le et placez-le sur vos tables. Vos clients scannent et commandent directement depuis leur téléphone.'
    },
    {
        'question': 'Faut-il une application mobile pour utiliser Open Food ?',
        'answer': 'Non. Open Food fonctionne directement dans le navigateur de vos clients. Aucune installation requise. Votre menu est accessible instantanément après le scan du QR code.'
    },
    {
        'question': 'Open Food fonctionne-t-il au Bénin et en Afrique de l\'Ouest ?',
        'answer': 'Oui, Open Food est conçu spécifiquement pour les restaurateurs africains. L\'interface supporte le Franc CFA (FCFA) et est optimisée pour les connexions mobiles 3G/4G.'
    },
    {
        'question': 'Combien coûte Open Food ?',
        'answer': 'Open Food propose un plan gratuit pour démarrer. Des plans professionnels avec des fonctionnalités avancées (analytics, domaine personnalisé, suppression du branding) sont disponibles à partir de 5 000 FCFA/mois.'
    },
    {
        'question': 'Puis-je personnaliser les couleurs de mon menu ?',
        'answer': 'Oui, chaque restaurant peut personnaliser les couleurs, la police, le logo et la photo de couverture de son menu digital depuis le tableau de bord.'
    }
]

def home(request):
    context = {
        'faqs': FAQS,
        'canonical_url': request.build_absolute_uri('/'),
    }
    return render(request, 'home/index.html', context)
```

- [ ] **Step 4 : Inclure la section FAQ dans `templates/home/index.html`**

Ajouter avant le footer :
```html
{% include 'home/faq.html' %}
```

- [ ] **Step 5 : Commit**

```bash
cd "/home/jey/Documents/projet /OpendFood"
git add templates/home/faq.html templates/home/index.html base/views.py
git commit -m "seo: FAQ schema.org pour AI SEO (Perplexity, ChatGPT Search) avec 5 questions cibles"
```

---

## Self-Review Checklist

### Spec coverage

| Requirement | Task couvrant |
|-------------|--------------|
| base.html avec blocks clairs | Task 1.1 |
| customer/base.html PWA-ready | Task 1.2 |
| admin/base.html sidebar moderne | Task 1.3 |
| Cards immersives client | Task 2.2 |
| Tabs catégories | Task 2.2 |
| Panier rétractable | Task 2.3 |
| Modal détail produit | Task 2.4 |
| Checkout épuré | Task 3.1 |
| Dashboard stats + commandes temps réel | Task 4.1 |
| Liste commandes filtrable | Task 4.2 |
| Module fidélisation WhatsApp | Task 5.1 |
| Parrainage/partage | Task 5.1 |
| PWA manifest dynamique | Task 5.2 |
| Service Worker | Task 5.2 |
| SEO méta-tags + schema.org | Task 6.1 |
| AI SEO FAQ schema | Task 6.2 |
| Tailwind CSS | Toutes tâches |
| Syntaxe Django `{% ... %}` | Toutes tâches |
| Touch-friendly | Task 2.x (active:scale, targets 44px+) |
| Mode plein écran PWA | Task 1.2 (viewport-fit=cover) |
| Inter/Geist typographie | Task 1.1, 1.2 |
| Palette Orange gourmand | Toutes tâches |
| rounded-xl | Toutes tâches |
| Ombres subtiles | shadow-soft, shadow-card |

### Types consistency

- `cartStore()` défini dans `customer/base.html` (Task 1.2), utilisé dans `cart_sidebar.html` (Task 2.3), `menu_detail_modal.html` (Task 2.4), `menu.html` (Task 2.2)
- `addToCart(item)` signature : `{id, name, price, image}` — cohérent dans Tasks 2.2 et 2.4
- `formatPrice(amount)` — défini dans `cartStore()`, utilisé partout
- `cartOpen` — défini dans `cartStore()`, utilisé dans `cart_sidebar.html` et FAB dans `base.html`
- `modalOpen`, `modalItem` — définis dans `cartStore()`, utilisés dans `menu_detail_modal.html`
- `pwa_manifest` view — référencée par `{% url 'pwa_manifest' restaurant.slug %}` dans `customer/base.html` (Task 1.2) et définie dans Task 5.2

---

## Résumé d'exécution

**Durée estimée :** 4-6 heures d'exécution agentique

**Ordre recommandé :** Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 (chaque phase est testable indépendamment)

**Tests manuels clés :**
1. Accéder à `/t/<uuid>/` → vérifier menu, panier FAB, slide-in, modal
2. Accéder au `/dashboard/` → vérifier sidebar collapse, stats, commandes
3. Scanner avec iPhone → vérifier "Add to Home Screen" PWA
4. Valider JSON-LD sur https://validator.schema.org
