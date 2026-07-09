"""Lecture des avis Google via l'API Places (New), avec cache court.

CGU Google : on ne stocke pas durablement les avis — cache seulement.
"""
import requests
from django.core.cache import cache

API_URL = "https://places.googleapis.com/v1/places/{place_id}"
FIELD_MASK = "rating,userRatingCount,googleMapsUri,reviews"


class ReputationError(Exception):
    """Échec de récupération des avis Google."""


def _normalize(data):
    reviews = []
    for r in (data.get("reviews") or [])[:5]:
        author = (r.get("authorAttribution") or {})
        reviews.append({
            "author": author.get("displayName", "Client Google"),
            "photo": author.get("photoUri", ""),
            "rating": r.get("rating"),
            "text": (r.get("text") or {}).get("text", ""),
            "relative_time": r.get("relativePublishTimeDescription", ""),
        })
    return {
        "rating": data.get("rating"),
        "total": data.get("userRatingCount", 0),
        "maps_uri": data.get("googleMapsUri", ""),
        "reviews": reviews,
    }


def get_reviews(place_id, api_key, cache_hours):
    if not api_key:
        raise ReputationError("Clé API Google manquante")
    if not place_id:
        raise ReputationError("Place ID manquant")

    cache_key = f"reputation:{place_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    headers = {"X-Goog-Api-Key": api_key, "X-Goog-FieldMask": FIELD_MASK}
    try:
        resp = requests.get(
            API_URL.format(place_id=place_id), headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        raise ReputationError(f"Échec Google Places : {exc}") from exc

    result = _normalize(data)
    cache.set(cache_key, result, int(cache_hours) * 3600)
    return result
