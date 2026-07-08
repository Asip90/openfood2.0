# Générateur d'affiche IA — Design (Bloc 2)

**Date :** 2026-07-08
**Statut :** Validé — autonomie accordée (relecture spec sautée sur demande)

## Objectif

Donner aux restaurants **Pro/Max** un outil qui génère, à partir d'un plat
(image + infos) et d'un angle optionnel, une **affiche appétissante** + une
**légende émotionnelle** prête à copier pour WhatsApp/réseaux. Deux étapes IA :
un modèle texte (**Mistral**, déjà intégré) fabrique un prompt image **varié**
et la légende ; puis **OpenRouter (API Image unifiée)** génère l'image. Le resto
peut **raffiner** (redonner des instructions sur une image générée) jusqu'au
rendu voulu, télécharger, et retrouver ses affiches dans une **galerie**.

## Décisions validées

- **Accès** : rôles **owner + coadmin** uniquement, restaurants **Pro/Max**
  uniquement, fonctionnalité activable globalement. **Quota/jour par
  restaurant** (défaut 5). La **plateforme paie** l'API (clé OpenRouter centrale).
- **Choix du modèle image = super-admin** (singleton, façon `AISettings`).
  Sélection **hybride** : une **liste déroulante** de modèles connus **+** un
  champ **saisie libre de l'ID** OpenRouter (pour tout modèle : GPT Image, Flux,
  Gemini « nano banana »…). Le super-admin arbitre coût/perf.
- **Étape texte** : réutilise `AISettings` (Mistral) existant.
- **Variété contrôlée** : palette de styles curée ; Mistral en choisit un
  différent à chaque génération.
- **Galerie/historique** par restaurant (image Cloudinary + légende + prompt).
- **Raffinage** : sélectionner une affiche → nouvelles instructions →
  nouvelle affiche liée à la précédente (chaîne `parent`).
- **Nuance modèle** : la référence-image (image du plat, raffinage sur image
  précédente) ne marche qu'avec des modèles d'**édition** (GPT Image, Gemini).
  Un Flux text-to-image pur ignore l'image d'entrée → repli propre sur le
  prompt texte enrichi. Le client OpenRouter envoie l'image de référence si
  disponible ; l'absence de prise en compte n'est pas une erreur.

## Architecture

### 1. Config super-admin — modèle `ImageGenSettings` (singleton, app `base`)

| Champ | Type | Rôle |
|---|---|---|
| `is_enabled` | BooleanField (défaut False) | active/désactive la fonctionnalité partout |
| `openrouter_api_key` | CharField (widget password) | clé API OpenRouter (plateforme) |
| `image_model` | CharField choices | liste déroulante ; valeur `custom` pour saisie libre |
| `image_model_custom` | CharField (blank) | ID modèle si `image_model == 'custom'` |
| `image_size` | CharField (défaut `1024x1536`) | ratio portrait réseaux par défaut |
| `daily_quota_per_restaurant` | PositiveIntegerField (défaut 5) | garde-fou coût |
| `updated_at` | DateTimeField (auto_now) | — |

- Choices `image_model` (exemples, éditables) : `openai/gpt-image-1-mini`,
  `openai/gpt-image-2`, `google/gemini-2.5-flash-image`,
  `black-forest-labs/flux-1.1-pro`, `custom`.
- Helper `effective_model()` → `image_model_custom` si `image_model=='custom'`
  sinon `image_model`.
- Singleton : `save()` force `pk=1` ; `load()` get_or_create ; enregistré dans
  Jazzmin avec `has_add_permission = not exists`, `has_delete_permission=False`,
  `openrouter_api_key` en `PasswordInput` (mêmes patterns que `AISettingsAdmin`).

### 2. Historique — modèle `MarketingPoster` (app `base`)

| Champ | Type | Rôle |
|---|---|---|
| `restaurant` | FK, `related_name='posters'` | — |
| `menu_item` | FK `MenuItem`, null/blank, SET_NULL | plat source |
| `image` | `CloudinaryField('image', resource_type='image', blank=True)` | affiche générée |
| `caption` | TextField (blank) | légende émotionnelle |
| `prompt_used` | TextField (blank) | prompt image envoyé (debug/raffinage) |
| `style` | CharField (blank) | style pioché |
| `user_text` | CharField (blank) | angle/offre saisi par le resto |
| `parent` | self-FK, null/blank, SET_NULL, `related_name='refinements'` | chaîne de raffinage |
| `created_by` | FK `accounts.User`, null, SET_NULL | — |
| `created_at` | DateTimeField (auto_now_add) | — |

- `Meta.ordering = ['-created_at']`.
- Quota : compter les `MarketingPoster` du resto sur les dernières 24 h.

### 3. Palette de styles — `base/services/imagegen/styles.py`

- `STYLE_PALETTE` : liste de ~10 directions visuelles (libellé + brief court),
  ex. « flat lay premium », « gros plan macro appétissant », « ambiance
  chaleureuse à table », « pop coloré réseaux », « fond studio épuré »,
  « street food énergique »…
- Utilisée par le prompt-builder pour imposer la variété.

### 4. Étape texte — `base/services/imagegen/prompt_builder.py`

