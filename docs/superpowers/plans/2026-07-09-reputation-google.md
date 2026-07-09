# Réputation — Avis Google reçus (Route A) — Plan (Bloc 4)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Afficher la note Google + jusqu'à 5 avis reçus d'un resto dans OpenFood via l'API Places (New), avec cache court, config super-admin, gating Pro.

**Architecture:** App `base`. Singleton `ReputationSettings` ; service `base/services/reputation/` (client Places + cache Django) ; page dashboard gardée.

**Tech Stack:** Django, `requests` (présent), cache Django (LocMemCache par défaut), templates Tailwind.

## Global Constraints

- venv shebang cassé → `./env/bin/python3`.
- Tests : `./env/bin/python3 manage.py test base.test_reputation -v 2` ; suite `./env/bin/python3 manage.py test base --noinput`.
- Aucun appel réseau réel en test (mocker `requests.get` ; cache réel LocMem OK).
- Conformité CGU Google : pas de stockage durable des avis ; cache seulement.
- Gating : owner/coadmin + `restaurant.is_pro()` + `is_enabled` + `google_place_id`.
- Réutilise `Restaurant.google_place_id` (existe déjà, bloc 1). Patterns singleton = `AISettings`/`ImageGenSettings`.
- Helpers test : `make_user`, `make_restaurant` (base.tests) ; `make_pro` existe dans `base/test_imagegen.py` — recréer un helper local dans le nouveau fichier de test.

---

### Task 1: ReputationSettings singleton + admin

**Files:**
- Modify: `base/models.py`, `base/admin.py`
- Create: migration
- Test: `base/test_reputation.py`

**Interfaces:**
- Produces: `base.models.ReputationSettings` (`is_enabled`, `google_api_key`, `cache_hours`, `load()`).

- [ ] **Step 1: Test (échec attendu)**

Créer `base/test_reputation.py` :

```python
from django.test import TestCase
from base.models import ReputationSettings


class ReputationSettingsTest(TestCase):
    def test_singleton_load_defaults(self):
        s = ReputationSettings.load()
        self.assertEqual(s.pk, 1)
        self.assertFalse(s.is_enabled)
        self.assertEqual(s.cache_hours, 12)
        self.assertEqual(ReputationSettings.load().pk, 1)
```

- [ ] **Step 2: Lancer (échec)**

Run: `./env/bin/python3 manage.py test base.test_reputation -v 2`
Expected: FAIL (modèle inexistant)

- [ ] **Step 3: Modèle**

Dans `base/models.py`, fin du fichier :

```python
class ReputationSettings(models.Model):
    """Config plateforme (singleton) pour l'affichage des avis Google."""
    is_enabled = models.BooleanField(default=False)
    google_api_key = models.CharField(max_length=255, blank=True)
    cache_hours = models.PositiveIntegerField(default=12)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres réputation (avis Google)"
        verbose_name_plural = "Paramètres réputation (avis Google)"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"ReputationSettings (enabled={self.is_enabled})"
```

- [ ] **Step 4: Admin**

Dans `base/admin.py`, ajouter `ReputationSettings` à l'import des modèles, puis
après `ImageGenSettingsAdmin` :

```python
class ReputationSettingsForm(forms.ModelForm):
    class Meta:
        model = ReputationSettings
        fields = "__all__"
        widgets = {"google_api_key": forms.PasswordInput(render_value=True)}


@admin.register(ReputationSettings)
class ReputationSettingsAdmin(admin.ModelAdmin):
    form = ReputationSettingsForm
    list_display = ("is_enabled", "cache_hours", "updated_at")

    def has_add_permission(self, request):
        return not ReputationSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 5: Migration + migrate**

```bash
./env/bin/python3 manage.py makemigrations base
./env/bin/python3 manage.py migrate
```

- [ ] **Step 6: Lancer (succès)** — `./env/bin/python3 manage.py test base.test_reputation -v 2` → PASS

- [ ] **Step 7: Commit**

```bash
git add base/models.py base/admin.py base/migrations/ base/test_reputation.py
git commit -m "feat: ReputationSettings — config super-admin avis Google (singleton + admin)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Service google_places.get_reviews + cache

