# Customer Feature Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corriger le flux complet client : ajout panier → sidebar → checkout → confirmation fonctionne sans rechargement de page.

**Architecture:** La session Django est la source de vérité pour le panier côté serveur. Alpine.js (`cartStore()` dans `base.html`) est la source de vérité côté client et synchronise via POST JSON vers `/t/<token>/cart/`. Le checkout lit la session et crée la commande.

**Tech Stack:** Django 4.x, Alpine.js 3.14, session Django (server-side cart), localStorage (client-side cart backup), Tailwind CSS.

---

## Root Cause Analysis

| # | Bug | Fichier | Ligne | Impact |
|---|-----|---------|-------|--------|
| 1 | `syncCartToServer()` envoie `{cart:[...]}` mais la vue attend `{action, item_id}` | `customer/views.py` | 79-115 | Session cart toujours vide → checkout redirige au menu |
| 2 | `{{ item.id }}` est un int JS mais Django stocke les clés en string | `customer/views.py` + `base.html` | — | `cart.find(i => i.id === item.id)` avec `"12" === 12` échoue silencieusement |
| 3 | `Order.objects.create()` n'inclut pas `customer_name`, `customer_phone`, `notes` | `customer/views.py` | 152-157 | Champs toujours vides en base |
| 4 | Pas de try/except autour de `MenuItem.objects.get()` dans `update_cart` | `customer/views.py` | 87-91 | Crash 500 si article indisponible |

---

## Fichiers à modifier

| Fichier | Rôle |
|---------|------|
| `customer/views.py` | Fix `update_cart` (format full-cart + try/except) + Fix `checkout` (customer fields) |
| `templates/customer/base.html` | Fix `cartStore().addToCart` (normalisation ID string) |

---

### Task 1 — Fix `update_cart` : accepter le format full-cart

**Fichier :** `customer/views.py` lignes 70-129

**Problème :** `syncCartToServer()` dans `cartStore()` envoie `{"cart": [{id, name, price, image, quantity}, ...]}`.
La vue lit `data.get("action")` qui est `None` → aucune branche if ne correspond → session jamais mise à jour.

- [ ] **Step 1 : Tester manuellement que le panier est vide en session**

```bash
# Ouvrir le menu, ajouter un article, puis :
curl -s http://le-festival-des-rois.localhost:8000/t/1b7632b9-3e2c-42f3-946a-09fd57fb5ffb/ \
  | python3 -c "import sys,re; print(re.findall(r'_cartInit\s*=\s*(\[.*?\]);', sys.stdin.read()))"
# Résultat attendu : _cartInit = [] (session vide)
```

- [ ] **Step 2 : Remplacer la vue `update_cart` dans `customer/views.py`**

```python
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
```

