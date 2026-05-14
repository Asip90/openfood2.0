# Waiter Call — Design Spec
**Date:** 2026-05-14
**Status:** Approved

## Résumé

Deux fonctionnalités liées :
1. **État vide** sur la page menu client quand le restaurant n'a pas de plats actifs.
2. **Appel de serveur** — bouton flottant côté client, notifications temps-quasi-réel côté staff/admin via polling JS.

---

## Modèle de données

Nouveau modèle `WaiterCall` dans `base/models.py` :

```python
class WaiterCall(models.Model):
    STATUS_CHOICES = [('pending', 'En attente'), ('claimed', 'Pris en charge')]

    restaurant  = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='waiter_calls')
    table       = models.ForeignKey(Table, on_delete=models.CASCADE, related_name='waiter_calls')
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at  = models.DateTimeField(auto_now_add=True)
    claimed_by  = models.ForeignKey(StaffMember, on_delete=models.SET_NULL, null=True, blank=True)
```

**Règles métier :**
- Si la table a déjà un appel `pending` actif (< 30 min), on ne crée pas de doublon.
- Appels de plus de 30 min : considérés expirés, filtrés dans les endpoints.
- `claimed_by` est renseigné lors de la prise en charge.

---

## Endpoints

### `POST /api/waiter-call/<table_token>/`
- Accessible sans auth (page client publique).
- Crée un `WaiterCall` si aucun appel `pending` actif pour cette table.
- Retourne `{ "status": "ok" }` ou `{ "status": "already_pending" }`.

### `GET /api/waiter-calls/pending/`
- Auth requise. Retourne les appels pending/claimed < 30 min pour le restaurant de l'utilisateur connecté.
- Payload : `[{ id, table_number, status, claimed_by_name, created_at }]`
- Utilisé par le polling JS toutes les 6 secondes.

### `POST /api/waiter-calls/<id>/claim/`
- Auth requise. Passe le status à `claimed`, renseigne `claimed_by`.
- Retourne `{ "status": "ok" }`.

---

## Interface client

### État vide (aucun plat actif)
- Affiché à la place de la liste des catégories quand toutes les catégories/items sont inactifs.
- SVG cloche ou assiette vide centrée.
- Titre : *"Oups, les repas ont pris congé !"*
- Sous-titre : *"Appelez un serveur pour en savoir plus"*
- Le bouton flottant reste présent dans cet état.

### Bouton flottant "Appeler un serveur"
- `position: fixed; bottom: 1.5rem; right: 1.5rem`
- Couleur de fond = `primary_color` du restaurant.
- Toujours visible sur la page menu, quel que soit l'état du menu.
- **Au clic :**
  - `POST /api/waiter-call/<table_token>/` en AJAX
  - Bouton passe à "Serveur appelé ✓" (état visuel désactivé)
  - Anti-spam : bouton désactivé 30 secondes après un appel réussi
  - Après 4s : retour à l'état normal (mais le cooldown de 30s reste actif)

---

## Interface admin — notifications

### Polling JS
- Injecté dans `templates/admin_user/base.html` (présent sur toutes les pages admin).
- Intervalle : 6 secondes.
- Endpoint : `GET /api/waiter-calls/pending/`
- Stocke en mémoire JS les IDs déjà notifiés pour ne déclencher son/toast que sur les nouveaux appels.

### Son
- Généré via Web Audio API (pas de fichier audio externe).
- Simple "ding" (oscillateur sinusoïdal, 880Hz, 200ms).
- Déclenché uniquement sur nouveaux appels (pas au chargement initial de la page).
- Activation : le contexte audio est débloqué dès le premier clic sur la page (contrainte autoplay navigateur).

### Cloche dans le header
- Badge rouge avec le nombre d'appels `pending` non traités.
- Au clic : dropdown/panneau listant les appels actifs.

### Panneau des appels
Chaque entrée affiche :
- "Table 4 — il y a 2 min"
- Bouton **"Prendre en charge"** → `POST /api/waiter-calls/<id>/claim/`
- Après claim : "Pris en charge par [Prénom]" en gris (plus de bouton)

**Pas de feedback côté client** lors de la prise en charge (côté client = table du restaurant).

---

## Périmètre technique

- **Nouveau fichier :** `base/migrations/XXXX_add_waitercall.py`
- **Modifié :** `base/models.py` (WaiterCall)
- **Nouveaux endpoints :** dans `base/views.py` ou `base/api_views.py`
- **Modifié :** `main/urls.py` ou `base/urls.py` pour router les 3 endpoints
- **Modifié :** `templates/customer/menu.html` — état vide + bouton flottant
- **Modifié :** `templates/admin_user/base.html` — polling JS + son + badge cloche
- **Modifié :** `templates/admin_user/header.html` — panneau dropdown des appels

## Hors périmètre
- Feedback temps réel côté client après prise en charge
- WebSockets / SSE
- Historique des appels
- Notifications push mobile
