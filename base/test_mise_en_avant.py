from django.test import TestCase
from django.urls import reverse
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


class FeaturedToggleTest(TestCase):
    def setUp(self):
        self.owner = make_user()
        self.resto = make_restaurant(self.owner)
        self.item = make_item(self.resto)
        self.client.force_login(self.owner)

    def _host(self):
        return {"HTTP_HOST": f"{self.resto.subdomain}.localhost"}

    def test_toggle_featured_flips_flag(self):
        self.assertFalse(self.item.is_featured)
        resp = self.client.get(
            reverse("menu_toggle_featured", args=[self.item.pk]), **self._host())
        self.assertEqual(resp.status_code, 302)
        self.item.refresh_from_db()
        self.assertTrue(self.item.is_featured)

    def test_update_saves_featured_label(self):
        resp = self.client.post(
            reverse("menu_update", args=[self.item.pk]),
            {"name": "Riz", "price": "1500", "description": "",
             "featured_label": "Coup de cœur"}, **self._host())
        self.item.refresh_from_db()
        self.assertEqual(self.item.featured_label, "Coup de cœur")
