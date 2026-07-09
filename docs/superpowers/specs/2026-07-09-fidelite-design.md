# Carte de fidélité — Design (Bloc 5)

**Date :** 2026-07-09
**Statut :** Validé — autonomie accordée

## Objectif

Fidéliser les clients : « carte à tampons » simple. Le client gagne **1 tampon
par commande payée** (identifié par son **téléphone**, posé au bloc 1). Après
`N` tampons, une **récompense** (ex. « 1 plat offert »). Le client voit sa
progression après commande ; le resto gère les récompenses depuis un onglet
dashboard. Réservé **Pro/Max**.

## Décisions

- **Modèle « tampons »** (buy N get reward) — le plus simple et le plus lisible.
- **Accrual = au paiement** (`mark_order_paid` / `mark_table_paid`, cashier),
  vrai signal de vente conclue. **Idempotent** via `Order.loyalty_awarded`.
- **Identité = `Order.customer_phone`** (E.164, bloc 1).
- **Config par restaurant** (pas super-admin) : activer, `stamps_required`
  (défaut 10), `reward_label` (ex. « 1 plat offert »). Dans Paramètres.
- **Récompense** : quand `stamps >= stamps_required`, « récompense disponible » ;
  le resto la donne puis **encaisse** (`redeem` : `stamps -= required`,
  `rewards_redeemed += 1`). Redemption manuelle (v1).
- **Gating** : Pro/Max + owner/coadmin (config + dashboard + affichage client).

## Architecture

### 1. Modèles (`base/models.py`)

**`LoyaltyProgram`** (OneToOne `Restaurant`) :
| Champ | Type |
|---|---|
| `restaurant` | OneToOneField, `related_name='loyalty'` |
| `is_enabled` | Bool (défaut False) |
| `stamps_required` | PositiveIntegerField (défaut 10) |
| `reward_label` | CharField(100, défaut « 1 récompense ») |

**`LoyaltyCard`** :
| Champ | Type |
|---|---|
| `restaurant` | FK, `related_name='loyalty_cards'` |
| `phone` | CharField(20) |
| `stamps` | PositiveIntegerField (défaut 0) |
| `rewards_redeemed` | PositiveIntegerField (défaut 0) |
| `updated_at` | auto_now |
- `unique_together = ('restaurant', 'phone')` ; `ordering = ['-stamps']`.

**`Order.loyalty_awarded`** : Bool (défaut False) — idempotence.

### 2. Service — `base/services/loyalty.py`

- `program_for(restaurant) -> LoyaltyProgram|None` (None si absent/désactivé).
- `award_for_order(order) -> LoyaltyCard|None` : si programme actif, `order`
  non déjà crédité (`loyalty_awarded`) et `customer_phone` présent →
  `get_or_create` la carte, `stamps += 1`, `loyalty_awarded=True`. Idempotent.
- `redeem(card) -> bool` : si `stamps >= program.stamps_required` →
  `stamps -= required`, `rewards_redeemed += 1`, save, True ; sinon False.
- `progress(restaurant, phone) -> dict|None` :
  `{"stamps", "required", "reward_available", "reward_label"}` ou None si
  programme inactif / phone vide.

### 3. Accrual (cashier)

- Dans `mark_order_paid` : après `order.save(...)`, appeler
  `loyalty.award_for_order(order)`.
- Dans `mark_table_paid` : idem pour chaque commande encaissée.
- (import local `from base.services import loyalty`.)

### 4. Config (Paramètres resto)

- Section **« Fidélité »** dans `settings.html` (gatée Pro comme
  « Communauté & avis »). `restaurant_settings` fait `get_or_create` du
  `LoyaltyProgram` et persiste `is_enabled`, `stamps_required`, `reward_label`.

### 5. Affichage client (page de succès)

- `order_confirmation` passe `loyalty = progress(restaurant, order.customer_phone)`
  (si Pro + programme actif). `confirmation.html` : carte « Fidélité :
  X/N tampons — plus que Y avant : <reward_label> » (ou « Récompense
  disponible 🎁 » si atteint). Affichée seulement si `loyalty`.

### 6. Dashboard — onglet « Fidélité »

- `loyalty_dashboard(request)` (owner/coadmin + `is_pro` → sinon Http404) :
  liste `restaurant.loyalty_cards` (téléphone, tampons, récompense dispo),
  triée par tampons. Bouton **« Récompense donnée »** par carte éligible →
  `loyalty_redeem(request, card_id)` (POST → `redeem`).
- URLs `fidelite/`, `fidelite/<int:card_id>/redeem/`.
- Template `templates/admin_user/loyalty/index.html` + entrée sidebar (🎟️,
  gatée Pro).

## Gating

- Config, affichage client, dashboard, redeem : Pro/Max + owner/coadmin.
- Accrual : se fait au paiement seulement si programme actif (indépendant du
  rôle qui encaisse — le cashier peut être serveur ; l'accrual n'est pas gaté
  par rôle, juste par `is_enabled` + Pro via `program_for`).

## Tests

- `award_for_order` : crédite 1 tampon, idempotent (2ᵉ appel ne recrédite pas),
  rien si programme off / phone vide.
- `redeem` : décrémente de `stamps_required` + incrémente `rewards_redeemed`
  seulement si seuil atteint.
- `progress` : valeurs correctes, `reward_available` au seuil, None si off.
- Accrual : `mark_order_paid` crédite la carte (Pro + programme actif).
- Vues : dashboard 404 si non-Pro ; redeem fonctionne.

## Découpage

1. Modèles + migration.
2. Service `loyalty` + tests.
3. Config settings + accrual (cashier) + affichage succès client + tests.
4. Dashboard fidélité (liste + redeem) + sidebar + gating + tests.

## Hors périmètre

- Points proportionnels au montant (on reste sur tampons/commande).
- Notifications automatiques « récompense débloquée ».
- Expiration des tampons.
