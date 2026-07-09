from django.test import TestCase
from base.models import ReputationSettings


class ReputationSettingsTest(TestCase):
    def test_singleton_load_defaults(self):
        s = ReputationSettings.load()
        self.assertEqual(s.pk, 1)
        self.assertFalse(s.is_enabled)
        self.assertEqual(s.cache_hours, 12)
        self.assertEqual(ReputationSettings.load().pk, 1)


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
