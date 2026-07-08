from django.test import TestCase

from base.models import ImageGenSettings
from base.models import Restaurant, MarketingPoster
from base.tests import make_user, make_restaurant


class ImageGenSettingsTest(TestCase):
    def test_singleton_load(self):
        a = ImageGenSettings.load()
        b = ImageGenSettings.load()
        self.assertEqual(a.pk, 1)
        self.assertEqual(a.pk, b.pk)

    def test_effective_model_uses_choice(self):
        s = ImageGenSettings.load()
        s.image_model = "openai/gpt-image-1-mini"
        s.image_model_custom = ""
        self.assertEqual(s.effective_model(), "openai/gpt-image-1-mini")

    def test_effective_model_uses_custom_when_selected(self):
        s = ImageGenSettings.load()
        s.image_model = "custom"
        s.image_model_custom = "some/new-model-id"
        self.assertEqual(s.effective_model(), "some/new-model-id")

    def test_default_quota(self):
        self.assertEqual(ImageGenSettings.load().daily_quota_per_restaurant, 5)


class MarketingPosterModelTest(TestCase):
    def test_create_poster_and_refinement_chain(self):
        resto = make_restaurant(make_user())
        parent = MarketingPoster.objects.create(
            restaurant=resto, caption="Miam", style="macro", prompt_used="p")
        child = MarketingPoster.objects.create(
            restaurant=resto, caption="Miam v2", parent=parent)
        self.assertEqual(resto.posters.count(), 2)
        self.assertEqual(child.parent, parent)
        self.assertEqual(parent.refinements.first(), child)
