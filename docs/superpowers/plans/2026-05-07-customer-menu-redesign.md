# Customer Menu Page — Redesign Complet

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Redesigner entièrement l'expérience client post-scan QR : menu, panier, checkout et confirmation en une interface moderne, mobile-first, respectant les customisations du restaurant.

**Architecture:** On conserve le backend Django existant (session-cart, views, API REST) et on refait uniquement les templates Django. Alpine.js gère la réactivité côté client (filtres, panier, modals). Les customisations restaurant (couleur, police, logo, cover) sont injectées via des CSS variables dans le `<head>`.

**Tech Stack:** Django templates, Alpine.js 3, Tailwind CSS CDN, Remix Icons, CSS variables pour le thème, session Django pour le panier.

---

## Fichiers concernés

| Action | Fichier | Rôle |
|--------|---------|------|
| Modifier | `templates/customer/base.html` | CSS vars du thème, police Google Fonts |
| Modifier | `templates/customer/navbar.html` | Logo + badge panier sticky |
| **Réécrire** | `templates/customer/menu.html` | Hero + tabs + grid items + search |
| **Réécrire** | `templates/customer/menu_detail_modal.html` | Modal détail article |
| **Réécrire** | `templates/customer/cart_sidebar.html` | Drawer panier bottom-sheet |
| **Réécrire** | `templates/customer/checkout.html` | Formulaire commande + résumé |
| **Réécrire** | `templates/customer/order_confirmation.html` | Écran succès |
| Vérifier | `customer/views.py` | S'assurer que le contexte est complet |

---

## Contexte disponible dans les templates

```python
# client_menu view passe :
{
    "restaurant": Restaurant,         # .name, .description, .address, .phone
    "table": Table,                   # .number, .token
    "customization": Customization,   # .primary_color, .secondary_color, .font_family, .logo, .cover_image
    "categories": QuerySet[Category], # with prefetch items
    "cart": [{"id","name","price","quantity","image","total"}],
    "cart_total": float,
    "cart_count": int,
    "table_token": UUID,
    "cart_json": str (JSON),
}
```

---

## Task 1 — Base template : CSS variables du thème

**Fichiers :**
- Modifier : `templates/customer/base.html`

**Objectif :** Injecter les couleurs et la police du restaurant via CSS variables sur `:root`, charger dynamiquement la bonne Google Font.

- [ ] **Lire le fichier actuel**

```bash
cat "templates/customer/base.html"
```

- [ ] **Remplacer le bloc `<head>` pour injecter le thème**

Dans `templates/customer/base.html`, ajouter dans `<head>` juste avant `</head>` :

```html
{% load static %}
<style>
  :root {
    --color-primary:   {{ customization.primary_color|default:"#f97316" }};
    --color-secondary: {{ customization.secondary_color|default:"#0f172a" }};
  }
  /* Appliquer primary_color à tous les éléments qui utilisent la couleur du thème */
  .btn-primary        { background-color: var(--color-primary) !important; }
  .text-theme         { color: var(--color-primary) !important; }
  .border-theme       { border-color: var(--color-primary) !important; }
  .bg-theme           { background-color: var(--color-primary) !important; }
  .ring-theme         { --tw-ring-color: var(--color-primary) !important; }
</style>

{% with font=customization.font_family|default:"outfit" %}
{% if font == "poppins" %}
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>body { font-family: 'Poppins', sans-serif; }</style>
{% elif font == "montserrat" %}
<link href="https://fonts.googleapis.com/css2?family=Montserrat:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>body { font-family: 'Montserrat', sans-serif; }</style>
{% elif font == "roboto" %}
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500;700&display=swap" rel="stylesheet">
<style>body { font-family: 'Roboto', sans-serif; }</style>
{% else %}
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>body { font-family: 'Outfit', sans-serif; }</style>
{% endif %}
{% endwith %}
```

- [ ] **Vérifier que Alpine.js, Tailwind CDN et Remix Icons sont chargés dans base.html**

```html
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://cdn.jsdelivr.net/npm/remixicon@3.5.0/fonts/remixicon.css" rel="stylesheet">
<script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.14.0/dist/cdn.min.js"></script>
```

- [ ] **Commit**

```bash
git add templates/customer/base.html
git commit -m "feat: inject restaurant theme CSS variables in customer base template"
```

---

## Task 2 — Navbar : logo, nom du restau, bouton panier

**Fichiers :**
- Modifier : `templates/customer/navbar.html`

**Objectif :** Navbar sticky avec logo du restau (ou initiales), nom, et bouton panier avec badge count animé.

- [ ] **Réécrire `templates/customer/navbar.html`**

