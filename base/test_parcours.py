from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from base.services import phone
from base.models import Restaurant, SubscriptionPlan, Order, CustomerFeedback
from base.tests import make_user, make_restaurant


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
