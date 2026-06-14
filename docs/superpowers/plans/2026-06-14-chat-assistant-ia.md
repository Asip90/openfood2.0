# Assistant IA conversationnel pour clients — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a premium floating assistant on the customer menu page that recommends dishes, advises by budget (FCFA), gives dish info, and calls staff — with action buttons (view detail / add to cart / call waiter) reusing existing endpoints.

**Architecture:** A global singleton `AISettings` (Jazzmin) holds provider/key/model. A provider layer (`base/services/ai/`) abstracts Mistral & Gemini behind one interface. An `assistant` service injects the restaurant menu into the system prompt and forces a structured JSON response (`{reply, actions}`); the backend validates every `item_id`. A new `chat_assistant` view keeps ephemeral history in the Django session. The frontend is an Alpine.js FAB that expands to a bell (waiter call, with confirm modal) and a chat icon, reusing the page's `cartStore()` methods and item data.

**Tech Stack:** Django, Jazzmin admin, `requests` (already installed), Tailwind + Alpine.js, Mistral / Gemini HTTP APIs.

**Reference spec:** `docs/superpowers/specs/2026-06-14-chat-assistant-ia-design.md`

---

## File Structure

**New:**
- `base/services/__init__.py` (if missing) and `base/services/ai/__init__.py` — package
- `base/services/ai/base.py` — `AIProvider` interface
- `base/services/ai/mistral.py` — `MistralProvider`
- `base/services/ai/gemini.py` — `GeminiProvider`
- `base/services/ai/factory.py` — `get_provider()`
- `base/services/ai/assistant.py` — `serialize_menu`, `build_system_prompt`, `validate_response`, `ask`, `is_assistant_available`
- `base/test_ai.py` — backend tests
- `templates/customer/_chat_assistant.html` — FAB + chat component
- `customer/test_chat.py` — view tests

**Modified:**
- `base/models.py` — append `AISettings`
- `base/admin.py` — register `AISettings` (singleton)
- `customer/views.py` — add `chat_assistant`
- `customer/urls.py` — add chat route
- `templates/customer/menu.html` — replace old waiter FAB with new FAB, add `window.MENU_ITEMS`, include partial

> Note: `base/services/` already exists as a directory (see `ls base/`). Only create `__init__.py` files if absent.

---

## Task 1: `AISettings` singleton model

**Files:**
- Modify: `base/models.py` (append at end of file)
- Test: `base/test_ai.py` (create)

- [ ] **Step 1: Write the failing test**

Create `base/test_ai.py`:

```python
from django.test import TestCase
from base.models import AISettings


class AISettingsModelTest(TestCase):
    def test_load_returns_singleton(self):
        a = AISettings.load()
        b = AISettings.load()
        self.assertEqual(a.pk, b.pk)
        self.assertEqual(AISettings.objects.count(), 1)

    def test_save_forces_single_row(self):
        AISettings.load()
        second = AISettings(provider="gemini")
        second.save()
        self.assertEqual(AISettings.objects.count(), 1)
        self.assertEqual(AISettings.objects.get().provider, "gemini")

    def test_defaults(self):
        a = AISettings.load()
        self.assertFalse(a.is_enabled)
        self.assertEqual(a.max_messages_per_session, 20)
        self.assertEqual(a.provider, "mistral")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai -v1`
Expected: FAIL — `ImportError: cannot import name 'AISettings'`

- [ ] **Step 3: Append the model to `base/models.py`**

```python
class AISettings(models.Model):
    PROVIDER_CHOICES = [
        ('mistral', 'Mistral'),
        ('gemini', 'Gemini'),
    ]
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default='mistral')
    api_key = models.CharField(max_length=255, blank=True)
    model = models.CharField(max_length=100, default='mistral-small-latest')
    is_enabled = models.BooleanField(default=False)
    system_prompt = models.TextField(blank=True)
    max_messages_per_session = models.PositiveIntegerField(default=20)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Paramètres IA"
        verbose_name_plural = "Paramètres IA"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Paramètres IA ({self.provider})"
```

- [ ] **Step 4: Create the migration**

Run: `python manage.py makemigrations base`
Expected: creates `base/migrations/0014_aisettings.py`

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test base.test_ai -v1`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add base/models.py base/migrations/0014_aisettings.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add AISettings singleton model

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: Register `AISettings` in Jazzmin (singleton)

**Files:**
- Modify: `base/admin.py`
- Test: `base/test_ai.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from django.contrib import admin as dj_admin
from base.admin import AISettingsAdmin


class AISettingsAdminTest(TestCase):
    def test_registered(self):
        self.assertIn(AISettings, dj_admin.site._registry)

    def test_add_disabled_when_instance_exists(self):
        AISettings.load()
        admin_obj = AISettingsAdmin(AISettings, dj_admin.site)
        request = None
        self.assertFalse(admin_obj.has_add_permission(request))

    def test_add_allowed_when_empty(self):
        admin_obj = AISettingsAdmin(AISettings, dj_admin.site)
        self.assertTrue(admin_obj.has_add_permission(None))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.AISettingsAdminTest -v1`
Expected: FAIL — `ImportError: cannot import name 'AISettingsAdmin'`

- [ ] **Step 3: Add admin registration to `base/admin.py`**

Add these imports/class (place near other admin registrations; keep existing `from .models import ...` lines — add `AISettings` to them or add a new import):

```python
from django import forms
from .models import AISettings


class AISettingsForm(forms.ModelForm):
    class Meta:
        model = AISettings
        fields = "__all__"
        widgets = {
            "api_key": forms.PasswordInput(render_value=True),
        }


