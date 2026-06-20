import json

from django.template import Context, Template
from django.test import SimpleTestCase

from base.templatetags.menu_extras import item_json


class _FakeMedia(list):
    def all(self):
        return self


class _FakeItem:
    """Minimal stand-in for MenuItem for filter rendering tests."""

    def __init__(self, name="poule bi", description=""):
        self.id = 2
        self.name = name
        self.description = description
        self.price = "4559.00"
        self.discount_price = None
        self.image = None
        self.media = _FakeMedia()
        self.is_vegetarian = False
        self.is_vegan = False
        self.is_spicy = False
        self.preparation_time = 15
        self.allergens = ""
        self.ingredients = ""


class ItemJsonScriptContextTest(SimpleTestCase):
    """Regression: the inline MENU_ITEMS <script> in menu.html must emit valid
    JavaScript. If item_json output is HTML-escaped there, `"` becomes `&quot;`,
    the whole <script> throws a SyntaxError, and window._chatUrl ends up
    undefined -> chat POSTs to /t/<token>/undefined (404, "service indisponible").
    """

    def _render_script(self, item):
        # Mirrors templates/customer/menu.html MENU_ITEMS assignment (script
        # context uses |safe so the JSON is emitted unescaped/valid JS).
        tpl = Template(
            "{% load menu_extras %}window.M = {\"{{ item.id }}\": "
            "{{ item|item_json|safe }} };"
        )
        return tpl.render(Context({"item": item}))

    def test_script_context_is_valid_unescaped_json(self):
        rendered = self._render_script(_FakeItem())
        self.assertNotIn("&quot;", rendered)  # must NOT be HTML-escaped
        # The object literal must be parseable JSON.
        body = rendered.split("window.M = ", 1)[1].rstrip("; ")
        data = json.loads(body)
        self.assertEqual(data["2"]["name"], "poule bi")

    def test_script_context_neutralizes_script_breakout(self):
        # A malicious / accidental "</script>" in item data must not break out.
        rendered = self._render_script(_FakeItem(name="x</script><b>"))
        self.assertNotIn("</script>", rendered)

    def test_attribute_context_stays_escaped(self):
        # In @click="openModal(...)" the value lives in a double-quoted HTML
        # attribute, so quotes MUST be escaped as &quot; to stay valid HTML.
        tpl = Template('{% load menu_extras %}<div data-x="{{ item|item_json }}">')
        rendered = tpl.render(Context({"item": _FakeItem()}))
        self.assertIn("&quot;", rendered)
