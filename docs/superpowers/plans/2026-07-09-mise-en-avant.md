# Mise en avant — Implementation Plan (Bloc 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Mettre un plat en avant (menu du jour / vedette / promo) : champs modèle, toggle dashboard + libellé, et section « À la une » + badge vedette sur le menu client. Tous plans.

**Architecture:** App `base` (modèle + vues dashboard) et `customer` (menu). Réutilise `discount_pct`/`first_image_url` (templatetags existants), le pattern de toggle `change_menu_status`, et les badges du menu.

**Tech Stack:** Django, templates + Tailwind + Alpine (déjà en place dans menu.html).

## Global Constraints

- venv shebang cassé → `./env/bin/python3` pour tout.
- Tests : `./env/bin/python3 manage.py test base.test_mise_en_avant -v 2` (nouveau fichier) ; suite complète `./env/bin/python3 manage.py test base --noinput`.
- Aucun gating (tous les plans).
- Réutiliser patterns existants (`@restaurant_required(allowed_roles=['owner','coadmin','cuisinier'])`, `request.restaurant`, `change_menu_status`).
- Monnaie FCFA.
- Helpers de test : `make_user`, `make_restaurant` depuis `base.tests`.

---

### Task 1: Champs modèle is_featured / featured_label

**Files:**
- Modify: `base/models.py` (classe `MenuItem`)
- Create: migration
- Test: `base/test_mise_en_avant.py`

**Interfaces:**
- Produces: `MenuItem.is_featured` (bool), `MenuItem.featured_label` (str).

- [ ] **Step 1: Écrire le test (échec attendu)**

Créer `base/test_mise_en_avant.py` :

```python
from django.test import TestCase
from base.models import Category, MenuItem
from base.tests import make_user, make_restaurant


def make_item(resto, **kw):
    cat = Category.objects.create(restaurant=resto, name="Plats")
    defaults = dict(restaurant=resto, category=cat, name="Riz", price=1500)
    defaults.update(kw)
    return MenuItem.objects.create(**defaults)


class FeaturedFieldsTest(TestCase):
    def test_defaults(self):
        it = make_item(make_restaurant(make_user()))
        self.assertFalse(it.is_featured)
        self.assertEqual(it.featured_label, "")

    def test_can_set_featured(self):
        it = make_item(make_restaurant(make_user()),
                       is_featured=True, featured_label="Menu du jour")
        it.refresh_from_db()
        self.assertTrue(it.is_featured)
        self.assertEqual(it.featured_label, "Menu du jour")
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_mise_en_avant -v 2`
Expected: FAIL (champs inexistants)

- [ ] **Step 3: Ajouter les champs**

Dans `base/models.py`, classe `MenuItem`, après le bloc `# Stock`
(`is_available`, `preparation_time`), ajouter :

```python
    # Mise en avant (menu du jour / vedette / promo)
    is_featured = models.BooleanField(default=False)
    featured_label = models.CharField(max_length=30, blank=True, default='')
```

- [ ] **Step 4: Migration + migrate**

```bash
./env/bin/python3 manage.py makemigrations base
./env/bin/python3 manage.py migrate
```

- [ ] **Step 5: Lancer (succès)**

Run: `./env/bin/python3 manage.py test base.test_mise_en_avant -v 2`
Expected: PASS (2)

- [ ] **Step 6: Commit**

```bash
git add base/models.py base/migrations/ base/test_mise_en_avant.py
git commit -m "feat: champs MenuItem is_featured / featured_label (mise en avant)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Toggle featured (dashboard) + libellé dans l'édition

**Files:**
- Modify: `base/views.py` (nouvelle vue `change_menu_featured` ; `menu_update` pour `featured_label`)
- Modify: `base/urls.py` (route toggle)
- Modify: `templates/admin_user/menus/list_menu.html` (bouton toggle)
- Modify: `templates/admin_user/menus/update_menu.html` (champ libellé)
- Test: `base/test_mise_en_avant.py`

**Interfaces:**
- Consumes: `MenuItem.is_featured`, `featured_label`.
- Produces: URL `menu_toggle_featured` (`menus/<int:pk>/toggle-featured/`).

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_mise_en_avant.py` :

```python
from django.urls import reverse


class FeaturedToggleTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.item = make_item(self.resto)
        self.client.force_login(self.owner)

    def _host(self):
        return {"HTTP_HOST": f"{self.resto.subdomain}.localhost"}

    def test_toggle_featured_flips_flag(self):
        self.assertFalse(self.item.is_featured)
        resp = self.client.get(
            reverse("menu_toggle_featured", args=[self.item.pk]), **self._host())
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_featured)

    def test_update_saves_featured_label(self):
        resp = self.client.post(
            reverse("menu_update", args=[self.item.pk]),
            {"name": "Riz", "price": "1500", "description": "",
             "featured_label": "Coup de cœur"}, **self._host())
        self.item.refresh_from_db()
        self.assertEqual(self.item.featured_label, "Coup de cœur")
```

