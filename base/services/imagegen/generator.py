"""Orchestration : quota → prompt (Mistral) → image (OpenRouter) → Cloudinary."""
from datetime import timedelta
from io import BytesIO

import cloudinary.uploader
from django.utils import timezone

from base.models import ImageGenSettings, MarketingPoster
from . import prompt_builder, openrouter
from .errors import Disabled, QuotaExceeded, ImageGenError


def _used_today(restaurant):
    since = timezone.now() - timedelta(days=1)
    return MarketingPoster.objects.filter(
        restaurant=restaurant, created_at__gte=since).count()


def remaining_quota(restaurant):
    settings = ImageGenSettings.load()
    return max(0, settings.daily_quota_per_restaurant - _used_today(restaurant))


def _check(settings, restaurant):
    if not settings.is_enabled:
        raise Disabled("Génération d'image désactivée")
    if _used_today(restaurant) >= settings.daily_quota_per_restaurant:
        raise QuotaExceeded("Quota quotidien atteint")


def _run(restaurant, user, menu_item, user_text, source_image_url, parent, exclude_style):
    settings = ImageGenSettings.load()
    _check(settings, restaurant)

    built = prompt_builder.build(
        restaurant, menu_item, user_text, bool(source_image_url), exclude_style)
    image_bytes = openrouter.generate_image(
        built["image_prompt"], settings.effective_model(),
        settings.image_size, settings.openrouter_api_key,
        reference_image_url=source_image_url)

    upload = cloudinary.uploader.upload(
        BytesIO(image_bytes), folder=f"posters/{restaurant.id}",
        resource_type="image")

    return MarketingPoster.objects.create(
        restaurant=restaurant,
        menu_item=menu_item,
        image=upload.get("public_id", ""),
        caption=built["caption"],
        prompt_used=built["image_prompt"],
        style=built["style"],
        user_text=user_text,
        parent=parent,
        created_by=user,
    )


def generate(restaurant, user, menu_item=None, user_text="", source_image_url=None):
    return _run(restaurant, user, menu_item, user_text, source_image_url,
                parent=None, exclude_style=None)


def refine(poster, new_instructions, user):
    ref_url = None
    if poster.image:
        try:
            ref_url = poster.image.url
        except Exception:
            ref_url = None
    return _run(
        poster.restaurant, user, poster.menu_item, new_instructions,
        source_image_url=ref_url, parent=poster, exclude_style=None)
