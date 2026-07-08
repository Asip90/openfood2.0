# Générateur d'affiche IA — Plan d'implémentation (Bloc 2)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Générer des affiches marketing appétissantes + légendes émotionnelles via un pipeline Mistral (prompt varié + légende) → OpenRouter (image), réservé Pro/Max, avec galerie et raffinage.

**Architecture:** App `base`. Deux singletons/settings et un modèle d'historique ; une couche service isolée `base/services/imagegen/` (styles, prompt-builder réutilisant la couche `ai` existante, client OpenRouter, orchestrateur avec quota) ; des vues dashboard gardées ; une page studio + galerie.

**Tech Stack:** Django, `requests` (2.33.1, déjà présent), `cloudinary` (1.42.1, déjà présent), couche IA existante (`base/services/ai/factory.get_provider`), Web Push non concerné.

## Global Constraints

- venv à shebang cassé → utiliser `./env/bin/python3` pour tout (`manage.py`, tests).
- Tests : `./env/bin/python3 manage.py test base.test_imagegen -v 2` (nouveau fichier) ; suite complète `./env/bin/python3 manage.py test base --noinput`.
- **Aucun appel réseau réel en test** : mocker `requests.post`, `cloudinary.uploader.upload`, et le provider IA.
- Gating : `restaurant.is_pro()` (Pro/Max) + rôle owner/coadmin (`@owner_or_coadmin_required`) + `ImageGenSettings.load().is_enabled` + quota/jour.
- Réutiliser les patterns existants : singleton façon `AISettings`/`AISettingsAdmin`, vues fonctions, `request.restaurant`, Cloudinary comme `MenuItemMedia`.
- Monnaie FCFA ; couleurs resto `primary_color`/`secondary_color`.
- Provider IA texte : `from base.services.ai.factory import get_provider` ; `provider.complete(system, messages)` renvoie une string JSON.
- Commits fréquents, un par tâche.

---

### Task 1: Config super-admin — ImageGenSettings + admin

**Files:**
- Modify: `base/models.py` (nouveau modèle `ImageGenSettings`)
- Modify: `base/admin.py` (form + admin Jazzmin)
- Create: migration
- Test: `base/test_imagegen.py`

**Interfaces:**
- Produces: `base.models.ImageGenSettings` avec `load()`, `effective_model()`, champs `is_enabled`, `openrouter_api_key`, `image_model`, `image_model_custom`, `image_size`, `daily_quota_per_restaurant`.

- [ ] **Step 1: Écrire les tests (échec attendu)**

Créer `base/test_imagegen.py` :

```python
from django.test import TestCase
from base.models import ImageGenSettings


class ImageGenSettingsTest(TestCase):
    def test_singleton_load(self):
        a = ImageGenSettings.load()
        b = ImageGenSettings.load()
        self.assertEqual(a.pk, 1)
        self.assertEqual(a.pk, b.pk)

    def test_effective_model_uses_choice(self):
        s = ImageGenSettings.load()
        s.image_model = "openai/gpt-image-1-mini"
        s.image_model_custom = ""
        self.assertEqual(s.effective_model(), "openai/gpt-image-1-mini")

    def test_effective_model_uses_custom_when_selected(self):
        s = ImageGenSettings.load()
        s.image_model = "custom"
        s.image_model_custom = "some/new-model-id"
        self.assertEqual(s.effective_model(), "some/new-model-id")

    def test_default_quota(self):
        self.assertEqual(ImageGenSettings.load().daily_quota_per_restaurant, 5)
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_imagegen -v 2`
Expected: FAIL (`ImageGenSettings` inexistant)

- [ ] **Step 3: Ajouter le modèle**

Dans `base/models.py`, à la fin du fichier, ajouter :

```python
class ImageGenSettings(models.Model):
    """Config plateforme (singleton) du générateur d'affiche IA."""
    MODEL_CHOICES = [
        ("openai/gpt-image-1-mini", "GPT Image 1 Mini (rapide/éco)"),
        ("openai/gpt-image-2", "GPT Image 2 (premium)"),
        ("google/gemini-2.5-flash-image", "Gemini 2.5 Flash Image (nano banana)"),
        ("black-forest-labs/flux-1.1-pro", "Flux 1.1 Pro"),
        ("custom", "Autre (saisir l'ID ci-dessous)"),
    ]
    is_enabled = models.BooleanField(default=False)
    openrouter_api_key = models.CharField(max_length=255, blank=True)
    image_model = models.CharField(
        max_length=100, choices=MODEL_CHOICES, default="openai/gpt-image-1-mini")
    image_model_custom = models.CharField(max_length=200, blank=True)
    image_size = models.CharField(max_length=20, default="1024x1536")
    daily_quota_per_restaurant = models.PositiveIntegerField(default=5)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres génération d'image"
        verbose_name_plural = "Paramètres génération d'image"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def effective_model(self):
        if self.image_model == "custom" and self.image_model_custom:
            return self.image_model_custom
        return self.image_model

    def __str__(self):
        return f"ImageGenSettings ({self.effective_model()})"
```

