"""Palette de styles visuels curée pour varier les affiches."""

STYLE_PALETTE = [
    {"key": "macro", "label": "Gros plan macro",
     "brief": "extreme close-up, shallow depth of field, rising steam, appetizing texture"},
    {"key": "flatlay", "label": "Flat lay premium",
     "brief": "top-down flat lay, elegant props, marble or wood surface, editorial"},
    {"key": "cozy_table", "label": "Ambiance chaleureuse à table",
     "brief": "warm restaurant table scene, candle warm light, inviting mood"},
    {"key": "pop", "label": "Pop coloré réseaux",
     "brief": "vibrant saturated colors, bold graphic background, social-media pop"},
    {"key": "studio", "label": "Studio épuré",
     "brief": "clean studio backdrop, soft shadows, product-hero lighting"},
    {"key": "street", "label": "Street food énergique",
     "brief": "dynamic street-food vibe, urban texture, energetic composition"},
    {"key": "rustic", "label": "Rustique authentique",
     "brief": "rustic wooden table, natural daylight, artisanal homemade feel"},
    {"key": "luxe", "label": "Gastronomique chic",
     "brief": "fine-dining plating, dark elegant background, luxurious mood"},
    {"key": "fresh", "label": "Frais et lumineux",
     "brief": "bright airy scene, fresh ingredients around, light and healthy"},
    {"key": "night", "label": "Ambiance nocturne néon",
     "brief": "night ambience, neon accents, moody cinematic lighting"},
]


def keys():
    return [s["key"] for s in STYLE_PALETTE]
