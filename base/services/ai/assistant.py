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


_VALID_ACTION_TYPES = {"view_item", "add_to_cart", "call_waiter"}
_DEFAULT_LABELS = {
    "view_item": "Voir le plat",
    "add_to_cart": "Ajouter au panier",
    "call_waiter": "Appeler un serveur",
}


def _fallback_text(raw):
    if isinstance(raw, str) and raw.strip():
        return raw.strip()[:600]
    return "Désolé, le service est momentanément indisponible."


def validate_response(raw, restaurant):
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"reply": _fallback_text(raw), "actions": []}
    if not isinstance(data, dict):
        return {"reply": _fallback_text(raw), "actions": []}

    reply = data.get("reply")
    if not isinstance(reply, str) or not reply.strip():
        reply = "Désolé, je n'ai pas compris. Pouvez-vous reformuler ?"
    reply = reply.strip()[:600]

    valid_ids = set(
        str(i)
        for i in MenuItem.objects.filter(
            restaurant=restaurant, is_available=True
        ).values_list("id", flat=True)
    )

    actions = []
    for a in (data.get("actions") or []):
        if not isinstance(a, dict):
            continue
        atype = a.get("type")
        if atype not in _VALID_ACTION_TYPES:
            continue
        label = str(a.get("label", "")).strip()[:60] or _DEFAULT_LABELS[atype]
        if atype in ("view_item", "add_to_cart"):
            item_id = str(a.get("item_id", "")).strip()
            if item_id in valid_ids:
                actions.append({"type": atype, "item_id": item_id, "label": label})
        else:  # call_waiter
            actions.append({"type": "call_waiter", "label": label})
    return {"reply": reply, "actions": actions[:6]}


def is_assistant_available():
    s = AISettings.load()
    return bool(s.is_enabled and s.api_key)


def ask(restaurant, history, user_message):
    """history: list of {role, content}. Returns {reply, actions, ...}."""
    from .factory import get_provider

    settings = AISettings.load()
    if not settings.is_enabled or not settings.api_key:
        return {
            "reply": "L'assistant n'est pas disponible pour le moment.",
            "actions": [],
            "unavailable": True,
        }
    provider = get_provider(settings)
    if provider is None:
        return {
            "reply": "L'assistant n'est pas disponible pour le moment.",
            "actions": [],
            "unavailable": True,
        }

    system = build_system_prompt(restaurant)
    messages = history + [{"role": "user", "content": user_message}]
    try:
        raw = provider.complete(system, messages)
    except Exception:
        return {
            "reply": "Je rencontre un souci technique. Vous pouvez appeler un serveur.",
            "actions": [{"type": "call_waiter", "label": "Appeler un serveur"}],
            "error": True,
        }
    return validate_response(raw, restaurant)