- [ ] **Step 4: Enregistrer dans l'admin**

Dans `base/admin.py` : ajouter `ImageGenSettings` à l'import des modèles (ligne des imports, à côté de `AISettings`). Puis, après `AISettingsAdmin`, ajouter :

```python
class ImageGenSettingsForm(forms.ModelForm):
    class Meta:
        model = ImageGenSettings
        fields = "__all__"
        widgets = {
            "openrouter_api_key": forms.PasswordInput(render_value=True),
        }


@admin.register(ImageGenSettings)
class ImageGenSettingsAdmin(admin.ModelAdmin):
    form = ImageGenSettingsForm
    list_display = ("effective_model", "is_enabled", "daily_quota_per_restaurant", "updated_at")

    def has_add_permission(self, request):
        return not ImageGenSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
```

- [ ] **Step 5: Migration + migrate**

Run:
```bash
./env/bin/python3 manage.py makemigrations base
./env/bin/python3 manage.py migrate
```

- [ ] **Step 6: Lancer les tests (succès)**

Run: `./env/bin/python3 manage.py test base.test_imagegen -v 2`
Expected: PASS (4)

- [ ] **Step 7: Commit**

```bash
git add base/models.py base/admin.py base/migrations/ base/test_imagegen.py
git commit -m "feat: ImageGenSettings — config super-admin du générateur d'affiche (singleton + admin)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Historique — modèle MarketingPoster

**Files:**
- Modify: `base/models.py`
- Create: migration
- Test: `base/test_imagegen.py`

**Interfaces:**
- Produces: `base.models.MarketingPoster` (champs `restaurant`, `menu_item`, `image`, `caption`, `prompt_used`, `style`, `user_text`, `parent`, `created_by`, `created_at`). `restaurant.posters` reverse.

- [ ] **Step 1: Écrire le test (échec attendu)**

Ajouter à `base/test_imagegen.py` :

```python
from base.models import Restaurant, MarketingPoster
from base.tests import make_user, make_restaurant


class MarketingPosterModelTest(TestCase):
    def test_create_poster_and_refinement_chain(self):
        resto = make_restaurant(make_user())
        parent = MarketingPoster.objects.create(
            restaurant=resto, caption="Miam", style="macro", prompt_used="p")
        child = MarketingPoster.objects.create(
            restaurant=resto, caption="Miam v2", parent=parent)
        self.assertEqual(resto.posters.count(), 2)
        self.assertEqual(child.parent, parent)
        self.assertEqual(parent.refinements.first(), child)
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.MarketingPosterModelTest -v 2`
Expected: FAIL (`MarketingPoster` inexistant)

- [ ] **Step 3: Ajouter le modèle**

Dans `base/models.py`, à la fin du fichier, ajouter (le `CloudinaryField` alias `_CloudinaryField` est déjà importé plus haut dans le fichier) :

```python
class MarketingPoster(models.Model):
    """Affiche marketing générée par IA (+ légende), avec chaînes de raffinage."""
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='posters')
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.SET_NULL, null=True, blank=True)
    image = _CloudinaryField('image', resource_type='image', blank=True)
    caption = models.TextField(blank=True)
    prompt_used = models.TextField(blank=True)
    style = models.CharField(max_length=80, blank=True)
    user_text = models.CharField(max_length=300, blank=True)
    parent = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='refinements')
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Affiche {self.restaurant.name} ({self.style or '—'})"
```

- [ ] **Step 4: Migration + migrate**

Run:
```bash
./env/bin/python3 manage.py makemigrations base
./env/bin/python3 manage.py migrate
```

- [ ] **Step 5: Lancer le test (succès)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.MarketingPosterModelTest -v 2`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add base/models.py base/migrations/ base/test_imagegen.py
git commit -m "feat: modèle MarketingPoster (historique affiches + chaîne de raffinage)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Palette de styles + prompt-builder

**Files:**
- Create: `base/services/imagegen/__init__.py`
- Create: `base/services/imagegen/styles.py`
- Create: `base/services/imagegen/prompt_builder.py`
- Test: `base/test_imagegen.py`

**Interfaces:**
- Consumes: `base.services.ai.factory.get_provider`.
- Produces:
  - `styles.STYLE_PALETTE` (liste de dicts `{"key": str, "label": str, "brief": str}`).
  - `prompt_builder.build(restaurant, menu_item, user_text, source_image_present, exclude_style=None) -> dict{"image_prompt","caption","style"}`.

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_imagegen.py` :

```python
from unittest.mock import patch, MagicMock
import json
from base.services.imagegen import styles, prompt_builder


class PromptBuilderTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())

    def test_style_palette_non_empty(self):
        self.assertTrue(len(styles.STYLE_PALETTE) >= 5)
        self.assertIn("key", styles.STYLE_PALETTE[0])

    @patch("base.services.imagegen.prompt_builder.get_provider")
    def test_build_parses_provider_json(self, mock_get_provider):
        provider = MagicMock()
        provider.complete.return_value = json.dumps({
            "image_prompt": "a delicious plate, macro, warm light",
            "caption": "Venez goûter notre plat signature 🔥",
            "style": "macro",
        })
        mock_get_provider.return_value = provider
        out = prompt_builder.build(self.resto, None, "promo -20%", False)
        self.assertEqual(out["style"], "macro")
        self.assertIn("delicious", out["image_prompt"])
        self.assertTrue(out["caption"])

    @patch("base.services.imagegen.prompt_builder.get_provider")
    def test_build_falls_back_on_invalid_json(self, mock_get_provider):
        provider = MagicMock()
        provider.complete.return_value = "pas du json"
        mock_get_provider.return_value = provider
        out = prompt_builder.build(self.resto, None, "", False)
        # repli : un dict complet malgré le JSON invalide
        self.assertIn("image_prompt", out)
        self.assertIn("caption", out)
        self.assertIn("style", out)
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.PromptBuilderTest -v 2`
Expected: FAIL (module inexistant)

- [ ] **Step 3: Créer le package + styles**

Créer `base/services/imagegen/__init__.py` (vide).

Créer `base/services/imagegen/styles.py` :

```python
"""Palette de styles visuels curée pour varier les affiches."""

STYLE_PALETTE = [
    {"key": "macro", "label": "Gros plan macro",
     "brief": "extreme close-up, shallow depth of field, rising steam, appetizing texture"},
    {"key": "flatlay", "label": "Flat lay premium",
     "brief": "top-down flat lay, elegant props, marble or wood surface, editorial"},
    {"key": "cozy_table", "label": "Ambiance chaleureuse à table",
     "brief": "warm restaurant table scene, candle warm light, inviting mood"},
    {"key": "pop", "label": "Pop coloré réseaux",
     "brief": "vibrant saturated colors, bold graphic background, social-media pop"},
    {"key": "studio", "label": "Studio épuré",
     "brief": "clean studio backdrop, soft shadows, product-hero lighting"},
    {"key": "street", "label": "Street food énergique",
     "brief": "dynamic street-food vibe, urban texture, energetic composition"},
    {"key": "rustic", "label": "Rustique authentique",
     "brief": "rustic wooden table, natural daylight, artisanal homemade feel"},
    {"key": "luxe", "label": "Gastronomique chic",
     "brief": "fine-dining plating, dark elegant background, luxurious mood"},
    {"key": "fresh", "label": "Frais et lumineux",
     "brief": "bright airy scene, fresh ingredients around, light and healthy"},
    {"key": "night", "label": "Ambiance nocturne néon",
     "brief": "night ambience, neon accents, moody cinematic lighting"},
]


def keys():
    return [s["key"] for s in STYLE_PALETTE]
```

- [ ] **Step 4: Créer le prompt-builder**

Créer `base/services/imagegen/prompt_builder.py` :

```python
"""Étape texte : Mistral fabrique un prompt image varié + une légende."""
import json
import random

from base.services.ai.factory import get_provider
from .styles import STYLE_PALETTE

SYSTEM = (
    "Tu es directeur artistique culinaire ET copywriter. À partir des infos "
    "d'un plat et d'un restaurant, tu produis (1) un PROMPT en anglais pour un "
    "modèle de génération d'image, décrivant une photo de plat ultra "
    "appétissante, et (2) une LÉGENDE courte en français, émotionnelle et "
    "percutante, prête à copier pour WhatsApp/réseaux (avec 1-3 emojis). "
    "Tu DOIS adopter le style visuel imposé ci-dessous. "
    "Réponds UNIQUEMENT en JSON : "
    '{\"image_prompt\": \"...\", \"caption\": \"...\", \"style\": \"<style_key>\"}.'
)


def _context(restaurant, menu_item, user_text, source_image_present, style):
    parts = [f"Restaurant: {restaurant.name}"]
    if restaurant.address:
        parts.append(f"Lieu: {restaurant.address}")
    parts.append(
        f"Couleurs marque: {restaurant.primary_color}, {restaurant.secondary_color}")
    if menu_item is not None:
        parts.append(f"Plat: {menu_item.name}")
        if menu_item.description:
            parts.append(f"Description: {menu_item.description}")
        if menu_item.ingredients:
            parts.append(f"Ingrédients: {menu_item.ingredients}")
        price = menu_item.discount_price or menu_item.price
        parts.append(f"Prix: {price:.0f} FCFA")
    if user_text:
        parts.append(f"Angle/offre demandé: {user_text}")
    if source_image_present:
        parts.append("Une image de référence du plat est fournie séparément.")
    parts.append(
        f"STYLE IMPOSÉ (style_key={style['key']}): {style['label']} — {style['brief']}")
    return "\n".join(parts)


def _fallback(restaurant, menu_item, style):
    name = menu_item.name if menu_item is not None else restaurant.name
    return {
        "image_prompt": (
            f"professional appetizing food photography of {name}, "
            f"{style['brief']}, high detail, mouth-watering"),
        "caption": f"{name} vous attend chez {restaurant.name} ! 😋",
        "style": style["key"],
    }