@admin.register(AISettings)
class AISettingsAdmin(admin.ModelAdmin):
    form = AISettingsForm
    list_display = ("provider", "model", "is_enabled", "updated_at")

    def has_add_permission(self, request):
        return not AISettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
```

> If `base/admin.py` already does `from django.contrib import admin`, reuse it. Ensure `admin` is imported.

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.AISettingsAdminTest -v1`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add base/admin.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: register AISettings in admin as singleton

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: AI package + provider interface

**Files:**
- Create: `base/services/ai/__init__.py`, `base/services/ai/base.py`
- Create if missing: `base/services/__init__.py`
- Test: `base/test_ai.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from base.services.ai.base import AIProvider


class AIProviderInterfaceTest(TestCase):
    def test_stores_credentials(self):
        p = AIProvider(api_key="k", model="m")
        self.assertEqual(p.api_key, "k")
        self.assertEqual(p.model, "m")

    def test_complete_not_implemented(self):
        p = AIProvider(api_key="k", model="m")
        with self.assertRaises(NotImplementedError):
            p.complete("sys", [{"role": "user", "content": "hi"}])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.AIProviderInterfaceTest -v1`
Expected: FAIL — `ModuleNotFoundError: No module named 'base.services.ai'`

- [ ] **Step 3: Create the package files**

Create `base/services/__init__.py` (only if it does not already exist) — empty file.

Create `base/services/ai/__init__.py` — empty file.

Create `base/services/ai/base.py`:

```python
class AIProvider:
    """Common interface for LLM providers. complete() returns the raw text
    reply from the model (expected to be a JSON string)."""

    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def complete(self, system, messages):
        raise NotImplementedError
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.AIProviderInterfaceTest -v1`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add base/services/__init__.py base/services/ai/__init__.py base/services/ai/base.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add AI provider package and base interface

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Mistral provider

**Files:**
- Create: `base/services/ai/mistral.py`
- Test: `base/test_ai.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from unittest.mock import patch, MagicMock
from base.services.ai.mistral import MistralProvider


class MistralProviderTest(TestCase):
    @patch("base.services.ai.mistral.requests.post")
    def test_complete_returns_content_and_sends_auth(self, mock_post):
        resp = MagicMock()
        resp.json.return_value = {"choices": [{"message": {"content": '{"reply":"ok"}'}}]}
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        p = MistralProvider(api_key="secret", model="mistral-small-latest")
        out = p.complete("SYS", [{"role": "user", "content": "salut"}])

        self.assertEqual(out, '{"reply":"ok"}')
        _, kwargs = mock_post.call_args
        self.assertEqual(kwargs["json"]["model"], "mistral-small-latest")
        self.assertEqual(kwargs["json"]["messages"][0], {"role": "system", "content": "SYS"})
        self.assertEqual(kwargs["json"]["response_format"], {"type": "json_object"})
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer secret")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.MistralProviderTest -v1`
Expected: FAIL — `ModuleNotFoundError: No module named 'base.services.ai.mistral'`

- [ ] **Step 3: Create `base/services/ai/mistral.py`**

```python
import requests

from .base import AIProvider


class MistralProvider(AIProvider):
    API_URL = "https://api.mistral.ai/v1/chat/completions"

    def complete(self, system, messages):
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}] + messages,
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
            "max_tokens": 500,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = requests.post(self.API_URL, json=payload, headers=headers, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.MistralProviderTest -v1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add base/services/ai/mistral.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add Mistral AI provider

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 5: Gemini provider

**Files:**
- Create: `base/services/ai/gemini.py`
- Test: `base/test_ai.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from base.services.ai.gemini import GeminiProvider


class GeminiProviderTest(TestCase):
    @patch("base.services.ai.gemini.requests.post")
    def test_complete_maps_roles_and_returns_text(self, mock_post):
        resp = MagicMock()
        resp.json.return_value = {
            "candidates": [{"content": {"parts": [{"text": '{"reply":"ok"}'}]}}]
        }
        resp.raise_for_status = MagicMock()
        mock_post.return_value = resp

        p = GeminiProvider(api_key="secret", model="gemini-2.0-flash")
        out = p.complete("SYS", [
            {"role": "user", "content": "salut"},
            {"role": "assistant", "content": "bonjour"},
        ])

        self.assertEqual(out, '{"reply":"ok"}')
        args, kwargs = mock_post.call_args
        url = args[0]
        self.assertIn("gemini-2.0-flash:generateContent", url)
        self.assertIn("key=secret", url)
        self.assertEqual(kwargs["json"]["systemInstruction"]["parts"][0]["text"], "SYS")
        # assistant role must be mapped to "model"
        self.assertEqual(kwargs["json"]["contents"][1]["role"], "model")
        self.assertEqual(
            kwargs["json"]["generationConfig"]["responseMimeType"], "application/json"
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.GeminiProviderTest -v1`
Expected: FAIL — `ModuleNotFoundError: No module named 'base.services.ai.gemini'`

- [ ] **Step 3: Create `base/services/ai/gemini.py`**

```python
import requests

from .base import AIProvider


class GeminiProvider(AIProvider):
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def complete(self, system, messages):
        contents = []
        for m in messages:
            role = "model" if m["role"] == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": m["content"]}]})
        payload = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": contents,
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.3,
                "maxOutputTokens": 500,
            },
        }
        url = f"{self.BASE_URL}/{self.model}:generateContent?key={self.api_key}"
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.GeminiProviderTest -v1`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add base/services/ai/gemini.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add Gemini AI provider

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 6: Provider factory

**Files:**
- Create: `base/services/ai/factory.py`
- Test: `base/test_ai.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from base.services.ai.factory import get_provider


