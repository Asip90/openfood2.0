from django.test import TestCase
from base.models import Category, MenuItem
from base.tests import make_user, make_restaurant


def make_item(resto, **kw):
    cat = Category.objects.create(restaurant=resto, name="Plats")
    defaults = dict(restaurant=resto, category=cat, name="Riz", price=1500)
    defaults.update(kw)
    return MenuItem.objects.create(**defaults)


class FeaturedFieldsTest(TestCase):
    def test_defaults(self):
        it = make_item(make_restaurant(make_user()))
        self.assertFalse(it.is_featured)
        self.assertEqual(it.featured_label, "")

    def test_can_set_featured(self):
        it = make_item(make_restaurant(make_user()),
                       is_featured=True, featured_label="Menu du jour")
        it.refresh_from_db()
        self.assertTrue(it.is_featured)
        self.assertEqual(it.featured_label, "Menu du jour")