```html
{% load static %}
<nav class="sticky top-0 z-40 bg-white/95 backdrop-blur-md border-b border-slate-100"
     style="box-shadow: 0 1px 12px rgba(0,0,0,0.06);">
  <div class="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between gap-3">

    <!-- Logo + nom -->
    <div class="flex items-center gap-2.5 min-w-0">
      {% if customization.logo %}
        <img src="{{ customization.logo.url }}" alt="{{ restaurant.name }}"
             class="h-8 w-8 rounded-xl object-cover flex-shrink-0">
      {% elif restaurant.logo %}
        <img src="{{ restaurant.logo.url }}" alt="{{ restaurant.name }}"
             class="h-8 w-8 rounded-xl object-cover flex-shrink-0">
      {% else %}
        <div class="h-8 w-8 rounded-xl bg-theme flex items-center justify-center flex-shrink-0 text-white text-xs font-black">
          {{ restaurant.name|slice:":2"|upper }}
        </div>
      {% endif %}
      <span class="font-bold text-slate-900 text-sm truncate">{{ restaurant.name }}</span>
    </div>

    <!-- Bouton panier -->
    <button @click="cartOpen = true"
            class="relative flex items-center gap-2 px-3 py-1.5 rounded-xl bg-theme text-white text-sm font-semibold transition-all active:scale-95"
            style="background-color: var(--color-primary);">
      <i class="ri-shopping-bag-line text-base"></i>
      <span class="hidden sm:inline">Panier</span>
      <span x-text="cartCount"
            x-show="cartCount > 0"
            class="absolute -top-1.5 -right-1.5 min-w-[18px] h-[18px] rounded-full bg-slate-900 text-white text-[10px] font-black flex items-center justify-center px-1">
      </span>
    </button>

  </div>
</nav>
```

- [ ] **Commit**

```bash
git add templates/customer/navbar.html
git commit -m "feat: modern sticky navbar with restaurant logo and cart badge"
```

---

## Task 3 — Menu principal : hero, tabs catégories, grille d'articles

**Fichiers :**
- Réécrire : `templates/customer/menu.html`

**Objectif :** Page menu complète avec : hero cover image, tabs catégories sticky sous la navbar, barre de recherche, grille d'articles par catégorie (cards modernes), respecte la couleur primaire du thème.

- [ ] **Réécrire `templates/customer/menu.html`**