Note multi-tenant : si `.localhost` ne résout pas `request.restaurant`, aligner
`_host()` sur le pattern des tests dashboard qui passent (voir
`base/test_parcours.py` / `base/test_imagegen.py`). Ne pas bloquer : skip
documenté + vérif manuelle en dernier recours.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_mise_en_avant.FeaturedToggleTest -v 2`
Expected: FAIL (URL inexistante)

- [ ] **Step 3: Ajouter la vue toggle**

Dans `base/views.py`, juste après `change_menu_status`, ajouter :

```python
@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def change_menu_featured(request, pk):
    restaurant = request.restaurant
    menu_item = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)
    menu_item.is_featured = not menu_item.is_featured
    menu_item.save(update_fields=["is_featured"])
    return redirect("menus_list")
```

- [ ] **Step 4: Persister featured_label dans menu_update**

Dans `menu_update`, dans le bloc `if request.method == "POST":`, après
`menu_item.description = request.POST.get("description")`, ajouter :

```python
        menu_item.featured_label = request.POST.get("featured_label", "").strip()
```

- [ ] **Step 5: Ajouter la route**

Dans `base/urls.py`, après la ligne `menu_toggle_availability`, ajouter (et
importer `change_menu_featured`) :

```python
    path("menus/<int:pk>/toggle-featured/", change_menu_featured, name="menu_toggle_featured"),
```

- [ ] **Step 6: Bouton toggle dans list_menu.html**

Dans `templates/admin_user/menus/list_menu.html`, à côté du bouton
« disponibilité » (autour des lignes 127-133), ajouter un lien-bouton toggle :

```html
                <a href="{% url 'menu_toggle_featured' item.id %}"
                   title="{% if item.is_featured %}Retirer de la une{% else %}Mettre à la une{% endif %}"
                   class="inline-flex items-center gap-1 px-2 py-1 rounded-lg text-xs font-semibold
                          {% if item.is_featured %}bg-amber-100 text-amber-700{% else %}bg-slate-50 text-slate-500 hover:bg-amber-50 hover:text-amber-600{% endif %}">
                  <i class="ri-star-{% if item.is_featured %}fill{% else %}line{% endif %} text-sm"></i>
                  <span class="hidden sm:inline">{% if item.is_featured %}À la une{% else %}Vedette{% endif %}</span>
                </a>
```

- [ ] **Step 7: Champ libellé dans update_menu.html**

Dans `templates/admin_user/menus/update_menu.html`, dans le formulaire (près du
champ description), ajouter :

```html
        <div>
          <label class="block text-sm font-medium text-slate-700 mb-1">Libellé « à la une » (optionnel)</label>
          <input type="text" name="featured_label" maxlength="30"
                 value="{{ menu_item.featured_label }}"
                 placeholder="ex : Menu du jour, Coup de cœur, Promo"
                 class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
          <p class="text-xs text-slate-400 mt-1">Affiché sur la carte du plat mis à la une.</p>
        </div>
```

- [ ] **Step 8: Lancer les tests (succès)**

Run: `./env/bin/python3 manage.py test base.test_mise_en_avant.FeaturedToggleTest -v 2`
Expected: PASS (2, ou skip documenté si multi-tenant)

- [ ] **Step 9: Commit**

```bash
git add base/views.py base/urls.py templates/admin_user/menus/list_menu.html templates/admin_user/menus/update_menu.html base/test_mise_en_avant.py
git commit -m "feat: toggle 'à la une' (dashboard) + libellé vedette dans l'édition du plat

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Menu client — section « À la une » + badge vedette

**Files:**
- Modify: `customer/views.py` (`client_menu` — contexte `featured_items`, `featured_ids`)
- Modify: `templates/customer/menu.html` (section À la une + badge)
- Test: `base/test_mise_en_avant.py`

**Interfaces:**
- Consumes: `MenuItem.is_featured`, `featured_label`, filtres `discount_pct`, `first_image_url`.

- [ ] **Step 1: Écrire le test (échec attendu)**

Ajouter à `base/test_mise_en_avant.py` :

```python
from base.models import Table


class ClientMenuFeaturedContextTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.table = Table.objects.create(restaurant=self.resto, number=1)

    def _host(self):
        return {"HTTP_HOST": f"{self.resto.subdomain}.localhost"}

    def test_featured_available_item_in_context(self):
        feat = make_item(self.resto, name="Vedette", is_featured=True)
        # plat vedette mais indisponible → exclu
        make_item(self.resto, name="Caché", is_featured=True, is_available=False)
        resp = self.client.get(
            reverse("client_menu", args=[self.table.token]), **self._host())
        self.assertEqual(resp.status_code, 200)
        featured = list(resp.context["featured_items"])
        self.assertIn(feat, featured)
        self.assertEqual(len(featured), 1)
        self.assertIn(feat.id, resp.context["featured_ids"])
```