- `build(restaurant, menu_item, user_text, source_image_present, exclude_style=None) -> dict`
  - Compose un message pour le provider IA (réutilise
    `base.services.ai.factory.get_provider()` + `AISettings`).
  - Contexte injecté : nom du plat, description, ingrédients, prix ; nom du
    resto, `primary_color`/`secondary_color`, adresse/lieu, présence logo ;
    `user_text` ; instruction de **choisir un style** dans `STYLE_PALETTE`
    (différent de `exclude_style` si fourni).
  - Retourne `{"image_prompt": str, "caption": str, "style": str}` (parse JSON,
    repli robuste si JSON invalide).

### 5. Client image — `base/services/imagegen/openrouter.py`

- `generate_image(prompt, model, size, reference_image_url=None) -> bytes`
  - POST `https://openrouter.ai/api/v1/images` (Authorization Bearer =
    `openrouter_api_key`), body `{model, prompt, size, ...}` + image de
    référence si fournie et supportée.
  - **⚠️ Implémentation : vérifier le format exact requête/réponse sur la doc
    OpenRouter** (https://openrouter.ai/docs/guides/overview/multimodal/image-generation)
    au moment de coder — champs et forme de la réponse (b64 vs URL) à confirmer.
  - Lève `ImageGenError` en cas d'échec (clé absente, quota API, HTTP != 2xx).
  - Les tests **mockent** cet appel HTTP (pas d'appel réseau réel en test).

### 6. Orchestrateur — `base/services/imagegen/generator.py`

- `generate(restaurant, user, menu_item=None, user_text='', source_image_url=None) -> MarketingPoster`
  - Vérifie `ImageGenSettings.is_enabled` + quota resto ; sinon `QuotaExceeded`/
    `Disabled`.
  - `prompt_builder.build(...)` → `openrouter.generate_image(...)` → upload
    Cloudinary → crée `MarketingPoster`.
- `refine(poster, new_instructions, user) -> MarketingPoster`
  - Réutilise le plat/contexte du `poster` parent, **image de référence = image
    du poster parent**, `user_text = new_instructions`, garde/ajuste le style →
    nouveau `MarketingPoster` avec `parent=poster`. Compte dans le quota.

### 7. Vues dashboard — app `base` (owner + coadmin, Pro/Max)

- `posters_studio(request)` (GET) : page « Affiches » — formulaire (choix plat
  → pré-remplit image/infos, upload optionnel, texte optionnel) + galerie
  (`restaurant.posters`) + compteur quota du jour.
- `posters_generate(request)` (POST) : lance `generator.generate(...)`,
  renvoie l'affiche (JSON ou redirect vers la page avec l'affiche en tête).
- `posters_refine(request, poster_id)` (POST) : `generator.refine(...)`.
- Toutes gardées : `@owner_or_coadmin_required` + garde `restaurant.is_pro()` +
  `ImageGenSettings.load().is_enabled` + quota. URLs sous `affiches/`.

### 8. UI

- Entrée sidebar « Affiches » (🎨), visible si `restaurant.is_pro` (+ zone
  owner/coadmin), badge/compteur quota facultatif.
- Template `templates/admin_user/posters/studio.html` : formulaire + résultat
  (image, légende avec bouton **copier**, bouton **télécharger**, champ
  **raffiner**), galerie en grille. Réutilise l'ossature `admin_user/base.html`
  (`{% block title %}`, `{% block page_title %}`, `{% block content %}`).

## Découpage en unités (implémentation)

1. **Config** : `ImageGenSettings` (modèle + singleton + admin Jazzmin) + migration.
2. **Historique** : modèle `MarketingPoster` + migration.
3. **Styles + prompt-builder** : `styles.py`, `prompt_builder.py` (réutilise la
   couche `ai`) + tests (provider mocké).
4. **Client OpenRouter** : `openrouter.py` + `ImageGenError` + tests (HTTP mocké).
5. **Orchestrateur** : `generator.generate` + `refine` + quota + tests
   (prompt-builder et client mockés, Cloudinary mocké).
6. **Vues + URLs + gating + quota serveur** + tests.
7. **UI** : page studio + galerie + raffinage + entrée sidebar.

## Tests

- `effective_model()` (choix vs custom).
- `prompt_builder.build` : JSON parsé → dict complet ; repli si JSON invalide ;
  style ≠ `exclude_style`.
- `openrouter.generate_image` : succès (mock 2xx → bytes) ; `ImageGenError` sur
  échec/clé absente.
- `generator.generate` : crée un `MarketingPoster` (composants mockés) ;
  `QuotaExceeded` quand quota atteint ; `Disabled` si `is_enabled=False`.
- `generator.refine` : crée un poster avec `parent` renseigné, compte au quota.
- Gating vues : 404/redirect si non-Pro, si mauvais rôle, ou `is_enabled=False`.

## Hors périmètre (bloc 2)

- Bloc 3 « Réputation » (avis Google reçus).
- Carte de fidélité.
- Publication automatique vers WhatsApp/réseaux (on fournit image + légende à
  copier/télécharger ; pas d'intégration API WhatsApp).