**Files:**
- Create: `base/services/reputation/__init__.py`, `base/services/reputation/google_places.py`
- Test: `base/test_reputation.py`

**Interfaces:**
- Produces:
  - `reputation.google_places.get_reviews(place_id, api_key, cache_hours) -> dict`
  - `reputation.google_places.ReputationError`

- [ ] **Step 1: Tests (échec attendu)**

Ajouter à `base/test_reputation.py` :

```python
from unittest.mock import patch, MagicMock
from django.core.cache import cache
from base.services.reputation import google_places
from base.services.reputation.google_places import ReputationError

GOOGLE_JSON = {
    "rating": 4.5,
    "userRatingCount": 128,
    "googleMapsUri": "https://maps.google.com/?cid=1",
    "reviews": [
        {"rating": 5, "text": {"text": "Excellent !"},
         "authorAttribution": {"displayName": "Awa", "photoUri": "http://p/1"},
         "relativePublishTimeDescription": "il y a une semaine"},
    ],
}


class GetReviewsTest(TestCase):
    def setUp(self):
        cache.clear()

    @patch("base.services.reputation.google_places.requests.get")
    def test_normalizes_google_response(self, mget):
        mget.return_value = MagicMock(status_code=200, json=lambda: GOOGLE_JSON)
        mget.return_value.raise_for_status = lambda: None
        out = google_places.get_reviews("PID", "KEY", 12)
        self.assertEqual(out["rating"], 4.5)
        self.assertEqual(out["total"], 128)
        self.assertEqual(len(out["reviews"]), 1)
        self.assertEqual(out["reviews"][0]["author"], "Awa")
        self.assertEqual(out["reviews"][0]["text"], "Excellent !")

    @patch("base.services.reputation.google_places.requests.get")
    def test_uses_cache_on_second_call(self, mget):
        mget.return_value = MagicMock(status_code=200, json=lambda: GOOGLE_JSON)
        mget.return_value.raise_for_status = lambda: None
        google_places.get_reviews("PID", "KEY", 12)
        google_places.get_reviews("PID", "KEY", 12)
        self.assertEqual(mget.call_count, 1)  # 2e appel servi par le cache

    def test_missing_key_raises(self):
        with self.assertRaises(ReputationError):
            google_places.get_reviews("PID", "", 12)

    @patch("base.services.reputation.google_places.requests.get")
    def test_http_error_raises(self, mget):
        def boom():
            raise Exception("500")
        mget.return_value = MagicMock(status_code=500, raise_for_status=boom)
        with self.assertRaises(ReputationError):
            google_places.get_reviews("PID", "KEY", 12)
```

- [ ] **Step 2: Lancer (échec)** — module inexistant.

- [ ] **Step 3: Package + service**

Créer `base/services/reputation/__init__.py` (vide).

Créer `base/services/reputation/google_places.py` :

```python
"""Lecture des avis Google via l'API Places (New), avec cache court.

CGU Google : on ne stocke pas durablement les avis — cache seulement.
"""
import requests
from django.core.cache import cache

API_URL = "https://places.googleapis.com/v1/places/{place_id}"
FIELD_MASK = "rating,userRatingCount,googleMapsUri,reviews"


class ReputationError(Exception):
    """Échec de récupération des avis Google."""


def _normalize(data):
    reviews = []
    for r in (data.get("reviews") or [])[:5]:
        author = (r.get("authorAttribution") or {})
        reviews.append({
            "author": author.get("displayName", "Client Google"),
            "photo": author.get("photoUri", ""),
            "rating": r.get("rating"),
            "text": (r.get("text") or {}).get("text", ""),
            "relative_time": r.get("relativePublishTimeDescription", ""),
        })
    return {
        "rating": data.get("rating"),
        "total": data.get("userRatingCount", 0),
        "maps_uri": data.get("googleMapsUri", ""),
        "reviews": reviews,
    }


def get_reviews(place_id, api_key, cache_hours):
    if not api_key:
        raise ReputationError("Clé API Google manquante")
    if not place_id:
        raise ReputationError("Place ID manquant")

    cache_key = f"reputation:{place_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK}
    try:
        resp = requests.get(
            API_URL.format(place_id=place_id), headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise ReputationError(f"Échec Google Places : {exc}") from exc

    result = _normalize(data)
    cache.set(cache_key, result, int(cache_hours) * 3600)
    return result
```

