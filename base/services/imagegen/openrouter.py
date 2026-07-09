"""Client de l'API Image unifiée d'OpenRouter."""
import base64

import requests

from .errors import ImageGenError

API_URL = "https://openrouter.ai/api/v1/images"


def generate_image(prompt, model, size, api_key, reference_image_urls=None):
    if not api_key:
        raise ImageGenError("Clé API OpenRouter manquante")

    payload = {"model": model, "prompt": prompt, "size": size}
    refs = [u for u in (reference_image_urls or []) if u]
    if refs:
        # Format confirmé : tableau d'objets typés (style contenu OpenAI).
        # Les modèles d'édition (GPT Image, Gemini) l'exploitent ; un
        # text-to-image pur peut l'ignorer. Plusieurs références possibles.
        payload["input_references"] = [
            {"type": "image_url", "image_url": {"url": u}} for u in refs
        ]

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    try:
        # La génération d'image peut dépasser une minute selon le modèle/résolution.
        resp = requests.post(API_URL, json=payload, headers=headers, timeout=180)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # réseau, HTTP != 2xx, JSON invalide
        raise ImageGenError(f"Échec OpenRouter : {exc}") from exc

    try:
        item = data["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise ImageGenError("Réponse OpenRouter inattendue") from exc

    if item.get("b64_json"):
        return base64.b64decode(item["b64_json"])
    if item.get("url"):
        try:
            img = requests.get(item["url"], timeout=60)
            img.raise_for_status()
            return img.content
        except Exception as exc:
            raise ImageGenError(f"Téléchargement image échoué : {exc}") from exc
    raise ImageGenError("Aucune image dans la réponse OpenRouter")
