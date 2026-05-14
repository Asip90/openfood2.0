# Mobile Settings Design Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Améliorer l'expérience mobile des pages Paramètres et Personnalisation en supprimant le contenu superflu qui s'empile sous le formulaire et en ajoutant une navigation retour vers le hub.

**Architecture:** Changements purement template — aucun Python ni JS. Deux fichiers modifiés. La colonne droite (preview / quick-actions / horaires) est masquée sur mobile avec `hidden lg:block` ; un lien breadcrumb mobile est injecté au-dessus du titre de chaque page.

**Tech Stack:** Django templates, Tailwind CSS, Remix Icons

---

## Analyse des problèmes mobiles

| Page | Problème | Fix |
|------|----------|-----|
| `settings.html` | Colonne droite (carte restaurant + quick-actions + aperçu horaires) s'empile sous le formulaire, 3× la hauteur utile | `hidden lg:block` sur la colonne |
| `settings.html` | Pas de lien retour sur mobile (`← Dashboard` est `hidden lg:flex`) | Breadcrumb mobile `← Paramètres` → `settings_hub` |
| `customization.html` | Phone mockup live preview s'empile sous le formulaire | `hidden lg:block` sur le wrapper preview |
| `customization.html` | Reset/Dashboard buttons sont `hidden lg:flex`, aucun retour mobile | Breadcrumb mobile `← Paramètres` → `settings_hub` |

---

## Files

- Modify: `templates/admin_user/settings.html:193-206` (header section — breadcrumb mobile)
- Modify: `templates/admin_user/settings.html:375-376` (colonne droite — hidden lg:block)
- Modify: `templates/admin_user/customization.html:245-265` (header section — breadcrumb mobile)
- Modify: `templates/admin_user/customization.html:482-483` (colonne preview — hidden lg:block)

---

### Task 1 : settings.html — Breadcrumb mobile + masquer colonne droite

**Files:**
- Modify: `templates/admin_user/settings.html`

- [ ] **Step 1 : Vérifier l'état actuel du header (ligne 192-205)**

Lire les lignes 190–210 du fichier pour confirmer la structure actuelle :

```bash
sed -n '190,210p' "templates/admin_user/settings.html"
```

Résultat attendu — un bloc `flex items-start justify-between` avec un `<h2>` et un `<a class="hidden lg:flex">` pointant vers `dashboard`.

- [ ] **Step 2 : Ajouter le breadcrumb mobile dans le header**

Localiser le bloc :
```html
  <div class="flex items-start justify-between">
    <div>
      <h2 class="font-display font-black text-slate-900 text-2xl leading-tight">
        {% trans "Restaurant settings" %}
      </h2>
      <p class="text-sm text-slate-500 mt-1">{% trans "Manage the basic information of your establishment" %}</p>
    </div>
    <a href="{% url 'dashboard' %}"
       class="hidden lg:flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-700 transition-colors">
      <i class="ri-arrow-left-line"></i>
      {% trans "Dashboard" %}
    </a>
  </div>
```

Le remplacer par :
```html
  <div class="flex items-start justify-between">
    <div>
      <!-- Mobile: retour au hub -->
      <a href="{% url 'settings_hub' %}"
         class="lg:hidden inline-flex items-center gap-1 text-xs text-slate-400 hover:text-primary transition-colors mb-2">
        <i class="ri-arrow-left-s-line text-sm"></i>
        {% trans "Settings" %}
      </a>
      <h2 class="font-display font-black text-slate-900 text-2xl leading-tight">
        {% trans "Restaurant settings" %}
      </h2>
      <p class="text-sm text-slate-500 mt-1">{% trans "Manage the basic information of your establishment" %}</p>
    </div>
    <a href="{% url 'dashboard' %}"
       class="hidden lg:flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-700 transition-colors">
      <i class="ri-arrow-left-line"></i>
      {% trans "Dashboard" %}
    </a>
  </div>
```

- [ ] **Step 3 : Masquer la colonne droite sur mobile**

Localiser la balise ouvrante de la colonne droite (après le `</div>` qui ferme la colonne formulaire, vers la ligne 375) :

```html
    <!-- ══ Colonne droite ══ -->
    <div class="space-y-4">
```

La remplacer par :
```html
    <!-- ══ Colonne droite — desktop uniquement ══ -->
    <div class="hidden lg:block space-y-4">
```

- [ ] **Step 4 : Vérifier visuellement**

Ouvrir `http://localhost:8000/restaurant/settings/` dans DevTools à 375 px.

Attendu :
- Lien `← Settings` visible en haut à gauche sous le titre
- Après le formulaire (tabs + champs), **aucune** carte restaurant / quick-actions / aperçu horaires
- Sur desktop (≥ 1024 px) : la colonne droite reste affichée normalement

