# Mobile Nav — QR Settings manquant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter le lien vers "Personnaliser QR" dans le hub Paramètres mobile, qui est le seul onglet présent sur la sidebar PC (pour owner/coadmin) mais absent du hub mobile.

**Architecture:** Deux fichiers template uniquement. Le `settings_hub.html` reçoit une nouvelle carte QR dans la section Configuration. Le `base.html` voit sa condition active-state du tab mobile Settings enrichie pour inclure l'URL QR.

**Tech Stack:** Django templates, Tailwind CSS, Remix Icons

---

## Analyse : PC vs Mobile

### PC sidebar (`sidebar.html`) affiche pour owner/coadmin :
| Onglet | URL name | Mobile ? |
|--------|----------|----------|
| Dashboard | `dashboard` | ✅ onglet direct |
| Commandes | `orders_list` | ✅ onglet direct |
| Menu | `menus_list` | ✅ onglet direct |
| Tables | `tables_list` | ✅ onglet direct |
| Personnaliser QR | `qr_settings` | ❌ **ABSENT** |
| Personnalisation | `customization` | ✅ dans settings_hub |
| Équipe | `staff_list` | ✅ dans settings_hub |
| Paramètres | `restaurant_settings` | ✅ dans settings_hub |
| Abonnement | `subscription_status` | ✅ dans settings_hub |

**Seul manquant : `qr_settings`** → à ajouter dans `settings_hub.html`.

Note : le backend `qr_settings_view` est décoré `@restaurant_required(allowed_roles=['owner', 'coadmin'])` donc seuls owner/coadmin y ont accès — cohérent avec le hub mobile qui n'est affiché qu'à owner/coadmin.

---

## Files

- Modify: `templates/admin_user/settings_hub.html:225-269` (section Configuration)
- Modify: `templates/admin_user/base.html:325-328` (active-state condition du tab Settings mobile)

---

### Task 1 : Ajouter la carte QR dans settings_hub

**Files:**
- Modify: `templates/admin_user/settings_hub.html`

- [ ] **Step 1 : Ouvrir le fichier et localiser la section Configuration**

Le bloc concerné se trouve entre les lignes 222 et 269. La section contient 3 cartes : Paramètres, Personnalisation, Équipe. On va insérer une 4e carte QR entre Personnalisation (ligne 241-252) et Équipe (ligne 254-267).

- [ ] **Step 2 : Ajouter la carte QR**

Remplacer le bloc de la carte Personnalisation + Équipe pour intercaler QR entre les deux :

```html
      <!-- Personnalisation -->
      <div class="hub-card">
        <a href="{% url 'customization' %}" class="hub-card-inner">
          <div class="hub-icon" style="background: linear-gradient(135deg, #fff7ed, #fed7aa);">
            <i class="ri-palette-line text-orange-500"></i>
          </div>
          <div class="hub-text">
            <p class="hub-title">Personnalisation</p>
            <p class="hub-desc">Couleurs, logo, police du menu client</p>
          </div>
          <i class="ri-arrow-right-s-line hub-arrow"></i>
        </a>
      </div>

      <!-- QR Code -->
      <div class="hub-card">
        <a href="{% url 'qr_settings' %}" class="hub-card-inner">
          <div class="hub-icon" style="background: linear-gradient(135deg, #f0fdf4, #bbf7d0);">
            <i class="ri-qr-code-line text-green-500"></i>
          </div>
          <div class="hub-text">
            <p class="hub-title">Personnaliser QR</p>
            <p class="hub-desc">Couleurs, logo et style des QR codes tables</p>
          </div>
          <i class="ri-arrow-right-s-line hub-arrow"></i>
        </a>
      </div>

      <!-- Équipe -->
      <div class="hub-card">
        <a href="{% url 'staff_list' %}" class="hub-card-inner">
          <div class="hub-icon" style="background: linear-gradient(135deg, #eef2ff, #c7d2fe);">
            <i class="ri-team-line text-indigo-500"></i>
          </div>
          <div class="hub-text">
            <p class="hub-title">Équipe</p>
            <p class="hub-desc">Inviter et gérer les membres du staff</p>
          </div>
          <i class="ri-arrow-right-s-line hub-arrow"></i>
        </a>
      </div>
```

La nouvelle carte est la 3e enfant du `.space-y-2.5`, donc ajouter son délai d'animation dans le CSS existant :

```css
  .hub-card:nth-child(3) { animation-delay: 0.16s; }
  .hub-card:nth-child(4) { animation-delay: 0.22s; }
  .hub-card:nth-child(5) { animation-delay: 0.28s; }
```

(Remplacer les lignes 18-19 existantes : `:nth-child(3)` et `:nth-child(4)` — ajouter `:nth-child(5)`.)

- [ ] **Step 3 : Vérifier visuellement**

Ouvrir `http://localhost:8000/reglages/` sur mobile (DevTools 375px). Vérifier que la carte QR apparaît entre Personnalisation et Équipe avec l'icône verte QR. Cliquer sur la carte — ça doit mener à la page QR settings.

- [ ] **Step 4 : Commit**

```bash
git add "templates/admin_user/settings_hub.html"
git commit -m "feat: add QR settings card to mobile settings hub"
```

---

### Task 2 : Mettre à jour l'active-state du tab Settings dans la mobile navbar

**Files:**
- Modify: `templates/admin_user/base.html`

- [ ] **Step 1 : Localiser la condition active-state**

Ligne ~325 dans `base.html`, la balise `<a href="{{ url_hub }}">` du tab Settings mobile contient :

```html
{% if current == url_hub or current == url_settings or current == url_custom or current == url_staff or current == url_sub %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}
```

Et ligne ~327 la même condition pour le `<span>` inner :

```html
{% if current == url_hub or current == url_settings or current == url_custom or current == url_staff or current == url_sub %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
```

- [ ] **Step 2 : Ajouter `url_qr` dans les deux conditions**

Remplacer les deux occurrences de la condition. Première occurrence (classe CSS sur `<a>`) :

**Avant :**
```html
{% if current == url_hub or current == url_settings or current == url_custom or current == url_staff or current == url_sub %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}
```

**Après :**
```html
{% if current == url_hub or current == url_settings or current == url_custom or current == url_staff or current == url_sub or current == url_qr %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}
```

Deuxième occurrence (badge highlight inner) :

**Avant :**
```html
{% if current == url_hub or current == url_settings or current == url_custom or current == url_staff or current == url_sub %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
```

**Après :**
```html
{% if current == url_hub or current == url_settings or current == url_custom or current == url_staff or current == url_sub or current == url_qr %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
```

- [ ] **Step 3 : Vérifier**

Naviguer vers `/tables/qr-settings/` en mode mobile (DevTools 375px). Vérifier que l'onglet Settings de la bottom navbar est surligné en orange (`text-primary`).

- [ ] **Step 4 : Commit**

```bash
git add "templates/admin_user/base.html"
git commit -m "fix: highlight mobile settings tab when on QR settings page"
```

---

## Self-Review

**Spec coverage :**
- ✅ QR ajouté dans settings_hub (Task 1)
- ✅ Active-state mobile navbar mis à jour (Task 2)
- ✅ Aucune modification backend nécessaire (le décorateur `@restaurant_required` garantit déjà que seul owner/coadmin accède à la vue)

**Placeholder scan :** aucun TBD ou TODO dans ce plan.

**Type consistency :** le nom d'URL `qr_settings` est cohérent dans les deux tâches et correspond à `base/urls.py:42`.
