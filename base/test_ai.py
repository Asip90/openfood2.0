from unittest.mock import patch, MagicMock

from django.test import TestCase
from base.models import AISettings
from base.services.ai.base import AIProvider


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