class FactoryTest(TestCase):
    def test_returns_mistral(self):
        s = AISettings.load()
        s.provider = "mistral"
        s.api_key = "k"
        s.model = "m1"
        s.save()
        p = get_provider()
        self.assertEqual(p.__class__.__name__, "MistralProvider")
        self.assertEqual(p.model, "m1")

    def test_returns_gemini(self):
        s = AISettings.load()
        s.provider = "gemini"
        s.save()
        self.assertEqual(get_provider().__class__.__name__, "GeminiProvider")

    def test_unknown_provider_returns_none(self):
        s = AISettings.load()
        s.provider = "mistral"
        s.save()
        s.provider = "unknown"  # bypass choices validation in memory
        self.assertIsNone(get_provider(s))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.FactoryTest -v1`
Expected: FAIL — `ModuleNotFoundError: No module named 'base.services.ai.factory'`

- [ ] **Step 3: Create `base/services/ai/factory.py`**

```python
from base.models import AISettings

from .mistral import MistralProvider
from .gemini import GeminiProvider

PROVIDERS = {
    "mistral": MistralProvider,
    "gemini": GeminiProvider,
}


def get_provider(settings=None):
    settings = settings or AISettings.load()
    provider_cls = PROVIDERS.get(settings.provider)
    if provider_cls is None:
        return None
    return provider_cls(api_key=settings.api_key, model=settings.model)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.FactoryTest -v1`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add base/services/ai/factory.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add AI provider factory

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 7: Assistant — menu serialization & system prompt

**Files:**
- Create: `base/services/ai/assistant.py`
- Test: `base/test_ai.py` (append)

> The tests need a Restaurant + Category + MenuItem. Use the real models. The custom `User` uses email as identifier (no `username` field) — create it with `User.objects.create_user(email=...)`. `Restaurant.objects.create(name=..., owner=user)` works as-is: `slug`/`subdomain` auto-generate in `save()`, and `address`/`phone`/`email` default to empty string. `Category.objects.create(restaurant=r, name=...)` works (`slug` auto, `order` defaults to 0).

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from accounts.models import User
from base.models import Restaurant, Category, MenuItem
from base.services.ai.assistant import serialize_menu, build_system_prompt


class MenuSerializationTest(TestCase):
    def _make_restaurant(self):
        user = User.objects.create_user(email="o1@example.com")
        return Restaurant.objects.create(name="Chez Test", owner=user)

    def test_serialize_includes_available_item_with_id_and_price(self):
        r = self._make_restaurant()
        cat = Category.objects.create(restaurant=r, name="Plats")
        MenuItem.objects.create(
            restaurant=r, category=cat, name="Riz arachide",
            price=2500, description="Plat complet", is_spicy=True, is_available=True,
        )
        out = serialize_menu(r)
        self.assertIn("Riz arachide", out)
        self.assertIn("2500", out)
        self.assertIn("épicé", out)

    def test_serialize_excludes_unavailable(self):
        r = self._make_restaurant()
        cat = Category.objects.create(restaurant=r, name="Plats")
        MenuItem.objects.create(
            restaurant=r, category=cat, name="Indispo",
            price=1000, is_available=False,
        )
        self.assertNotIn("Indispo", serialize_menu(r))

    def test_serialize_uses_discount_price_when_set(self):
        r = self._make_restaurant()
        cat = Category.objects.create(restaurant=r, name="Plats")
        MenuItem.objects.create(
            restaurant=r, category=cat, name="Promo",
            price=3000, discount_price=2000, is_available=True,
        )
        out = serialize_menu(r)
        self.assertIn("2000", out)

    def test_system_prompt_contains_restaurant_name_and_menu(self):
        r = self._make_restaurant()
        cat = Category.objects.create(restaurant=r, name="Plats")
        MenuItem.objects.create(
            restaurant=r, category=cat, name="Attieke", price=1500, is_available=True,
        )
        prompt = build_system_prompt(r)
        self.assertIn("Chez Test", prompt)
        self.assertIn("Attieke", prompt)
        self.assertIn("JSON", prompt)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.MenuSerializationTest -v1`
Expected: FAIL — `ModuleNotFoundError: No module named 'base.services.ai.assistant'`

- [ ] **Step 3: Create `base/services/ai/assistant.py` (this part only)**