```html
{% extends "customer/base.html" %}
{% load static %}

{% block content %}
{# État Alpine global : panier + recherche + catégorie active + modal #}
<div x-data="{
  cartOpen: false,
  cartItems: {{ cart_json|safe }},
  cartCount: {{ cart_count }},
  cartTotal: {{ cart_total }},
  search: '',
  activeCategory: 'all',
  modalItem: null,
  modalOpen: false,

  openModal(item) {
    this.modalItem = item;
    this.modalOpen = true;
    document.body.style.overflow = 'hidden';
  },
  closeModal() {
    this.modalOpen = false;
    document.body.style.overflow = '';
  },
  filteredItems(items) {
    if (!this.search) return items;
    const q = this.search.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
    return items.filter(item => {
      const n = item.name.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
      return n.includes(q);
    });
  }
}">

  {# NAVBAR #}
  {% include 'customer/navbar.html' %}

  {# ── HERO ────────────────────────────────────────────── #}
  <div class="relative h-48 sm:h-60 overflow-hidden bg-slate-900">
    {% if customization.cover_image %}
      <img src="{{ customization.cover_image.url }}" alt="{{ restaurant.name }}"
           class="absolute inset-0 w-full h-full object-cover opacity-75">
    {% elif restaurant.cover_image %}
      <img src="{{ restaurant.cover_image.url }}" alt="{{ restaurant.name }}"
           class="absolute inset-0 w-full h-full object-cover opacity-75">
    {% endif %}
    <div class="absolute inset-0 bg-gradient-to-t from-black/70 via-black/20 to-transparent"></div>
    <div class="absolute bottom-0 left-0 right-0 px-4 pb-4">
      <h1 class="text-white font-black text-xl sm:text-2xl leading-tight">{{ restaurant.name }}</h1>
      {% if restaurant.description %}
        <p class="text-white/70 text-xs mt-1 line-clamp-1">{{ restaurant.description }}</p>
      {% endif %}
      <p class="text-white/60 text-[11px] mt-1">
        <i class="ri-map-pin-line"></i> {{ restaurant.address|default:"" }}
        {% if table %} · <i class="ri-table-line"></i> Table {{ table.number }}{% endif %}
      </p>
    </div>
  </div>

  {# ── BARRE DE RECHERCHE ─────────────────────────────── #}
  <div class="sticky top-14 z-30 bg-white border-b border-slate-100 px-4 py-2.5">
    <div class="max-w-2xl mx-auto">
      <div class="relative">
        <i class="ri-search-line absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 text-sm"></i>
        <input x-model="search" type="text" placeholder="Rechercher un plat..."
               class="w-full pl-9 pr-4 py-2 text-sm bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:border-transparent transition-all"
               style="--tw-ring-color: var(--color-primary);">
        <button x-show="search" @click="search=''"
                class="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
          <i class="ri-close-line text-sm"></i>
        </button>
      </div>
    </div>
  </div>

  {# ── TABS CATÉGORIES ────────────────────────────────── #}
  <div class="sticky top-[calc(3.5rem+52px)] z-20 bg-white border-b border-slate-100">
    <div class="max-w-2xl mx-auto px-4 overflow-x-auto scrollbar-none">
      <div class="flex gap-1 py-2.5 w-max min-w-full">
        <button @click="activeCategory = 'all'"
                :class="activeCategory === 'all' ? 'text-white shadow-sm' : 'bg-slate-50 text-slate-600'"
                :style="activeCategory === 'all' ? 'background-color: var(--color-primary);' : ''"
                class="px-3.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all">
          Tout
        </button>
        {% for category in categories %}
        <button @click="activeCategory = '{{ category.id }}'"
                :class="activeCategory === '{{ category.id }}' ? 'text-white shadow-sm' : 'bg-slate-50 text-slate-600'"
                :style="activeCategory === '{{ category.id }}' ? 'background-color: var(--color-primary);' : ''"
                class="px-3.5 py-1.5 rounded-lg text-xs font-semibold whitespace-nowrap transition-all"
                x-show="activeCategory === 'all' || activeCategory === '{{ category.id }}'
                        || {{ category.items.count }} > 0">
          {{ category.name }}
        </button>
        {% endfor %}
      </div>
    </div>
  </div>

  {# ── GRILLE D'ARTICLES ──────────────────────────────── #}
  <div class="max-w-2xl mx-auto px-4 py-4 space-y-8 pb-32">

    {% for category in categories %}
    <section x-show="activeCategory === 'all' || activeCategory === '{{ category.id }}'">
      <h2 class="text-slate-900 font-black text-base mb-3">{{ category.name }}</h2>

      {# Message si recherche sans résultat #}
      <template x-if="filteredItems({{ category.items_json|safe }}).length === 0 && search">
        <p class="text-slate-400 text-sm py-4 text-center">Aucun résultat pour "<span x-text="search"></span>"</p>
      </template>

      <div class="grid grid-cols-1 gap-3">
        {% for item in category.items.all %}
        {# Carte article #}
        <div class="bg-white rounded-2xl border border-slate-100 overflow-hidden flex gap-3 p-3 cursor-pointer active:scale-[0.99] transition-transform"
             style="box-shadow: 0 2px 8px rgba(0,0,0,0.04);"
             @click="openModal({{ item|item_json }})">

          {# Infos #}
          <div class="flex-1 min-w-0">
            <div class="flex items-start gap-1.5 flex-wrap mb-1">
              {% if item.is_vegetarian %}
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-green-100 text-green-700">Végé</span>
              {% endif %}
              {% if item.is_vegan %}
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-emerald-100 text-emerald-700">Vegan</span>
              {% endif %}
              {% if item.is_spicy %}
                <span class="text-[9px] font-bold px-1.5 py-0.5 rounded bg-red-100 text-red-700">🌶 Épicé</span>
              {% endif %}
            </div>
            <h3 class="font-semibold text-slate-900 text-sm leading-snug truncate">{{ item.name }}</h3>
            {% if item.description %}
              <p class="text-slate-400 text-xs mt-0.5 line-clamp-2 leading-relaxed">{{ item.description }}</p>
            {% endif %}
            {% if item.preparation_time %}
              <p class="text-slate-300 text-[11px] mt-1"><i class="ri-time-line"></i> {{ item.preparation_time }} min</p>
            {% endif %}
            <div class="flex items-center justify-between mt-2">
              <div>
                {% if item.discount_price %}
                  <span class="font-black text-sm" style="color: var(--color-primary);">{{ item.discount_price }} FCFA</span>
                  <span class="text-slate-300 text-xs line-through ml-1">{{ item.price }} FCFA</span>
                {% else %}
                  <span class="font-black text-sm text-slate-900">{{ item.price }} FCFA</span>
                {% endif %}
              </div>
              <button @click.stop="$dispatch('add-to-cart', {id: {{ item.id }}, name: '{{ item.name|escapejs }}', price: {{ item.discount_price|default:item.price }}, image: '{% if item.image %}{{ item.image.url }}{% endif %}'})"
                      class="w-7 h-7 rounded-lg flex items-center justify-center text-white text-base transition-all active:scale-90"
                      style="background-color: var(--color-primary);">
                <i class="ri-add-line"></i>
              </button>
            </div>
          </div>

          {# Image #}
          {% if item.image %}
          <div class="w-20 h-20 rounded-xl overflow-hidden flex-shrink-0">
            <img src="{{ item.image.url }}" alt="{{ item.name }}"
                 class="w-full h-full object-cover">
          </div>
          {% else %}
          <div class="w-20 h-20 rounded-xl bg-slate-50 flex items-center justify-center flex-shrink-0">
            <i class="ri-restaurant-line text-2xl text-slate-200"></i>
          </div>
          {% endif %}

        </div>
        {% empty %}
        <p class="text-slate-400 text-sm text-center py-6">Aucun article dans cette catégorie.</p>
        {% endfor %}
      </div>
    </section>
    {% endfor %}

  </div>

  {# MODAL + CART (inclus depuis fichiers séparés) #}
  {% include 'customer/menu_detail_modal.html' %}
  {% include 'customer/cart_sidebar.html' %}

  {# Listener Alpine pour ajout au panier via AJAX #}
  <script>
  document.addEventListener('alpine:init', () => {
    document.addEventListener('add-to-cart', async (e) => {
      const item = e.detail;
      const resp = await fetch(`/t/{{ table_token }}/cart/`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}'},
        body: JSON.stringify({action: 'add', item_id: item.id, quantity: 1})
      });
      const data = await resp.json();
      // Mettre à jour l'état Alpine global
      const alpine = document.querySelector('[x-data]').__x.$data;
      alpine.cartItems = data.cart;
      alpine.cartCount = data.cart_count;
      alpine.cartTotal = data.cart_total;
    });
  });
  </script>

</div>
{% endblock %}
```

