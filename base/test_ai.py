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
