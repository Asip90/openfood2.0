# Parcours de commande & après-commande — Design (Bloc 1)

**Date :** 2026-07-08
**Statut :** Validé — autonomie accordée par l'utilisateur (relecture du spec sautée sur sa demande)

## Objectif

Transformer la fin du parcours de commande client en **levier de rétention** pour
les restaurants. Trois briques, toutes situées autour du flux commande →
page de succès :

1. **Téléphone client fiable** — sélecteur d'indicatif pays + validation du
   format, numéro rendu **obligatoire**, stocké en **E.164**. C'est la future
   clé d'identité pour la fidélité.
2. **Invite communauté WhatsApp** — sur la page de succès, un appel à rejoindre
   la chaîne/groupe/communauté du restaurant.
3. **Avis & retour client** — bouton « Laisser un avis Google » + un canal de
   **retour privé** (formulaire) ouvert à tous, conforme à la politique Google
   (pas de *review gating* filtré).

## Décisions validées

- **Téléphone obligatoire** à la commande, stocké en **E.164** (`+229...`).
- **Sélecteur d'indicatif : liste courte** — Bénin (+229, défaut), Togo, Côte
  d'Ivoire, Nigéria, Ghana, Sénégal, Burkina Faso, Mali, Niger, France.
- **Validation** : front léger (JS vanilla, pas de CDN) + back robuste avec la
  lib Python **`phonenumbers`**. Stockage du E.164 normalisé.
- **Gating par offre : les 3 blocs de la page de succès sont réservés Pro/Max.**
  (WhatsApp + avis Google + retour privé). Un resto gratuit ne voit rien de
  spécial sur la page de succès.
- **Avis Google** : lien direct « écrire un avis » via `google_place_id`,
  affiché **pour tous les clients** (du moment que le resto est Pro et a
  renseigné le Place ID).
- **Retour privé** : formulaire ouvert à tous → nouveau modèle
  `CustomerFeedback`, consultable dans un **onglet dédié du dashboard** +
  **notification push** au staff. Pas d'email.
- **Hors périmètre bloc 1** : carte de fidélité, génération d'affiche IA
  (bloc 2), affichage des avis Google reçus (bloc 3 « Réputation »).

## Architecture

### 1. Modèle de données (migrations)

**`Restaurant`** — deux nouveaux champs de configuration :

| Champ | Type | Rôle |
|---|---|---|
| `whatsapp_community_url` | `URLField(blank=True, default='')` | lien chaîne/groupe/communauté WhatsApp |
| `google_place_id` | `CharField(max_length=255, blank=True, default='')` | Place ID pour le lien d'avis Google |

**Nouveau modèle `CustomerFeedback`** (app `base`) — le canal de retour privé :

| Champ | Type | Rôle |
|---|---|---|
| `restaurant` | FK `Restaurant`, `related_name='feedbacks'` | — |
| `order` | FK `Order`, null/blank, `on_delete=SET_NULL` | commande liée si dispo |
| `rating` | `PositiveSmallIntegerField(null=True, blank=True)` | note 1–5 optionnelle |
| `message` | `TextField(blank=True)` | texte libre du client |
| `phone` | `CharField(max_length=20, blank=True)` | repris de la commande |
| `is_read` | `BooleanField(default=False)` | pour le badge dashboard |
| `created_at` | `DateTimeField(auto_now_add=True)` | — |

- `Meta.ordering = ['-created_at']`.

**`Order.customer_phone`** — reste un `CharField(max_length=20)` mais devient
**requis à la saisie** (validation vue + front) et est **normalisé E.164** avant
sauvegarde.

### 2. Validation téléphone — `base/services/phone.py`

Unité isolée, un seul rôle, testable :

- `COUNTRIES` — liste ordonnée de `(iso2, indicatif, label, exemple)` pour les
  10 pays retenus (Bénin en tête).
- `normalize(raw: str, country_iso2: str) -> str` — parse via `phonenumbers`,
  lève `ValueError` si invalide, retourne le E.164.
- `is_valid(raw, country_iso2) -> bool` — wrapper booléen.
- Ajout de **`phonenumbers`** à `requirements.txt`.

### 3. Checkout (`templates/customer/checkout.html` + vue `client_checkout`)

- Le champ téléphone devient : `<select name="phone_country">` (indicatifs) +
  `<input name="customer_phone" required>`.
