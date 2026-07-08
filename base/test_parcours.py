from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from django.urls import reverse
from base.services import phone
from base.models import Restaurant, SubscriptionPlan, Order, CustomerFeedback, MenuItem, Category, Table
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


class CheckoutPhoneTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.host = f"{self.resto.subdomain}.localhost"
        self.table = Table.objects.create(restaurant=self.resto, number=1, capacity=4)
        cat = Category.objects.create(restaurant=self.resto, name="Plats")
        self.item = MenuItem.objects.create(
            restaurant=self.resto, category=cat, name="Riz", price=1500)

    def _seed_cart(self, client):
        session = client.session
        session[f"cart_{self.resto.id}_{self.table.token}"] = {
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
            HTTP_HOST=self.host,
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
            HTTP_HOST=self.host,
        )
        self.assertEqual(resp.status_code, 200)  # ré-affiche le form
        self.assertFalse(Order.objects.filter(restaurant=self.resto).exists())


class SettingsCommunityTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.host = f"{self.resto.subdomain}.localhost"
        self.client.force_login(self.owner)

    def test_post_saves_whatsapp_and_place_id(self):
        # request.restaurant est résolu par le middleware via le sous-domaine ;
        # on poste avec HTTP_HOST pour reproduire la résolution multi-tenant
        # (même pattern que CheckoutPhoneTest ci-dessus).
        resp = self.client.post(reverse("restaurant_settings"), {
            "name": self.resto.name, "email": self.resto.email,
            "phone": self.resto.phone, "address": self.resto.address,
            "description": "",
            "whatsapp_community_url": "https://chat.whatsapp.com/abc",
            "google_place_id": "ChIJ_test",
        }, HTTP_HOST=self.host)
        self.assertEqual(resp.status_code, 302)
        self.resto.refresh_from_db()
        self.assertEqual(self.resto.whatsapp_community_url, "https://chat.whatsapp.com/abc")
        self.assertEqual(self.resto.google_place_id, "ChIJ_test")


class SuccessPageTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.host = f"{self.resto.subdomain}.localhost"
        self.order = Order.objects.create(
            restaurant=self.resto, customer_phone="+2290197000000")

    def test_free_plan_hides_after_order_blocks(self):
        resp = self.client.get(
            reverse("order_confirmation", args=[self.order.public_token]),
            HTTP_HOST=self.host)
        self.assertNotContains(resp, "Rejoignez notre communauté")

    def test_pro_plan_shows_whatsapp_when_url_set(self):
        self.resto.subscription_plan = make_pro_plan()
        self.resto.subscription_end = timezone.now() + timedelta(days=10)
        self.resto.whatsapp_community_url = "https://chat.whatsapp.com/abc"
        self.resto.save()
        resp = self.client.get(
            reverse("order_confirmation", args=[self.order.public_token]),
            HTTP_HOST=self.host)
        self.assertContains(resp, "chat.whatsapp.com/abc")


class SubmitFeedbackTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        # Le retour client est une fonctionnalité Pro : on active le plan
        # pour exercer la création réelle dans ces tests.
        self.resto.subscription_plan = make_pro_plan()
        self.resto.subscription_end = timezone.now() + timedelta(days=10)
        self.resto.save()
        self.host = f"{self.resto.subdomain}.localhost"
        self.order = Order.objects.create(
            restaurant=self.resto, customer_phone="+2290197000000")

    def test_submit_creates_feedback(self):
        resp = self.client.post(
            reverse("submit_feedback", args=[self.order.public_token]),
            {"rating": "4", "message": "Bien"}, HTTP_HOST=self.host)
        self.assertEqual(resp.status_code, 302)
        fb = CustomerFeedback.objects.get(restaurant=self.resto)
        self.assertEqual(fb.rating, 4)
        self.assertEqual(fb.phone, "+2290197000000")

    def test_double_submit_creates_single_feedback(self):
        url = reverse("submit_feedback", args=[self.order.public_token])
        self.client.post(url, {"rating": "5", "message": "A"}, HTTP_HOST=self.host)
        self.client.post(url, {"rating": "1", "message": "B"}, HTTP_HOST=self.host)
        self.assertEqual(
            CustomerFeedback.objects.filter(order=self.order).count(), 1)

    def test_non_pro_restaurant_rejects_feedback(self):
        # Restaurant free : pas de plan pro -> aucune création côté serveur,
        # même si le client force le POST (gating doit être serveur, pas juste UI).
        free_resto = make_restaurant(make_user(email="free@test.com"))
        host = f"{free_resto.subdomain}.localhost"
        order = Order.objects.create(
            restaurant=free_resto, customer_phone="+2290197000001")
        resp = self.client.post(
            reverse("submit_feedback", args=[order.public_token]),
            {"rating": "4", "message": "Bien"}, HTTP_HOST=host)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(CustomerFeedback.objects.filter(order=order).count(), 0)

    def test_empty_submission_creates_no_feedback(self):
        resp = self.client.post(
            reverse("submit_feedback", args=[self.order.public_token]),
            {"rating": "", "message": ""}, HTTP_HOST=self.host)
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(
            CustomerFeedback.objects.filter(order=self.order).count(), 0)

    def test_out_of_range_rating_is_clamped_to_none(self):
        resp = self.client.post(
            reverse("submit_feedback", args=[self.order.public_token]),
            {"rating": "9", "message": "Bien quand même"}, HTTP_HOST=self.host)
        self.assertEqual(resp.status_code, 302)
        fb = CustomerFeedback.objects.get(order=self.order)
        self.assertIsNone(fb.rating)


class FeedbackDashboardTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        # La liste des retours est réservée aux restaurants Pro (cohérent
        # avec le masquage de l'onglet dans la sidebar).
        self.resto.subscription_plan = make_pro_plan()
        self.resto.subscription_end = timezone.now() + timedelta(days=10)
        self.resto.save()
        self.host = f"{self.resto.subdomain}.localhost"
        self.client.force_login(self.owner)
        CustomerFeedback.objects.create(
            restaurant=self.resto, rating=3, message="Bof", phone="+2290197000000")

    def test_feedback_list_shows_items_and_marks_read(self):
        resp = self.client.get(reverse("feedback_list"), HTTP_HOST=self.host)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Bof")
        self.assertFalse(
            CustomerFeedback.objects.filter(restaurant=self.resto, is_read=False).exists())

    def test_feedback_list_404_for_non_pro_restaurant(self):
        free_owner = make_user(email="free-dashboard@test.com")
        free_resto = make_restaurant(free_owner)
        host = f"{free_resto.subdomain}.localhost"
        self.client.force_login(free_owner)
        resp = self.client.get(reverse("feedback_list"), HTTP_HOST=host)
        self.assertEqual(resp.status_code, 404)