def build(restaurant, menu_item, user_text, source_image_present, exclude_style=None):
    pool = [s for s in STYLE_PALETTE if s["key"] != exclude_style] or STYLE_PALETTE
    style = random.choice(pool)

    provider = get_provider()
    if provider is None:
        return _fallback(restaurant, menu_item, style)

    context = _context(restaurant, menu_item, user_text, source_image_present, style)
    try:
        raw = provider.complete(SYSTEM, [{"role": "user", "content": context}])
        data = json.loads(raw)
        return {
            "image_prompt": data.get("image_prompt") or _fallback(restaurant, menu_item, style)["image_prompt"],
            "caption": data.get("caption") or _fallback(restaurant, menu_item, style)["caption"],
            "style": data.get("style") or style["key"],
        }
    except (ValueError, KeyError, TypeError, Exception):
        return _fallback(restaurant, menu_item, style)
```

Note : le `except ... Exception` large est volontaire — l'étape texte ne doit jamais casser la génération ; en cas de souci provider on retombe sur le fallback. Ne PAS masquer d'erreur de programmation ici : garder l'ordre (ValueError, KeyError, TypeError, Exception) et le comportement de repli.

- [ ] **Step 5: Lancer les tests (succès)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.PromptBuilderTest -v 2`
Expected: PASS (3)

- [ ] **Step 6: Commit**

```bash
git add base/services/imagegen/ base/test_imagegen.py
git commit -m "feat: palette de styles + prompt-builder IA (prompt image varié + légende)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Client OpenRouter (génération d'image)

**Files:**
- Create: `base/services/imagegen/errors.py`
- Create: `base/services/imagegen/openrouter.py`
- Test: `base/test_imagegen.py`

**Interfaces:**
- Produces:
  - `errors.ImageGenError`, `errors.QuotaExceeded`, `errors.Disabled` (exceptions).
  - `openrouter.generate_image(prompt, model, size, api_key, reference_image_url=None) -> bytes`.

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_imagegen.py` :

```python
import base64
from base.services.imagegen import openrouter
from base.services.imagegen.errors import ImageGenError


class OpenRouterClientTest(TestCase):
    @patch("base.services.imagegen.openrouter.requests.post")
    def test_generate_image_returns_bytes_from_b64(self, mock_post):
        raw = b"PNGDATA"
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"b64_json": base64.b64encode(raw).decode()}]},
        )
        mock_post.return_value.raise_for_status = lambda: None
        out = openrouter.generate_image("a plate", "openai/gpt-image-1-mini", "1024x1536", "KEY")
        self.assertEqual(out, raw)

    def test_missing_key_raises(self):
        with self.assertRaises(ImageGenError):
            openrouter.generate_image("a plate", "m", "1024x1536", "")

    @patch("base.services.imagegen.openrouter.requests.post")
    def test_http_error_raises_imagegenerror(self, mock_post):
        def boom():
            raise Exception("500")
        mock_post.return_value = MagicMock(status_code=500, raise_for_status=boom)
        with self.assertRaises(ImageGenError):
            openrouter.generate_image("a plate", "m", "1024x1536", "KEY")
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.OpenRouterClientTest -v 2`
Expected: FAIL (module inexistant)

- [ ] **Step 3: Créer les exceptions**

Créer `base/services/imagegen/errors.py` :

```python
class ImageGenError(Exception):
    """Échec de génération d'image (config, réseau, réponse invalide)."""


class QuotaExceeded(ImageGenError):
    """Quota quotidien du restaurant atteint."""


class Disabled(ImageGenError):
    """Fonctionnalité désactivée globalement."""
```

- [ ] **Step 4: Créer le client**

**⚠️ AVANT de coder, l'implémenteur DOIT récupérer la doc OpenRouter Image API pour confirmer le format exact requête/réponse** (WebFetch sur `https://openrouter.ai/docs/guides/overview/multimodal/image-generation` et `https://openrouter.ai/blog/announcements/image-api/`). Adapter le corps de requête et le parsing en conséquence. L'implémentation ci-dessous est une base défensive (gère réponse `b64_json` OU `url`) ; ajuster les noms de champs si la doc diffère, mais **conserver la signature et le comportement d'erreur** (les tests en dépendent), et garder le parsing tolérant b64/url.

Créer `base/services/imagegen/openrouter.py` :

```python
"""Client de l'API Image unifiée d'OpenRouter."""
import base64

import requests

from .errors import ImageGenError

API_URL = "https://openrouter.ai/api/v1/images"


def generate_image(prompt, model, size, api_key, reference_image_url=None):
    if not api_key:
        raise ImageGenError("Clé API OpenRouter manquante")

    payload = {"model": model, "prompt": prompt, "size": size}
    if reference_image_url:
        # Les modèles d'édition acceptent une image de référence ; ignorée
        # silencieusement par les modèles text-to-image purs.
        payload["image"] = reference_image_url

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # réseau, HTTP != 2xx, JSON invalide
        raise ImageGenError(f"Échec OpenRouter : {exc}") from exc

    try:
        item = data["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ImageGenError("Réponse OpenRouter inattendue") from exc

    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        try:
            img = requests.get(item["url"], timeout=60)
            img.raise_for_status()
            return img.content
        except Exception as exc:
            raise ImageGenError(f"Téléchargement image échoué : {exc}") from exc
    raise ImageGenError("Aucune image dans la réponse OpenRouter")
```