- [ ] **Step 3 : Vérifier Django ne crash pas**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py check
```
Résultat attendu : `System check identified no issues (0 silenced).`

---

### Task 2 — Fix IDs : normaliser en string partout

**Fichier :** `templates/customer/base.html` dans `cartStore()`

**Problème :** `{{ item.id }}` dans le template Django produit un entier JS (`12`), mais `_cartInit` reçoit des IDs string (`"12"`) depuis `json.dumps()`. `cart.find(i => i.id === "12")` échoue si `id` vaut `12`.

- [ ] **Step 1 : Modifier `addToCart` dans `cartStore()` pour normaliser l'ID**

Dans `templates/customer/base.html`, dans la fonction `cartStore()`, remplacer :

```javascript
addToCart(idOrItem, name, price, image) {
  const item = (idOrItem !== null && typeof idOrItem === 'object')
    ? idOrItem
    : { id: idOrItem, name, price, image };
  const ex = this.cart.find(i => i.id === item.id);
  if (ex) { ex.quantity += 1; this.cart = [...this.cart]; }
  else { this.cart = [...this.cart, { ...item, quantity: 1 }]; }
  this.syncCartToServer();
},
```

Par :

```javascript
addToCart(idOrItem, name, price, image) {
  const raw = (idOrItem !== null && typeof idOrItem === 'object')
    ? idOrItem
    : { id: idOrItem, name, price, image };
  const item = { ...raw, id: String(raw.id) };
  const ex = this.cart.find(i => String(i.id) === item.id);
  if (ex) { ex.quantity += 1; this.cart = [...this.cart]; }
  else { this.cart = [...this.cart, item]; }
  this.syncCartToServer();
},
```

- [ ] **Step 2 : Normaliser aussi `updateQty` et `removeFromCart`**

```javascript
updateQty(itemId, qty) {
  const id = String(itemId);
  if (qty <= 0) { this.cart = this.cart.filter(i => String(i.id) !== id); }
  else { this.cart = this.cart.map(i => String(i.id) === id ? { ...i, quantity: qty } : i); }
  this.syncCartToServer();
},
removeFromCart(itemId) {
  const id = String(itemId);
  this.cart = this.cart.filter(i => String(i.id) !== id);
  this.syncCartToServer();
},
```

---

### Task 3 — Fix `checkout` : sauvegarder les champs client

**Fichier :** `customer/views.py` ligne 152

**Problème :** Le formulaire envoie `customer_name`, `customer_phone`, `notes` mais la vue ne les passe pas à `Order.objects.create()`.

- [ ] **Step 1 : Modifier `Order.objects.create()` dans `checkout`**

Remplacer :

```python
order = Order.objects.create(
    restaurant=restaurant,
    table=table,
    order_type="dine_in",
    status="pending"
)
```

Par :

```python
order = Order.objects.create(
    restaurant=restaurant,
    table=table,
    order_type="dine_in",
    status="pending",
    customer_name=request.POST.get("customer_name", "").strip(),
    customer_phone=request.POST.get("customer_phone", "").strip(),
    notes=request.POST.get("notes", "").strip(),
)
```

---

### Task 4 — Test du flux complet

- [ ] **Step 1 : Démarrer le serveur**

```bash
cd "/home/jey/Documents/projet /OpendFood" && python manage.py runserver
```

- [ ] **Step 2 : Ouvrir le menu client**

URL : `http://le-festival-des-rois.localhost:8000/t/1b7632b9-3e2c-42f3-946a-09fd57fb5ffb/`

- [ ] **Step 3 : Vérifier l'ajout au panier**
  - Cliquer sur `+` d'un article
  - FAB "Voir mon panier" doit apparaître avec le count
  - Ouvrir le sidebar : l'article doit y être listé
  - Ouvrir DevTools → Network → chercher la requête POST vers `/cart/` → réponse `{"success": true}`

- [ ] **Step 4 : Vérifier que `_cartInit` est rempli au rechargement**

Recharger la page menu → inspecter le HTML source → `var _cartInit = [{...}]` doit contenir les articles.

- [ ] **Step 5 : Tester le checkout**
  - Cliquer "Commander" dans le sidebar
  - Page `/checkout/` doit afficher les articles et le total
  - Remplir le prénom et soumettre
  - Doit rediriger vers `/order/<id>/confirmation/`

- [ ] **Step 6 : Vérifier la commande en admin**

```
http://localhost:8000/admin/base/order/
```

La commande doit avoir `customer_name` renseigné et les items corrects.

- [ ] **Step 7 : Vérifier que le panier est vidé après confirmation**

Revenir sur la page menu → FAB ne doit pas apparaître → panier vide.

---

## Checklist de vérification finale

- [ ] Ajout article → requête AJAX `/cart/` retourne `success: true`
- [ ] Session Django contient le panier après ajout
- [ ] `_cartInit` n'est plus `[]` au rechargement de la page menu
- [ ] Sidebar affiche les articles et les quantités correctes
- [ ] Bouton "Commander" mène au checkout (pas au menu)
- [ ] Checkout affiche le bon récapitulatif
- [ ] Soumission checkout crée la commande avec `customer_name`
- [ ] Confirmation affiche le numéro de commande et le total
- [ ] localStorage est vidé sur la page confirmation
- [ ] Aucune erreur console Alpine.js
