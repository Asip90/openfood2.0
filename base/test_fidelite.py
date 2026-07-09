from django.test import TestCase
from base.models import LoyaltyProgram, LoyaltyCard, Order
from base.tests import make_user, make_restaurant


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