- [ ] **Ajouter le filtre `item_json` dans un templatetag ou dans la view**

Dans `customer/views.py`, dans le contexte, ajouter pour chaque item un sérialiseur JSON utilisable dans les templates Alpine. Le plus simple : passer `cart_json` déjà fait, et pour les items utiliser un custom filter.

Créer `base/templatetags/menu_extras.py` :

```python
import json
from django import template
register = template.Library()

@register.filter
def item_json(item):
    return json.dumps({
        'id': item.id,
        'name': item.name,
        'description': item.description or '',
        'price': str(item.price),
        'discount_price': str(item.discount_price) if item.discount_price else None,
        'image': item.image.url if item.image else None,
        'is_vegetarian': item.is_vegetarian,
        'is_vegan': item.is_vegan,
        'is_spicy': item.is_spicy,
        'preparation_time': item.preparation_time,
        'allergens': item.allergens or '',
        'ingredients': item.ingredients or '',
    })
```

Ajouter `{% load menu_extras %}` en haut de `menu.html`.

- [ ] **Dans `customer/views.py`, vérifier que `cart_json` est bien sérialisé**

```python
import json

cart_items = []  # construire à partir de la session comme existant
context = {
    ...
    "cart_json": json.dumps(cart_items),
    ...
}
```

- [ ] **Commit**

```bash
git add templates/customer/menu.html base/templatetags/menu_extras.py
git commit -m "feat: redesign customer menu page with hero, sticky tabs, search and modern item cards"
```

---

## Task 4 — Modal détail article

**Fichiers :**
- Réécrire : `templates/customer/menu_detail_modal.html`

**Objectif :** Modal plein-écran (mobile) ou centré (desktop) avec image large, description, badges, allergènes, prépa time, et bouton "Ajouter au panier" prominent.

- [ ] **Réécrire `templates/customer/menu_detail_modal.html`**

```html
{# Modal détail — contrôlé par modalOpen + modalItem dans le x-data parent #}
<div x-show="modalOpen"
     x-transition:enter="transition ease-out duration-200"
     x-transition:enter-start="opacity-0"
     x-transition:enter-end="opacity-100"
     x-transition:leave="transition ease-in duration-150"
     x-transition:leave-start="opacity-100"
     x-transition:leave-end="opacity-0"
     class="fixed inset-0 z-50 flex items-end sm:items-center justify-center"
     @keydown.escape.window="closeModal()"
     x-cloak>

  {# Overlay #}
  <div class="absolute inset-0 bg-black/50 backdrop-blur-sm" @click="closeModal()"></div>

  {# Panel #}
  <div class="relative bg-white w-full sm:max-w-sm sm:rounded-3xl rounded-t-3xl overflow-hidden z-10 max-h-[90vh] flex flex-col"
       x-transition:enter="transition ease-out duration-300"
       x-transition:enter-start="translate-y-full sm:translate-y-4 sm:opacity-0"
       x-transition:enter-end="translate-y-0 sm:opacity-100"
       x-transition:leave="transition ease-in duration-200"
       x-transition:leave-start="translate-y-0"
       x-transition:leave-end="translate-y-full">

    {# Drag handle (mobile) #}
    <div class="flex justify-center pt-3 pb-1 flex-shrink-0">
      <div class="w-10 h-1 rounded-full bg-slate-200"></div>
    </div>

    {# Scrollable content #}
    <div class="overflow-y-auto flex-1">

      {# Image #}
      <template x-if="modalItem && modalItem.image">
        <div class="w-full h-52 overflow-hidden">
          <img :src="modalItem.image" :alt="modalItem.name" class="w-full h-full object-cover">
        </div>
      </template>
      <template x-if="!modalItem || !modalItem.image">
        <div class="w-full h-40 bg-slate-50 flex items-center justify-center">
          <i class="ri-restaurant-line text-5xl text-slate-200"></i>
        </div>
      </template>

      <div class="px-5 pt-4 pb-6">

        {# Badges #}
        <div class="flex gap-1.5 flex-wrap mb-3" x-show="modalItem && (modalItem.is_vegetarian || modalItem.is_vegan || modalItem.is_spicy)">
          <span x-show="modalItem && modalItem.is_vegetarian"
                class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-green-100 text-green-700">🥦 Végétarien</span>
          <span x-show="modalItem && modalItem.is_vegan"
                class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">🌱 Vegan</span>
          <span x-show="modalItem && modalItem.is_spicy"
                class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-red-100 text-red-700">🌶 Épicé</span>
        </div>

        {# Nom + prix #}
        <h2 class="text-slate-900 font-black text-xl leading-tight" x-text="modalItem && modalItem.name"></h2>
        <div class="flex items-baseline gap-2 mt-1.5">
          <span class="font-black text-lg" style="color: var(--color-primary);"
                x-text="modalItem ? (modalItem.discount_price || modalItem.price) + ' FCFA' : ''"></span>
          <span class="text-slate-300 text-sm line-through" x-show="modalItem && modalItem.discount_price"
                x-text="modalItem ? modalItem.price + ' FCFA' : ''"></span>
        </div>

        {# Temps de préparation #}
        <p class="text-slate-400 text-xs mt-2" x-show="modalItem && modalItem.preparation_time">
          <i class="ri-time-line"></i>
          Préparation : <span x-text="modalItem && modalItem.preparation_time"></span> min
        </p>

        {# Description #}
        <p class="text-slate-500 text-sm leading-relaxed mt-3"
           x-text="modalItem && modalItem.description"
           x-show="modalItem && modalItem.description"></p>

        {# Ingrédients #}
        <div x-show="modalItem && modalItem.ingredients" class="mt-4">
          <h4 class="text-xs font-bold text-slate-700 uppercase tracking-wide mb-1">Ingrédients</h4>
          <p class="text-slate-400 text-xs" x-text="modalItem && modalItem.ingredients"></p>
        </div>

        {# Allergènes #}
        <div x-show="modalItem && modalItem.allergens" class="mt-3 bg-amber-50 border border-amber-100 rounded-xl px-3 py-2.5">
          <p class="text-xs font-semibold text-amber-700">
            <i class="ri-alert-line"></i> Allergènes :
            <span class="font-normal" x-text="modalItem && modalItem.allergens"></span>
          </p>
        </div>

      </div>
    </div>

    {# Footer : bouton ajouter #}
    <div class="px-5 py-4 border-t border-slate-100 flex-shrink-0 bg-white">
      <button @click="$dispatch('add-to-cart', {
                id: modalItem.id,
                name: modalItem.name,
                price: modalItem.discount_price || modalItem.price,
                image: modalItem.image
              }); closeModal();"
              class="w-full py-3.5 rounded-2xl text-white font-bold text-base transition-all active:scale-[0.98]"
              style="background-color: var(--color-primary);">
        Ajouter au panier · <span x-text="modalItem ? (modalItem.discount_price || modalItem.price) + ' FCFA' : ''"></span>
      </button>
    </div>

  </div>
</div>
```

