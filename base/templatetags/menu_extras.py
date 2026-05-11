import json
from django import template

register = template.Library()

@register.filter
def item_json(item):
    media_qs = list(item.media.all())  # pre-fetched via prefetch_related

    images = [m.url for m in media_qs if m.media_type == 'image'][:3]

    # Fallback: backward compat with old MenuItem.image field
    if not images and item.image:
        images = [item.image.url]

    video_media = next((m for m in media_qs if m.media_type == 'video'), None)

    return json.dumps({
        'id': str(item.id),
        'name': item.name,
        'description': item.description or '',
        'price': str(item.price),
        'discount_price': str(item.discount_price) if item.discount_price else None,
        'image': images[0] if images else None,
        'images': images,
        'video': video_media.url if video_media else None,
        'is_vegetarian': getattr(item, 'is_vegetarian', False),
        'is_vegan': getattr(item, 'is_vegan', False),
        'is_spicy': getattr(item, 'is_spicy', False),
        'preparation_time': getattr(item, 'preparation_time', None),
        'allergens': getattr(item, 'allergens', '') or '',
        'ingredients': getattr(item, 'ingredients', '') or '',
    })