```python
import json

from base.models import AISettings, MenuItem

DEFAULT_SYSTEM_PROMPT = (
    'Tu es l\'assistant du restaurant "{restaurant_name}". '
    "Tu aides UNIQUEMENT sur le menu et le service : recommander des plats, "
    "conseiller selon un budget, donner les infos d'un plat (ingrédients, "
    "allergènes, végétarien, épicé), et proposer d'appeler le serveur. "
    "Refuse poliment toute demande hors menu/service et recentre vers le menu. "
    "Réponds en français, de façon courte et précise, ton chaleureux mais sobre, "
    "sans emoji. La monnaie est le FCFA. "
    "Réponds UNIQUEMENT en JSON valide de la forme "
    '{{"reply": "texte court", "actions": [ ... ]}}. '
    "Chaque action est l'un de : "
    '{{"type":"view_item","item_id":"<id>","label":"..."}}, '
    '{{"type":"add_to_cart","item_id":"<id>","label":"..."}}, '
    '{{"type":"call_waiter","label":"..."}}. '
    "N'invente jamais de plat : n'utilise que les id du MENU ci-dessous. "
    "actions peut être une liste vide.\n\nMENU:\n{menu}"
)


def serialize_menu(restaurant):
    items = (
        MenuItem.objects.filter(restaurant=restaurant, is_available=True)
        .select_related("category")
        .order_by("category__order", "order", "name")
    )
    lines = []
    for it in items:
        price = it.discount_price if it.discount_price else it.price
        tags = []
        if it.is_vegetarian:
            tags.append("végétarien")
        if it.is_vegan:
            tags.append("végan")
        if it.is_spicy:
            tags.append("épicé")
        desc = (it.description or "").strip().replace("\n", " ")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        line = f"- id={it.id} | {it.name} | {price:.0f} FCFA"
        if it.category_id:
            line += f" | catégorie: {it.category.name}"
        if desc:
            line += f" | {desc}"
        if it.allergens:
            line += f" | allergènes: {it.allergens}"
        if tags:
            line += f" | {', '.join(tags)}"
        lines.append(line)
    return "\n".join(lines) if lines else "(aucun plat disponible)"


def build_system_prompt(restaurant):
    settings = AISettings.load()
    template = settings.system_prompt.strip() or DEFAULT_SYSTEM_PROMPT
    menu = serialize_menu(restaurant)
    try:
        return template.format(restaurant_name=restaurant.name, menu=menu)
    except (KeyError, IndexError, ValueError):
        # Custom prompt without placeholders: append the menu so the model still
        # gets it, and ensure the JSON contract is present.
        return (
            f"{template}\n\nRestaurant: {restaurant.name}\n\nMENU:\n{menu}\n\n"
            'Réponds UNIQUEMENT en JSON {"reply": "...", "actions": [...]}.'
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.MenuSerializationTest -v1`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add base/services/ai/assistant.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add menu serialization and system prompt builder

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 8: Assistant — response validation, `ask`, availability

**Files:**
- Modify: `base/services/ai/assistant.py` (append functions)
- Test: `base/test_ai.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `base/test_ai.py`:

```python
from unittest.mock import patch as _patch
from base.services.ai.assistant import validate_response, ask, is_assistant_available


class ValidateResponseTest(TestCase):
    def _make_restaurant_with_item(self):
        user = User.objects.create_user(email="o2@example.com")
        r = Restaurant.objects.create(name="R2", owner=user)
        cat = Category.objects.create(restaurant=r, name="Plats")
        item = MenuItem.objects.create(
            restaurant=r, category=cat, name="Plat A", price=1000, is_available=True,
        )
        return r, item

    def test_valid_actions_kept(self):
        r, item = self._make_restaurant_with_item()
        raw = json.dumps({
            "reply": "Voici",
            "actions": [
                {"type": "view_item", "item_id": str(item.id), "label": "Voir"},
                {"type": "call_waiter", "label": "Serveur"},
            ],
        })
        out = validate_response(raw, r)
        self.assertEqual(out["reply"], "Voici")
        self.assertEqual(len(out["actions"]), 2)

    def test_unknown_item_id_dropped(self):
        r, item = self._make_restaurant_with_item()
        raw = json.dumps({
            "reply": "X",
            "actions": [{"type": "add_to_cart", "item_id": "999999", "label": "Z"}],
        })
        out = validate_response(raw, r)
        self.assertEqual(out["actions"], [])

    def test_unknown_action_type_dropped(self):
        r, item = self._make_restaurant_with_item()
        raw = json.dumps({"reply": "X", "actions": [{"type": "delete_db"}]})
        self.assertEqual(validate_response(raw, r)["actions"], [])

    def test_invalid_json_falls_back_to_text(self):
        r, item = self._make_restaurant_with_item()
        out = validate_response("pas du json", r)
        self.assertIn("pas du json", out["reply"])
        self.assertEqual(out["actions"], [])

    def test_missing_reply_gets_default(self):
        r, item = self._make_restaurant_with_item()
        out = validate_response(json.dumps({"actions": []}), r)
        self.assertTrue(out["reply"])


class AskTest(TestCase):
    def _make_restaurant(self):
        user = User.objects.create_user(email="o3@example.com")
        return Restaurant.objects.create(name="R3", owner=user)

    def test_unavailable_when_disabled(self):
        s = AISettings.load()
        s.is_enabled = False
        s.save()
        r = self._make_restaurant()
        out = ask(r, [], "salut")
        self.assertTrue(out.get("unavailable"))

    @_patch("base.services.ai.factory.get_provider")
    def test_calls_provider_and_validates(self, mock_get_provider):
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        provider = MagicMock()
        provider.complete.return_value = json.dumps({"reply": "Bonjour", "actions": []})
        mock_get_provider.return_value = provider
        r = self._make_restaurant()
        out = ask(r, [], "salut")
        self.assertEqual(out["reply"], "Bonjour")
        provider.complete.assert_called_once()

    @_patch("base.services.ai.factory.get_provider")
    def test_provider_exception_returns_graceful_error(self, mock_get_provider):
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        provider = MagicMock()
        provider.complete.side_effect = RuntimeError("boom")
        mock_get_provider.return_value = provider
        r = self._make_restaurant()
        out = ask(r, [], "salut")
        self.assertTrue(out.get("error"))
        self.assertTrue(any(a["type"] == "call_waiter" for a in out["actions"]))