- [ ] **Commit**

```bash
git add templates/customer/menu_detail_modal.html
git commit -m "feat: modern item detail modal with bottom-sheet on mobile"
```

---

## Task 5 — Panier bottom-sheet

**Fichiers :**
- Réécrire : `templates/customer/cart_sidebar.html`

**Objectif :** Drawer panier en bottom-sheet (mobile) / side panel (desktop). Affiche articles, quantité +/-, total, notes, et CTA "Commander".

- [ ] **Réécrire `templates/customer/cart_sidebar.html`**

```html
{# Panier — contrôlé par cartOpen + cartItems dans le x-data parent #}
<div x-show="cartOpen"
     x-cloak
     class="fixed inset-0 z-50 flex items-end sm:items-end sm:justify-end">

  {# Overlay #}
  <div class="absolute inset-0 bg-black/40 backdrop-blur-sm" @click="cartOpen = false"></div>

  {# Panel #}
  <div class="relative bg-white w-full sm:w-96 rounded-t-3xl sm:rounded-t-3xl sm:rounded-b-none overflow-hidden z-10 flex flex-col max-h-[85vh] sm:max-h-screen sm:h-full"
       x-transition:enter="transition ease-out duration-300"
       x-transition:enter-start="translate-y-full sm:translate-y-0 sm:translate-x-full"
       x-transition:enter-end="translate-y-0 sm:translate-x-0"
       x-transition:leave="transition ease-in duration-200"
       x-transition:leave-start="translate-y-0"
       x-transition:leave-end="translate-y-full">

    {# Handle + Header #}
    <div class="flex-shrink-0 px-5 pt-3 pb-4 border-b border-slate-100">
      <div class="flex justify-center mb-3">
        <div class="w-10 h-1 rounded-full bg-slate-200 sm:hidden"></div>
      </div>
      <div class="flex items-center justify-between">
        <h2 class="font-black text-slate-900 text-lg">Mon panier</h2>
        <button @click="cartOpen = false"
                class="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center text-slate-500 hover:bg-slate-200 transition-colors">
          <i class="ri-close-line text-base"></i>
        </button>
      </div>
      <p class="text-slate-400 text-xs mt-0.5" x-text="cartCount + ' article' + (cartCount > 1 ? 's' : '')"></p>
    </div>

    {# Contenu scrollable #}
    <div class="flex-1 overflow-y-auto px-5 py-4 space-y-3">

      {# Vide #}
      <template x-if="cartItems.length === 0">
        <div class="flex flex-col items-center justify-center py-12 text-center">
          <div class="w-16 h-16 rounded-2xl bg-slate-50 flex items-center justify-center mb-4">
            <i class="ri-shopping-bag-line text-2xl text-slate-300"></i>
          </div>
          <p class="text-slate-400 text-sm font-medium">Votre panier est vide</p>
          <p class="text-slate-300 text-xs mt-1">Ajoutez des articles depuis le menu</p>
        </div>
      </template>

      {# Articles #}
      <template x-for="item in cartItems" :key="item.id">
        <div class="flex items-center gap-3 bg-slate-50 rounded-2xl p-3">
          {# Image #}
          <template x-if="item.image">
            <img :src="item.image" :alt="item.name" class="w-14 h-14 rounded-xl object-cover flex-shrink-0">
          </template>
          <template x-if="!item.image">
            <div class="w-14 h-14 rounded-xl bg-white border border-slate-100 flex items-center justify-center flex-shrink-0">
              <i class="ri-restaurant-line text-xl text-slate-200"></i>
            </div>
          </template>

          {# Infos #}
          <div class="flex-1 min-w-0">
            <p class="text-slate-900 font-semibold text-sm truncate" x-text="item.name"></p>
            <p class="font-bold text-sm mt-0.5" style="color: var(--color-primary);"
               x-text="item.price + ' FCFA'"></p>
          </div>

          {# Contrôles quantité #}
          <div class="flex items-center gap-2 flex-shrink-0">
            <button @click="updateQty(item.id, item.quantity - 1)"
                    class="w-7 h-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-500 hover:border-slate-300 transition-colors text-sm">
              <i class="ri-subtract-line"></i>
            </button>
            <span class="font-bold text-slate-900 text-sm min-w-[1.5rem] text-center" x-text="item.quantity"></span>
            <button @click="updateQty(item.id, item.quantity + 1)"
                    class="w-7 h-7 rounded-lg flex items-center justify-center text-white transition-colors text-sm"
                    style="background-color: var(--color-primary);">
              <i class="ri-add-line"></i>
            </button>
          </div>
        </div>
      </template>

    </div>

    {# Footer : notes + total + commander #}
    <div class="flex-shrink-0 px-5 py-4 border-t border-slate-100 space-y-3 bg-white">

      {# Notes (optionnel) #}
      <textarea placeholder="Notes pour le restaurant (optionnel)"
                class="w-full text-sm px-3 py-2.5 border border-slate-200 rounded-xl resize-none focus:outline-none focus:ring-2 focus:border-transparent h-16"
                style="--tw-ring-color: var(--color-primary);"
                id="cart-notes"></textarea>

      {# Total #}
      <div class="flex items-center justify-between">
        <span class="text-slate-500 text-sm">Total</span>
        <span class="font-black text-slate-900 text-lg" x-text="cartTotal + ' FCFA'"></span>
      </div>

      {# Bouton commander #}
      <a :href="cartItems.length > 0 ? '/t/{{ table_token }}/checkout/' : '#'"
         class="block w-full py-3.5 rounded-2xl text-white font-bold text-center text-base transition-all active:scale-[0.98]"
         :class="cartItems.length === 0 ? 'opacity-50 pointer-events-none' : ''"
         style="background-color: var(--color-primary);">
        Commander · <span x-text="cartTotal + ' FCFA'"></span>
      </a>

    </div>
  </div>
</div>

<script>
async function updateQty(itemId, qty) {
  const action = qty <= 0 ? 'remove' : 'update';
  const resp = await fetch(`/t/{{ table_token }}/cart/`, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', 'X-CSRFToken': '{{ csrf_token }}'},
    body: JSON.stringify({action, item_id: itemId, quantity: qty})
  });
  const data = await resp.json();
  const alpine = document.querySelector('[x-data]').__x.$data;
  alpine.cartItems = data.cart;
  alpine.cartCount = data.cart_count;
  alpine.cartTotal = data.cart_total;
}
</script>
```

