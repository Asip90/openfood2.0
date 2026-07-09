# Mise en avant — Menu du jour / Plat vedette / Promo — Design (Bloc 3)

**Date :** 2026-07-09
**Statut :** Validé — autonomie accordée

## Objectif

Permettre au restaurant de **mettre un plat en avant** (menu du jour, coup de
cœur, promo) pour booster les ventes. Le plat vedette apparaît dans une section
**« À la une »** en haut du menu client, avec un libellé personnalisable et le
badge de remise existant. Disponible **pour tous les plans**.

## Décisions

- **Disponible pour tous les plans** (merchandising de base, favorise l'adoption).
- On **réutilise l'existant** : le champ `MenuItem.discount_price` (badge `-X%`
  via le filtre `discount_pct` déjà présent), les badges menu, le pattern de
  toggle `change_menu_status`. Pas de nouveau modèle de « promo ».
- Deux champs ajoutés à `MenuItem` : `is_featured` (bool) + `featured_label`
  (texte court, ex. « Menu du jour », « Coup de cœur », « Promo » ; défaut vide
  → libellé générique « À la une »).
- Le resto active/désactive la mise en avant depuis la **gestion du menu**
  (toggle) et saisit le libellé dans le formulaire d'édition du plat.

## Architecture

### 1. Modèle (`base/models.py`, `MenuItem`)

| Champ | Type | Rôle |
|---|---|---|
| `is_featured` | `BooleanField(default=False)` | plat mis à la une |
| `featured_label` | `CharField(max_length=30, blank=True, default='')` | libellé (ex. « Menu du jour ») |

Migration incluse.

### 2. Toggle « à la une » (dashboard)

- Nouvelle vue `change_menu_featured(request, pk)` calquée sur
  `change_menu_status` (mêmes rôles `owner/coadmin/cuisinier`,
  `is_featured = not is_featured`, redirect `menus_list`).
- URL `menus/<int:pk>/toggle-featured/` nommée `menu_toggle_featured`.
- Bouton toggle dans `templates/admin_user/menus/list_menu.html` (à côté du
  toggle de disponibilité existant), état visuel actif/inactif.

### 3. Libellé (formulaire d'édition)

- Ajouter `featured_label` au traitement POST de `menu_update` (et à
  `menu_create` si le formulaire y est), champ texte optionnel dans
  `update_menus.html` (et `create_menus.html`).

### 4. Menu client (`customer/views.py` `client_menu` + `templates/customer/menu.html`)

- La vue passe `featured_items` =
  `MenuItem.objects.filter(restaurant=…, is_available=True, is_featured=True)`
  (limité à ~6) au contexte.
- **Section « À la une »** en haut du menu (avant les catégories), affichée
  seulement si `featured_items` non vide. Cartes réutilisant le style existant :
  image (`first_image_url`), libellé (`featured_label` ou « À la une »), badge
  `-X%` (`discount_pct`), prix. Clic → ouvre la même modale de détail.
- **Badge « Vedette ⭐ »** sur les cartes des plats vedette dans leur catégorie
  (dans le bloc de badges existant, à côté de « Populaire »/« -X% »), via un set
  `featured_ids` passé au contexte.

## Gating

- Aucun (tous les plans).

## Tests

- Modèle : champs présents, défauts.
- `change_menu_featured` : bascule `is_featured` et redirige.
- `menu_update` : persiste `featured_label`.
- `client_menu` : `featured_items`/`featured_ids` corrects (un plat vedette non
  disponible n'apparaît pas).

## Découpage

1. Modèle + migration.
2. Toggle featured (vue + url + bouton list_menu) + `featured_label` dans le
   formulaire d'édition.
3. Menu client : section « À la une » + badge vedette + contexte vue.

## Hors périmètre

- Programmation horaire du « menu du jour » (auto on/off par créneau) — plus
  tard si besoin.
- Réputation (bloc suivant), fidélité (bloc d'après).
