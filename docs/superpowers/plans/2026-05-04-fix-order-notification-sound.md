# Fix Notification Sonore Nouvelles Commandes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger la sonnerie qui ne se déclenche jamais quand une nouvelle commande arrive, et confirmer que le polling temps réel fonctionne correctement.

**Architecture:** Le système utilise un polling JS (`setInterval`) qui appelle `/orders/check/` toutes les 10-15 secondes. La vue retourne l'ID de la dernière commande. Le bug est que le JS compare `d.new_count` (inexistant dans la réponse) au lieu de `d.latest_order_id` — la condition est donc toujours `undefined > number = false`. Le fix consiste à aligner la clé retournée par la vue avec ce que le JS compare.

**Tech Stack:** Django (views.py), Jinja2/Django templates (HTML+JS vanilla), Audio Web API

---

## Diagnostic — Cause Racine

| Fichier | Ligne | Problème |
|---|---|---|
| `base/views.py` | 77 | Retourne `'id': latest_order_in_db.id` |
| `templates/admin_user/index.html` | 144 | Lit `d.new_count` → toujours `undefined` |
| `templates/admin_user/orders/list_orders.html` | 134 | Lit `d.new_count` → toujours `undefined` |

**Conséquence :** `undefined > 0` est toujours `false` → le son ne joue jamais, la page ne reload jamais.

**La page est-elle en temps réel ?** Oui, via polling. Dashboard : toutes les 15s. Liste commandes : toutes les 10s. C'est suffisant pour un restaurant. Une fois le bug corrigé, tout fonctionnera sans WebSocket.

---

## Fichiers Modifiés

| Fichier | Action | Responsabilité |
|---|---|---|
| `base/views.py:55-90` | Modifier | Renommer `id` → `latest_order_id` dans la réponse JSON |
| `base/views.py:141-217` | Modifier | Ajouter `latest_order_id` au contexte du dashboard |
| `base/views.py:417-434` | Modifier | Ajouter `latest_order_id` au contexte de la liste commandes |
| `templates/admin_user/index.html:134-151` | Modifier | Comparer par ID au lieu de `new_count` |
| `templates/admin_user/orders/list_orders.html:123-141` | Modifier | Comparer par ID au lieu de `new_count` |

---

## Task 1 : Corriger la vue `check_new_orders`

**Files:**
- Modify: `base/views.py:76-88`

- [ ] **Step 1 : Lire la vue actuelle**

  Ouvrir `base/views.py` lignes 55-90 et confirmer que `data` contient la clé `'id'` mais pas `'latest_order_id'`.

- [ ] **Step 2 : Modifier le dictionnaire retourné**

  Dans `base/views.py`, remplacer le bloc `data = { ... }` (lignes 76-85) par :

  ```python
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
  ```

  Et remplacer le bloc `else` (ligne 88) par :

  ```python
  else:
      data = {'latest_order_id': None}
  ```

- [ ] **Step 3 : Vérifier manuellement l'endpoint**

  Lancer le serveur et ouvrir `/orders/check/` dans le navigateur (en étant connecté). La réponse JSON doit contenir `"latest_order_id"` et non `"id"`.

- [ ] **Step 4 : Commit**

  ```bash
  git add base/views.py
  git commit -m "fix: check_new_orders retourne latest_order_id au lieu de id"
  ```

---

## Task 2 : Passer `latest_order_id` au contexte du dashboard

**Files:**
- Modify: `base/views.py:204-215`

- [ ] **Step 1 : Ajouter la requête dans la vue `dashboard`**

  Dans `base/views.py`, juste avant le `context = { ... }` de la vue `dashboard` (ligne 204), ajouter :

  ```python
  latest_order = Order.objects.filter(restaurant=restaurant).order_by('-created_at', '-id').first()
  latest_order_id = latest_order.id if latest_order else None
  ```

- [ ] **Step 2 : Ajouter la clé au contexte**

  Dans le `context` dict (lignes 204-215), ajouter :

  ```python
  "latest_order_id": latest_order_id,
  ```

- [ ] **Step 3 : Commit**

  ```bash
  git add base/views.py
  git commit -m "fix: dashboard passe latest_order_id au template"
  ```

---

## Task 3 : Passer `latest_order_id` au contexte de la liste commandes

**Files:**
- Modify: `base/views.py:417-434`

- [ ] **Step 1 : Ajouter la requête dans la vue `orders_list`**

  Dans `base/views.py`, dans la vue `orders_list`, ajouter avant le `return render(...)` :

  ```python
  latest_order = Order.objects.filter(restaurant=restaurant).order_by('-created_at', '-id').first()
  latest_order_id = latest_order.id if latest_order else None
  ```

- [ ] **Step 2 : Ajouter la clé au contexte du render**

  Modifier le `return render(...)` pour inclure :

  ```python
  return render(request, "admin_user/orders/list_orders.html", {
      "restaurant": restaurant,
      "orders": orders,
      "current_status": status_filter,
      "status_choices": Order.STATUS_CHOICES,
      "pending_count": Order.objects.filter(restaurant=restaurant, status="pending").count(),
      "latest_order_id": latest_order_id,
  })
  ```

