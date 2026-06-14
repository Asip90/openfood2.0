# Assistant IA conversationnel pour clients — Design

**Date :** 2026-06-14
**Statut :** Validé (en attente de relecture utilisateur avant plan d'implémentation)

## Objectif

Ajouter un assistant IA conversationnel sur la page client du restaurant
(`templates/customer/menu.html`, vue `client_menu`). Accessible via un bouton
flottant, il aide le client à : se faire conseiller un plat, choisir selon un
budget (ex. « j'ai 2500F, qu'est-ce que je prends ? »), obtenir les infos d'un
plat (ingrédients, allergènes, végé/épicé), et appeler le staff. Les réponses
sont **courtes et précises**, et peuvent contenir des **boutons d'action**
(voir détail, ajouter au panier, appeler un serveur) qui réutilisent les
endpoints existants. Le tout dans une atmosphère premium.

## Décisions validées

- **Configuration IA : globale (plateforme).** Un seul `AISettings` (singleton)
  géré dans Jazzmin par le superadmin. Tous les restaurants partagent la même
  IA ; la plateforme paye l'API.
- **Rôle : focalisé menu + service.** L'IA aide uniquement sur le restaurant
  (menu, budget, infos plats, appel staff) et recadre poliment le hors-sujet.
- **Mémoire : éphémère.** Conversation stockée en session Django pendant la
  visite, rien en base de données.
- **Approche technique : A — menu injecté + réponse JSON structurée.** Un seul
  appel API par message, provider-agnostique (Mistral ou Gemini), réutilise la
  logique existante (panier, modale détail, appel serveur).
- **Fournisseurs : Mistral ou Gemini**, sélectionnables dans l'admin.

## Architecture

### 1. Modèle de données

Nouveau modèle `AISettings` dans l'app `base` (singleton — une seule ligne) :

| Champ | Type | Rôle |
|---|---|---|
| `provider` | CharField choices `mistral`/`gemini` | fournisseur actif |
| `api_key` | CharField | clé API (champ password dans l'admin) |
| `model` | CharField | ex. `mistral-small-latest`, `gemini-2.0-flash` |
| `is_enabled` | BooleanField (défaut False) | active/désactive le chat partout |
| `system_prompt` | TextField (blank) | override du brief système ; valeur par défaut fournie si vide |
| `max_messages_per_session` | IntegerField (défaut 20) | garde-fou coût/abus |
| `updated_at` | DateTimeField (auto_now) | — |

- Garde-fou singleton : `save()` force `pk=1` (ou empêche la création d'une 2ᵉ
  ligne) ; helper `AISettings.load()` qui renvoie/crée l'unique instance.
- **Aucune autre table** (mémoire éphémère).

### 2. Admin (Jazzmin)

- Enregistrement de `AISettings` ; `api_key` rendu via un widget password.
- Désactivation du bouton « Ajouter » quand une instance existe déjà (singleton).

### 3. Couche fournisseur — `base/services/ai/`

Unités isolées, chacune un seul rôle, testables indépendamment :

- `base.py` — interface `AIProvider` avec `complete(system: str, messages: list) -> str`.
- `mistral.py` — implémentation Mistral (HTTP via `requests`, mode JSON).
- `gemini.py` — implémentation Gemini (HTTP via `requests`, mode JSON).
- `factory.py` — lit `AISettings`, retourne l'instance du bon provider.

Ajouter un fournisseur plus tard = 1 nouveau fichier, sans toucher au reste.

### 4. Couche métier — `base/services/ai/assistant.py`

- Construit le **brief système** : règles (focalisé menu + service, recadrage
  hors-sujet, réponses courtes/précises, ton premium sans emoji, devise du
  resto) + **menu injecté** = liste des plats **disponibles** du resto
  (`id`, nom, prix, description courte, allergènes, flags végé/végan/épicé).
- Impose le **format de sortie JSON** (voir Contrat de réponse).
- Reçoit l'historique de session + le nouveau message.
- **Valide la réponse** : `reply` obligatoire (tronqué si trop long) ; chaque
  action vérifiée (`item_id` doit exister et être disponible dans CE resto,
  sinon l'action est retirée) ; `type` inconnu ignoré ; JSON invalide → repli
  sur une réponse texte simple.

### 5. Endpoint — `customer/views.py`

Nouvelle vue `chat_assistant(request, table_token)` :

- `POST` JSON `{ "message": "..." }`.
- Récupère restaurant + table via `get_client_context(request, table_token)`
  (logique existante).
- Historique lu/écrit dans `request.session`, clé par table, plafonné à
  `max_messages_per_session`.
- Si `AISettings.is_enabled` faux ou clé absente → réponse propre
  « assistant indisponible » (jamais d'erreur 500).
- Route ajoutée dans `customer/urls.py` :
  `path("t/<str:table_token>/chat/", chat_assistant, name="chat_assistant")`.

**Aucun nouvel endpoint d'action** : les boutons réutilisent
`get_item_details`, `update_cart`, `create_waiter_call`.

## Contrat de réponse (JSON structuré)

L'IA répond toujours dans ce format :

```json
{
  "reply": "Avec 2500F, je te conseille le Riz sauce arachide, copieux et parfumé.",
  "actions": [
    { "type": "view_item",   "item_id": "42", "label": "Voir le Riz arachide" },
    { "type": "add_to_cart", "item_id": "42", "label": "Ajouter au panier" },
    { "type": "call_waiter", "label": "Appeler un serveur" }
  ]
}
```

Types d'actions reconnus (seuls ceux-là sont câblés côté front) :

| `type` | Bouton | Branché sur (existant) |
|---|---|---|
| `view_item` | Voir détail | modale `get_item_details` |
| `add_to_cart` | Ajouter au panier | `update_cart` |
| `call_waiter` | Appeler un serveur | `create_waiter_call` |

Règles : `reply` texte court obligatoire ; `actions` optionnel ; `item_id`
vérifié côté serveur ; `type` inconnu ignoré ; JSON invalide → repli texte.

## Interface (Tailwind + Alpine.js, SVG inline — pas d'emoji)

**Bouton flottant unique** (FAB) en bas à droite, aux couleurs du resto
(`customization.primary_color`), premium. Remplace l'ancien bouton
« Appeler un serveur » isolé.

Au clic, le FAB **se déplie** et révèle **deux icônes SVG** :

- **Cloche** → ouvre une **modale de confirmation** « Voulez-vous appeler un
  serveur ? » avec **Oui / Annuler**. Si Oui → `create_waiter_call`, puis
  « Serveur appelé ✓ ».
- **Chat** → ouvre la **fenêtre de chat** avec l'assistant.

Re-cliquer sur le FAB (ou cliquer ailleurs) replie les icônes.

**Fenêtre de chat** :
- Carte premium (fond sombre / glassmorphism léger), en-tête nom du resto +
  bouton fermer, hauteur ~70vh, plein écran sur mobile.
- Fil de messages : bulles user (droite) / IA (gauche) ; **boutons d'action**
  rendus sous chaque réponse IA.
- Chips de départ (1ʳᵉ ouverture) : « Propose-moi un plat »,
  « J'ai 2500F, qu'est-ce que je prends ? », « Une entrée pas chère ? ».
- Zone de saisie : champ + bouton envoyer + indicateur « … » pendant la
  réflexion de l'IA.

**État désactivé** : si `AISettings.is_enabled` faux, le FAB n'affiche que la
**cloche** (appel serveur toujours possible) ; pas d'icône chat.

Composant isolé dans `templates/customer/_chat_assistant.html`, inclus depuis
`menu.html`.

## Sécurité, coûts & erreurs

- Clé API **jamais exposée** au navigateur ; le front parle seulement à `…/chat/`.
- Limite `max_messages_per_session` (défaut 20) → message « limite atteinte,
  appelez un serveur ».
- Throttle basique par session/table (ex. 1 message / 2 s).
- Validation : longueur max du message entrant ; réponses tronquées si trop
  longues ; `item_id` toujours vérifiés.
- Menu injecté borné aux plats **disponibles** (pas toute la base).
- Dégradation propre : clé absente / IA désactivée / fournisseur en panne /
  JSON invalide → message courtois, jamais de 500 ; la cloche marche toujours.
- Confidentialité : rien en base (session éphémère).

## Fichiers touchés

**Nouveaux :**
- `base/models.py` → `AISettings` (+ migration)
- `base/admin.py` → enregistrement Jazzmin (singleton, clé masquée)
- `base/services/ai/{__init__,base,mistral,gemini,factory,assistant}.py`
- `templates/customer/_chat_assistant.html`

**Modifiés :**
- `customer/views.py` → vue `chat_assistant`
- `customer/urls.py` → route `…/chat/`
- `templates/customer/menu.html` → nouveau FAB déplié (cloche + chat) + include
- `requirements.txt` → `requests` si absent

**Réutilisés sans modification :** `get_item_details`, `update_cart`,
`create_waiter_call`, `get_client_context`.

## Hors périmètre (YAGNI)

- Configuration IA par restaurant ou override (globale uniquement pour le MVP).
- Stockage des conversations / analytics (mémoire éphémère).
- Function/tool calling (approche A retenue).
- Streaming des réponses (réponse unique suffit pour des messages courts).
- Multi-langue explicite (français par défaut ; l'IA suit la langue du client).
