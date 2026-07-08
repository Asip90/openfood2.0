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


from unittest.mock import patch, MagicMock
import json
from base.services.imagegen import styles, prompt_builder


class PromptBuilderTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())

    def test_style_palette_non_empty(self):
        self.assertTrue(len(styles.STYLE_PALETTE) >= 5)
        self.assertIn("key", styles.STYLE_PALETTE[0])

    @patch("base.services.imagegen.prompt_builder.get_provider")
    def test_build_parses_provider_json(self, mock_get_provider):
        provider = MagicMock()
        provider.complete.return_value = json.dumps({
            "image_prompt": "a delicious plate, macro, warm light",
            "caption": "Venez goûter notre plat signature 🔥",
            "style": "macro",
        })
        mock_get_provider.return_value = provider
        out = prompt_builder.build(self.resto, None, "promo -20%", False)
        self.assertEqual(out["style"], "macro")
        self.assertIn("delicious", out["image_prompt"])
        self.assertTrue(out["caption"])

    @patch("base.services.imagegen.prompt_builder.get_provider")
    def test_build_falls_back_on_invalid_json(self, mock_get_provider):
        provider = MagicMock()
        provider.complete.return_value = "pas du json"
        mock_get_provider.return_value = provider
        out = prompt_builder.build(self.resto, None, "", False)
        # repli : un dict complet malgré le JSON invalide
        self.assertIn("image_prompt", out)
        self.assertIn("caption", out)
        self.assertIn("style", out)


import base64
from base.services.imagegen import openrouter
from base.services.imagegen.errors import ImageGenError


class OpenRouterClientTest(TestCase):
    @patch("base.services.imagegen.openrouter.requests.post")
    def test_generate_image_returns_bytes_from_b64(self, mock_post):
        raw = b"PNGDATA"
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"data": [{"b64_json": base64.b64encode(raw).decode()}]},
        )
        mock_post.return_value.raise_for_status = lambda: None
        out = openrouter.generate_image("a plate", "openai/gpt-image-1-mini", "1024x1536", "KEY")
        self.assertEqual(out, raw)

    def test_missing_key_raises(self):
        with self.assertRaises(ImageGenError):
            openrouter.generate_image("a plate", "m", "1024x1536", "")

    @patch("base.services.imagegen.openrouter.requests.post")
    def test_http_error_raises_imagegenerror(self, mock_post):
        def boom():
            raise Exception("500")
        mock_post.return_value = MagicMock(status_code=500, raise_for_status=boom)
        with self.assertRaises(ImageGenError):
            openrouter.generate_image("a plate", "m", "1024x1536", "KEY")


from base.services.imagegen import generator
from base.services.imagegen.errors import QuotaExceeded, Disabled


def _enable_imagegen(quota=5):
    s = ImageGenSettings.load()
    s.is_enabled = True
    s.openrouter_api_key = "KEY"
    s.daily_quota_per_restaurant = quota
    s.save()
    return s


class GeneratorTest(TestCase):
    def setUp(self):
        self.resto = make_restaurant(make_user())
        self.user = self.resto.owner
        _enable_imagegen()

    @patch("base.services.imagegen.generator.cloudinary.uploader.upload",
           return_value={"public_id": "posters/x", "secure_url": "http://img"})
    @patch("base.services.imagegen.generator.openrouter.generate_image",
           return_value=b"PNG")
    @patch("base.services.imagegen.generator.prompt_builder.build",
           return_value={"image_prompt": "p", "caption": "c", "style": "macro"})
    def test_generate_creates_poster(self, mb, mg, mu):
        poster = generator.generate(self.resto, self.user, user_text="promo")
        self.assertEqual(poster.caption, "c")
        self.assertEqual(poster.style, "macro")
        self.assertEqual(self.resto.posters.count(), 1)

    def test_generate_disabled_raises(self):
        s = ImageGenSettings.load()
        s.is_enabled = False
        s.save()
        with self.assertRaises(Disabled):
            generator.generate(self.resto, self.user)

    @patch("base.services.imagegen.generator.cloudinary.uploader.upload",
           return_value={"public_id": "posters/x"})
    @patch("base.services.imagegen.generator.openrouter.generate_image", return_value=b"PNG")
    @patch("base.services.imagegen.generator.prompt_builder.build",
           return_value={"image_prompt": "p", "caption": "c", "style": "macro"})
    def test_quota_exceeded_raises(self, mb, mg, mu):
        _enable_imagegen(quota=1)
        generator.generate(self.resto, self.user)
        with self.assertRaises(QuotaExceeded):
            generator.generate(self.resto, self.user)

    @patch("base.services.imagegen.generator.cloudinary.uploader.upload",
           return_value={"public_id": "posters/x"})
    @patch("base.services.imagegen.generator.openrouter.generate_image", return_value=b"PNG")
    @patch("base.services.imagegen.generator.prompt_builder.build",
           return_value={"image_prompt": "p2", "caption": "c2", "style": "pop"})
    def test_refine_links_parent(self, mb, mg, mu):
        parent = MarketingPoster.objects.create(
            restaurant=self.resto, caption="c", style="macro")
        child = generator.refine(parent, "plus lumineux", self.user)
        self.assertEqual(child.parent, parent)
        self.assertEqual(child.user_text, "plus lumineux")