Note : aligner `_host()` sur le pattern qui résout `request`/restaurant dans les
tests existants si `.localhost` ne suffit pas.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_mise_en_avant.ClientMenuFeaturedContextTest -v 2`
Expected: FAIL (`featured_items` absent du contexte)

- [ ] **Step 3: Contexte dans client_menu**

Dans `customer/views.py`, vue `client_menu`, avant le `context = {…}` final,
ajouter :

```python
    featured_items = list(
        MenuItem.objects.filter(
            restaurant=restaurant, is_available=True, is_featured=True
        ).order_by("order", "name")[:6]
    )
    featured_ids = {it.id for it in featured_items}
```

Puis ajouter au dict `context` :

```python
        "featured_items": featured_items,
        "featured_ids": featured_ids,
```

- [ ] **Step 4: Section « À la une » dans menu.html**

Dans `templates/customer/menu.html`, juste AVANT la boucle des catégories
(`{% for category in categories %}` autour de la ligne 149), insérer :

```html
{% load menu_extras %}
{% if featured_items %}
<section class="mb-5">
  <div class="flex items-center gap-2 mb-3">
    <i class="ri-star-fill text-amber-400"></i>
    <h2 class="text-slate-900 font-black text-base">À la une</h2>
  </div>
  <div class="flex gap-3 overflow-x-auto pb-1 -mx-1 px-1">
    {% for item in featured_items %}
    {% with thumb=item|first_image_url pct=item|discount_pct %}
    <div class="flex-shrink-0 w-40 rounded-2xl overflow-hidden bg-white shadow-sm border border-amber-100 cursor-pointer"
         @click="openModal({{ item|item_json }})">
      <div class="relative h-28 bg-slate-100">
        {% if thumb %}
        <img src="{{ thumb }}" alt="{{ item.name }}" loading="lazy" class="w-full h-full object-cover" />
        {% endif %}
        <div class="absolute top-2 left-2 flex items-center gap-1 flex-wrap">
          <span class="text-[10px] font-black px-1.5 py-0.5 rounded-full bg-amber-400 text-white shadow-sm">
            {{ item.featured_label|default:"À la une" }}
          </span>
          {% if pct %}
          <span class="text-[10px] font-black px-1.5 py-0.5 rounded-full text-white shadow-sm bg-red-500">-{{ pct }}%</span>
          {% endif %}
        </div>
      </div>
      <div class="px-2.5 py-2">
        <h3 class="font-bold text-slate-900 text-sm leading-snug truncate">{{ item.name }}</h3>
        <p class="text-primary font-black text-sm mt-0.5">
          {% if item.discount_price %}{{ item.discount_price|floatformat:0 }}{% else %}{{ item.price|floatformat:0 }}{% endif %} FCFA
        </p>
      </div>
    </div>
    {% endwith %}
    {% endfor %}
  </div>
</section>
{% endif %}
```

(Si `{% load menu_extras %}` est déjà chargé en haut du template, ne pas le
redoubler — le placer une seule fois en tête du fichier.)

- [ ] **Step 5: Badge « Vedette » dans la carte catégorie**

Dans `templates/customer/menu.html`, dans le bloc de badges sur l'image
(là où figure `{% if item.id in popular_ids %}` … « Populaire »), ajouter juste
avant le badge Populaire :

```html
              {% if item.id in featured_ids %}
              <span class="inline-flex items-center gap-1 text-[10px] font-black px-1.5 py-0.5 rounded-full bg-amber-400 text-white shadow-sm">
                <i class="ri-star-fill"></i>Vedette
              </span>
              {% endif %}
```

- [ ] **Step 6: Lancer les tests (succès) + non-régression**

Run: `./env/bin/python3 manage.py test base.test_mise_en_avant -v 2`
Expected: PASS (tous)
Puis : `./env/bin/python3 manage.py test base --noinput` → aucune régression.

- [ ] **Step 7: Commit**

```bash
git add customer/views.py templates/customer/menu.html base/test_mise_en_avant.py
git commit -m "feat: menu client — section 'À la une' + badge vedette

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (couverture spec)

- **Champs is_featured / featured_label** → Task 1. ✅
- **Toggle dashboard + libellé édition** → Task 2. ✅
- **Section À la une + badge vedette (client)** → Task 3. ✅
- **Réutilise discount_pct / first_image_url / pattern toggle** → Tasks 2-3. ✅
- **Tous plans (aucun gating)** → aucune garde ajoutée. ✅
- **Exclusion des vedettes indisponibles** → Task 3 (filtre `is_available=True` + test). ✅

**À surveiller :** résolution multi-tenant dans les tests de vues (Tasks 2-3) — aligner `_host()` sur le pattern des tests dashboard qui passent ; nom du bloc `item_json`/`openModal` déjà utilisés dans menu.html (réutilisés tels quels).