- [ ] **Step 5: Lancer les tests (succès)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.OpenRouterClientTest -v 2`
Expected: PASS (3)

- [ ] **Step 6: Commit**

```bash
git add base/services/imagegen/errors.py base/services/imagegen/openrouter.py base/test_imagegen.py
git commit -m "feat: client OpenRouter Image API + exceptions imagegen

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Orchestrateur — generate/refine + quota

**Files:**
- Create: `base/services/imagegen/generator.py`
- Test: `base/test_imagegen.py`

**Interfaces:**
- Consumes: `prompt_builder.build`, `openrouter.generate_image`, `ImageGenSettings`, `MarketingPoster`, `cloudinary.uploader.upload`.
- Produces:
  - `generator.generate(restaurant, user, menu_item=None, user_text='', source_image_url=None) -> MarketingPoster`.
  - `generator.refine(poster, new_instructions, user) -> MarketingPoster`.
  - `generator.remaining_quota(restaurant) -> int`.

- [ ] **Step 1: Écrire les tests (échec attendu)**

Ajouter à `base/test_imagegen.py` :

```python
from base.services.imagegen import generator
from base.services.imagegen.errors import QuotaExceeded, Disabled


def _enable_imagegen(quota=5):
    s = ImageGenSettings.load()
    s.is_enabled = True
    s.openrouter_api_key = "KEY"
    s.daily_quota_per_restaurant = quota
    s.save()
    return s


class GeneratorTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.user = self.resto.owner
        _enable_imagegen()

    @patch("base.services.imagegen.generator.cloudinary.uploader.upload",
           return_value={"public_id": "posters/x", "secure_url": "http://img"})
    @patch("base.services.imagegen.generator.openrouter.generate_image",
           return_value=b"PNG")
    @patch("base.services.imagegen.generator.prompt_builder.build",
           return_value={"image_prompt": "p", "caption": "c", "style": "macro"})
    def test_generate_creates_poster(self, mb, mg, mu):
        poster = generator.generate(self.resto, self.user, user_text="promo")
        self.assertEqual(poster.caption, "c")
        self.assertEqual(poster.style, "macro")
        self.assertEqual(self.resto.posters.count(), 1)

    def test_generate_disabled_raises(self):
        s = ImageGenSettings.load()
        s.is_enabled = False
        s.save()
        with self.assertRaises(Disabled):
            generator.generate(self.resto, self.user)

    @patch("base.services.imagegen.generator.cloudinary.uploader.upload",
           return_value={"public_id": "posters/x"})
    @patch("base.services.imagegen.generator.openrouter.generate_image", return_value=b"PNG")
    @patch("base.services.imagegen.generator.prompt_builder.build",
           return_value={"image_prompt": "p", "caption": "c", "style": "macro"})
    def test_quota_exceeded_raises(self, mb, mg, mu):
        _enable_imagegen(quota=1)
        generator.generate(self.resto, self.user)
        with self.assertRaises(QuotaExceeded):
            generator.generate(self.resto, self.user)

    @patch("base.services.imagegen.generator.cloudinary.uploader.upload",
           return_value={"public_id": "posters/x"})
    @patch("base.services.imagegen.generator.openrouter.generate_image", return_value=b"PNG")
    @patch("base.services.imagegen.generator.prompt_builder.build",
           return_value={"image_prompt": "p2", "caption": "c2", "style": "pop"})
    def test_refine_links_parent(self, mb, mg, mu):
        parent = MarketingPoster.objects.create(
            restaurant=self.resto, caption="c", style="macro")
        child = generator.refine(parent, "plus lumineux", self.user)
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.user_text, "plus lumineux")
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.GeneratorTest -v 2`
Expected: FAIL (module inexistant)

- [ ] **Step 3: Créer l'orchestrateur**

Créer `base/services/imagegen/generator.py` :