- [ ] **Step 5 : Commit**

```bash
git add "templates/admin_user/settings.html"
git commit -m "feat(mobile): add back-nav breadcrumb and hide sidebar on settings page"
```

---

### Task 2 : customization.html — Breadcrumb mobile + masquer phone preview

**Files:**
- Modify: `templates/admin_user/customization.html`

- [ ] **Step 1 : Vérifier l'état actuel du header (ligne 245-265)**

```bash
sed -n '244,270p' "templates/admin_user/customization.html"
```

Résultat attendu — bloc `flex items-start justify-between` avec `<div class="hidden lg:flex ...">` pour les actions desktop.

- [ ] **Step 2 : Ajouter le breadcrumb mobile dans le header**

Localiser le bloc :
```html
  <div class="flex items-start justify-between">
    <div>
      <h2 class="font-display font-black text-slate-900 text-2xl leading-tight">
        Personnalisation
      </h2>
      <p class="text-sm text-slate-500 mt-1">Personnalisez l'apparence de votre menu client en temps réel</p>
    </div>
    <div class="hidden lg:flex items-center gap-4">
      <a href="{% url 'reset_customization' %}"
         onclick="return confirm('Réinitialiser toutes les personnalisations ? Cette action est irréversible.');"
         class="reset-link">
        <i class="ri-refresh-line text-sm"></i>
        Réinitialiser
      </a>
      <a href="{% url 'dashboard' %}"
         class="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-700 transition-colors">
        <i class="ri-arrow-left-line"></i>
        Dashboard
      </a>
    </div>
  </div>
```

Le remplacer par :
```html
  <div class="flex items-start justify-between">
    <div>
      <!-- Mobile: retour au hub -->
      <a href="{% url 'settings_hub' %}"
         class="lg:hidden inline-flex items-center gap-1 text-xs text-slate-400 hover:text-primary transition-colors mb-2">
        <i class="ri-arrow-left-s-line text-sm"></i>
        Paramètres
      </a>
      <h2 class="font-display font-black text-slate-900 text-2xl leading-tight">
        Personnalisation
      </h2>
      <p class="text-sm text-slate-500 mt-1">Personnalisez l'apparence de votre menu client en temps réel</p>
    </div>
    <div class="hidden lg:flex items-center gap-4">
      <a href="{% url 'reset_customization' %}"
         onclick="return confirm('Réinitialiser toutes les personnalisations ? Cette action est irréversible.');"
         class="reset-link">
        <i class="ri-refresh-line text-sm"></i>
        Réinitialiser
      </a>
      <a href="{% url 'dashboard' %}"
         class="flex items-center gap-1.5 text-sm text-slate-400 hover:text-slate-700 transition-colors">
        <i class="ri-arrow-left-line"></i>
        Dashboard
      </a>
    </div>
  </div>
```

- [ ] **Step 3 : Masquer la colonne phone preview sur mobile**

Localiser le commentaire et la div ouvrante de la colonne preview (vers ligne 482) :
```html
    <!-- ══ Prévisualisation phone ══ -->
    <div class="lg:sticky lg:top-24 self-start space-y-4">
```

Le remplacer par :
```html
    <!-- ══ Prévisualisation phone — desktop uniquement ══ -->
    <div class="hidden lg:block lg:sticky lg:top-24 self-start space-y-4">
```

- [ ] **Step 4 : Vérifier visuellement**

Ouvrir `http://localhost:8000/restaurant/customization/` dans DevTools à 375 px.

Attendu :
- Lien `← Paramètres` visible en haut à gauche
- Après le formulaire de personnalisation, **aucun** phone mockup ni preview
- Sur desktop (≥ 1024 px) : le phone preview reste affiché en colonne droite sticky

- [ ] **Step 5 : Commit**

```bash
git add "templates/admin_user/customization.html"
git commit -m "feat(mobile): add back-nav breadcrumb and hide phone preview on customization page"
```

---

## Self-Review

**Spec coverage :**
- ✅ `settings.html` : breadcrumb mobile ajouté (Task 1 Step 2)
- ✅ `settings.html` : colonne droite masquée sur mobile (Task 1 Step 3)
- ✅ `customization.html` : breadcrumb mobile ajouté (Task 2 Step 2)
- ✅ `customization.html` : phone preview masqué sur mobile (Task 2 Step 3)

**Placeholder scan :** aucun TBD ou TODO dans ce plan.

**Cohérence :**
- `{% url 'settings_hub' %}` est utilisé dans les deux tasks — cohérent avec `base/urls.py` (`name="settings_hub"`)
- `hidden lg:block` est le pattern Tailwind correct pour "masqué sur mobile, visible desktop"
- Le lien breadcrumb mobile utilise `lg:hidden` (visible mobile, masqué desktop) — correct