- **Front** : au submit, validation légère par pays (longueur attendue) ;
  affichage d'un message d'erreur inline si invalide ; on n'envoie pas tant que
  ce n'est pas valide.
- **Back** (`customer/views.py`, création de commande) : lire `phone_country`,
  appeler `phone.normalize()` ; si invalide, ré-afficher le formulaire avec
  l'erreur (pas de création de commande). Stocker le E.164 dans
  `order.customer_phone`.

### 4. Page de succès (`templates/customer/order_confirmation.html`)

Ajout d'une zone « après-commande », visible **uniquement si le restaurant est
Pro/Max** (`get_effective_plan(...).plan_type in ('pro','max')` ; helper à
exposer proprement). Trois cartes, dans l'ordre :

1. **Invite WhatsApp** — affichée si `whatsapp_community_url` est renseigné.
   Carte « Rejoignez notre communauté » + bouton `target="_blank"` vers le lien.
2. **Avis Google** — affichée si `google_place_id` est renseigné. Bouton
   « Laisser un avis sur Google » →
   `https://search.google.com/local/writereview?placeid=<PLACE_ID>`.
3. **Retour privé** — carte « Un souci ? Dites-le au resto » : mini-formulaire
   (note 1–5 optionnelle en étoiles + message). POST vers une nouvelle vue
   `submit_feedback(public_token)` qui crée un `CustomerFeedback` (rating,
   message, phone repris de la commande) et déclenche une **push au staff**.
   Confirmation inline après envoi.

La vue `order_confirmation` doit passer au template : le flag `is_pro`, l'URL
WhatsApp, le lien d'avis Google construit, et un flag « feedback déjà envoyé »
(anti double-envoi via session ou champ).

### 5. Paramètres restaurant (page Paramètres existante)

Nouvelle section **« Communauté & avis »** :

- Champ **lien communauté WhatsApp** — si le resto est en offre gratuite,
  afficher un état désactivé + mention « Disponible avec l'offre Pro ».
- Champ **Google Place ID** — avec un lien d'aide « Comment trouver mon
  Place ID ? » (Place ID Finder de Google).
- Persistés dans la vue paramètres existante (ajout au form/traitement POST).

### 6. Dashboard — onglet « Retours clients »

- Nouvelle vue + template listant les `CustomerFeedback` du restaurant
  (note, message, téléphone, date, statut lu/non-lu).
- Marquage « lu » à l'ouverture ; **badge de compteur non-lus** dans la sidebar.
- Entrée de menu réservée Pro/Max (cohérent avec le gating de collecte).
- Notification **push** au staff à chaque nouveau retour (réutilise
  `base/push.py`).

## Découpage en unités (pour l'implémentation)

1. **Migrations & modèles** — champs `Restaurant`, modèle `CustomerFeedback`.
2. **Service téléphone** — `base/services/phone.py` + `phonenumbers` + tests.
3. **Checkout** — sélecteur indicatif, validation front + back, stockage E.164.
4. **Paramètres resto** — section « Communauté & avis ».
5. **Page de succès** — 3 cartes + vue feedback + push.
6. **Dashboard retours** — vue, template, badge, gating.

Chaque unité est indépendante (interfaces claires) et testable isolément.

## Tests

- `phone.normalize` : cas valides/invalides par pays (Bénin 10 chiffres, etc.).
- Checkout : refus si téléphone absent/invalide ; E.164 stocké si valide.
- Page de succès : blocs cachés pour resto gratuit, affichés pour Pro selon
  champs renseignés.
- `submit_feedback` : crée le `CustomerFeedback`, push déclenchée, anti double-envoi.
- Gating dashboard : onglet inaccessible hors Pro.

## Feuille de route (hors bloc 1)

- **Bloc 2 — Générateur d'affiche IA** : à partir des photos + infos d'un plat,
  générer une affiche appétissante (GPT OpenAI **via OpenRouter**) + un texte
  émotionnel prêt à copier-coller pour WhatsApp/réseaux.
- **Bloc 3 — Réputation** : afficher les avis Google reçus dans OpenFood.
  Route A (Places API, 5 avis max, pas de stockage durable — widget vitrine) en
  premier ; Route B (Business Profile API, tous les avis + réponses, OAuth par
  resto, offre Max) plus tard.
- **Bloc futur — Carte de fidélité** : s'appuie sur l'identité par téléphone
  posée ici.