class AvailabilityTest(TestCase):
    def test_false_when_disabled(self):
        s = AISettings.load()
        s.is_enabled = False
        s.api_key = "k"
        s.save()
        self.assertFalse(is_assistant_available())

    def test_true_when_enabled_with_key(self):
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        self.assertTrue(is_assistant_available())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test base.test_ai.ValidateResponseTest base.test_ai.AskTest base.test_ai.AvailabilityTest -v1`
Expected: FAIL — `ImportError: cannot import name 'validate_response'`

- [ ] **Step 3: Append to `base/services/ai/assistant.py`**

```python
_VALID_ACTION_TYPES = {"view_item", "add_to_cart", "call_waiter"}
_DEFAULT_LABELS = {
    "view_item": "Voir le plat",
    "add_to_cart": "Ajouter au panier",
    "call_waiter": "Appeler un serveur",
}


def _fallback_text(raw):
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:600]
    return "Désolé, le service est momentanément indisponible."


def validate_response(raw, restaurant):
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"reply": _fallback_text(raw), "actions": []}
    if not isinstance(data, dict):
        return {"reply": _fallback_text(raw), "actions": []}

    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        reply = "Désolé, je n'ai pas compris. Pouvez-vous reformuler ?"
    reply = reply.strip()[:600]

    valid_ids = set(
        str(i)
        for i in MenuItem.objects.filter(
            restaurant=restaurant, is_available=True
        ).values_list("id", flat=True)
    )

    actions = []
    for a in (data.get("actions") or []):
        if not isinstance(a, dict):
            continue
        atype = a.get("type")
        if atype not in _VALID_ACTION_TYPES:
            continue
        label = str(a.get("label", "")).strip()[:60] or _DEFAULT_LABELS[atype]
        if atype in ("view_item", "add_to_cart"):
            item_id = str(a.get("item_id", "")).strip()
            if item_id in valid_ids:
                actions.append({"type": atype, "item_id": item_id, "label": label})
        else:  # call_waiter
            actions.append({"type": "call_waiter", "label": label})
    return {"reply": reply, "actions": actions[:6]}


def is_assistant_available():
    s = AISettings.load()
    return bool(s.is_enabled and s.api_key)


def ask(restaurant, history, user_message):
    """history: list of {role, content}. Returns {reply, actions, ...}."""
    from .factory import get_provider

    settings = AISettings.load()
    if not settings.is_enabled or not settings.api_key:
        return {
            "reply": "L'assistant n'est pas disponible pour le moment.",
            "actions": [],
            "unavailable": True,
        }
    provider = get_provider(settings)
    if provider is None:
        return {
            "reply": "L'assistant n'est pas disponible pour le moment.",
            "actions": [],
            "unavailable": True,
        }

    system = build_system_prompt(restaurant)
    messages = history + [{"role": "user", "content": user_message}]
    try:
        raw = provider.complete(system, messages)
    except Exception:
        return {
            "reply": "Je rencontre un souci technique. Vous pouvez appeler un serveur.",
            "actions": [{"type": "call_waiter", "label": "Appeler un serveur"}],
            "error": True,
        }
    return validate_response(raw, restaurant)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python manage.py test base.test_ai.ValidateResponseTest base.test_ai.AskTest base.test_ai.AvailabilityTest -v1`
Expected: PASS

- [ ] **Step 5: Run the full backend suite**

Run: `python manage.py test base.test_ai -v1`
Expected: PASS (all classes)

- [ ] **Step 6: Commit**

```bash
git add base/services/ai/assistant.py base/test_ai.py
git commit -m "$(cat <<'EOF'
feat: add response validation, ask orchestration, availability check

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 9: `chat_assistant` view + URL

**Files:**
- Modify: `customer/views.py` (add view + imports)
- Modify: `customer/urls.py` (add route)
- Test: `customer/test_chat.py` (create)

- [ ] **Step 1: Write the failing test**

Create `customer/test_chat.py`:

```python
import json
from unittest.mock import patch
from django.test import TestCase, RequestFactory

from base.models import AISettings
from customer import views


class ChatAssistantViewTest(TestCase):
    def setUp(self):
        self.rf = RequestFactory()
        self.fake_restaurant = type("R", (), {"id": 1, "name": "R"})()

    def _post(self, body):
        req = self.rf.post(
            "/t/tok/chat/", data=json.dumps(body), content_type="application/json"
        )
        # session
        from django.contrib.sessions.backends.db import SessionStore
        req.session = SessionStore()
        return req

    @patch("customer.views.get_client_context")
    def test_disabled_returns_unavailable(self, mock_ctx):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        s = AISettings.load()
        s.is_enabled = False
        s.save()
        req = self._post({"message": "salut"})
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertTrue(data.get("unavailable"))

    @patch("customer.views.ask")
    @patch("customer.views.get_client_context")
    def test_returns_reply_and_persists_history(self, mock_ctx, mock_ask):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        mock_ask.return_value = {"reply": "Bonjour", "actions": []}
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        req = self._post({"message": "salut"})
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertEqual(data["reply"], "Bonjour")
        hist = req.session.get("chat_1_tok")
        self.assertEqual(len(hist), 2)  # user + assistant

    @patch("customer.views.ask")
    @patch("customer.views.get_client_context")
    def test_message_limit_blocks(self, mock_ctx, mock_ask):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        mock_ask.return_value = {"reply": "x", "actions": []}
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.max_messages_per_session = 1
        s.save()
        req = self._post({"message": "deuxieme"})
        req.session["chat_1_tok"] = [{"role": "user", "content": "premier"},
                                     {"role": "assistant", "content": "r"}]
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertTrue(data.get("limit_reached"))
        mock_ask.assert_not_called()

    @patch("customer.views.get_client_context")
    def test_empty_message(self, mock_ctx):
        mock_ctx.return_value = (self.fake_restaurant, object(), object(), None)
        s = AISettings.load()
        s.is_enabled = True
        s.api_key = "k"
        s.save()
        req = self._post({"message": "   "})
        resp = views.chat_assistant(req, "tok")
        data = json.loads(resp.content)
        self.assertEqual(data["actions"], [])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python manage.py test customer.test_chat -v1`
