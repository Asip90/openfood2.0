# Réputation — Avis Google reçus (Route A) — Design (Bloc 4)

**Date :** 2026-07-09
**Statut :** Validé — autonomie accordée

## Objectif

Afficher dans OpenFood la **note Google** et les **avis reçus** d'un restaurant
(preuve sociale), via l'**API Google Places (New)**, en réutilisant le
`google_place_id` déjà stocké au bloc 1. Route A : lecture seule, jusqu'à
5 avis (limite Google), pas de stockage durable (conforme CGU), cache court.

## Décisions

- **Route A** (Places API New, Place Details). Pas de réponse aux avis (ce
  serait Route B / Business Profile API, offre Max, plus tard).
- **Clé Google Places = super-admin** (singleton `ReputationSettings`,
  plateforme paie). `is_enabled`, `google_api_key`, `cache_hours` (défaut 12).
- **Conformité CGU** : on **ne stocke pas** les avis en base ; on **cache** la
  réponse Google (cache Django, TTL = `cache_hours`) pour limiter le coût API,
  avec attribution « Avis Google ».
- **Gating** : owner/coadmin + **Pro/Max** (cohérent avec le côté collecte
  d'avis du bloc 1) + `is_enabled` + `google_place_id` renseigné.
- Réutilise `Restaurant.google_place_id` (bloc 1) — pas de nouveau champ resto.

## Architecture

### 1. Config super-admin — `ReputationSettings` (singleton, app `base`)

| Champ | Type | Rôle |
|---|---|---|
| `is_enabled` | Bool (défaut False) | active la fonctionnalité |
| `google_api_key` | CharField (password) | clé API Google Places (plateforme) |
| `cache_hours` | PositiveIntegerField (défaut 12) | TTL du cache des avis |
| `updated_at` | DateTime auto | — |

Singleton `load()`/`save(pk=1)` + admin Jazzmin (password widget, add si absent,
pas de delete) — mêmes patterns que `AISettings`/`ImageGenSettings`.

### 2. Service — `base/services/reputation/google_places.py`

- `get_reviews(place_id, api_key, cache_hours) -> dict` :
  - Clé cache `reputation:<place_id>` ; si présent → renvoyer le cache.
  - Sinon : `GET https://places.googleapis.com/v1/places/<place_id>` avec
    headers `X-Goog-Api-Key: <key>` et
    `X-Goog-FieldMask: rating,userRatingCount,googleMapsUri,reviews`.
  - Normaliser en
    `{"rating": float|None, "total": int, "maps_uri": str,
      "reviews": [{"author": str, "rating": int, "text": str,
      "relative_time": str, "photo": str}]}` (max 5).
  - Mettre en cache `cache_hours` heures. Lève `ReputationError` en cas
    d'échec (clé absente, HTTP != 2xx).
  - `ReputationError` défini dans le même module (ou `errors.py`).
- Tests : mocker `requests.get` et le cache (aucun réseau réel).

### 3. Vue + page dashboard

- `reputation_view(request)` (GET) : gardée `@owner_or_coadmin_required` +
  `restaurant.is_pro()` (sinon `Http404`). Lit `ReputationSettings` ; si
  `is_enabled` et `google_place_id` renseigné → `get_reviews(...)` (try/except
  `ReputationError` → message d'erreur, page quand même rendue). Passe au
  template : `data` (ou None), `place_id_set`, `enabled`, `error`.
- URL `reputation/` nommée `reputation`.
- Template `templates/admin_user/reputation/index.html` : entête note moyenne
  + nombre d'avis + lien « Voir sur Google » (`maps_uri`), liste des avis
  (auteur, étoiles, texte, date relative), attribution « Avis Google ». États :
  non-Pro (géré par gating), non configuré (« Renseignez votre Place ID dans
  Paramètres »), désactivé, erreur.
- Entrée sidebar « Réputation » (⭐), gatée Pro (owner/coadmin).

## Gating

- Page + service : owner/coadmin + `is_pro()` + `is_enabled` + `google_place_id`.

## Tests

- `ReputationSettings` singleton/`load`.
- `get_reviews` : succès (mock JSON Google → dict normalisé, ≤5 avis) ; cache
  hit (2ᵉ appel ne refait pas de requête) ; `ReputationError` si clé absente /
  HTTP erreur.
- Vue : 404 si non-Pro ; rendu 200 si Pro (avec `get_reviews` mocké) ; message
  si `google_place_id` vide.

## Découpage

1. `ReputationSettings` + admin + migration.
2. Service `google_places.get_reviews` + cache + erreurs + tests.
3. Vue + URL + template + sidebar + gating + tests.

## Hors périmètre

- Route B (répondre aux avis, OAuth Business Profile, offre Max).
- Stockage/analytics des avis dans le temps (CGU Google l'interdisent en
  Route A).
- Vérification e2e réelle : nécessite une clé Google Places (à fournir par le
  super-admin) ; les tests mockent l'appel.
