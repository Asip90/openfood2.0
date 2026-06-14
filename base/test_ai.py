import json
from unittest.mock import patch, MagicMock

from django.test import TestCase
from base.models import AISettings
from base.services.ai.base import AIProvider
from accounts.models import User
from base.models import Restaurant, Category, MenuItem
from base.services.ai.assistant import serialize_menu, build_system_prompt


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


class AIProviderInterfaceTest(TestCase):
    def test_stores_credentials(self):
        p = AIProvider(api_key="k", model="m")
        self.assertEqual(p.api_key, "k")
        self.assertEqual(p.model, "m")

    def test_complete_not_implemented(self):
        p = AIProvider(api_key="k", model="m")
        with self.assertRaises(NotImplementedError):
            p.complete("sys", [{"role": "user", "content": "hi"}])


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
