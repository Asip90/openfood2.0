import json

from base.models import AISettings, MenuItem

DEFAULT_SYSTEM_PROMPT = (
    'Tu es l\'assistant du restaurant "{restaurant_name}". '
    "Tu aides UNIQUEMENT sur le menu et le service : recommander des plats, "
    "conseiller selon un budget, donner les infos d'un plat (ingrédients, "
    "allergènes, végétarien, épicé), et proposer d'appeler le serveur. "
    "Refuse poliment toute demande hors menu/service et recentre vers le menu. "
    "Réponds en français, de façon courte et précise, ton chaleureux mais sobre, "
    "sans emoji. La monnaie est le FCFA. "
    "Réponds UNIQUEMENT en JSON valide de la forme "
    '{{"reply": "texte court", "actions": [ ... ]}}. '
    "Chaque action est l'un de : "
    '{{"type":"view_item","item_id":"<id>","label":"..."}}, '
    '{{"type":"add_to_cart","item_id":"<id>","label":"..."}}, '
    '{{"type":"call_waiter","label":"..."}}. '
    "N'invente jamais de plat : n'utilise que les id du MENU ci-dessous. "
    "actions peut être une liste vide.\n\nMENU:\n{menu}"
)


def serialize_menu(restaurant):
    items = (
        MenuItem.objects.filter(restaurant=restaurant, is_available=True)
        .select_related("category")
        .order_by("category__order", "order", "name")
    )
    lines = []
    for it in items:
        price = it.discount_price if it.discount_price else it.price
        tags = []
        if it.is_vegetarian:
            tags.append("végétarien")
        if it.is_vegan:
            tags.append("végan")
        if it.is_spicy:
            tags.append("épicé")
        desc = (it.description or "").strip().replace("\n", " ")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        line = f"- id={it.id} | {it.name} | {price:.0f} FCFA"
        if it.category_id:
            line += f" | catégorie: {it.category.name}"
        if desc:
            line += f" | {desc}"
        if it.allergens:
            line += f" | allergènes: {it.allergens}"
        if tags:
            line += f" | {', '.join(tags)}"
        lines.append(line)
    return "\n".join(lines) if lines else "(aucun plat disponible)"


def build_system_prompt(restaurant):
    settings = AISettings.load()
    template = settings.system_prompt.strip() or DEFAULT_SYSTEM_PROMPT
    menu = serialize_menu(restaurant)
    try:
        return template.format(restaurant_name=restaurant.name, menu=menu)
    except (KeyError, IndexError, ValueError):
        # Custom prompt without placeholders: append the menu so the model still
        # gets it, and ensure the JSON contract is present.
        return (
            f"{template}\n\nRestaurant: {restaurant.name}\n\nMENU:\n{menu}\n\n"
            'Réponds UNIQUEMENT en JSON {"reply": "...", "actions": [...]}.'
        )