- [ ] **Step 4: Lancer (succès)** — `./env/bin/python3 manage.py test base.test_reputation.GetReviewsTest -v 2` → PASS (4)

- [ ] **Step 5: Commit**

```bash
git add base/services/reputation/ base/test_reputation.py
git commit -m "feat: service avis Google (Places API New) + cache court

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Vue + URL + template + sidebar + gating

**Files:**
- Modify: `base/views.py` (`reputation_view`)
- Modify: `base/urls.py` (route)
- Create: `templates/admin_user/reputation/index.html`
- Modify: `templates/admin_user/sidebar.html`
- Test: `base/test_reputation.py`

**Interfaces:**
- Consumes: `ReputationSettings`, `google_places.get_reviews`, `Restaurant.is_pro()`, `Restaurant.google_place_id`.
- Produces: URL `reputation` (`reputation/`).

- [ ] **Step 1: Test (échec attendu)**

Ajouter à `base/test_reputation.py` :

```python
from django.urls import reverse
from base.models import SubscriptionPlan
from base.tests import make_user, make_restaurant
from django.utils import timezone
from datetime import timedelta


def make_pro(resto):
    plan = SubscriptionPlan.objects.create(name="Pro", plan_type="pro", price=1)
    resto.subscription_plan = plan
    resto.subscription_end = timezone.now() + timedelta(days=10)
    resto.save()


class ReputationViewTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.client.force_login(self.owner)
        s = ReputationSettings.load()
        s.is_enabled = True
        s.google_api_key = "KEY"
        s.save()

    def _host(self):
        return {"HTTP_HOST": f"{self.resto.subdomain}.localhost"}

    def test_non_pro_forbidden(self):
        resp = self.client.get(reverse("reputation"), **self._host())
        self.assertIn(resp.status_code, (302, 404))

    @patch("base.views.google_places.get_reviews",
           return_value={"rating": 4.5, "total": 10, "maps_uri": "", "reviews": []})
    def test_pro_renders(self, mget):
        make_pro(self.resto)
        self.resto.google_place_id = "PID"
        self.resto.save()
        resp = self.client.get(reverse("reputation"), **self._host())
        self.assertEqual(resp.status_code, 200)
```

Note multi-tenant : aligner `_host()` sur le pattern qui passe dans
`base/test_imagegen.py`/`base/test_parcours.py`. Skip documenté en dernier
recours.

- [ ] **Step 2: Lancer (échec)** — URL inexistante.

- [ ] **Step 3: Vue**

Dans `base/views.py`, ajouter en haut (imports) :

```python
from base.services.reputation import google_places
from base.services.reputation.google_places import ReputationError
```

Puis, près de `feedback_list` :

```python
@owner_or_coadmin_required
def reputation_view(request):
    restaurant = request.restaurant
    if not restaurant.is_pro():
        raise Http404()
    from base.models import ReputationSettings
    settings = ReputationSettings.load()
    data, error = None, ""
    place_id_set = bool(restaurant.google_place_id)
    if settings.is_enabled and place_id_set:
        try:
            data = google_places.get_reviews(
                restaurant.google_place_id, settings.google_api_key,
                settings.cache_hours)
        except ReputationError as exc:
            error = str(exc)
    return render(request, "admin_user/reputation/index.html", {
        "restaurant": restaurant,
        "enabled": settings.is_enabled,
        "place_id_set": place_id_set,
        "data": data,
        "error": error,
    })
```

- [ ] **Step 4: URL**

Dans `base/urls.py`, après `retours/`, ajouter (et importer `reputation_view`) :

```python
    path("reputation/", reputation_view, name="reputation"),
