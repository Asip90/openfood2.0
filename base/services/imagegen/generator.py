"""Orchestration : quota → affiche « en cours » → (thread) prompt (Mistral)
→ image (OpenRouter) → Cloudinary → statut « terminée »/« échec »."""
import threading
from io import BytesIO

import cloudinary.uploader
from django.db import connections, transaction
from django.utils import timezone

from base.models import ImageGenSettings, MarketingPoster, Restaurant
from . import prompt_builder, openrouter
from .errors import Disabled, QuotaExceeded, ImageGenError


def _used_today(restaurant):
    # Les échecs ne consomment pas le quota.
    return MarketingPoster.objects.filter(
        restaurant=restaurant, created_at__date=timezone.localdate()
    ).exclude(status='failed').count()


def remaining_quota(restaurant):
    settings = ImageGenSettings.load()
    return max(0, settings.daily_quota_per_restaurant - _used_today(restaurant))


def _check(settings, restaurant):
    if not settings.is_enabled:
        raise Disabled("Génération d'image désactivée")
    if _used_today(restaurant) >= settings.daily_quota_per_restaurant:
        raise QuotaExceeded("Quota quotidien atteint")


def _create_pending(restaurant, user, menu_item, user_text, parent):
    """Crée l'affiche en statut « en cours » après contrôle quota (verrou).
    Lève Disabled / QuotaExceeded le cas échéant."""
    with transaction.atomic():
        Restaurant.objects.select_for_update().filter(pk=restaurant.pk).first()
        settings = ImageGenSettings.load()
        _check(settings, restaurant)
        return MarketingPoster.objects.create(
            restaurant=restaurant, menu_item=menu_item, user_text=user_text,
            parent=parent, created_by=user, status='generating')


def _fill_poster(poster, source_image_urls, exclude_style=None):
    """Génère réellement l'image et remplit l'affiche (statut « terminée »)."""
    settings = ImageGenSettings.load()
    refs = [u for u in (source_image_urls or []) if u]
    built = prompt_builder.build(
        poster.restaurant, poster.menu_item, poster.user_text, bool(refs), exclude_style)
    try:
        image_bytes = openrouter.generate_image(
            built["image_prompt"], settings.effective_model(),
            settings.image_size, settings.openrouter_api_key,
            reference_image_urls=refs)
    except ImageGenError:
        # Une référence cassée/inaccessible ne doit pas condamner la génération :
        # on réessaie une fois sans référence (le prompt décrit déjà le plat).
        if not refs:
            raise
        image_bytes = openrouter.generate_image(
            built["image_prompt"], settings.effective_model(),
            settings.image_size, settings.openrouter_api_key,
            reference_image_urls=None)

    try:
        upload = cloudinary.uploader.upload(
            BytesIO(image_bytes), folder=f"posters/{poster.restaurant_id}",
            resource_type="image")
    except Exception as exc:
        raise ImageGenError(f"Enregistrement de l'affiche échoué : {exc}") from exc

    poster.image = upload.get("public_id", "")
    poster.caption = built["caption"]
    poster.prompt_used = built["image_prompt"]
    poster.style = built["style"]
    poster.status = "done"
    poster.save(update_fields=[
        "image", "caption", "prompt_used", "style", "status", "updated_at"])
    return poster


# --- Chemin synchrone (tests / usage direct) ---

def generate(restaurant, user, menu_item=None, user_text="", source_image_urls=None):
    poster = _create_pending(restaurant, user, menu_item, user_text, parent=None)
    try:
        return _fill_poster(poster, source_image_urls)
    except ImageGenError:
        poster.status = "failed"
        poster.save(update_fields=["status", "updated_at"])
        raise


def refine(poster, new_instructions, user):
    ref_urls = [poster.image_url] if poster.image else []
    child = _create_pending(
        poster.restaurant, user, poster.menu_item, new_instructions, parent=poster)
    try:
        return _fill_poster(child, ref_urls)
    except ImageGenError:
        child.status = "failed"
        child.save(update_fields=["status", "updated_at"])
        raise


# --- Chemin asynchrone (vue web : skeleton + thread de fond) ---

def _spawn(poster_id, source_image_urls):
    def _target():
        try:
            poster = MarketingPoster.objects.get(id=poster_id)
            _fill_poster(poster, source_image_urls)
        except Exception:
            MarketingPoster.objects.filter(id=poster_id).update(status="failed")
        finally:
            connections.close_all()
    threading.Thread(target=_target, daemon=True).start()


def start_async(restaurant, user, menu_item=None, user_text="", source_image_urls=None):
    """Crée l'affiche « en cours » et lance la génération en tâche de fond.
    Lève Disabled/QuotaExceeded immédiatement si besoin."""
    poster = _create_pending(restaurant, user, menu_item, user_text, parent=None)
    _spawn(poster.id, list(source_image_urls or []))
    return poster


def start_refine_async(poster, new_instructions, user):
    ref_urls = [poster.image_url] if poster.image else []
    child = _create_pending(
        poster.restaurant, user, poster.menu_item, new_instructions, parent=poster)
    _spawn(child.id, ref_urls)
    return child
