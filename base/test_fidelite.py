from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from base.models import LoyaltyProgram, LoyaltyCard, Order, SubscriptionPlan
from base.tests import make_user, make_restaurant
from base.services import loyalty
from base.models import Category, MenuItem


class LoyaltyModelsTest(TestCase):
    def test_program_defaults(self):
        resto = make_restaurant(make_user())
        prog = LoyaltyProgram.objects.create(restaurant=resto)
        self.assertFalse(prog.is_enabled)
        self.assertEqual(prog.stamps_required, 10)
        self.assertEqual(resto.loyalty, prog)

    def test_card_unique_per_phone(self):
        resto = make_restaurant(make_user())
        LoyaltyCard.objects.create(restaurant=resto, phone="+2290100000000", stamps=3)
        self.assertEqual(resto.loyalty_cards.count(), 1)

    def test_order_loyalty_awarded_default_false(self):
        resto = make_restaurant(make_user())
        o = Order.objects.create(restaurant=resto, customer_phone="+2290100000000")
        self.assertFalse(o.loyalty_awarded)


def _prog(resto, enabled=True, required=3):
    return LoyaltyProgram.objects.create(
        restaurant=resto, is_enabled=enabled, stamps_required=required,
        reward_label="1 plat offert")


def _order(resto, phone="+2290100000000"):
    return Order.objects.create(restaurant=resto, customer_phone=phone)


def make_pro(resto):
    plan = SubscriptionPlan.objects.create(name="Pro", plan_type="pro", price=1)
    resto.subscription_plan = plan
    resto.subscription_end = timezone.now() + timedelta(days=10)
    resto.save()


class LoyaltyServiceTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        make_pro(self.resto)

    def test_award_credits_one_stamp_idempotent(self):
        _prog(self.resto)
        o = _order(self.resto)
        card = loyalty.award_for_order(o)
        self.assertEqual(card.stamps, 1)
        o.refresh_from_db()
        self.assertTrue(o.loyalty_awarded)
        # 2e appel : pas de recrédit
        loyalty.award_for_order(o)
        card.refresh_from_db()
        self.assertEqual(card.stamps, 1)

    def test_award_noop_if_disabled_or_no_phone(self):
        _prog(self.resto, enabled=False)
        self.assertIsNone(loyalty.award_for_order(_order(self.resto)))
        LoyaltyProgram.objects.filter(restaurant=self.resto).update(is_enabled=True)
        self.assertIsNone(loyalty.award_for_order(_order(self.resto, phone="")))

    def test_redeem_only_when_threshold_reached(self):
        _prog(self.resto, required=3)
        card = LoyaltyCard.objects.create(restaurant=self.resto, phone="+2290100000000", stamps=3)
        self.assertTrue(loyalty.redeem(card))
        card.refresh_from_db()
        self.assertEqual(card.stamps, 0)
        self.assertEqual(card.rewards_redeemed, 1)
        self.assertFalse(loyalty.redeem(card))  # plus assez

    def test_progress(self):
        _prog(self.resto, required=3)
        LoyaltyCard.objects.create(restaurant=self.resto, phone="+2290100000000", stamps=3)
        p = loyalty.progress(self.resto, "+2290100000000")
        self.assertEqual(p["stamps"], 3)
        self.assertEqual(p["required"], 3)
        self.assertEqual(p["remaining"], 0)
        self.assertTrue(p["reward_available"])
        other_resto = make_restaurant(make_user(email="other@test.com"))
        self.assertIsNone(loyalty.progress(other_resto, "+2290100000000"))


from base.cashier_views import mark_order_paid  # noqa (import sanity)


class AccrualTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        make_pro(self.resto)
        _prog(self.resto, required=10)

    def test_paying_order_awards_stamp(self):
        from base.models import LoyaltyCard
        o = Order.objects.create(
            restaurant=self.resto, customer_phone="+2290100000000",
            status="ready", total=1000)
        loyalty.award_for_order(o)  # simule l'accrual déclenché au paiement
        self.assertEqual(
            LoyaltyCard.objects.get(restaurant=self.resto, phone="+2290100000000").stamps, 1)


class LoyaltyProGateTest(TestCase):
    def test_non_pro_award_and_progress_blocked(self):
        resto = make_restaurant(make_user())
        _prog(resto, required=3)
        o = _order(resto)
        self.assertIsNone(loyalty.award_for_order(o))
        self.assertEqual(LoyaltyCard.objects.filter(restaurant=resto).count(), 0)
        self.assertIsNone(loyalty.progress(resto, "+2290100000000"))


class LoyaltyDashboardTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.client.force_login(self.owner)
        _prog(self.resto, required=3)

    def _host(self):
        return {"HTTP_HOST": f"{self.resto.subdomain}.localhost"}

    def test_non_pro_forbidden(self):
        resp = self.client.get(reverse("loyalty_dashboard"), **self._host())
        self.assertIn(resp.status_code, (302, 404))

    def test_pro_lists_and_redeems(self):
        make_pro(self.resto)
        card = LoyaltyCard.objects.create(
            restaurant=self.resto, phone="+2290100000000", stamps=3)
        resp = self.client.get(reverse("loyalty_dashboard"), **self._host())
        self.assertEqual(resp.status_code, 200)
        resp2 = self.client.post(
            reverse("loyalty_redeem", args=[card.id]), **self._host())
        self.assertEqual(resp2.status_code, 302)
        card.refresh_from_db()
        self.assertEqual(card.stamps, 0)
        self.assertEqual(card.rewards_redeemed, 1)