- [ ] **Step 3 : Commit**

  ```bash
  git add base/views.py
  git commit -m "fix: orders_list passe latest_order_id au template"
  ```

---

## Task 4 : Corriger le polling JS dans le template Dashboard

**Files:**
- Modify: `templates/admin_user/index.html:134-151`

- [ ] **Step 1 : Remplacer le bloc polling**

  Dans `templates/admin_user/index.html`, remplacer le bloc :

  ```javascript
  // Polling nouvelles commandes (son + refresh)
  const orderSound = new Audio('{% static "sounds/new-order.mp3" %}');
  let lastCount = {{ today_orders|default:0 }};

  async function checkNewOrders() {
    try {
      const r = await fetch('{% url "check_new_orders" %}', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const d = await r.json();
      if (d.new_count > lastCount) {
        orderSound.play().catch(() => {});
        lastCount = d.new_count;
        location.reload();
      }
    } catch(e) {}
  }
  setInterval(checkNewOrders, 15000);
  ```

  Par :

  ```javascript
  // Polling nouvelles commandes (son + refresh)
  const orderSound = new Audio('{% static "sounds/new-order.mp3" %}');
  let lastOrderId = {{ latest_order_id|default:"null" }};

  async function checkNewOrders() {
    try {
      const r = await fetch('{% url "check_new_orders" %}', {
        headers: { 'X-Requested-With': 'XMLHttpRequest' }
      });
      const d = await r.json();
      if (d.latest_order_id && d.latest_order_id !== lastOrderId) {
        orderSound.play().catch(() => {});
        lastOrderId = d.latest_order_id;
        location.reload();
      }
    } catch(e) {}
  }
  setInterval(checkNewOrders, 15000);
  ```

- [ ] **Step 2 : Tester manuellement**

  1. Ouvrir le dashboard admin dans un onglet
  2. Dans un autre onglet/device, passer une commande client via `/t/<token>/`
  3. Attendre max 15 secondes → la sonnerie doit se déclencher et la page se recharger

  > **Note Browser Policy :** Le son ne joue que si l'utilisateur a interagi avec la page au moins une fois (click/tap). C'est une restriction navigateur, pas un bug code.

- [ ] **Step 3 : Commit**

  ```bash
  git add templates/admin_user/index.html
  git commit -m "fix: dashboard polling compare latest_order_id au lieu de new_count inexistant"
  ```

---

## Task 5 : Corriger le polling JS dans le template Liste Commandes

**Files:**
- Modify: `templates/admin_user/orders/list_orders.html:123-141`

- [ ] **Step 1 : Remplacer le bloc polling**

  Dans `templates/admin_user/orders/list_orders.html`, remplacer :

  ```javascript
  <!-- Polling nouvelles commandes -->
  <script>
    const audio = new Audio('{% static "sounds/new-order.mp3" %}');
    let knownCount = {{ pending_count|default:0 }};

    setInterval(async () => {
      try {
        const r = await fetch('{% url "check_new_orders" %}', {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const d = await r.json();
        if (d.new_count > knownCount) {
          audio.play().catch(() => {});
          knownCount = d.new_count;
          location.reload();
        }
      } catch(e) {}
    }, 10000);
  </script>
  ```

  Par :

  ```javascript
  <!-- Polling nouvelles commandes -->
  <script>
    const audio = new Audio('{% static "sounds/new-order.mp3" %}');
    let lastOrderId = {{ latest_order_id|default:"null" }};

    setInterval(async () => {
      try {
        const r = await fetch('{% url "check_new_orders" %}', {
          headers: { 'X-Requested-With': 'XMLHttpRequest' }
        });
        const d = await r.json();
        if (d.latest_order_id && d.latest_order_id !== lastOrderId) {
          audio.play().catch(() => {});
          lastOrderId = d.latest_order_id;
          location.reload();
        }
      } catch(e) {}
    }, 10000);
  </script>
  ```

- [ ] **Step 2 : Tester manuellement**

  1. Ouvrir la page `/orders/` admin
  2. Passer une commande client
  3. Attendre max 10 secondes → sonnerie + reload

- [ ] **Step 3 : Commit**

  ```bash
  git add templates/admin_user/orders/list_orders.html
  git commit -m "fix: orders/list polling compare latest_order_id au lieu de new_count inexistant"
  ```

---

## Self-Review

**Couverture du spec :**
- [x] Sonnerie ne joue pas → corrigée (Tasks 1, 4, 5)
- [x] Page commande en temps réel → confirmée (polling 10s/15s, fonctionnel après fix)

**Scan placeholders :** Aucun TBD ou TODO dans ce plan.

**Cohérence des types :** `latest_order_id` est un entier dans la vue, comparé avec `!==` (strict) en JS — correct car Django serialise en JSON int, JS le reçoit comme number.

**Note sur la politique navigateur :** `audio.play()` est bloqué par les navigateurs modernes si l'utilisateur n'a pas encore interagi avec la page. Le `.catch(() => {})` silences l'erreur. C'est un comportement natif, pas un bug. Pour contourner, l'admin doit cliquer n'importe où sur la page au moins une fois après l'ouverture.
