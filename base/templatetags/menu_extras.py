import json
from django import template

register = template.Library()

@register.filter
def item_json(item):
    return json.dumps({
        'id': item.id,
        'name': item.name,
        'description': item.description or '',
        'price': str(item.price),
        'discount_price': str(item.discount_price) if item.discount_price else None,
        'image': item.image.url if item.image else None,
        'is_vegetarian': getattr(item, 'is_vegetarian', False),
        'is_vegan': getattr(item, 'is_vegan', False),
        'is_spicy': getattr(item, 'is_spicy', False),
        'preparation_time': getattr(item, 'preparation_time', None),
        'allergens': getattr(item, 'allergens', '') or '',
        'ingredients': getattr(item, 'ingredients', '') or '',
    })