```python
"""Orchestration : quota → prompt (Mistral) → image (OpenRouter) → Cloudinary."""
from datetime import timedelta
from io import BytesIO

import cloudinary.uploader
from django.utils import timezone

from base.models import ImageGenSettings, MarketingPoster
from . import prompt_builder, openrouter
from .errors import Disabled, QuotaExceeded, ImageGenError


def _used_today(restaurant):
    since = timezone.now() - timedelta(days=1)
    return MarketingPoster.objects.filter(
        restaurant=restaurant, created_at__gte=since).count()


def remaining_quota(restaurant):
    settings = ImageGenSettings.load()
    return max(0, settings.daily_quota_per_restaurant - _used_today(restaurant))


def _check(settings, restaurant):
    if not settings.is_enabled:
        raise Disabled("Génération d'image désactivée")
    if _used_today(restaurant) >= settings.daily_quota_per_restaurant:
        raise QuotaExceeded("Quota quotidien atteint")


def _run(restaurant, user, menu_item, user_text, source_image_url, parent, exclude_style):
    settings = ImageGenSettings.load()
    _check(settings, restaurant)

    built = prompt_builder.build(
        restaurant, menu_item, user_text, bool(source_image_url), exclude_style)
    image_bytes = openrouter.generate_image(
        built["image_prompt"], settings.effective_model(),
        settings.image_size, settings.openrouter_api_key,
        reference_image_url=source_image_url)

    upload = cloudinary.uploader.upload(
        BytesIO(image_bytes), folder=f"posters/{restaurant.id}",
        resource_type="image")

    return MarketingPoster.objects.create(
        restaurant=restaurant,
        menu_item=menu_item,
        image=upload.get("public_id", ""),
        caption=built["caption"],
        prompt_used=built["image_prompt"],
        style=built["style"],
        user_text=user_text,
        parent=parent,
        created_by=user,
    )


def generate(restaurant, user, menu_item=None, user_text="", source_image_url=None):
    return _run(restaurant, user, menu_item, user_text, source_image_url,
                parent=None, exclude_style=None)


def refine(poster, new_instructions, user):
    ref_url = None
    if poster.image:
        try:
            ref_url = poster.image.url
        except Exception:
            ref_url = None
    return _run(
        poster.restaurant, user, poster.menu_item, new_instructions,
        source_image_url=ref_url, parent=poster, exclude_style=None)
```

- [ ] **Step 4: Lancer les tests (succès)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.GeneratorTest -v 2`
Expected: PASS (4)

- [ ] **Step 5: Commit**

```bash
git add base/services/imagegen/generator.py base/test_imagegen.py
git commit -m "feat: orchestrateur imagegen (generate/refine + quota/jour)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Vues dashboard + URLs + gating serveur

**Files:**
- Modify: `base/views.py` (vues `posters_studio`, `posters_generate`, `posters_refine`)
- Modify: `base/urls.py` (routes `affiches/`)
- Test: `base/test_imagegen.py`

**Interfaces:**
- Consumes: `generator.generate/refine/remaining_quota`, `ImageGenSettings`, `Restaurant.is_pro()`, `@owner_or_coadmin_required`, `MenuItem`.
- Produces: URLs `posters_studio` (`affiches/`), `posters_generate` (`affiches/generer/`), `posters_refine` (`affiches/<int:poster_id>/raffiner/`).

- [ ] **Step 1: Écrire le test (échec attendu)**

Ajouter à `base/test_imagegen.py` :

```python
from django.urls import reverse


def make_pro(resto):
    from base.models import SubscriptionPlan
    from django.utils import timezone as tz
    from datetime import timedelta as td
    plan = SubscriptionPlan.objects.create(name="Pro", plan_type="pro", price=1)
    resto.subscription_plan = plan
    resto.subscription_end = tz.now() + td(days=10)
    resto.save()


class PostersViewGatingTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.client.force_login(self.owner)
        _enable_imagegen()

    def _host(self):
        return {"HTTP_HOST": f"{self.resto.subdomain}.testserver"}

    def test_studio_forbidden_for_free_plan(self):
        # non-pro → 404 (mirror sidebar/feedback gating)
        resp = self.client.get(reverse("posters_studio"), **self._host())
        self.assertIn(resp.status_code, (302, 404))

    def test_studio_ok_for_pro(self):
        make_pro(self.resto)
        resp = self.client.get(reverse("posters_studio"), **self._host())
        self.assertEqual(resp.status_code, 200)
```

Note multi-tenant : réutiliser exactement le pattern host/`force_login` déjà utilisé par les tests dashboard qui passent dans `base/test_parcours.py` (ex. `SettingsCommunityTest`, `FeedbackDashboardTest`). Si la résolution `request.restaurant` diffère, aligner `_host()` sur ce pattern. Ne pas bloquer sur le harnais : si vraiment insoluble, `@unittest.skip` documenté + vérif manuelle.

- [ ] **Step 2: Lancer (échec attendu)**

Run: `./env/bin/python3 manage.py test base.test_imagegen.PostersViewGatingTest -v 2`
Expected: FAIL (URL inexistante)

- [ ] **Step 3: Créer les vues**

Dans `base/views.py`, près de `feedback_list`, ajouter (vérifier que `owner_or_coadmin_required`, `redirect`, `render`, `get_object_or_404`, `JsonResponse`, `Http404`, `MenuItem` sont importés — ajouter ce qui manque) :

