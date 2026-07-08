# Parcours de commande & après-commande — Plan d'implémentation (Bloc 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rendre le téléphone client fiable (E.164 + indicatif pays), et transformer la page de succès en levier de rétention (invite WhatsApp, avis Google, retour privé), avec un onglet dashboard pour les retours.

**Architecture:** Django (apps `base` + `customer`). Nouveau service isolé de normalisation téléphone (`base/services/phone.py`), deux champs sur `Restaurant`, un modèle `CustomerFeedback`, et des ajouts ciblés aux vues/templates du parcours client et du dashboard. Gating Pro/Max via le helper existant `get_effective_plan`.

**Tech Stack:** Django, PostgreSQL/SQLite, `phonenumbers` (nouvelle dépendance), Web Push existant (`base/push.py`), templates Django + Tailwind.

## Global Constraints

- Python/Django : suivre les patterns existants du repo (vues fonctions, `request.restaurant` via middleware, décorateurs `@restaurant_required` / `@owner_or_coadmin_required`).
- Tests : Django `TestCase` dans `base/tests.py` (ou nouveau fichier `base/test_parcours.py`), helpers existants `make_user`, `make_restaurant`.
- Lancer les tests avec : `python manage.py test` (venv `./env`).
- Gating Pro : `get_effective_plan(restaurant).plan_type in ('pro','max')` — exposé via `Restaurant.is_pro()`.
- Téléphone stocké en **E.164** (`+229...`).
- Commits fréquents, un par tâche minimum.
- Monnaie affichée : FCFA (cohérent avec l'existant).

---

### Task 1: Service de normalisation téléphone

**Files:**
- Modify: `requirements.txt` (ajouter `phonenumbers`)
- Create: `base/services/phone.py`
- Test: `base/test_parcours.py`

**Interfaces:**
- Produces:
  - `base.services.phone.COUNTRIES` — liste ordonnée de dicts `{"iso2": str, "dial": str, "label": str, "example": str}`, Bénin en premier.
  - `base.services.phone.normalize(raw: str, country_iso2: str) -> str` — retourne le E.164, lève `ValueError` si invalide/vide.
  - `base.services.phone.is_valid(raw: str, country_iso2: str) -> bool`.

- [ ] **Step 1: Ajouter la dépendance**

Dans `requirements.txt`, ajouter une ligne :

```
phonenumbers
```

Puis installer : `./env/bin/pip install phonenumbers`

- [ ] **Step 2: Écrire les tests (échec attendu)**

Créer `base/test_parcours.py` :

```python
from django.test import TestCase
from base.services import phone


class PhoneNormalizeTest(TestCase):
    def test_benin_local_number_normalizes_to_e164(self):
        # Bénin : numéros à 10 chiffres depuis 2023 (préfixe 01)
        self.assertEqual(phone.normalize("0197000000", "BJ"), "+2290197000000")

    def test_number_with_plus_prefix_is_accepted(self):
        self.assertEqual(phone.normalize("+2290197000000", "BJ"), "+2290197000000")

    def test_france_number(self):
        self.assertEqual(phone.normalize("0612345678", "FR"), "+33612345678")

    def test_invalid_number_raises(self):
        with self.assertRaises(ValueError):
            phone.normalize("123", "BJ")

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            phone.normalize("", "BJ")

    def test_is_valid_wrapper(self):
        self.assertTrue(phone.is_valid("0197000000", "BJ"))
        self.assertFalse(phone.is_valid("123", "BJ"))

    def test_countries_benin_first(self):
        self.assertEqual(phone.COUNTRIES[0]["iso2"], "BJ")
        self.assertEqual(phone.COUNTRIES[0]["dial"], "+229")
```

- [ ] **Step 3: Lancer les tests (échec attendu)**

Run: `python manage.py test base.test_parcours -v 2`
Expected: FAIL (module `base.services.phone` introuvable)

- [ ] **Step 4: Implémenter le service**

Créer `base/services/phone.py` :

```python
"""Normalisation et validation des numéros de téléphone client (E.164)."""
import phonenumbers

# Liste courte : Afrique de l'Ouest + France. Bénin par défaut (premier).
COUNTRIES = [
    {"iso2": "BJ", "dial": "+229", "label": "Bénin",          "example": "01 97 00 00 00"},
    {"iso2": "TG", "dial": "+228", "label": "Togo",           "example": "90 00 00 00"},
    {"iso2": "CI", "dial": "+225", "label": "Côte d'Ivoire",  "example": "01 23 45 67 89"},
    {"iso2": "NG", "dial": "+234", "label": "Nigéria",        "example": "0801 234 5678"},
    {"iso2": "GH", "dial": "+233", "label": "Ghana",          "example": "024 000 0000"},
    {"iso2": "SN", "dial": "+221", "label": "Sénégal",        "example": "70 000 00 00"},
    {"iso2": "BF", "dial": "+226", "label": "Burkina Faso",   "example": "70 00 00 00"},
    {"iso2": "ML", "dial": "+223", "label": "Mali",           "example": "70 00 00 00"},
    {"iso2": "NE", "dial": "+227", "label": "Niger",          "example": "90 00 00 00"},
    {"iso2": "FR", "dial": "+33",  "label": "France",         "example": "06 12 34 56 78"},
]

_VALID_ISO2 = {c["iso2"] for c in COUNTRIES}


def normalize(raw, country_iso2):
    """Retourne le numéro au format E.164, lève ValueError si invalide."""
    raw = (raw or "").strip()
    if not raw:
        raise ValueError("Numéro de téléphone requis")
    region = country_iso2 if country_iso2 in _VALID_ISO2 else "BJ"
    try:
        num = phonenumbers.parse(raw, region)
    except phonenumbers.NumberParseException as exc:
        raise ValueError("Numéro de téléphone invalide") from exc
    if not phonenumbers.is_valid_number(num):
        raise ValueError("Numéro de téléphone invalide")
    return phonenumbers.format_number(num, phonenumbers.PhoneNumberFormat.E164)


def is_valid(raw, country_iso2):
    try:
        normalize(raw, country_iso2)
        return True
    except ValueError:
        return False
```

- [ ] **Step 5: Lancer les tests (succès attendu)**

Run: `python manage.py test base.test_parcours -v 2`
Expected: PASS (7 tests)

- [ ] **Step 6: Commit**

```bash
git add requirements.txt base/services/phone.py base/test_parcours.py
git commit -m "feat: service de normalisation téléphone E.164 (phonenumbers)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Modèles — champs Restaurant, CustomerFeedback, helper is_pro

**Files:**
- Modify: `base/models.py` (classe `Restaurant` ; nouveau modèle `CustomerFeedback`)
- Create: migration via `makemigrations`
- Test: `base/test_parcours.py`

**Interfaces:**
- Produces:
  - `Restaurant.whatsapp_community_url` (URLField), `Restaurant.google_place_id` (CharField).
  - `Restaurant.is_pro() -> bool`.
  - `Restaurant.google_review_url` (property) -> str ("" si pas de place id).
  - `base.models.CustomerFeedback` (champs : `restaurant`, `order`, `rating`, `message`, `phone`, `is_read`, `created_at`).

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_parcours.py` :

```python
from django.utils import timezone
from datetime import timedelta
from base.models import Restaurant, SubscriptionPlan, Order, CustomerFeedback
from base.tests import make_user, make_restaurant


def make_pro_plan():
    return SubscriptionPlan.objects.create(
        name="Pro", plan_type="pro", price=5000, remove_branding=True)


class RestaurantProAndReviewTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())

    def test_is_pro_false_by_default(self):
        self.assertFalse(self.resto.is_pro())

    def test_is_pro_true_with_active_pro_plan(self):
        self.resto.subscription_plan = make_pro_plan()
        self.resto.subscription_end = timezone.now() + timedelta(days=10)
        self.resto.save()
        self.assertTrue(self.resto.is_pro())

    def test_google_review_url_empty_without_place_id(self):
        self.assertEqual(self.resto.google_review_url, "")

    def test_google_review_url_built_from_place_id(self):
        self.resto.google_place_id = "ChIJ_test"
        self.assertIn("ChIJ_test", self.resto.google_review_url)
        self.assertIn("writereview", self.resto.google_review_url)


class CustomerFeedbackModelTest(TestCase):
    def test_create_feedback(self):
        resto = make_restaurant(make_user())
        order = Order.objects.create(restaurant=resto, customer_phone="+2290197000000")
        fb = CustomerFeedback.objects.create(
            restaurant=resto, order=order, rating=4,
            message="Très bon", phone="+2290197000000")
        self.assertFalse(fb.is_read)
        self.assertEqual(resto.feedbacks.count(), 1)
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `python manage.py test base.test_parcours.RestaurantProAndReviewTest base.test_parcours.CustomerFeedbackModelTest -v 2`
Expected: FAIL (`is_pro`, `google_review_url`, `CustomerFeedback` inexistants)

- [ ] **Step 3: Ajouter les champs et le helper à Restaurant**

Dans `base/models.py`, classe `Restaurant`, après le bloc `# Customization` (champs `primary_color`/`secondary_color`), ajouter :

```python
    # Communauté & avis (bloc rétention — offre Pro)
    whatsapp_community_url = models.URLField(blank=True, default='')
    google_place_id = models.CharField(max_length=255, blank=True, default='')
```

Puis, dans la même classe, après la méthode `hide_branding`, ajouter :

```python
    def is_pro(self):
        """Vrai si le plan effectif est Pro ou Max."""
        from base.services.subscription import get_effective_plan
        plan = get_effective_plan(self)
        return bool(plan and plan.plan_type in ('pro', 'max'))

    @property
    def google_review_url(self):
        if not self.google_place_id:
            return ''
        return (
            "https://search.google.com/local/writereview?placeid="
            + self.google_place_id
        )
```

- [ ] **Step 4: Ajouter le modèle CustomerFeedback**

Dans `base/models.py`, à la fin du fichier (après `ActivityLog`), ajouter :

```python
class CustomerFeedback(models.Model):
    """Retour privé d'un client (canal 'un souci ?' de la page de succès)."""
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='feedbacks')
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='feedbacks')
    rating = models.PositiveSmallIntegerField(null=True, blank=True)
    message = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Feedback {self.restaurant.name} ({self.rating or '—'})"
```

- [ ] **Step 5: Générer et appliquer la migration**

Run:
```bash
python manage.py makemigrations base
python manage.py migrate
```
Expected: nouvelle migration créée (champs Restaurant + modèle CustomerFeedback), migrate OK.

- [ ] **Step 6: Lancer les tests (succès attendu)**

Run: `python manage.py test base.test_parcours -v 2`
Expected: PASS (tous)

- [ ] **Step 7: Commit**

```bash
git add base/models.py base/migrations/ base/test_parcours.py
git commit -m "feat: champs Restaurant (WhatsApp/Place ID), helper is_pro, modèle CustomerFeedback

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Checkout — indicatif pays, téléphone obligatoire, stockage E.164

**Files:**
- Modify: `customer/views.py` (vue `checkout`, création de commande)
- Modify: `templates/customer/checkout.html` (champ téléphone)
- Test: `base/test_parcours.py`

**Interfaces:**
- Consumes: `base.services.phone.normalize`, `phone.COUNTRIES`.
- Produces: la commande créée a `customer_phone` en E.164 ; POST invalide → pas de commande, formulaire ré-affiché avec erreur.

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_parcours.py` :

```python
from django.urls import reverse
from base.models import MenuItem, Category, Table


class CheckoutPhoneTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.table = Table.objects.create(restaurant=self.resto, number=1)
        cat = Category.objects.create(restaurant=self.resto, name="Plats")
        self.item = MenuItem.objects.create(
            restaurant=self.resto, category=cat, name="Riz", price=1500)

    def _seed_cart(self, client):
        session = client.session
        session[f"cart_{self.table.token}"] = {
            str(self.item.id): {"name": "Riz", "price": "1500", "quantity": 1, "image": None}
        }
        session.save()

    def test_valid_phone_creates_order_in_e164(self):
        c = self.client
        self._seed_cart(c)
        resp = c.post(
            reverse("checkout", args=[self.table.token]),
            {"order_type": "dine_in", "customer_name": "Ali",
             "phone_country": "BJ", "customer_phone": "0197000000"},
        )
        self.assertEqual(resp.status_code, 302)
        order = Order.objects.get(restaurant=self.resto)
        self.assertEqual(order.customer_phone, "+2290197000000")

    def test_invalid_phone_does_not_create_order(self):
        c = self.client
        self._seed_cart(c)
        resp = c.post(
            reverse("checkout", args=[self.table.token]),
            {"order_type": "dine_in", "customer_name": "Ali",
             "phone_country": "BJ", "customer_phone": "123"},
        )
        self.assertEqual(resp.status_code, 200)  # ré-affiche le form
        self.assertFalse(Order.objects.filter(restaurant=self.resto).exists())
```

Note : si `Table` n'a pas de champ `token` auto-généré, adapter le seed avec l'attribut réel (vérifier `base/models.py` classe `Table`). Le nom d'URL du checkout est `checkout` et prend `table_token`.

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `python manage.py test base.test_parcours.CheckoutPhoneTest -v 2`
Expected: FAIL (téléphone pas normalisé / commande créée malgré numéro invalide)

- [ ] **Step 3: Modifier la vue checkout**

Dans `customer/views.py`, vue `checkout`, dans le bloc `if request.method == "POST":` (autour de la ligne 232), AVANT `with transaction.atomic():`, insérer la validation :

```python
        from base.services import phone as phone_service
        phone_country = request.POST.get("phone_country", "BJ").strip() or "BJ"
        raw_phone = request.POST.get("customer_phone", "").strip()
        try:
            customer_phone = phone_service.normalize(raw_phone, phone_country)
        except ValueError:
            messages.error(request, "Numéro de téléphone invalide.")
            # on retombe sur le rendu du formulaire en bas de la vue
            customer_phone = None
```

Puis remplacer, dans `Order.objects.create(...)`, la ligne :

```python
                customer_phone=request.POST.get("customer_phone", "").strip(),
```

par :

```python
                customer_phone=customer_phone,
```

Et englober la création dans une garde : juste après le `try/except` ci-dessus, si `customer_phone` est valide, exécuter le `with transaction.atomic():` existant ; sinon sauter au rendu du formulaire. Concrètement, envelopper le bloc existant :

```python
        if customer_phone:
            with transaction.atomic():
                order = Order.objects.create(
                    ...
                )
                ...
                return redirect("order_confirmation", public_token=order.public_token)
        # sinon : on continue vers le rendu du formulaire (contexte ci-dessous)
```

- [ ] **Step 4: Passer la liste des pays au template**

Toujours dans `checkout`, dans le `context` du `return render(request, "customer/checkout.html", {...})` final, ajouter :

```python
        "phone_countries": phone_service.COUNTRIES,
```

(importer `from base.services import phone as phone_service` en haut de la fonction si pas déjà fait à l'étape 3 — l'import local suffit.)

- [ ] **Step 5: Modifier le template checkout**

Dans `templates/customer/checkout.html`, remplacer le bloc du champ téléphone (label « Téléphone (optionnel) » + input `customer_phone`, autour des lignes 147-153) par :

```html
        <!-- Téléphone (obligatoire) -->
        <div>
          <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
            Téléphone <span class="text-rose-500">*</span>
          </label>
          <div class="flex gap-2">
            <select name="phone_country" id="phone_country"
                    class="rounded-xl border border-slate-200 bg-white px-2 py-2 text-sm">
              {% for c in phone_countries %}
              <option value="{{ c.iso2 }}" data-example="{{ c.example }}">
                {{ c.dial }} {{ c.label }}
              </option>
              {% endfor %}
            </select>
            <input type="tel" name="customer_phone" id="customer_phone" required
                   inputmode="tel" placeholder="01 97 00 00 00"
                   class="flex-1 rounded-xl border border-slate-200 px-3 py-2 text-sm" />
          </div>
          <p id="phone_error" class="mt-1 text-xs text-rose-500 hidden">
            Entrez un numéro valide.
          </p>
        </div>
```

Ajouter, en bas du template (avant `{% endblock %}` ou dans le bloc scripts existant), une validation front légère :

```html
<script>
(function () {
  var form = document.querySelector('form');
  var input = document.getElementById('customer_phone');
  var err = document.getElementById('phone_error');
  if (!form || !input) return;
  form.addEventListener('submit', function (e) {
    var digits = (input.value || '').replace(/\D/g, '');
    if (digits.length < 8) {           // garde-fou léger ; la vraie validation est côté serveur
      e.preventDefault();
      err.classList.remove('hidden');
      input.focus();
    }
  });
})();
</script>
```

- [ ] **Step 6: Lancer les tests (succès attendu)**

Run: `python manage.py test base.test_parcours.CheckoutPhoneTest -v 2`
Expected: PASS (2 tests)

- [ ] **Step 7: Commit**

```bash
git add customer/views.py templates/customer/checkout.html base/test_parcours.py
git commit -m "feat: checkout — indicatif pays + téléphone obligatoire normalisé E.164

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Paramètres resto — section « Communauté & avis »

**Files:**
- Modify: `base/views.py` (vue `restaurant_settings`)
- Modify: `templates/admin_user/settings.html`
- Test: `base/test_parcours.py`

**Interfaces:**
- Consumes: `Restaurant.whatsapp_community_url`, `Restaurant.google_place_id`, `Restaurant.is_pro()`.
- Produces: POST des deux champs persiste sur le restaurant.

- [ ] **Step 1: Écrire le test (échec attendu)**

Ajouter à `base/test_parcours.py` :

```python
class SettingsCommunityTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.client.force_login(self.owner)

    def test_post_saves_whatsapp_and_place_id(self):
        # request.restaurant est résolu par le middleware ; on poste sur la vue settings
        resp = self.client.post(reverse("restaurant_settings"), {
            "name": self.resto.name, "email": self.resto.email,
            "phone": self.resto.phone, "address": self.resto.address,
            "description": "",
            "whatsapp_community_url": "https://chat.whatsapp.com/abc",
            "google_place_id": "ChIJ_test",
        })
        self.resto.refresh_from_db()
        self.assertEqual(self.resto.whatsapp_community_url, "https://chat.whatsapp.com/abc")
        self.assertEqual(self.resto.google_place_id, "ChIJ_test")
```

Note : la résolution de `request.restaurant` dépend du middleware/domaine. Si le test échoue à cause du contexte multi-tenant (pas de restaurant résolu), adapter en appelant la vue avec le sous-domaine attendu, ou marquer ce test `@skip` avec un commentaire et valider manuellement. Ne pas bloquer la tâche sur le harnais multi-tenant.

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `python manage.py test base.test_parcours.SettingsCommunityTest -v 2`
Expected: FAIL (champs non persistés)

- [ ] **Step 3: Modifier la vue restaurant_settings**

Dans `base/views.py`, vue `restaurant_settings`, dans le bloc `if request.method == "POST":`, après la ligne `restaurant.address = request.POST.get("address", restaurant.address)`, ajouter :

```python
        restaurant.whatsapp_community_url = request.POST.get(
            "whatsapp_community_url", restaurant.whatsapp_community_url).strip()
        restaurant.google_place_id = request.POST.get(
            "google_place_id", restaurant.google_place_id).strip()
```

- [ ] **Step 4: Ajouter la section au template settings**

Dans `templates/admin_user/settings.html`, dans le `<form>` (avant le bouton de soumission), ajouter une section :

```html
<div class="mt-8 border-t border-slate-200 pt-6">
  <h3 class="text-sm font-semibold text-slate-700 mb-1">Communauté & avis</h3>
  <p class="text-xs text-slate-500 mb-4">
    {% if restaurant.is_pro %}
      Affichés au client après sa commande pour le fidéliser.
    {% else %}
      Disponible avec l'offre <strong>Pro</strong>.
    {% endif %}
  </p>

  <div class="space-y-4 {% if not restaurant.is_pro %}opacity-50 pointer-events-none{% endif %}">
    <div>
      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
        Lien communauté WhatsApp
      </label>
      <input type="url" name="whatsapp_community_url"
             value="{{ restaurant.whatsapp_community_url }}"
             placeholder="https://chat.whatsapp.com/..."
             class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
    </div>
    <div>
      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">
        Google Place ID
      </label>
      <input type="text" name="google_place_id"
             value="{{ restaurant.google_place_id }}"
             placeholder="ChIJ..."
             class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
      <a href="https://developers.google.com/maps/documentation/places/web-service/place-id"
         target="_blank" class="mt-1 inline-block text-xs text-primary underline">
        Comment trouver mon Place ID ?
      </a>
    </div>
  </div>
</div>
```

- [ ] **Step 5: Lancer le test**

Run: `python manage.py test base.test_parcours.SettingsCommunityTest -v 2`
Expected: PASS (ou skip documenté si contrainte multi-tenant — voir note Step 1).

- [ ] **Step 6: Commit**

```bash
git add base/views.py templates/admin_user/settings.html base/test_parcours.py
git commit -m "feat: paramètres resto — section Communauté & avis (WhatsApp, Place ID)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Page de succès — 3 cartes + endpoint feedback + push

**Files:**
- Modify: `customer/views.py` (vue `order_confirmation` ; nouvelle vue `submit_feedback`)
- Modify: `customer/urls.py` (route feedback)
- Modify: `templates/customer/confirmation.html`
- Modify: `base/push.py` (worker + `notify_new_feedback`)
- Test: `base/test_parcours.py`

**Interfaces:**
- Consumes: `Restaurant.is_pro()`, `Restaurant.whatsapp_community_url`, `Restaurant.google_review_url`, `CustomerFeedback`.
- Produces:
  - `order_confirmation` passe au template : `is_pro`, `whatsapp_url`, `google_review_url`, `feedback_submitted`.
  - URL nommée `submit_feedback` (`order/<uuid:public_token>/feedback/`).
  - `base.push.notify_new_feedback(feedback_id)`.

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_parcours.py` :

```python
class SuccessPageTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.order = Order.objects.create(
            restaurant=self.resto, customer_phone="+2290197000000")

    def test_free_plan_hides_after_order_blocks(self):
        resp = self.client.get(
            reverse("order_confirmation", args=[self.order.public_token]))
        self.assertNotContains(resp, "Rejoignez notre communauté")

    def test_pro_plan_shows_whatsapp_when_url_set(self):
        self.resto.subscription_plan = make_pro_plan()
        self.resto.subscription_end = timezone.now() + timedelta(days=10)
        self.resto.whatsapp_community_url = "https://chat.whatsapp.com/abc"
        self.resto.save()
        resp = self.client.get(
            reverse("order_confirmation", args=[self.order.public_token]))
        self.assertContains(resp, "chat.whatsapp.com/abc")


class SubmitFeedbackTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.order = Order.objects.create(
            restaurant=self.resto, customer_phone="+2290197000000")

    def test_submit_creates_feedback(self):
        resp = self.client.post(
            reverse("submit_feedback", args=[self.order.public_token]),
            {"rating": "4", "message": "Bien"})
        self.assertEqual(resp.status_code, 302)
        fb = CustomerFeedback.objects.get(restaurant=self.resto)
        self.assertEqual(fb.rating, 4)
        self.assertEqual(fb.phone, "+2290197000000")

    def test_double_submit_creates_single_feedback(self):
        url = reverse("submit_feedback", args=[self.order.public_token])
        self.client.post(url, {"rating": "5", "message": "A"})
        self.client.post(url, {"rating": "1", "message": "B"})
        self.assertEqual(
            CustomerFeedback.objects.filter(order=self.order).count(), 1)
```

- [ ] **Step 2: Lancer les tests (échec attendu)**

Run: `python manage.py test base.test_parcours.SuccessPageTest base.test_parcours.SubmitFeedbackTest -v 2`
Expected: FAIL (contexte manquant / URL `submit_feedback` inexistante)

- [ ] **Step 3: Ajouter le worker push**

Dans `base/push.py`, après `_worker_order_ready`, ajouter le worker :

```python
def _worker_new_feedback(feedback_id):
    from base.models import CustomerFeedback
    fb = CustomerFeedback.objects.select_related('restaurant').filter(id=feedback_id).first()
    if not fb:
        return
    note = f"{fb.rating}★ " if fb.rating else ""
    extrait = (fb.message[:60] + "…") if len(fb.message) > 60 else fb.message
    _send_to_roles(fb.restaurant, ['owner', 'coadmin'], {
        "title": "Nouveau retour client 💬",
        "body": f"{note}{extrait}".strip() or "Un client a laissé un retour",
        "tag": f"feedback-{fb.id}",
        "url": "/retours/",
    })
```

Puis, près des autres `notify_*` (ex. après `notify_order_ready`), ajouter :

```python
def notify_new_feedback(feedback_id):
    _run_async(_worker_new_feedback, feedback_id)
```

- [ ] **Step 4: Ajouter la vue submit_feedback + enrichir order_confirmation**

Dans `customer/views.py`, remplacer le corps de `order_confirmation` par une version qui passe le contexte rétention :

```python
def order_confirmation(request, public_token):
    order = get_object_or_404(Order, public_token=public_token)
    customization = RestaurantCustomization.objects.filter(
        restaurant=order.restaurant
    ).first()
    table_token = order.table.token if order.table else None
    resto = order.restaurant
    is_pro = resto.is_pro()

    return render(request, "customer/confirmation.html", {
        "order": order,
        "restaurant": resto,
        "customization": customization,
        "table": order.table,
        "table_token": table_token,
        "is_pro": is_pro,
        "whatsapp_url": resto.whatsapp_community_url if is_pro else "",
        "google_review_url": resto.google_review_url if is_pro else "",
        "feedback_submitted": order.feedbacks.exists(),
    })
```

Puis ajouter la nouvelle vue (après `order_status`) :

```python
@require_POST
def submit_feedback(request, public_token):
    order = get_object_or_404(Order, public_token=public_token)
    # anti double-envoi : un seul feedback par commande
    if order.feedbacks.exists():
        return redirect("order_confirmation", public_token=public_token)
    rating = request.POST.get("rating")
    try:
        rating = int(rating) if rating else None
    except (TypeError, ValueError):
        rating = None
    from base.models import CustomerFeedback
    from base import push
    fb = CustomerFeedback.objects.create(
        restaurant=order.restaurant,
        order=order,
        rating=rating,
        message=request.POST.get("message", "").strip(),
        phone=order.customer_phone or "",
    )
    push.notify_new_feedback(fb.id)
    return redirect("order_confirmation", public_token=public_token)
```

Vérifier que `require_POST` et `redirect` sont importés en haut de `customer/views.py` (ils le sont déjà — `require_POST` utilisé ailleurs, `redirect` aussi).

- [ ] **Step 5: Ajouter la route**

Dans `customer/urls.py`, après la ligne `order_status`, ajouter :

```python
    path("order/<uuid:public_token>/feedback/", submit_feedback, name="submit_feedback"),
```

Et ajouter `submit_feedback` à l'import des vues en haut du fichier (même style d'import que `order_confirmation`, `order_status`).

- [ ] **Step 6: Ajouter les 3 cartes au template confirmation**

Dans `templates/customer/confirmation.html`, à un endroit visible après le récap de commande, ajouter :

```html
{% if is_pro %}
<div class="mt-6 space-y-4">

  {% if whatsapp_url %}
  <div class="rounded-2xl bg-emerald-50 border border-emerald-100 p-4 text-center">
    <p class="font-semibold text-emerald-800">Rejoignez notre communauté</p>
    <p class="text-sm text-emerald-700 mt-1">Offres, nouveautés et bons plans en avant-première.</p>
    <a href="{{ whatsapp_url }}" target="_blank" rel="noopener"
       class="mt-3 inline-block rounded-xl bg-emerald-600 px-5 py-2 text-white text-sm font-semibold">
      Rejoindre sur WhatsApp
    </a>
  </div>
  {% endif %}

  {% if google_review_url %}
  <div class="rounded-2xl bg-amber-50 border border-amber-100 p-4 text-center">
    <p class="font-semibold text-amber-800">Vous avez aimé ?</p>
    <a href="{{ google_review_url }}" target="_blank" rel="noopener"
       class="mt-2 inline-block rounded-xl bg-amber-500 px-5 py-2 text-white text-sm font-semibold">
      ⭐ Laisser un avis sur Google
    </a>
  </div>
  {% endif %}

  <div class="rounded-2xl bg-slate-50 border border-slate-200 p-4">
    {% if feedback_submitted %}
      <p class="text-center text-sm text-slate-600">Merci pour votre retour 🙏</p>
    {% else %}
      <p class="font-semibold text-slate-700 text-center">Un souci ? Dites-le au resto</p>
      <form method="post" action="{% url 'submit_feedback' order.public_token %}" class="mt-3 space-y-3">
        {% csrf_token %}
        <div class="flex justify-center gap-1" id="fb-stars">
          {% for n in "12345" %}
          <label class="cursor-pointer">
            <input type="radio" name="rating" value="{{ forloop.counter }}" class="sr-only peer">
            <span class="text-2xl text-slate-300 peer-checked:text-amber-400">★</span>
          </label>
          {% endfor %}
        </div>
        <textarea name="message" rows="2" placeholder="Votre message (optionnel)"
                  class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm"></textarea>
        <button type="submit"
                class="w-full rounded-xl bg-slate-800 px-4 py-2 text-white text-sm font-semibold">
          Envoyer au restaurant
        </button>
      </form>
    {% endif %}
  </div>

</div>
{% endif %}
```

- [ ] **Step 7: Lancer les tests (succès attendu)**

Run: `python manage.py test base.test_parcours.SuccessPageTest base.test_parcours.SubmitFeedbackTest -v 2`
Expected: PASS (4 tests)

- [ ] **Step 8: Commit**

```bash
git add customer/views.py customer/urls.py templates/customer/confirmation.html base/push.py base/test_parcours.py
git commit -m "feat: page de succès — invite WhatsApp, avis Google, retour privé + push staff

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Dashboard — onglet « Retours clients »

**Files:**
- Create: `base/views.py` nouvelle vue `feedback_list` (+ marquage lu)
- Modify: `base/urls.py` (route `retours/`)
- Create: `templates/admin_user/feedback/list.html`
- Modify: `templates/admin_user/sidebar.html` (nav + badge)
- Modify: `base/context_processors.py` (compteur non-lus, si un context processor existe pour la sidebar)
- Test: `base/test_parcours.py`

**Interfaces:**
- Consumes: `CustomerFeedback`, `Restaurant.is_pro()`, décorateur `@owner_or_coadmin_required`.
- Produces: URL nommée `feedback_list` (`retours/`).

- [ ] **Step 1: Écrire le test (échec attendu)**

Ajouter à `base/test_parcours.py` :

```python
class FeedbackDashboardTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.client.force_login(self.owner)
        CustomerFeedback.objects.create(
            restaurant=self.resto, rating=3, message="Bof", phone="+2290197000000")

    def test_feedback_list_shows_items_and_marks_read(self):
        resp = self.client.get(reverse("feedback_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bof")
        self.assertFalse(
            CustomerFeedback.objects.filter(restaurant=self.resto, is_read=False).exists())
```

Même note multi-tenant que Task 4 : si `request.restaurant` n'est pas résolu dans le harnais de test, documenter un skip et valider manuellement.

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `python manage.py test base.test_parcours.FeedbackDashboardTest -v 2`
Expected: FAIL (URL `feedback_list` inexistante)

- [ ] **Step 3: Ajouter la vue feedback_list**

Dans `base/views.py`, près de `customers_list`, ajouter :

```python
@owner_or_coadmin_required
def feedback_list(request):
    restaurant = request.restaurant
    feedbacks = restaurant.feedbacks.all()
    # marquer comme lus à l'ouverture
    restaurant.feedbacks.filter(is_read=False).update(is_read=True)
    return render(request, "admin_user/feedback/list.html", {
        "restaurant": restaurant,
        "feedbacks": feedbacks,
    })
```

Vérifier que `owner_or_coadmin_required` est déjà importé dans `base/views.py` (il l'est — utilisé par `customers_list`).

- [ ] **Step 4: Ajouter la route**

Dans `base/urls.py`, après la ligne `clients/`, ajouter :

```python
    path("retours/", feedback_list, name="feedback_list"),
```

Ajouter `feedback_list` à l'import des vues en haut de `base/urls.py` (même mécanisme que `customers_list`).

- [ ] **Step 5: Créer le template**

Créer `templates/admin_user/feedback/list.html` (calquer l'ossature de `templates/admin_user/customers/list.html` — mêmes `{% extends %}` / `{% block %}`) :

```html
{% extends "admin_user/base.html" %}
{% block content %}
<div class="p-4">
  <h1 class="text-lg font-semibold text-slate-800 mb-4">Retours clients</h1>

  {% if not feedbacks %}
    <p class="text-sm text-slate-500">Aucun retour pour l'instant.</p>
  {% else %}
    <div class="space-y-3">
      {% for fb in feedbacks %}
      <div class="rounded-xl border border-slate-200 bg-white p-4">
        <div class="flex items-center justify-between">
          <span class="text-amber-500">
            {% if fb.rating %}{% for _ in "12345"|make_list %}{% if forloop.counter <= fb.rating %}★{% else %}☆{% endif %}{% endfor %}{% else %}—{% endif %}
          </span>
          <span class="text-xs text-slate-400">{{ fb.created_at|date:"d/m/Y H:i" }}</span>
        </div>
        {% if fb.message %}<p class="mt-2 text-sm text-slate-700">{{ fb.message }}</p>{% endif %}
        {% if fb.phone %}<p class="mt-1 text-xs text-slate-400">{{ fb.phone }}</p>{% endif %}
      </div>
      {% endfor %}
    </div>
  {% endif %}
</div>
{% endblock %}
```

Vérifier le nom réel du `{% block %}` de contenu dans `admin_user/base.html` et l'utiliser (ajuster `content` si le projet utilise un autre nom).

- [ ] **Step 6: Ajouter l'entrée sidebar (gating Pro)**

Dans `templates/admin_user/sidebar.html`, dans la zone « owner et coadmin uniquement » (près de l'entrée Clients), ajouter la déclaration d'URL en haut avec les autres `{% url ... as ... %}` :

```html
  {% url 'feedback_list' as url_feedback %}
```

Puis, après le lien « Clients », ajouter le lien (visible seulement si Pro) :

```html
{% if restaurant.is_pro %}
<a href="{{ url_feedback }}"
   class="flex items-center gap-3 rounded-xl px-3 py-2 text-sm
          {% if current == url_feedback %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <span>💬</span>
  {% trans "Retours" %}
  {% if unread_feedback_count %}
  <span class="ml-auto rounded-full bg-rose-500 text-white text-xs px-2">{{ unread_feedback_count }}</span>
  {% endif %}
</a>
{% endif %}
```

- [ ] **Step 7: Exposer le compteur non-lus (badge)**

Vérifier s'il existe un context processor pour la sidebar dans `base/context_processors.py`. Si oui, y ajouter (dans la fonction qui expose `restaurant` au layout) :

```python
    unread_feedback_count = 0
    if restaurant is not None:
        unread_feedback_count = restaurant.feedbacks.filter(is_read=False).count()
    # ... ajouter 'unread_feedback_count': unread_feedback_count au dict retourné
```

Si aucun context processor sidebar n'existe, ignorer le badge (le lien reste fonctionnel sans compteur) — ne pas bloquer la tâche.

- [ ] **Step 8: Lancer le test**

Run: `python manage.py test base.test_parcours.FeedbackDashboardTest -v 2`
Expected: PASS (ou skip documenté si contrainte multi-tenant).

- [ ] **Step 9: Lancer toute la suite**

Run: `python manage.py test base -v 1`
Expected: pas de régression.

- [ ] **Step 10: Commit**

```bash
git add base/views.py base/urls.py templates/admin_user/feedback/list.html templates/admin_user/sidebar.html base/context_processors.py base/test_parcours.py
git commit -m "feat: dashboard — onglet Retours clients (liste, badge non-lus, gating Pro)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (couverture spec)

- **Téléphone E.164 + indicatif + validation** → Tasks 1, 3. ✅
- **Champs Restaurant (WhatsApp URL, Place ID)** → Task 2. ✅
- **Modèle CustomerFeedback** → Task 2. ✅
- **Gating Pro (is_pro)** → Task 2 (helper), Tasks 5 & 6 (usage). ✅
- **Paramètres « Communauté & avis »** → Task 4. ✅
- **Page de succès : WhatsApp + Google + retour privé** → Task 5. ✅
- **Push staff sur nouveau retour** → Task 5. ✅
- **Onglet dashboard Retours + badge + gating** → Task 6. ✅
- **Tests par unité** → chaque task. ✅

**Risque connu / à surveiller pendant l'exécution :** la résolution `request.restaurant` (multi-tenant par sous-domaine) peut compliquer les tests de vues dashboard/settings (Tasks 4 & 6). Le plan autorise un skip documenté + validation manuelle si le harnais de test ne résout pas le restaurant — sans bloquer la livraison. Vérifier aussi le nom réel du champ `token` sur `Table` (Task 3) et le nom du `{% block %}` de contenu (`admin_user/base.html`, Task 6).
```