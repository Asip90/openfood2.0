from django.test import TestCase
from base.models import ReputationSettings


class ReputationSettingsTest(TestCase):
    def test_singleton_load_defaults(self):
        s = ReputationSettings.load()
        self.assertEqual(s.pk, 1)
        self.assertFalse(s.is_enabled)
        self.assertEqual(s.cache_hours, 12)
        self.assertEqual(ReputationSettings.load().pk, 1)