```python
@owner_or_coadmin_required
def posters_studio(request):
    restaurant = request.restaurant
    if not restaurant.is_pro():
        raise Http404()
    from base.models import ImageGenSettings, MenuItem
    from base.services.imagegen import generator
    settings = ImageGenSettings.load()
    return render(request, "admin_user/posters/studio.html", {
        "restaurant": restaurant,
        "enabled": settings.is_enabled,
        "menu_items": MenuItem.objects.filter(restaurant=restaurant),
        "posters": restaurant.posters.all()[:60],
        "remaining": generator.remaining_quota(restaurant),
    })


def _guard_pro(request):
    if not request.restaurant.is_pro():
        raise Http404()


@owner_or_coadmin_required
@require_POST
def posters_generate(request):
    _guard_pro(request)
    from base.models import MenuItem
    from base.services.imagegen import generator
    from base.services.imagegen.errors import ImageGenError
    restaurant = request.restaurant
    menu_item = None
    mid = request.POST.get("menu_item")
    if mid:
        menu_item = MenuItem.objects.filter(id=mid, restaurant=restaurant).first()
    user_text = request.POST.get("user_text", "").strip()
    source_url = None
    if menu_item and menu_item.image:
        try:
            source_url = menu_item.image.url
        except Exception:
            source_url = None
    try:
        generator.generate(restaurant, request.user, menu_item=menu_item,
                            user_text=user_text, source_image_url=source_url)
        messages.success(request, "Affiche générée.")
    except ImageGenError as exc:
        messages.error(request, f"Échec : {exc}")
    return redirect("posters_studio")


@owner_or_coadmin_required
@require_POST
def posters_refine(request, poster_id):
    _guard_pro(request)
    from base.models import MarketingPoster
    from base.services.imagegen import generator
    from base.services.imagegen.errors import ImageGenError
    poster = get_object_or_404(
        MarketingPoster, id=poster_id, restaurant=request.restaurant)
    instructions = request.POST.get("instructions", "").strip()
    try:
        generator.refine(poster, instructions, request.user)
        messages.success(request, "Nouvelle version générée.")
    except ImageGenError as exc:
        messages.error(request, f"Échec : {exc}")
    return redirect("posters_studio")
```

- [ ] **Step 4: Ajouter les routes**

Dans `base/urls.py`, après la route `retours/`, ajouter (et importer les vues) :

```python
    path("affiches/", posters_studio, name="posters_studio"),
    path("affiches/generer/", posters_generate, name="posters_generate"),
    path("affiches/<int:poster_id>/raffiner/", posters_refine, name="posters_refine"),
```

- [ ] **Step 5: Lancer le test**

Run: `./env/bin/python3 manage.py test base.test_imagegen.PostersViewGatingTest -v 2`
Expected: PASS (ou skip documenté si multi-tenant insoluble).

- [ ] **Step 6: Commit**

```bash
git add base/views.py base/urls.py base/test_imagegen.py
git commit -m "feat: vues studio d'affiches (generate/refine) + gating Pro serveur

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: UI — page studio, galerie, raffinage, sidebar

**Files:**
- Create: `templates/admin_user/posters/studio.html`
- Modify: `templates/admin_user/sidebar.html`
- Test: manuel (rendu template) — pas de test unitaire ; lancer la suite pour non-régression.

**Interfaces:**
- Consumes: contexte de `posters_studio` (`restaurant`, `enabled`, `menu_items`, `posters`, `remaining`), URLs `posters_generate`, `posters_refine`.

- [ ] **Step 1: Créer le template studio**

Créer `templates/admin_user/posters/studio.html` (calquer l'ossature de `templates/admin_user/customers/list.html` : `{% extends "admin_user/base.html" %}`, blocs `title`, `page_title`, `content`) :

```html
{% extends "admin_user/base.html" %}
{% load static %}
{% block title %}Affiches — {{ restaurant.name }}{% endblock %}
{% block page_title %}Affiches marketing{% endblock %}
{% block content %}
<div class="p-4 space-y-6">

  {% if not enabled %}
    <div class="rounded-xl bg-amber-50 border border-amber-100 p-4 text-sm text-amber-800">
      La génération d'affiches est momentanément indisponible.
    </div>
  {% endif %}

  <form method="post" action="{% url 'posters_generate' %}"
        class="rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
    {% csrf_token %}
    <div class="flex items-center justify-between">
      <h2 class="font-semibold text-slate-800">Générer une affiche</h2>
      <span class="text-xs text-slate-500">{{ remaining }} génération(s) restante(s) aujourd'hui</span>
    </div>
    <div>
      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Plat</label>
      <select name="menu_item" class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm">
        <option value="">— Aucun (affiche générique) —</option>
        {% for it in menu_items %}
        <option value="{{ it.id }}">{{ it.name }}</option>
        {% endfor %}
      </select>
    </div>
    <div>
      <label class="block text-xs font-semibold uppercase tracking-wide text-slate-500 mb-1">Angle / offre (optionnel)</label>
      <input type="text" name="user_text" maxlength="300" placeholder="ex : promo -20% ce week-end"
             class="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm" />
    </div>
    <button type="submit" {% if not enabled or remaining == 0 %}disabled{% endif %}
            class="rounded-xl bg-primary px-5 py-2 text-white text-sm font-semibold disabled:opacity-50">
      🎨 Générer
    </button>
  </form>

  <div>
    <h2 class="font-semibold text-slate-800 mb-3">Vos affiches</h2>
    {% if not posters %}
      <p class="text-sm text-slate-500">Aucune affiche pour l'instant.</p>
    {% else %}
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {% for p in posters %}
        <div class="rounded-2xl border border-slate-200 bg-white overflow-hidden">
          {% if p.image %}
          <img src="{{ p.image.url }}" alt="Affiche" class="w-full aspect-[3/4] object-cover" />
          {% endif %}
          <div class="p-3 space-y-2">
            <p class="text-sm text-slate-700 whitespace-pre-line">{{ p.caption }}</p>
            <div class="flex flex-wrap gap-2">
              {% if p.image %}
              <a href="{{ p.image.url }}" download target="_blank"
                 class="text-xs rounded-lg bg-slate-800 text-white px-3 py-1">Télécharger</a>
              {% endif %}
              <button type="button" class="text-xs rounded-lg bg-slate-100 px-3 py-1 copy-caption"
                      data-caption="{{ p.caption }}">Copier la légende</button>
            </div>
            <form method="post" action="{% url 'posters_refine' p.id %}" class="flex gap-2 pt-1">
              {% csrf_token %}
              <input type="text" name="instructions" placeholder="Raffiner : plus lumineux…"
                     class="flex-1 rounded-lg border border-slate-200 px-2 py-1 text-xs" />
              <button type="submit" {% if remaining == 0 %}disabled{% endif %}
                      class="text-xs rounded-lg bg-primary text-white px-3 py-1 disabled:opacity-50">↻</button>
            </form>
          </div>
        </div>
        {% endfor %}
      </div>
    {% endif %}
  </div>