- [ ] **Vérifier que la view `update_cart` retourne bien le bon JSON**

Dans `customer/views.py`, s'assurer que `update_cart` retourne :

```python
return JsonResponse({
    "cart": cart_items,        # list of dicts with id, name, price, quantity, image, total
    "cart_count": cart_count,
    "cart_total": cart_total,
})
```

- [ ] **Commit**

```bash
git add templates/customer/cart_sidebar.html
git commit -m "feat: modern cart bottom-sheet with quantity controls and order CTA"
```

---

## Task 6 — Checkout page

**Fichiers :**
- Réécrire : `templates/customer/checkout.html`

**Objectif :** Page checkout avec deux colonnes (résumé à gauche, formulaire à droite). Sur mobile : stacked. Design épuré, bouton "Confirmer" prominent.

- [ ] **Lire la view checkout pour connaître le contexte et la méthode POST**

```bash
grep -n "def checkout" "customer/views.py" -A 40
```

- [ ] **Réécrire `templates/customer/checkout.html`**

```html
{% extends "customer/base.html" %}
{% load static %}

{% block content %}
<div class="min-h-screen bg-slate-50">

  {# Header minimal #}
  <header class="bg-white border-b border-slate-100 px-4 h-14 flex items-center gap-3">
    <a href="/t/{{ table_token }}/"
       class="w-8 h-8 rounded-xl bg-slate-100 flex items-center justify-center text-slate-600 hover:bg-slate-200 transition-colors">
      <i class="ri-arrow-left-line text-sm"></i>
    </a>
    <h1 class="font-black text-slate-900 text-base">Finaliser la commande</h1>
  </header>

  <div class="max-w-2xl mx-auto px-4 py-5 space-y-4">

    {# ── RÉCAPITULATIF ─────────────────────────────────── #}
    <div class="bg-white rounded-2xl border border-slate-100 overflow-hidden"
         style="box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
      <div class="px-4 py-3 border-b border-slate-50">
        <h2 class="font-bold text-slate-900 text-sm">Récapitulatif</h2>
      </div>
      <div class="divide-y divide-slate-50">
        {% for item in cart %}
        <div class="flex items-center justify-between px-4 py-3">
          <div class="flex items-center gap-3">
            <span class="w-5 h-5 rounded-md bg-slate-100 text-slate-600 text-[10px] font-bold flex items-center justify-center">{{ item.quantity }}</span>
            <span class="text-slate-700 text-sm font-medium">{{ item.name }}</span>
          </div>
          <span class="text-slate-900 font-semibold text-sm">{{ item.total }} FCFA</span>
        </div>
        {% empty %}
        <p class="text-slate-400 text-sm text-center py-6">Panier vide.</p>
        {% endfor %}
      </div>
      <div class="px-4 py-3 bg-slate-50 flex items-center justify-between border-t border-slate-100">
        <span class="text-slate-500 text-sm font-medium">Total</span>
        <span class="font-black text-slate-900 text-base">{{ cart_total }} FCFA</span>
      </div>
    </div>

    {# ── FORMULAIRE ────────────────────────────────────── #}
    <form method="post" class="bg-white rounded-2xl border border-slate-100 overflow-hidden space-y-0"
          style="box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
      {% csrf_token %}

      <div class="px-4 py-3 border-b border-slate-50">
        <h2 class="font-bold text-slate-900 text-sm">Vos informations</h2>
      </div>

      <div class="px-4 py-4 space-y-3">

        {# Type de commande #}
        <div>
          <label class="text-xs font-semibold text-slate-600 block mb-1.5">Type de commande</label>
          <div class="grid grid-cols-2 gap-2">
            <label class="relative cursor-pointer">
              <input type="radio" name="order_type" value="dine_in" checked class="peer sr-only">
              <div class="border-2 border-slate-200 peer-checked:border-[--color-primary] rounded-xl px-3 py-2.5 text-center transition-all"
                   style="--color-primary: var(--color-primary);">
                <i class="ri-table-line text-base block mb-0.5 text-slate-400 peer-checked:text-theme"></i>
                <span class="text-xs font-semibold text-slate-600">Sur place</span>
              </div>
            </label>
            <label class="relative cursor-pointer">
              <input type="radio" name="order_type" value="takeaway" class="peer sr-only">
              <div class="border-2 border-slate-200 peer-checked:border-[--color-primary] rounded-xl px-3 py-2.5 text-center transition-all">
                <i class="ri-shopping-bag-line text-base block mb-0.5 text-slate-400"></i>
                <span class="text-xs font-semibold text-slate-600">À emporter</span>
              </div>
            </label>
          </div>
        </div>

        {# Nom #}
        <div>
          <label class="text-xs font-semibold text-slate-600 block mb-1.5">Votre prénom <span class="text-red-400">*</span></label>
          <input type="text" name="customer_name" required placeholder="ex: Jean"
                 class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:border-transparent transition-all"
                 style="--tw-ring-color: var(--color-primary);">
        </div>

        {# Téléphone #}
        <div>
          <label class="text-xs font-semibold text-slate-600 block mb-1.5">Téléphone <span class="text-slate-400 font-normal">(optionnel)</span></label>
          <input type="tel" name="customer_phone" placeholder="+229 01 23 45 67"
                 class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:border-transparent transition-all"
                 style="--tw-ring-color: var(--color-primary);">
        </div>

        {# Notes #}
        <div>
          <label class="text-xs font-semibold text-slate-600 block mb-1.5">Notes pour la cuisine <span class="text-slate-400 font-normal">(optionnel)</span></label>
          <textarea name="notes" rows="2" placeholder="Allergie, cuisson, demande spéciale..."
                    class="w-full px-3.5 py-2.5 border border-slate-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:border-transparent transition-all"
                    style="--tw-ring-color: var(--color-primary);"></textarea>
        </div>

      </div>

      {# Bouton submit #}
      <div class="px-4 py-4 border-t border-slate-100">
        <button type="submit"
                class="w-full py-3.5 rounded-2xl text-white font-bold text-base transition-all active:scale-[0.98]"
                style="background-color: var(--color-primary);">
          Confirmer la commande · {{ cart_total }} FCFA
        </button>
      </div>

    </form>

    {# Table info #}
    {% if table %}
    <p class="text-slate-400 text-xs text-center">
      <i class="ri-table-line"></i> Table {{ table.number }} · {{ restaurant.name }}
    </p>
    {% endif %}

  </div>
</div>
{% endblock %}
```