```

- [ ] **Step 5: Template**

Créer `templates/admin_user/reputation/index.html` (ossature `admin_user/base.html`, blocs `title`, `page_title`, `content`) :

```html
{% extends "admin_user/base.html" %}
{% block title %}Réputation — {{ restaurant.name }}{% endblock %}
{% block page_title %}Réputation{% endblock %}
{% block content %}
<div class="p-4 space-y-5">
  {% if not enabled %}
    <div class="rounded-xl bg-amber-50 border border-amber-100 p-4 text-sm text-amber-800">
      L'affichage des avis Google est momentanément indisponible.
    </div>
  {% elif not place_id_set %}
    <div class="rounded-xl bg-slate-50 border border-slate-200 p-4 text-sm text-slate-600">
      Renseignez votre <strong>Google Place ID</strong> dans
      <a href="{% url 'restaurant_settings' %}" class="text-primary underline">Paramètres</a>
      pour afficher vos avis.
    </div>
  {% elif error %}
    <div class="rounded-xl bg-rose-50 border border-rose-100 p-4 text-sm text-rose-700">
      Impossible de charger les avis pour le moment.
    </div>
  {% elif data %}
    <div class="rounded-2xl border border-slate-200 bg-white p-4 flex items-center justify-between">
      <div>
        <div class="text-3xl font-black text-slate-900">
          {{ data.rating|default:"—" }} <span class="text-amber-400">★</span>
        </div>
        <div class="text-xs text-slate-500">{{ data.total }} avis Google</div>
      </div>
      {% if data.maps_uri %}
      <a href="{{ data.maps_uri }}" target="_blank" rel="noopener"
         class="text-sm rounded-xl bg-slate-800 text-white px-4 py-2">Voir sur Google</a>
      {% endif %}
    </div>

    <div class="space-y-3">
      {% for r in data.reviews %}
      <div class="rounded-2xl border border-slate-200 bg-white p-4">
        <div class="flex items-center justify-between">
          <span class="font-semibold text-slate-800">{{ r.author }}</span>
          <span class="text-amber-500 text-sm">
            {% for _ in "12345"|make_list %}{% if forloop.counter <= r.rating %}★{% else %}☆{% endif %}{% endfor %}
          </span>
        </div>
        {% if r.text %}<p class="mt-2 text-sm text-slate-700">{{ r.text }}</p>{% endif %}
        <p class="mt-1 text-xs text-slate-400">{{ r.relative_time }}</p>
      </div>
      {% empty %}
      <p class="text-sm text-slate-500">Aucun avis pour l'instant.</p>
      {% endfor %}
    </div>
    <p class="text-xs text-slate-400">Avis fournis par Google.</p>
  {% endif %}
</div>
{% endblock %}
```

- [ ] **Step 6: Sidebar**

Dans `templates/admin_user/sidebar.html`, déclarer l'URL en haut :

```html
  {% url 'reputation'           as url_reputation   %}
```

Puis, dans la zone owner/coadmin (près de « Retours »), gaté Pro :

```html
{% if restaurant.is_pro %}
<a href="{{ url_reputation }}"
   class="flex items-center gap-3 rounded-xl px-3 py-2 text-sm
          {% if current == url_reputation %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <span>⭐</span>
  {% trans "Réputation" %}
</a>
{% endif %}
```

- [ ] **Step 7: Lancer les tests + non-régression**

Run: `./env/bin/python3 manage.py test base.test_reputation -v 2` → PASS
Puis: `./env/bin/python3 manage.py test base --noinput` → aucune régression.

- [ ] **Step 8: Commit**

```bash
git add base/views.py base/urls.py templates/admin_user/reputation/index.html templates/admin_user/sidebar.html base/test_reputation.py
git commit -m "feat: page Réputation — note + avis Google (gating Pro, cache)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (couverture spec)

- **ReputationSettings super-admin** → Task 1. ✅
- **Service Places API + cache + conformité (pas de stockage)** → Task 2. ✅
- **Vue + gating Pro + états (non configuré/désactivé/erreur)** → Task 3. ✅
- **Template + sidebar** → Task 3. ✅
- **Réutilise google_place_id (bloc 1)** → Task 3. ✅

**À surveiller :** format exact de l'API Places (New) — non vérifiable e2e sans
clé Google ; l'implémenteur suit le field mask indiqué, tests mockés. Résolution
multi-tenant des tests de vue (aligner `_host()`).
