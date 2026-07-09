"""Étape texte : Mistral fabrique un prompt image varié + une légende."""
import json
import random

from base.services.ai.factory import get_provider
from .styles import STYLE_PALETTE

SYSTEM = (
    "Tu es directeur artistique culinaire ET copywriter. À partir des infos "
    "d'un plat et d'un restaurant, tu produis (1) un PROMPT en anglais pour un "
    "modèle de génération d'image, décrivant une photo de plat ultra "
    "appétissante, et (2) une LÉGENDE courte en français, émotionnelle et "
    "percutante, prête à copier pour WhatsApp/réseaux, SANS aucun emoji. "
    "Tu DOIS adopter le style visuel imposé ci-dessous. "
    "Réponds UNIQUEMENT en JSON : "
    '{"image_prompt": "...", "caption": "...", "style": "<style_key>"}.'
)


def _context(restaurant, menu_item, user_text, source_image_present, style):
    parts = [f"Restaurant: {restaurant.name}"]
    if restaurant.address:
        parts.append(f"Lieu: {restaurant.address}")
    parts.append(
        f"Couleurs marque: {restaurant.primary_color}, {restaurant.secondary_color}")
    if menu_item is not None:
        parts.append(f"Plat: {menu_item.name}")
        if menu_item.description:
            parts.append(f"Description: {menu_item.description}")
        if menu_item.ingredients:
            parts.append(f"Ingrédients: {menu_item.ingredients}")
        price = menu_item.discount_price or menu_item.price
        parts.append(f"Prix: {price:.0f} FCFA")
    if user_text:
        parts.append(f"Angle/offre demandé: {user_text}")
    if source_image_present:
        parts.append("Une image de référence du plat est fournie séparément.")
    parts.append(
        f"STYLE IMPOSÉ (style_key={style['key']}): {style['label']} — {style['brief']}")
    return "\n".join(parts)


def _fallback(restaurant, menu_item, style):
    name = menu_item.name if menu_item is not None else restaurant.name
    return {
        "image_prompt": (
            f"professional appetizing food photography of {name}, "
            f"{style['brief']}, high detail, mouth-watering"),
        "caption": f"{name} vous attend chez {restaurant.name} !",
        "style": style["key"],
    }


def build(restaurant, menu_item, user_text, source_image_present, exclude_style=None):
    pool = [s for s in STYLE_PALETTE if s["key"] != exclude_style] or STYLE_PALETTE
    style = random.choice(pool)

    provider = get_provider()
    if provider is None:
        return _fallback(restaurant, menu_item, style)

    context = _context(restaurant, menu_item, user_text, source_image_present, style)
    try:
        raw = provider.complete(SYSTEM, [{"role": "user", "content": context}])
        data = json.loads(raw)
        return {
            "image_prompt": data.get("image_prompt") or _fallback(restaurant, menu_item, style)["image_prompt"],
            "caption": data.get("caption") or _fallback(restaurant, menu_item, style)["caption"],
            "style": data.get("style") or style["key"],
        }
    except Exception:
        return _fallback(restaurant, menu_item, style)