- [ ] **Commit**

```bash
git add templates/customer/checkout.html
git commit -m "feat: modern checkout page with order summary and customer form"
```

---

## Task 7 — Page de confirmation

**Fichiers :**
- Réécrire : `templates/customer/order_confirmation.html`

**Objectif :** Écran succès avec icône de validation, numéro de commande, résumé des articles et un bouton retour au menu.

- [ ] **Lire la view `order_confirmation` pour connaître le contexte**

```bash
grep -n "def order_confirmation" "customer/views.py" -A 20
```

- [ ] **Réécrire `templates/customer/order_confirmation.html`**

```html
{% extends "customer/base.html" %}
{% load static %}

{% block content %}
<div class="min-h-screen bg-slate-50 flex flex-col items-center justify-center px-4 py-12">

  <div class="w-full max-w-sm space-y-4">

    {# Icône succès #}
    <div class="flex justify-center mb-2">
      <div class="w-20 h-20 rounded-3xl flex items-center justify-center"
           style="background-color: var(--color-primary);">
        <i class="ri-check-line text-4xl text-white"></i>
      </div>
    </div>

    {# Titre #}
    <div class="text-center">
      <h1 class="font-black text-slate-900 text-2xl">Commande envoyée !</h1>
      <p class="text-slate-400 text-sm mt-1">La cuisine a bien reçu votre commande.</p>
    </div>

    {# Carte commande #}
    <div class="bg-white rounded-2xl border border-slate-100 overflow-hidden"
         style="box-shadow: 0 4px 16px rgba(0,0,0,0.06);">

      <div class="px-4 py-3 border-b border-slate-50 flex items-center justify-between">
        <h2 class="font-bold text-slate-900 text-sm">Commande #{{ order.order_number|default:order.id }}</h2>
        <span class="text-[10px] font-bold px-2 py-0.5 rounded-full bg-amber-100 text-amber-700">
          {{ order.get_status_display|default:"En attente" }}
        </span>
      </div>

      <div class="divide-y divide-slate-50">
        {% for item in order.items.all %}
        <div class="flex items-center justify-between px-4 py-3">
          <div class="flex items-center gap-2">
            <span class="w-5 h-5 rounded bg-slate-100 text-[10px] font-bold flex items-center justify-center text-slate-500">{{ item.quantity }}</span>
            <span class="text-slate-700 text-sm">{{ item.menu_item.name }}</span>
          </div>
          <span class="text-slate-900 font-semibold text-sm">{{ item.subtotal }} FCFA</span>
        </div>
        {% endfor %}
      </div>

      <div class="px-4 py-3 bg-slate-50 border-t border-slate-100 flex items-center justify-between">
        <span class="text-slate-500 text-sm">Total payé</span>
        <span class="font-black text-slate-900">{{ order.total }} FCFA</span>
      </div>

    </div>

    {# Infos table #}
    {% if order.table %}
    <div class="bg-white rounded-xl border border-slate-100 px-4 py-3 flex items-center gap-3">
      <i class="ri-table-line text-slate-400"></i>
      <div>
        <p class="text-slate-900 font-semibold text-sm">Table {{ order.table.number }}</p>
        <p class="text-slate-400 text-xs">{{ restaurant.name }}</p>
      </div>
    </div>
    {% endif %}

    {# CTA retour au menu #}
    <a href="/t/{{ table_token }}/"
       class="block w-full py-3.5 rounded-2xl text-white font-bold text-center text-base transition-all active:scale-[0.98]"
       style="background-color: var(--color-primary);">
      Retour au menu
    </a>

    <p class="text-slate-400 text-xs text-center">
      Un serveur passera bientôt vous voir.
    </p>

  </div>

</div>
{% endblock %}
```