</div>

<script>
document.querySelectorAll('.copy-caption').forEach(function (b) {
  b.addEventListener('click', function () {
    navigator.clipboard.writeText(b.dataset.caption || '').then(function () {
      var t = b.textContent; b.textContent = 'Copié ✓';
      setTimeout(function () { b.textContent = t; }, 1500);
    });
  });
});
</script>
{% endblock %}
```

- [ ] **Step 2: Ajouter l'entrée sidebar**

Dans `templates/admin_user/sidebar.html`, déclarer l'URL en haut avec les autres :

```html
  {% url 'posters_studio'       as url_posters      %}
```

Puis, dans la zone owner/coadmin (près de « Retours »/« Clients »), ajouter (gaté Pro) :

```html
{% if restaurant.is_pro %}
<a href="{{ url_posters }}"
   class="flex items-center gap-3 rounded-xl px-3 py-2 text-sm
          {% if current == url_posters %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <span>🎨</span>
  {% trans "Affiches" %}
</a>
{% endif %}
```

- [ ] **Step 3: Vérifier le rendu (manuel) + non-régression**

Run: `./env/bin/python3 manage.py test base --noinput`
Expected: toute la suite passe (aucune régression).

Vérifier aussi qu'aucune erreur de template n'est levée en résolvant l'URL `posters_studio` pour un resto Pro (déjà couvert par `PostersViewGatingTest.test_studio_ok_for_pro` en Task 6, qui rend le template).

- [ ] **Step 4: Commit**

```bash
git add templates/admin_user/posters/studio.html templates/admin_user/sidebar.html
git commit -m "feat: page studio d'affiches (galerie, téléchargement, copie légende, raffinage) + sidebar

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review (couverture spec)

- **ImageGenSettings super-admin (liste + saisie libre)** → Task 1 (`image_model` choices + `image_model_custom` + `effective_model`). ✅
- **Quota/jour, plateforme paie** → Task 1 (champ) + Task 5 (`_check`/`remaining_quota`). ✅
- **MarketingPoster + chaîne raffinage** → Task 2. ✅
- **Palette de styles + variété** → Task 3 (`STYLE_PALETTE`, `random.choice` avec `exclude_style`). ✅
- **Prompt-builder Mistral (prompt image + légende), repli** → Task 3. ✅
- **Client OpenRouter (référence image, b64/url), erreurs** → Task 4. ✅
- **Orchestrateur generate/refine, Cloudinary** → Task 5. ✅
- **Vues + gating Pro/rôle/enabled + quota** → Task 6. ✅
- **UI studio + galerie + download + copie + raffinage + sidebar** → Task 7. ✅

**Risques / à surveiller :**
- **Format exact de l'API Image OpenRouter** (Task 4) : l'implémenteur DOIT confirmer via la doc (WebFetch) et ajuster requête/parsing, en gardant signature + comportement d'erreur.
- **Résolution multi-tenant** dans les tests de vues (Task 6) : réutiliser le pattern host des tests dashboard qui passent ; skip documenté toléré en dernier recours.
- **`provider.complete` température 0.3** : la variété vient surtout de la rotation de styles (`exclude_style` + `random.choice`), pas de la température — c'est voulu.