Expected: FAIL — `AttributeError: module 'customer.views' has no attribute 'chat_assistant'`

- [ ] **Step 3: Add the view to `customer/views.py`**

At the top of `customer/views.py`, ensure these imports exist (add what's missing):

```python
import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from base.models import AISettings
from base.services.ai.assistant import ask
```

Add the view (anywhere after `get_item_details`):

```python
MAX_USER_MESSAGE_LEN = 500


@csrf_exempt
@require_POST
def chat_assistant(request, table_token):
    restaurant, table, customization, error = get_client_context(request, table_token)
    if error:
        return JsonResponse({"reply": "Session invalide.", "actions": []}, status=400)

    settings = AISettings.load()
    if not settings.is_enabled or not settings.api_key:
        return JsonResponse(
            {"reply": "L'assistant n'est pas disponible.", "actions": [], "unavailable": True}
        )

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, TypeError):
        return JsonResponse({"reply": "Requête invalide.", "actions": []}, status=400)

    user_message = str(data.get("message", "")).strip()[:MAX_USER_MESSAGE_LEN]
    if not user_message:
        return JsonResponse({"reply": "Posez-moi une question sur le menu.", "actions": []})

    hist_key = f"chat_{restaurant.id}_{table_token}"
    history = request.session.get(hist_key, [])

    user_turns = sum(1 for m in history if m.get("role") == "user")
    if user_turns >= settings.max_messages_per_session:
        return JsonResponse({
            "reply": "Vous avez atteint la limite de messages. Appelez un serveur pour plus d'aide.",
            "actions": [{"type": "call_waiter", "label": "Appeler un serveur"}],
            "limit_reached": True,
        })

    result = ask(restaurant, history, user_message)

    history.append({"role": "user", "content": user_message})
    history.append({"role": "assistant", "content": result["reply"]})
    request.session[hist_key] = history[-(settings.max_messages_per_session * 2):]
    request.session.modified = True

    return JsonResponse({"reply": result["reply"], "actions": result.get("actions", [])})
```

- [ ] **Step 4: Add the route to `customer/urls.py`**

Add inside `urlpatterns` (near the other `t/<str:table_token>/` routes):

```python
    path("t/<str:table_token>/chat/", chat_assistant, name="chat_assistant"),
```

> `customer/urls.py` uses `from .views import *`, so `chat_assistant` is imported automatically.

- [ ] **Step 5: Run test to verify it passes**

Run: `python manage.py test customer.test_chat -v1`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add customer/views.py customer/urls.py customer/test_chat.py
git commit -m "$(cat <<'EOF'
feat: add chat_assistant endpoint with ephemeral session history

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 10: Frontend — FAB, chat panel, integration

**Files:**
- Create: `templates/customer/_chat_assistant.html`
- Modify: `templates/customer/menu.html` (remove old waiter FAB block at lines ~224-257, add `window.MENU_ITEMS`, include partial)
- Modify: `customer/views.py` `client_menu` context (add `ai_enabled`)

> Verification for this task is **manual in the browser** (UI), preceded by a Django system check. No unit test — Alpine behavior is verified visually.

- [ ] **Step 1: Add `ai_enabled` to the `client_menu` context**

In `customer/views.py`, inside `client_menu`, before `return render(...)`, add to the `context` dict:

```python
        "ai_enabled": is_assistant_available(),
```

And add the import at top (with the other assistant import):

```python
from base.services.ai.assistant import ask, is_assistant_available
```

- [ ] **Step 2: Create `templates/customer/_chat_assistant.html`**

```html
{# Floating assistant: bell (waiter call + confirm) + AI chat. #}
{# Lives inside the cartStore() scope of base.html, so it can call #}
{# addToCart() and openModal() via Alpine's scope chain. #}
<div x-data="chatAssistant()" x-init="init()" class="select-none">

  {# ---- Speed-dial actions (shown when fab is open) ---- #}
  <div class="fixed bottom-24 right-6 z-50 flex flex-col items-end gap-3"
       x-show="fabOpen" x-transition x-cloak>

    {# Chat icon (only if AI enabled) #}
    {% if ai_enabled %}
    <button @click="openChat()"
            class="flex items-center gap-2 rounded-full pl-4 pr-3 py-3 shadow-lg text-white"
            style="background: var(--color-primary);">
      <span class="text-sm font-semibold">Assistant</span>
      <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round"
              d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8 8.5 8.5 0 01-3.7-.84L3 21l1.9-5.3A8 8 0 1121 12z"/>
      </svg>
    </button>
    {% endif %}

    {# Bell -> confirm modal #}
    <button @click="confirmWaiter = true"
            class="flex items-center gap-2 rounded-full pl-4 pr-3 py-3 shadow-lg bg-white text-slate-800">
      <span class="text-sm font-semibold" x-text="waiterCalled ? 'Serveur appelé' : 'Serveur'"></span>
      <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
        <path stroke-linecap="round" stroke-linejoin="round"
              d="M15 17h5l-1.4-1.4A2 2 0 0118 14.2V11a6 6 0 10-12 0v3.2a2 2 0 01-.6 1.4L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/>
      </svg>
    </button>
  </div>

  {# ---- Main FAB ---- #}
  <button @click="fabOpen = !fabOpen"
          class="fixed bottom-6 right-6 z-50 w-14 h-14 rounded-full shadow-xl flex items-center justify-center text-white"
          style="background: var(--color-primary);"
          :aria-expanded="fabOpen">
    <svg x-show="!fabOpen" class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round"
            d="M8 10h.01M12 10h.01M16 10h.01M21 12a8 8 0 01-8 8 8.5 8.5 0 01-3.7-.84L3 21l1.9-5.3A8 8 0 1121 12z"/>
    </svg>
    <svg x-show="fabOpen" x-cloak class="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
      <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
    </svg>
  </button>

  {# ---- Waiter confirm modal ---- #}
  <div x-show="confirmWaiter" x-cloak class="fixed inset-0 z-[60] flex items-center justify-center p-4"
       style="background: rgba(0,0,0,.5);" @click.self="confirmWaiter = false">
    <div class="bg-white rounded-2xl p-6 max-w-sm w-full text-center">
      <p class="text-lg font-semibold text-slate-800 mb-1">Appeler un serveur ?</p>
      <p class="text-sm text-slate-500 mb-5">Un membre du staff sera prévenu pour votre table.</p>
      <div class="flex gap-3">
        <button @click="confirmWaiter = false"
                class="flex-1 py-2.5 rounded-xl border border-slate-200 text-slate-600 font-medium">Annuler</button>
        <button @click="callWaiter()"
                class="flex-1 py-2.5 rounded-xl text-white font-semibold" style="background: var(--color-primary);">Oui</button>
      </div>
    </div>
  </div>

  {# ---- Chat panel ---- #}
  {% if ai_enabled %}
  <div x-show="chatOpen" x-cloak
       class="fixed z-[60] bg-slate-900 text-slate-100 shadow-2xl flex flex-col
              inset-0 sm:inset-auto sm:bottom-6 sm:right-6 sm:w-96 sm:h-[70vh] sm:rounded-2xl overflow-hidden">
    {# Header #}
    <div class="flex items-center justify-between px-4 py-3 border-b border-white/10">
      <div class="font-semibold truncate">{{ restaurant.name }}</div>
      <button @click="chatOpen = false" class="p-1 text-slate-300 hover:text-white">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/>
        </svg>
      </button>
    </div>

    {# Messages #}
    <div class="flex-1 overflow-y-auto px-3 py-4 space-y-3" x-ref="scroll">
      <template x-if="messages.length === 0">
        <div class="space-y-2">
          <p class="text-sm text-slate-400 px-1">Comment puis-je vous aider ?</p>
          <template x-for="chip in starterChips" :key="chip">
            <button @click="send(chip)"
                    class="block w-full text-left text-sm bg-white/5 hover:bg-white/10 rounded-xl px-3 py-2"
                    x-text="chip"></button>
          </template>
        </div>
      </template>

      <template x-for="(msg, i) in messages" :key="i">
        <div :class="msg.role === 'user' ? 'flex justify-end' : 'flex justify-start'">
          <div class="max-w-[85%]">
            <div :class="msg.role === 'user'
                          ? 'bg-white text-slate-900 rounded-2xl rounded-br-sm px-3 py-2'
                          : 'bg-white/10 text-slate-100 rounded-2xl rounded-bl-sm px-3 py-2'"
                 class="text-sm whitespace-pre-wrap" x-text="msg.content"></div>
            <template x-if="msg.actions && msg.actions.length">
              <div class="mt-2 flex flex-wrap gap-2">
                <template x-for="(action, ai) in msg.actions" :key="ai">
                  <button
                    @click="action.type === 'view_item'   ? (MENU_ITEMS[action.item_id] && openModal(MENU_ITEMS[action.item_id]))
                          : action.type === 'add_to_cart'  ? (MENU_ITEMS[action.item_id] && addToCart(MENU_ITEMS[action.item_id]))
                          : (confirmWaiter = true)"
                    class="text-xs font-semibold rounded-full px-3 py-1.5 bg-white/10 hover:bg-white/20"
                    x-text="action.label"></button>
                </template>
              </div>
            </template>
          </div>
        </div>
      </template>

      <template x-if="loading">
        <div class="flex justify-start">
          <div class="bg-white/10 rounded-2xl px-3 py-2 text-sm text-slate-400">…</div>
        </div>
      </template>
    </div>

    {# Input #}
    <form @submit.prevent="send()" class="p-3 border-t border-white/10 flex gap-2">
      <input x-model="input" type="text" maxlength="500" placeholder="Votre message…"
             class="flex-1 bg-white/5 rounded-xl px-3 py-2 text-sm outline-none placeholder-slate-500"/>
      <button type="submit" :disabled="loading"
              class="w-10 h-10 rounded-xl flex items-center justify-center text-white disabled:opacity-50"
              style="background: var(--color-primary);">
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M5 12h14M13 6l6 6-6 6"/>
        </svg>
      </button>
    </form>
  </div>
  {% endif %}

  <script>
    function chatAssistant() {
      return {
        fabOpen: false,
        chatOpen: false,
        confirmWaiter: false,
        waiterCalled: false,
        loading: false,
        input: '',
        messages: [],
        starterChips: [
          'Propose-moi un plat',
          "J'ai 2500F, qu'est-ce que je prends ?",
          'Une entrée pas chère ?',
        ],
        init() {
          window.MENU_ITEMS = window.MENU_ITEMS || {};
        },
        openChat() {
          this.fabOpen = false;
          this.chatOpen = true;
        },
        scrollDown() {
          this.$nextTick(() => {
            const el = this.$refs.scroll;
            if (el) el.scrollTop = el.scrollHeight;
          });
        },
        async send(preset) {
          const text = (preset || this.input || '').trim();
          if (!text || this.loading) return;
          this.input = '';
          this.messages.push({ role: 'user', content: text, actions: [] });
          this.loading = true;
          this.scrollDown();
          try {
            const r = await fetch(window._chatUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ message: text }),
            });
            const data = await r.json();
            this.messages.push({
              role: 'assistant',
              content: data.reply || '…',
              actions: data.actions || [],
            });
          } catch (e) {
            this.messages.push({
              role: 'assistant',
              content: "Souci de connexion. Réessayez ou appelez un serveur.",
              actions: [{ type: 'call_waiter', label: 'Appeler un serveur' }],
            });
          } finally {
            this.loading = false;
            this.scrollDown();
          }
        },
        async callWaiter() {
          this.confirmWaiter = false;
          try {
            await fetch(window._waiterCallUrl, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({}),
            });
            this.waiterCalled = true;
          } catch (e) { /* silent */ }
        },
      };
    }
  </script>
</div>
```

- [ ] **Step 3: Wire `menu.html` — remove old FAB, add data, include partial**

In `templates/customer/menu.html`:

(a) **Remove** the old waiter-call block (the `<script>var _waiterCallUrl ...</script>` line and the entire `<div id="waiterCallBtn" ...>...</div>` block — currently lines ~224-257).

(b) **Add** near the end of the `{% block content %}` (before its `{% endblock %}`), the data + include:

```html
<script>
  window._waiterCallUrl = "{% url 'create_waiter_call' table_token=table.token %}";
  window._chatUrl = "{% url 'chat_assistant' table_token=table.token %}";
  window.MENU_ITEMS = {
    {% for category in categories %}{% for item in category.items.all %}"{{ item.id }}": {{ item|item_json }},
    {% endfor %}{% endfor %}
  };
</script>
{% include "customer/_chat_assistant.html" %}
```

> `menu.html` already `{% load %}`s the tag library providing `item_json` (used at line ~129). Reuse it. Confirm the `{% load ... %}` line is present at the top of `menu.html`; if the include needs it too, the partial inherits the parent's loaded tags only within the same template — but here `item_json` is used in `menu.html` itself, not the partial, so no extra load is needed.

- [ ] **Step 4: Django system check**

Run: `python manage.py check`
Expected: `System check identified no issues`

- [ ] **Step 5: Manual browser verification**

Start the server: `python manage.py runserver`

In the Django admin (Jazzmin), open **Paramètres IA**, set `provider`, a real `api_key`, a `model` (e.g. `mistral-small-latest`), and tick `is_enabled`. Save.

Open a table menu page: `http://<restaurant-subdomain>.localhost:8000/t/<table_token>/` (use a real table token from the DB; the subdomain middleware needs the restaurant host).

Verify:
- [ ] A single round FAB shows bottom-right.
- [ ] Clicking it reveals **two** actions: **Serveur** (bell) and **Assistant** (chat).
- [ ] Bell → confirmation modal "Appeler un serveur ?" with **Oui/Annuler**. **Oui** triggers the call (check a `WaiterCall` row is created / staff sees it) and the label becomes "Serveur appelé".
- [ ] Chat → premium dark panel opens; starter chips visible.
- [ ] Ask "j'ai 2500F qu'est-ce que tu proposes ?" → concise reply + action buttons.
- [ ] "Voir le plat" button opens the existing detail modal with the correct dish.
- [ ] "Ajouter au panier" button adds the dish (cart count increases).
- [ ] Ask something off-topic (e.g. "raconte une blague") → assistant politely refocuses on the menu.
- [ ] In admin, untick `is_enabled`, reload the page → only the bell shows inside the FAB, no chat icon.

- [ ] **Step 6: Commit**

```bash
git add templates/customer/_chat_assistant.html templates/customer/menu.html customer/views.py
git commit -m "$(cat <<'EOF'
feat: add floating assistant UI (FAB + bell + AI chat) on customer menu

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
EOF
)"
```

---

## Task 11: Full verification & wrap-up

- [ ] **Step 1: Run the entire test suite**

Run: `python manage.py test base customer -v1`
Expected: all PASS

- [ ] **Step 2: System check**

Run: `python manage.py check`
Expected: no issues

- [ ] **Step 3: Confirm no migration drift**

Run: `python manage.py makemigrations --check --dry-run`
Expected: `No changes detected`

- [ ] **Step 4: Final manual smoke** — repeat the key flows from Task 10 Step 5 once more (chat reply, view detail, add to cart, bell→call), confirming nothing regressed.

---

## Notes for the implementer

- **Subdomain middleware:** the customer pages resolve the restaurant from the host via `customer.middleware.SubdomainMiddleware`. For local manual testing you need the restaurant's subdomain in the host (`<sub>.localhost:8000`). Backend unit tests bypass this by patching `get_client_context`.
- **DB migration state:** the dev DB is only migrated to `base.0009`. Before manual testing, run `python manage.py migrate` so `WaiterCall` (0013) and `AISettings` (0014) tables exist.
- **No new dependency:** `requests==2.33.1` is already in `requirements.txt`.
- **Cost guardrails** live in two places: `max_messages_per_session` (enforced in the view) and `max_tokens`/`maxOutputTokens: 500` (in each provider). Both are intentional.
- **Provider neutrality:** adding a third provider later = new file in `base/services/ai/` + one entry in `factory.PROVIDERS`. Nothing else changes.