- [ ] **Commit**

```bash
git add templates/customer/order_confirmation.html
git commit -m "feat: modern order confirmation screen with order details"
```

---

## Task 8 — Vérifications finales et polissage

**Fichiers :**
- Vérifier : `customer/views.py` (contexte complet)
- Vérifier : `base/templatetags/menu_extras.py` (filtres)

- [ ] **S'assurer que la view `client_menu` passe `cart_json` correctement**

```python
# customer/views.py — vérifier ce bloc
cart_items = []
for item_id, item_data in cart.items():
    cart_items.append({
        "id": int(item_id),
        "name": item_data.get("name", ""),
        "price": float(item_data.get("price", 0)),
        "quantity": item_data.get("quantity", 1),
        "image": item_data.get("image", None),
        "total": float(item_data.get("price", 0)) * item_data.get("quantity", 1),
    })

context["cart_json"] = json.dumps(cart_items)
context["cart_total"] = sum(i["total"] for i in cart_items)
context["cart_count"] = sum(i["quantity"] for i in cart_items)
```

- [ ] **S'assurer que `base/templatetags/` a un `__init__.py`**

```bash
touch base/templatetags/__init__.py
```

- [ ] **Tester le parcours complet**

1. Ouvrir `http://la-tables-despoir.localhost:8000/t/6e8a5374-d7d6-403b-9cf2-c9d31d2ad1c9/`
2. Vérifier que la couleur primaire du restaurant s'applique (header, boutons)
3. Cliquer sur un article → modal détail s'ouvre
4. Ajouter au panier → badge count s'incrémente
5. Ouvrir le panier → articles affichés, total correct
6. Cliquer Commander → checkout avec résumé
7. Remplir nom, soumettre → confirmation avec numéro de commande

- [ ] **Commit final**

```bash
git add -A
git commit -m "feat: complete customer menu redesign — modern UI with themed colors, cart and checkout"
```

---

## Notes d'implémentation importantes

### Gestion du CSRF sur les appels AJAX
```javascript
// Tous les fetch AJAX vers Django nécessitent le CSRF token
headers: {
    'Content-Type': 'application/json',
    'X-CSRFToken': document.cookie.match(/csrftoken=([^;]+)/)?.[1] || ''
}
```

### CSS variable `var(--color-primary)` dans Tailwind CDN
Tailwind CDN ne supporte pas les CSS variables dans ses classes utilitaires directement. Utiliser `style="background-color: var(--color-primary);"` plutôt que `class="bg-[var(--color-primary)]"` pour garantir la compatibilité.

### Scrollbar horizontale sur les tabs catégories
```css
/* Ajouter dans base.html */
.scrollbar-none { scrollbar-width: none; }
.scrollbar-none::-webkit-scrollbar { display: none; }
```

### `x-cloak` dans Alpine.js
Ajouter dans `customer/base.html` :
```css
[x-cloak] { display: none !important; }
```
