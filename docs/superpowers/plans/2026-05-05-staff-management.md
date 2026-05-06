# Staff Management (Coadmin · Cuisinier · Serveur) — Plan d'implémentation

> **Pour les workers agentiques :** SOUS-SKILL REQUIS : Utilise `superpowers:subagent-driven-development` (recommandé) ou `superpowers:executing-plans` pour implémenter ce plan tâche par tâche. Les étapes utilisent la syntaxe case à cocher (`- [ ]`) pour le suivi.

**Goal:** Permettre à l'admin d'un restaurant d'ajouter des membres du staff (coadmin, cuisinier, serveur), chacun disposant d'un accès dédié avec des permissions et des vues adaptées à son rôle, avec des notifications temps réel par polling.

**Architecture:** On ajoute un modèle `StaffMember` lié à `Restaurant`, avec un système d'authentification par session indépendant de Django auth (session key `staff_id`). Un décorateur `admin_or_coadmin_required` accepte les deux types d'authentifiés (owner Django user OU coadmin staff session). Les cuisiniers et serveurs ont leur propre portail de commandes avec polling.

**Tech Stack:** Django 4.x, SQLite, Tailwind CSS CDN, Remix Icons, polling JS natif (pas de WebSockets), `django.contrib.auth.hashers` pour le hachage des mots de passe staff.

---

## Cartographie des fichiers

| Action | Fichier | Responsabilité |
|--------|---------|----------------|
| Créer | `base/models.py` | +`StaffMember` model, +`Order.preparing_by_name` |
| Créer | `base/migrations/XXXX_staffmember.py` | Migration auto-générée |
| Créer | `base/staff_forms.py` | `StaffLoginForm`, `StaffMemberForm` |
| Créer | `base/decorators.py` | `staff_required`, `admin_or_coadmin_required`, helpers |
| Créer | `base/staff_views.py` | Portail staff : login, logout, orders, status, polling |
| Créer | `base/staff_admin_views.py` | Admin : CRUD staff members |
| Créer | `base/staff_urls.py` | URLs `/staff/*` |
| Modifier | `base/urls.py` | +URLs gestion staff (`/equipe/*`) |
| Modifier | `main/urls.py` | +include `staff_urls` |
| Modifier | `base/tests.py` | Tests models + views |
| Créer | `templates/staff/base.html` | Layout base portail staff |
| Créer | `templates/staff/connexion.html` | Page login staff |
| Créer | `templates/staff/orders/list.html` | Vue commandes cuisinier/serveur |
| Créer | `templates/admin_user/staff/list.html` | Liste staff (admin) |
| Créer | `templates/admin_user/staff/create.html` | Ajout staff (admin) |
| Créer | `templates/admin_user/staff/update.html` | Édition staff (admin) |
| Modifier | `templates/auth/connexion.html` | +bouton discret lien staff |
| Modifier | `templates/admin_user/base.html` | +lien "Équipe" sidebar + bottom nav |
| Modifier | `templates/admin_user/sidebar.html` | +entrée Équipe |

---

## Tâche 1 : Modèle `StaffMember` + champ `Order.preparing_by_name`

**Fichiers :**
- Modifier : `base/models.py`
- Modifier : `base/tests.py`

- [ ] **Étape 1 : Écrire le test du modèle**

```python
# base/tests.py
from django.test import TestCase
from django.contrib.auth.hashers import check_password
from accounts.models import User
from base.models import Restaurant, Order, StaffMember, SubscriptionPlan


def make_owner():
    return User.objects.create_user(email='owner@test.com', password='pass', first_name='Admin', last_name='Owner')


def make_restaurant(owner):
    return Restaurant.objects.create(
        owner=owner, name='TestResto', slug='testResto', subdomain='testresto'
    )


class StaffMemberModelTest(TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.restaurant = make_restaurant(self.owner)

    def test_create_staff_member(self):
        staff = StaffMember(
            restaurant=self.restaurant,
            first_name='Jean',
            last_name='Dupont',
            username='jean',
            role='cuisinier',
        )
        staff.set_password('secret123')
        staff.save()
        self.assertEqual(StaffMember.objects.count(), 1)
        self.assertEqual(staff.get_full_name(), 'Jean Dupont')

    def test_password_hashing(self):
        staff = StaffMember(
            restaurant=self.restaurant, first_name='A', last_name='B',
            username='ab', role='serveur',
        )
        staff.set_password('mypassword')
        staff.save()
        fresh = StaffMember.objects.get(pk=staff.pk)
        self.assertTrue(fresh.check_password('mypassword'))
        self.assertFalse(fresh.check_password('wrongpassword'))

    def test_username_unique_per_restaurant(self):
        from django.db import IntegrityError
        StaffMember.objects.create(
            restaurant=self.restaurant, first_name='A', last_name='B',
            username='chef', role='cuisinier', password='x'
        )
        with self.assertRaises(Exception):
            StaffMember.objects.create(
                restaurant=self.restaurant, first_name='C', last_name='D',
                username='chef', role='serveur', password='y'
            )

    def test_order_has_preparing_by_name(self):
        order = Order(
            restaurant=self.restaurant,
            order_type='dine_in',
            status='preparing',
            preparing_by_name='Jean Dupont',
        )
        order.save()
        self.assertEqual(Order.objects.get(pk=order.pk).preparing_by_name, 'Jean Dupont')
```

- [ ] **Étape 2 : Lancer le test pour confirmer qu'il échoue**

```bash
cd "/home/jey/Documents/projet /OpendFood"
source env/bin/activate
python manage.py test base.tests.StaffMemberModelTest -v 2
```

Résultat attendu : `ImportError: cannot import name 'StaffMember'`

- [ ] **Étape 3 : Ajouter le modèle `StaffMember` et le champ `preparing_by_name` dans `base/models.py`**

Ajouter après la classe `Order` (après la ligne `def __str__` de Order, avant `class OrderItem`) :

```python
# Dans Order, ajouter le champ (dans la classe Order existante, après `notes`) :
preparing_by_name = models.CharField(max_length=150, blank=True, default='')
```

Puis ajouter la classe `StaffMember` après `class OrderItem` :

```python
class StaffMember(models.Model):
    ROLE_CHOICES = [
        ('coadmin', 'Co-administrateur'),
        ('cuisinier', 'Cuisinier'),
        ('serveur', 'Serveur'),
    ]

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='staff'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    username = models.CharField(max_length=50)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('restaurant', 'username')

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password as _check
        return _check(raw_password, self.password)

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()}) — {self.restaurant.name}"
```

- [ ] **Étape 4 : Créer et appliquer la migration**

```bash
python manage.py makemigrations base --name staffmember_and_preparing_by
python manage.py migrate
```

Résultat attendu : `Applying base.XXXX_staffmember_and_preparing_by... OK`

- [ ] **Étape 5 : Lancer le test pour confirmer qu'il passe**

```bash
python manage.py test base.tests.StaffMemberModelTest -v 2
```

Résultat attendu : `Ran 4 tests in X.XXXs — OK`

- [ ] **Étape 6 : Commit**

```bash
git add base/models.py base/migrations/ base/tests.py
git commit -m "feat: add StaffMember model and Order.preparing_by_name"
```

---

## Tâche 2 : Formulaires staff

**Fichiers :**
- Créer : `base/staff_forms.py`
- Modifier : `base/tests.py`

- [ ] **Étape 1 : Écrire les tests de formulaires**

```python
# Ajouter dans base/tests.py :
from base.staff_forms import StaffLoginForm, StaffMemberForm


class StaffFormsTest(TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.restaurant = make_restaurant(self.owner)

    def test_login_form_valid(self):
        form = StaffLoginForm(data={'username': 'jean', 'password': 'pass'})
        self.assertTrue(form.is_valid())

    def test_login_form_missing_fields(self):
        form = StaffLoginForm(data={'username': ''})
        self.assertFalse(form.is_valid())

    def test_staff_member_form_valid(self):
        form = StaffMemberForm(data={
            'first_name': 'Marie', 'last_name': 'Martin',
            'username': 'marie', 'role': 'serveur',
            'password': 'secret', 'confirm_password': 'secret',
            'is_active': True,
        })
        self.assertTrue(form.is_valid())

    def test_staff_member_form_password_mismatch(self):
        form = StaffMemberForm(data={
            'first_name': 'A', 'last_name': 'B', 'username': 'ab',
            'role': 'cuisinier', 'password': 'abc', 'confirm_password': 'xyz',
            'is_active': True,
        })
        self.assertFalse(form.is_valid())
        self.assertIn('confirm_password', form.errors)
```

- [ ] **Étape 2 : Lancer les tests pour confirmer qu'ils échouent**

```bash
python manage.py test base.tests.StaffFormsTest -v 2
```

Résultat attendu : `ImportError: cannot import name 'StaffLoginForm'`

- [ ] **Étape 3 : Créer `base/staff_forms.py`**

```python
# base/staff_forms.py
from django import forms


class StaffLoginForm(forms.Form):
    username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'placeholder': "Nom d'utilisateur", 'autocomplete': 'username'}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Mot de passe', 'autocomplete': 'current-password'}),
    )


class StaffMemberForm(forms.Form):
    ROLE_CHOICES = [
        ('coadmin', 'Co-administrateur'),
        ('cuisinier', 'Cuisinier'),
        ('serveur', 'Serveur'),
    ]

    first_name = forms.CharField(max_length=100, label='Prénom')
    last_name = forms.CharField(max_length=100, label='Nom')
    username = forms.CharField(
        max_length=50,
        label="Identifiant",
        help_text="Unique au sein du restaurant",
    )
    role = forms.ChoiceField(choices=ROLE_CHOICES, label='Rôle')
    password = forms.CharField(
        widget=forms.PasswordInput(),
        label='Mot de passe',
        required=False,
        help_text="Laisser vide pour ne pas modifier (édition uniquement)",
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(),
        label='Confirmer le mot de passe',
        required=False,
    )
    is_active = forms.BooleanField(required=False, initial=True, label='Compte actif')

    def clean(self):
        cleaned = super().clean()
        p1 = cleaned.get('password')
        p2 = cleaned.get('confirm_password')
        if p1 or p2:
            if p1 != p2:
                self.add_error('confirm_password', 'Les mots de passe ne correspondent pas.')
        return cleaned
```

- [ ] **Étape 4 : Lancer les tests pour confirmer qu'ils passent**

```bash
python manage.py test base.tests.StaffFormsTest -v 2
```

Résultat attendu : `Ran 4 tests in X.XXXs — OK`

- [ ] **Étape 5 : Commit**

```bash
git add base/staff_forms.py base/tests.py
git commit -m "feat: add StaffLoginForm and StaffMemberForm"
```

---

## Tâche 3 : Décorateurs et helpers de session

**Fichiers :**
- Créer : `base/decorators.py`
- Modifier : `base/tests.py`

- [ ] **Étape 1 : Écrire les tests**

```python
# Ajouter dans base/tests.py :
from django.test import RequestFactory
from base.decorators import get_staff_from_session, staff_required, admin_or_coadmin_required
from base.models import StaffMember


class DecoratorsTest(TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.restaurant = make_restaurant(self.owner)
        self.staff = StaffMember.objects.create(
            restaurant=self.restaurant,
            first_name='Chef', last_name='Test',
            username='chef', role='cuisinier', is_active=True,
        )
        self.staff.set_password('pass')
        self.staff.save()

    def test_get_staff_from_session_found(self):
        request = RequestFactory().get('/')
        request.session = {'staff_id': self.staff.id}
        result = get_staff_from_session(request)
        self.assertEqual(result.id, self.staff.id)

    def test_get_staff_from_session_not_found(self):
        request = RequestFactory().get('/')
        request.session = {}
        result = get_staff_from_session(request)
        self.assertIsNone(result)

    def test_staff_required_redirects_without_session(self):
        client = self.client
        response = client.get('/staff/commandes/')
        self.assertEqual(response.status_code, 302)
        self.assertIn('/staff/connexion/', response['Location'])
```

- [ ] **Étape 2 : Lancer les tests pour confirmer qu'ils échouent**

```bash
python manage.py test base.tests.DecoratorsTest -v 2
```

Résultat attendu : `ImportError: cannot import name 'get_staff_from_session'`

- [ ] **Étape 3 : Créer `base/decorators.py`**

```python
# base/decorators.py
from functools import wraps
from django.shortcuts import redirect
from base.models import StaffMember, Restaurant


def get_staff_from_session(request):
    """Retourne le StaffMember actif depuis la session, ou None."""
    staff_id = request.session.get('staff_id')
    if not staff_id:
        return None
    try:
        return StaffMember.objects.select_related('restaurant').get(
            id=staff_id, is_active=True
        )
    except StaffMember.DoesNotExist:
        return None


def staff_required(roles=None):
    """
    Décorateur pour les vues accessibles uniquement aux StaffMember actifs.
    roles: liste de rôles autorisés, ex: ['cuisinier', 'serveur'] ; None = tous.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            staff = get_staff_from_session(request)
            if staff is None:
                return redirect('staff_login')
            if roles and staff.role not in roles:
                return redirect('staff_orders')
            request.staff_member = staff
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_or_coadmin_required(view_func):
    """
    Décorateur pour les vues de gestion du staff :
    accepte le propriétaire Django authentifié OU un coadmin via session staff.
    Attache request.managing_restaurant et optionnellement request.staff_member.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Cas 1 : propriétaire Django
        if request.user.is_authenticated:
            restaurant = Restaurant.objects.filter(owner=request.user).first()
            if restaurant:
                request.managing_restaurant = restaurant
                request.staff_member = None
                return view_func(request, *args, **kwargs)
        # Cas 2 : coadmin via session staff
        staff = get_staff_from_session(request)
        if staff and staff.role == 'coadmin':
            request.managing_restaurant = staff.restaurant
            request.staff_member = staff
            return view_func(request, *args, **kwargs)
        return redirect('connexion')
    return wrapper
```

- [ ] **Étape 4 : Créer `base/staff_urls.py` (stub pour que le test de redirection fonctionne)**

```python
# base/staff_urls.py
from django.urls import path
from django.http import HttpResponse

# Stubs temporaires — seront remplacés dans la Tâche 4
def _stub(request, **kw):
    return HttpResponse('stub')

urlpatterns = [
    path('connexion/', _stub, name='staff_login'),
    path('deconnexion/', _stub, name='staff_logout'),
    path('commandes/', _stub, name='staff_orders'),
    path('commandes/<int:pk>/statut/', _stub, name='staff_change_status'),
    path('commandes/check/', _stub, name='staff_check_updates'),
]
```

- [ ] **Étape 5 : Inclure `staff_urls.py` dans `main/urls.py`**

```python
# main/urls.py — modifier urlpatterns pour ajouter :
from django.urls import path, include
# ...
urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('llms.txt', TemplateView.as_view(template_name='llms.txt', content_type='text/plain')),
    path('', include('accounts.urls')),
    path('', include('base.urls')),
    path('', include('customer.urls')),
    path('staff/', include('base.staff_urls')),   # <-- ajouter cette ligne
]
```

- [ ] **Étape 6 : Lancer les tests**

```bash
python manage.py test base.tests.DecoratorsTest -v 2
```

Résultat attendu : `Ran 3 tests in X.XXXs — OK`

- [ ] **Étape 7 : Commit**

```bash
git add base/decorators.py base/staff_urls.py main/urls.py base/tests.py
git commit -m "feat: add staff session decorators and stub staff URLs"
```

---

## Tâche 4 : Vues d'authentification staff (login / logout)

**Fichiers :**
- Créer : `base/staff_views.py`
- Modifier : `base/staff_urls.py`
- Modifier : `base/tests.py`

- [ ] **Étape 1 : Écrire les tests de login/logout**

```python
# Ajouter dans base/tests.py :
class StaffAuthViewsTest(TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.restaurant = make_restaurant(self.owner)
        self.staff = StaffMember(
            restaurant=self.restaurant,
            first_name='Chef', last_name='Test',
            username='chef', role='cuisinier', is_active=True,
        )
        self.staff.set_password('secret')
        self.staff.save()

    def test_staff_login_page_loads(self):
        response = self.client.get('/staff/connexion/')
        self.assertEqual(response.status_code, 200)

    def test_staff_login_success(self):
        response = self.client.post('/staff/connexion/', {
            'username': 'chef', 'password': 'secret',
        }, follow=True)
        self.assertRedirects(response, '/staff/commandes/')
        self.assertIn('staff_id', self.client.session)

    def test_staff_login_wrong_password(self):
        response = self.client.post('/staff/connexion/', {
            'username': 'chef', 'password': 'wrong',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('staff_id', self.client.session)

    def test_staff_login_inactive_account(self):
        self.staff.is_active = False
        self.staff.save()
        response = self.client.post('/staff/connexion/', {
            'username': 'chef', 'password': 'secret',
        })
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('staff_id', self.client.session)

    def test_staff_logout_clears_session(self):
        session = self.client.session
        session['staff_id'] = self.staff.id
        session.save()
        self.client.get('/staff/deconnexion/')
        self.assertNotIn('staff_id', self.client.session)
```

- [ ] **Étape 2 : Lancer les tests pour confirmer qu'ils échouent**

```bash
python manage.py test base.tests.StaffAuthViewsTest -v 2
```

Résultat attendu : échoue (stubs renvoient 200 sans logique)

- [ ] **Étape 3 : Créer `base/staff_views.py` avec login/logout**

```python
# base/staff_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from base.models import StaffMember, Order, Restaurant
from base.staff_forms import StaffLoginForm
from base.decorators import staff_required, get_staff_from_session


def staff_login(request):
    """Page de connexion du portail staff."""
    # Si déjà connecté en staff, rediriger
    if get_staff_from_session(request):
        return redirect('staff_orders')

    form = StaffLoginForm()
    error = None

    if request.method == 'POST':
        form = StaffLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']

            # Chercher le staff dans tous les restaurants actifs
            # On ne connaît pas le restaurant à ce stade — on cherche par username global
            # (unicité garantie par restaurant, donc on prend le premier qui correspond)
            try:
                staff = StaffMember.objects.get(username=username, is_active=True)
                if staff.check_password(password):
                    request.session['staff_id'] = staff.id
                    request.session['staff_role'] = staff.role
                    return redirect('staff_orders')
                else:
                    error = "Identifiant ou mot de passe incorrect."
            except StaffMember.DoesNotExist:
                error = "Identifiant ou mot de passe incorrect."
            except StaffMember.MultipleObjectsReturned:
                error = "Identifiant ambigu. Contactez votre administrateur."

    return render(request, 'staff/connexion.html', {'form': form, 'error': error})


def staff_logout(request):
    """Déconnexion du portail staff."""
    request.session.pop('staff_id', None)
    request.session.pop('staff_role', None)
    return redirect('staff_login')
```

- [ ] **Étape 4 : Mettre à jour `base/staff_urls.py` pour remplacer les stubs login/logout**

```python
# base/staff_urls.py
from django.urls import path
from django.http import HttpResponse
from base import staff_views

def _stub(request, **kw):
    return HttpResponse('stub')

urlpatterns = [
    path('connexion/',     staff_views.staff_login,   name='staff_login'),
    path('deconnexion/',   staff_views.staff_logout,  name='staff_logout'),
    path('commandes/',     _stub,                     name='staff_orders'),
    path('commandes/<int:pk>/statut/', _stub,         name='staff_change_status'),
    path('commandes/check/', _stub,                   name='staff_check_updates'),
]
```

- [ ] **Étape 5 : Créer le template minimaliste `templates/staff/connexion.html`** (sera enrichi en Tâche 7)

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/templates/staff"
```

```html
{# templates/staff/connexion.html — structure fonctionnelle, design en Tâche 7 #}
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Connexion Staff – OpenFood</title></head>
<body>
  <h1>Portail Staff</h1>
  {% if error %}<p style="color:red">{{ error }}</p>{% endif %}
  <form method="post">
    {% csrf_token %}
    {{ form.username }}
    {{ form.password }}
    <button type="submit">Se connecter</button>
  </form>
</body>
</html>
```

- [ ] **Étape 6 : Lancer les tests**

```bash
python manage.py test base.tests.StaffAuthViewsTest -v 2
```

Résultat attendu : `Ran 5 tests in X.XXXs — OK`

- [ ] **Étape 7 : Commit**

```bash
git add base/staff_views.py base/staff_urls.py templates/staff/connexion.html base/tests.py
git commit -m "feat: staff login/logout views and session auth"
```

---

## Tâche 5 : Vues commandes du portail staff (cuisinier + serveur + polling)

**Fichiers :**
- Modifier : `base/staff_views.py`
- Modifier : `base/staff_urls.py`
- Modifier : `base/tests.py`

**Règles métier :**
- Cuisinier : voit toutes les commandes `pending`/`preparing`/`ready` ; peut passer à `preparing` (stocke son nom dans `preparing_by_name`) ou `ready`.
- Serveur : voit toutes les commandes `ready`/`delivered` en priorité ; peut passer à `delivered`.
- Coadmin : peut changer le statut comme un cuisinier ET un serveur (tous les statuts).

- [ ] **Étape 1 : Écrire les tests**

```python
# Ajouter dans base/tests.py :
class StaffOrdersViewsTest(TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.restaurant = make_restaurant(self.owner)
        self.cook = StaffMember(
            restaurant=self.restaurant, first_name='Jean', last_name='Chef',
            username='jean', role='cuisinier', is_active=True,
        )
        self.cook.set_password('pass')
        self.cook.save()

        self.server = StaffMember(
            restaurant=self.restaurant, first_name='Marie', last_name='Serv',
            username='marie', role='serveur', is_active=True,
        )
        self.server.set_password('pass')
        self.server.save()

        self.order = Order.objects.create(
            restaurant=self.restaurant, status='pending', order_type='dine_in'
        )

    def _login_staff(self, staff):
        session = self.client.session
        session['staff_id'] = staff.id
        session['staff_role'] = staff.role
        session.save()

    def test_orders_list_requires_staff_session(self):
        response = self.client.get('/staff/commandes/')
        self.assertEqual(response.status_code, 302)

    def test_orders_list_accessible_to_cook(self):
        self._login_staff(self.cook)
        response = self.client.get('/staff/commandes/')
        self.assertEqual(response.status_code, 200)

    def test_cook_can_set_preparing(self):
        self._login_staff(self.cook)
        response = self.client.post(
            f'/staff/commandes/{self.order.pk}/statut/',
            {'status': 'preparing'},
        )
        self.assertEqual(response.status_code, 302)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'preparing')
        self.assertEqual(self.order.preparing_by_name, 'Jean Chef')

    def test_server_cannot_set_preparing(self):
        self._login_staff(self.server)
        response = self.client.post(
            f'/staff/commandes/{self.order.pk}/statut/',
            {'status': 'preparing'},
        )
        # doit être refusé (redirection ou 403)
        self.order.refresh_from_db()
        self.assertNotEqual(self.order.status, 'preparing')

    def test_server_can_set_delivered(self):
        self.order.status = 'ready'
        self.order.save()
        self._login_staff(self.server)
        response = self.client.post(
            f'/staff/commandes/{self.order.pk}/statut/',
            {'status': 'delivered'},
        )
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'delivered')

    def test_check_updates_returns_json(self):
        self._login_staff(self.cook)
        response = self.client.get('/staff/commandes/check/?last_id=0')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('orders', data)
        self.assertIn('ready_count', data)
```

- [ ] **Étape 2 : Lancer les tests pour confirmer qu'ils échouent**

```bash
python manage.py test base.tests.StaffOrdersViewsTest -v 2
```

Résultat attendu : plusieurs erreurs (stubs)

- [ ] **Étape 3 : Ajouter les vues dans `base/staff_views.py`**

```python
# Ajouter à la suite dans base/staff_views.py :

COOK_ALLOWED_STATUSES = {'preparing', 'ready', 'cancelled'}
SERVER_ALLOWED_STATUSES = {'delivered'}
COADMIN_ALLOWED_STATUSES = {'pending', 'confirmed', 'preparing', 'ready', 'delivered', 'cancelled'}


@staff_required(roles=['cuisinier', 'serveur', 'coadmin'])
def staff_orders(request):
    """Vue principale des commandes pour le portail staff."""
    staff = request.staff_member
    restaurant = staff.restaurant

    if staff.role == 'serveur':
        # Le serveur voit en priorité les commandes prêtes, puis toutes
        active_orders = Order.objects.filter(
            restaurant=restaurant,
            status__in=['pending', 'confirmed', 'preparing', 'ready'],
        ).order_by('-created_at')
    else:
        # Cuisinier et coadmin voient tout sauf livré/annulé
        active_orders = Order.objects.filter(
            restaurant=restaurant,
            status__in=['pending', 'confirmed', 'preparing', 'ready'],
        ).order_by('created_at')

    latest = Order.objects.filter(restaurant=restaurant).order_by('-id').first()
    latest_order_id = latest.id if latest else 0

    return render(request, 'staff/orders/list.html', {
        'orders': active_orders,
        'staff': staff,
        'latest_order_id': latest_order_id,
        'ready_count': active_orders.filter(status='ready').count(),
    })


@staff_required(roles=['cuisinier', 'serveur', 'coadmin'])
def staff_change_status(request, pk):
    """Change le statut d'une commande selon les permissions du rôle."""
    staff = request.staff_member
    restaurant = staff.restaurant
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)

    if request.method != 'POST':
        return redirect('staff_orders')

    new_status = request.POST.get('status', '').strip()

    if staff.role == 'cuisinier':
        allowed = COOK_ALLOWED_STATUSES
    elif staff.role == 'serveur':
        allowed = SERVER_ALLOWED_STATUSES
    else:  # coadmin
        allowed = COADMIN_ALLOWED_STATUSES

    if new_status not in allowed:
        return redirect('staff_orders')

    order.status = new_status
    if new_status == 'preparing':
        order.preparing_by_name = staff.get_full_name()
    order.save(update_fields=['status', 'preparing_by_name', 'updated_at'])
    return redirect('staff_orders')


@staff_required(roles=['cuisinier', 'serveur', 'coadmin'])
def staff_check_updates(request):
    """
    Endpoint de polling JSON.
    Paramètre GET : last_id (dernier order.id connu du client)
    Retourne : nouvelles commandes + statuts actuels + ready_count
    """
    staff = request.staff_member
    restaurant = staff.restaurant
    last_id = int(request.GET.get('last_id', 0))

    new_orders = Order.objects.filter(
        restaurant=restaurant, id__gt=last_id
    ).order_by('id')

    active_orders = Order.objects.filter(
        restaurant=restaurant,
        status__in=['pending', 'confirmed', 'preparing', 'ready'],
    ).values('id', 'order_number', 'status', 'preparing_by_name', 'updated_at')

    return JsonResponse({
        'new_count': new_orders.count(),
        'orders': list(active_orders),
        'ready_count': Order.objects.filter(restaurant=restaurant, status='ready').count(),
        'latest_id': new_orders.last().id if new_orders.exists() else last_id,
    })
```

- [ ] **Étape 4 : Mettre à jour `base/staff_urls.py`**

```python
# base/staff_urls.py — version complète
from django.urls import path
from base import staff_views

urlpatterns = [
    path('connexion/',                   staff_views.staff_login,         name='staff_login'),
    path('deconnexion/',                 staff_views.staff_logout,        name='staff_logout'),
    path('commandes/',                   staff_views.staff_orders,        name='staff_orders'),
    path('commandes/<int:pk>/statut/',   staff_views.staff_change_status, name='staff_change_status'),
    path('commandes/check/',             staff_views.staff_check_updates, name='staff_check_updates'),
]
```

- [ ] **Étape 5 : Créer le template stub `templates/staff/orders/list.html`**

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/templates/staff/orders"
```

```html
{# templates/staff/orders/list.html — structure fonctionnelle, design en Tâche 7 #}
<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><title>Commandes – {{ staff.get_full_name }}</title></head>
<body>
  <p>Connecté : {{ staff.get_full_name }} ({{ staff.get_role_display }})</p>
  <a href="{% url 'staff_logout' %}">Déconnexion</a>
  <hr>
  {% for order in orders %}
  <div>
    <b>#{{ order.order_number }}</b> — {{ order.get_status_display }}
    {% if order.preparing_by_name %} par {{ order.preparing_by_name }}{% endif %}
    <form method="post" action="{% url 'staff_change_status' order.pk %}" style="display:inline">
      {% csrf_token %}
      {% if staff.role == 'cuisinier' or staff.role == 'coadmin' %}
        {% if order.status == 'pending' or order.status == 'confirmed' %}
          <button name="status" value="preparing">En préparation</button>
        {% endif %}
        {% if order.status == 'preparing' %}
          <button name="status" value="ready">Prête ✓</button>
        {% endif %}
      {% endif %}
      {% if staff.role == 'serveur' or staff.role == 'coadmin' %}
        {% if order.status == 'ready' %}
          <button name="status" value="delivered">Servie ✓</button>
        {% endif %}
      {% endif %}
    </form>
  </div>
  {% empty %}
  <p>Aucune commande active.</p>
  {% endfor %}
</body>
</html>
```

- [ ] **Étape 6 : Lancer les tests**

```bash
python manage.py test base.tests.StaffOrdersViewsTest -v 2
```

Résultat attendu : `Ran 7 tests in X.XXXs — OK`

- [ ] **Étape 7 : Commit**

```bash
git add base/staff_views.py base/staff_urls.py templates/staff/orders/list.html base/tests.py
git commit -m "feat: staff orders view, status change, polling endpoint"
```

---

## Tâche 6 : Vues de gestion du staff (côté admin)

**Fichiers :**
- Créer : `base/staff_admin_views.py`
- Modifier : `base/urls.py`
- Modifier : `base/tests.py`

**Règles :**
- Admin (propriétaire Django) → peut ajouter/éditer/supprimer TOUS les rôles (coadmin inclus)
- Coadmin (session staff) → peut ajouter/éditer/supprimer cuisinier et serveur, **pas** les coadmins

- [ ] **Étape 1 : Écrire les tests**

```python
# Ajouter dans base/tests.py :
class StaffAdminViewsTest(TestCase):

    def setUp(self):
        self.owner = make_owner()
        self.restaurant = make_restaurant(self.owner)
        self.coadmin = StaffMember(
            restaurant=self.restaurant, first_name='Co', last_name='Admin',
            username='coadmin', role='coadmin', is_active=True,
        )
        self.coadmin.set_password('pass')
        self.coadmin.save()
        self.cook = StaffMember(
            restaurant=self.restaurant, first_name='Chef', last_name='Two',
            username='chef2', role='cuisinier', is_active=True,
        )
        self.cook.set_password('pass')
        self.cook.save()

    def _login_owner(self):
        self.client.login(username='owner@test.com', password='pass')

    def _login_coadmin(self):
        session = self.client.session
        session['staff_id'] = self.coadmin.id
        session['staff_role'] = 'coadmin'
        session.save()

    def test_staff_list_requires_auth(self):
        response = self.client.get('/equipe/')
        self.assertNotEqual(response.status_code, 200)

    def test_staff_list_accessible_by_owner(self):
        self._login_owner()
        response = self.client.get('/equipe/')
        self.assertEqual(response.status_code, 200)

    def test_staff_list_accessible_by_coadmin(self):
        self._login_coadmin()
        response = self.client.get('/equipe/')
        self.assertEqual(response.status_code, 200)

    def test_owner_can_create_coadmin(self):
        self._login_owner()
        response = self.client.post('/equipe/create/', {
            'first_name': 'New', 'last_name': 'Coadmin',
            'username': 'newco', 'role': 'coadmin',
            'password': 'abc123', 'confirm_password': 'abc123',
            'is_active': 'on',
        })
        self.assertEqual(StaffMember.objects.filter(role='coadmin').count(), 2)

    def test_coadmin_cannot_delete_another_coadmin(self):
        self._login_coadmin()
        response = self.client.post(f'/equipe/{self.coadmin.pk}/delete/')
        # La suppression du coadmin par lui-même ou d'un autre coadmin est refusée
        self.assertEqual(StaffMember.objects.filter(role='coadmin').count(), 1)

    def test_owner_can_delete_coadmin(self):
        self._login_owner()
        self.client.post(f'/equipe/{self.coadmin.pk}/delete/')
        self.assertEqual(StaffMember.objects.filter(role='coadmin').count(), 0)
```

- [ ] **Étape 2 : Lancer les tests pour confirmer qu'ils échouent**

```bash
python manage.py test base.tests.StaffAdminViewsTest -v 2
```

Résultat attendu : erreur 404 sur `/equipe/`

- [ ] **Étape 3 : Créer `base/staff_admin_views.py`**

```python
# base/staff_admin_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from base.models import StaffMember
from base.staff_forms import StaffMemberForm
from base.decorators import admin_or_coadmin_required


@admin_or_coadmin_required
def staff_list(request):
    restaurant = request.managing_restaurant
    members = StaffMember.objects.filter(restaurant=restaurant).order_by('role', 'first_name')
    return render(request, 'admin_user/staff/list.html', {
        'members': members,
        'restaurant': restaurant,
        'is_owner': request.staff_member is None,  # True si Django user
    })


@admin_or_coadmin_required
def staff_create(request):
    restaurant = request.managing_restaurant
    form = StaffMemberForm()

    if request.method == 'POST':
        form = StaffMemberForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Coadmin ne peut pas créer d'autre coadmin
            if request.staff_member and cd['role'] == 'coadmin':
                messages.error(request, "Un co-administrateur ne peut pas créer un autre co-administrateur.")
                return render(request, 'admin_user/staff/create.html', {'form': form, 'restaurant': restaurant})

            if not cd.get('password'):
                messages.error(request, "Un mot de passe est requis à la création.")
                return render(request, 'admin_user/staff/create.html', {'form': form, 'restaurant': restaurant})

            if StaffMember.objects.filter(restaurant=restaurant, username=cd['username']).exists():
                form.add_error('username', "Cet identifiant est déjà utilisé dans ce restaurant.")
                return render(request, 'admin_user/staff/create.html', {'form': form, 'restaurant': restaurant})

            member = StaffMember(
                restaurant=restaurant,
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                username=cd['username'],
                role=cd['role'],
                is_active=cd.get('is_active', True),
            )
            member.set_password(cd['password'])
            member.save()
            messages.success(request, f"Compte créé pour {member.get_full_name()}.")
            return redirect('staff_list')

    return render(request, 'admin_user/staff/create.html', {'form': form, 'restaurant': restaurant})


@admin_or_coadmin_required
def staff_update(request, pk):
    restaurant = request.managing_restaurant
    member = get_object_or_404(StaffMember, pk=pk, restaurant=restaurant)

    # Coadmin ne peut pas éditer un autre coadmin
    if request.staff_member and member.role == 'coadmin':
        messages.error(request, "Action non autorisée.")
        return redirect('staff_list')

    form = StaffMemberForm(initial={
        'first_name': member.first_name, 'last_name': member.last_name,
        'username': member.username, 'role': member.role, 'is_active': member.is_active,
    })

    if request.method == 'POST':
        form = StaffMemberForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Coadmin ne peut pas promouvoir vers coadmin
            if request.staff_member and cd['role'] == 'coadmin':
                messages.error(request, "Un co-administrateur ne peut pas attribuer le rôle co-administrateur.")
                return render(request, 'admin_user/staff/update.html', {
                    'form': form, 'member': member, 'restaurant': restaurant
                })

            member.first_name = cd['first_name']
            member.last_name = cd['last_name']
            member.username = cd['username']
            member.role = cd['role']
            member.is_active = cd.get('is_active', True)
            if cd.get('password'):
                member.set_password(cd['password'])
            member.save()
            messages.success(request, f"Compte de {member.get_full_name()} mis à jour.")
            return redirect('staff_list')

    return render(request, 'admin_user/staff/update.html', {
        'form': form, 'member': member, 'restaurant': restaurant
    })


@admin_or_coadmin_required
def staff_delete(request, pk):
    restaurant = request.managing_restaurant
    member = get_object_or_404(StaffMember, pk=pk, restaurant=restaurant)

    # Coadmin ne peut pas supprimer un autre coadmin
    if request.staff_member and member.role == 'coadmin':
        messages.error(request, "Un co-administrateur ne peut pas supprimer un autre co-administrateur.")
        return redirect('staff_list')

    if request.method == 'POST':
        name = member.get_full_name()
        member.delete()
        messages.success(request, f"{name} a été supprimé.")
        return redirect('staff_list')

    return redirect('staff_list')
```

- [ ] **Étape 4 : Ajouter les URLs dans `base/urls.py`**

Dans `base/urls.py`, ajouter ces imports et paths :

```python
from base import staff_admin_views

# Ajouter dans urlpatterns :
path('equipe/',                  staff_admin_views.staff_list,   name='staff_list'),
path('equipe/create/',           staff_admin_views.staff_create, name='staff_create'),
path('equipe/<int:pk>/update/',  staff_admin_views.staff_update, name='staff_update'),
path('equipe/<int:pk>/delete/',  staff_admin_views.staff_delete, name='staff_delete'),
```

- [ ] **Étape 5 : Créer les templates stubs (seront redesignés en Tâche 8)**

```bash
mkdir -p "/home/jey/Documents/projet /OpendFood/templates/admin_user/staff"
```

```html
{# templates/admin_user/staff/list.html #}
{% extends "admin_user/base.html" %}
{% block content %}
<h1>Équipe</h1>
<a href="{% url 'staff_create' %}">+ Ajouter</a>
{% for m in members %}
<div>{{ m.get_full_name }} ({{ m.get_role_display }}) — {{ m.username }}
  <a href="{% url 'staff_update' m.pk %}">Éditer</a>
  <form method="post" action="{% url 'staff_delete' m.pk %}" style="display:inline">
    {% csrf_token %}<button>Supprimer</button>
  </form>
</div>
{% endfor %}
{% endblock %}
```

```html
{# templates/admin_user/staff/create.html #}
{% extends "admin_user/base.html" %}
{% block content %}
<h1>Ajouter un membre</h1>
<form method="post">{% csrf_token %}{{ form.as_p }}<button>Créer</button></form>
{% endblock %}
```

```html
{# templates/admin_user/staff/update.html #}
{% extends "admin_user/base.html" %}
{% block content %}
<h1>Modifier {{ member.get_full_name }}</h1>
<form method="post">{% csrf_token %}{{ form.as_p }}<button>Enregistrer</button></form>
{% endblock %}
```

- [ ] **Étape 6 : Lancer les tests**

```bash
python manage.py test base.tests.StaffAdminViewsTest -v 2
```

Résultat attendu : `Ran 6 tests in X.XXXs — OK`

- [ ] **Étape 7 : Vérifier Django check**

```bash
python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Étape 8 : Commit**

```bash
git add base/staff_admin_views.py base/urls.py base/tests.py templates/admin_user/staff/
git commit -m "feat: admin staff management CRUD (list/create/update/delete)"
```

---

## Tâche 7 : Templates du portail staff (design moderne)

> **⚠️ Invoquer le skill `frontend-design` pour cette tâche** avec le brief ci-dessous avant de coder les templates.

**Brief pour `frontend-design` :**
> Portail staff d'un restaurant (OpenFood). Thème sombre industriel / cuisine professionnelle. Trois fichiers :
> 1. `staff/base.html` — layout minimal, barre haute avec nom du staff + rôle + bouton déconnexion, couleur #0f172a (dark slate), pas de sidebar
> 2. `staff/connexion.html` — page de login standalone, champ username + password, pas d'email, bouton "Se connecter", lien retour vers login admin discret en bas
> 3. `staff/orders/list.html` — liste de commandes en temps réel : cards par commande avec numéro, statut coloré, "en préparation par {nom}", boutons d'action contextuels (cuisinier : préparer/prête ; serveur : servie). Badge rouge animé pour commandes "ready". Polling JS toutes les 8s sur `/staff/commandes/check/`.

**Fichiers à créer :**
- `templates/staff/base.html`
- `templates/staff/connexion.html` (remplace le stub)
- `templates/staff/orders/list.html` (remplace le stub)

- [ ] **Étape 1 : Invoquer le skill frontend-design**

```
/frontend-design Brief : [brief ci-dessus]
```

- [ ] **Étape 2 : Implémenter `templates/staff/base.html`**

Le template doit :
- Avoir les blocs `{% block title %}`, `{% block content %}`, `{% block extra_js %}`
- Charger Tailwind CDN et Remix Icons CDN
- Afficher `{{ staff.get_full_name }}` et `{{ staff.get_role_display }}` dans la barre
- Avoir un lien `{% url 'staff_logout' %}`
- Inclure un bloc `{% block page_header %}` pour le titre de page

```html
{# templates/staff/base.html — implémentation finale après frontend-design #}
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}Staff – OpenFood{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: { extend: {
        colors: { primary: { DEFAULT: '#f97316', dark: '#ea580c' } },
        fontFamily: { display: ['Syne', 'sans-serif'], body: ['DM Sans', 'sans-serif'] },
      }}
    }
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800;900&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body class="bg-slate-950 text-slate-100 font-body min-h-screen">
  <!-- Top bar -->
  <header class="sticky top-0 z-40 bg-slate-900 border-b border-slate-800 px-4 py-3 flex items-center justify-between">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-primary/20 border border-primary/30 flex items-center justify-center">
        <i class="ri-restaurant-2-line text-primary text-sm"></i>
      </div>
      <div>
        <span class="font-display font-black text-white text-sm">{{ staff.get_full_name }}</span>
        <span class="ml-2 px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-800 text-slate-400">
          {{ staff.get_role_display }}
        </span>
      </div>
    </div>
    <a href="{% url 'staff_logout' %}"
       class="flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-400 hover:text-white hover:bg-slate-800 transition-colors">
      <i class="ri-logout-box-line"></i> Déconnexion
    </a>
  </header>

  <main class="max-w-3xl mx-auto px-4 py-6">
    {% block page_header %}{% endblock %}
    {% block content %}{% endblock %}
  </main>

  {% block extra_js %}{% endblock %}
</body>
</html>
```

- [ ] **Étape 3 : Implémenter `templates/staff/connexion.html`**

Le template doit :
- Être standalone (pas d'extend staff/base)
- Afficher champ username + champ password + bouton "Se connecter"
- Afficher `{{ error }}` si présent
- Avoir en bas : `<a href="{% url 'connexion' %}">Retour connexion admin</a>` (très discret)
- Thème sombre, logo OpenFood centré

```html
{# templates/staff/connexion.html — implémentation finale #}
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Portail Staff – OpenFood</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: { extend: {
        colors: { primary: { DEFAULT: '#f97316', dark: '#ea580c' } },
        fontFamily: { display: ['Syne', 'sans-serif'] },
      }}
    }
  </script>
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800;900&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
</head>
<body class="min-h-screen bg-slate-950 flex items-center justify-center p-4 font-[DM_Sans]">
  <div class="w-full max-w-sm">
    <!-- Logo -->
    <div class="text-center mb-8">
      <div class="inline-flex items-center gap-2.5 mb-3">
        <div class="w-10 h-10 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center">
          <i class="ri-restaurant-2-line text-primary text-xl"></i>
        </div>
        <span class="font-display font-black text-white text-xl">Open<span class="text-primary">Food</span></span>
      </div>
      <p class="text-slate-400 text-sm">Portail de l'équipe</p>
    </div>

    <!-- Carte login -->
    <div class="bg-slate-900 border border-slate-800 rounded-3xl p-6 shadow-2xl">
      {% if error %}
      <div class="mb-4 px-4 py-3 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm flex items-center gap-2">
        <i class="ri-error-warning-line flex-shrink-0"></i>
        {{ error }}
      </div>
      {% endif %}

      <form method="post" class="space-y-4">
        {% csrf_token %}
        <div>
          <label class="block text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Identifiant</label>
          <input type="text" name="username" required autocomplete="username"
                 class="w-full px-4 py-3 text-sm bg-slate-800 border border-slate-700 rounded-xl text-white placeholder:text-slate-600 focus:outline-none focus:border-primary transition-colors"
                 placeholder="Votre identifiant">
        </div>
        <div>
          <label class="block text-[10px] font-semibold text-slate-500 uppercase tracking-wide mb-1.5">Mot de passe</label>
          <input type="password" name="password" required autocomplete="current-password"
                 class="w-full px-4 py-3 text-sm bg-slate-800 border border-slate-700 rounded-xl text-white placeholder:text-slate-600 focus:outline-none focus:border-primary transition-colors"
                 placeholder="••••••••">
        </div>
        <button type="submit"
                class="w-full py-3.5 rounded-2xl bg-primary text-white text-sm font-bold hover:bg-primary-dark transition-colors mt-2">
          Se connecter
        </button>
      </form>
    </div>

    <!-- Lien discret admin -->
    <p class="text-center mt-6">
      <a href="{% url 'connexion' %}" class="text-slate-600 hover:text-slate-400 text-xs transition-colors">
        Connexion administrateur
      </a>
    </p>
  </div>
</body>
</html>
```

- [ ] **Étape 4 : Implémenter `templates/staff/orders/list.html`**

Ce template doit :
- Étendre `staff/base.html`
- Afficher les commandes en cards colorées par statut
- Cuisinier : boutons "En préparation" (pending/confirmed) et "Prête ✓" (preparing)
- Serveur : bouton "Servie ✓" (ready uniquement)
- Badge animé "● PRÊTE" en rouge pour les ready (serveur)
- Afficher "En préparation par {preparing_by_name}" quand applicable
- Script JS de polling toutes les 8s avec rechargement si nouvelles données

```html
{# templates/staff/orders/list.html #}
{% extends "staff/base.html" %}
{% block title %}Commandes – OpenFood Staff{% endblock %}

{% block page_header %}
<div class="flex items-center justify-between mb-6">
  <div>
    <h1 class="font-display font-black text-white text-xl">Commandes</h1>
    {% if staff.role == 'serveur' and ready_count > 0 %}
    <span class="inline-flex items-center gap-1.5 mt-1 text-xs font-bold text-red-400 animate-pulse">
      <span class="w-2 h-2 rounded-full bg-red-400"></span>
      {{ ready_count }} commande{{ ready_count|pluralize }} prête{{ ready_count|pluralize }} à servir
    </span>
    {% endif %}
  </div>
  <span class="text-xs text-slate-500">Màj auto. toutes les 8s</span>
</div>
{% endblock %}

{% block content %}
<div class="space-y-3" id="orders-list">
  {% for order in orders %}
  {% with status=order.status %}
  <div class="bg-slate-900 border rounded-2xl overflow-hidden
    {% if status == 'ready' %}border-green-500/50{% elif status == 'preparing' %}border-amber-500/40{% else %}border-slate-800{% endif %}">

    <!-- Header commande -->
    <div class="px-4 py-3 flex items-center justify-between
      {% if status == 'ready' %}bg-green-500/10{% elif status == 'preparing' %}bg-amber-500/10{% endif %}">
      <div class="flex items-center gap-3">
        <span class="font-display font-black text-white text-sm">#{{ order.order_number }}</span>
        <span class="px-2.5 py-1 rounded-full text-[10px] font-bold
          {% if status == 'pending' %}bg-slate-700 text-slate-300
          {% elif status == 'confirmed' %}bg-blue-500/20 text-blue-300
          {% elif status == 'preparing' %}bg-amber-500/20 text-amber-300
          {% elif status == 'ready' %}bg-green-500/20 text-green-300
          {% elif status == 'delivered' %}bg-slate-700 text-slate-400
          {% endif %}">
          {% if status == 'ready' %}<span class="animate-pulse">●</span> {% endif %}
          {{ order.get_status_display }}
        </span>
      </div>
      <span class="text-xs text-slate-500">{{ order.created_at|time:"H:i" }}</span>
    </div>

    <!-- Corps -->
    <div class="px-4 py-3">
      {% if order.customer_name %}
      <p class="text-xs text-slate-400 mb-2">
        <i class="ri-user-line mr-1"></i>{{ order.customer_name }}
        {% if order.table %} · Table {{ order.table.number }}{% endif %}
      </p>
      {% endif %}

      {% if order.preparing_by_name %}
      <p class="text-xs text-amber-400 mb-2">
        <i class="ri-fire-line mr-1"></i>En préparation par <strong>{{ order.preparing_by_name }}</strong>
      </p>
      {% endif %}

      <!-- Articles -->
      <div class="space-y-1 mb-3">
        {% for item in order.items.all %}
        <div class="flex items-center gap-2 text-xs text-slate-300">
          <span class="w-5 h-5 rounded-md bg-slate-800 flex items-center justify-center text-[10px] font-bold text-slate-400 flex-shrink-0">{{ item.quantity }}</span>
          {{ item.menu_item.name }}
        </div>
        {% endfor %}
      </div>

      <!-- Actions -->
      <form method="post" action="{% url 'staff_change_status' order.pk %}" class="flex gap-2 flex-wrap">
        {% csrf_token %}
        {% if staff.role == 'cuisinier' or staff.role == 'coadmin' %}
          {% if status == 'pending' or status == 'confirmed' %}
          <button name="status" value="preparing"
                  class="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-amber-500/20 text-amber-300 border border-amber-500/30 text-xs font-bold hover:bg-amber-500/30 transition-colors">
            <i class="ri-fire-line"></i> En préparation
          </button>
          {% endif %}
          {% if status == 'preparing' %}
          <button name="status" value="ready"
                  class="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-green-500/20 text-green-300 border border-green-500/30 text-xs font-bold hover:bg-green-500/30 transition-colors">
            <i class="ri-checkbox-circle-line"></i> Prête ✓
          </button>
          {% endif %}
        {% endif %}
        {% if staff.role == 'serveur' or staff.role == 'coadmin' %}
          {% if status == 'ready' %}
          <button name="status" value="delivered"
                  class="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-slate-700 text-slate-200 border border-slate-600 text-xs font-bold hover:bg-slate-600 transition-colors">
            <i class="ri-check-double-line"></i> Servie ✓
          </button>
          {% endif %}
        {% endif %}
      </form>
    </div>
  </div>
  {% endwith %}
  {% empty %}
  <div class="text-center py-16">
    <i class="ri-restaurant-line text-4xl text-slate-700 block mb-3"></i>
    <p class="text-slate-500 text-sm">Aucune commande active</p>
  </div>
  {% endfor %}
</div>
{% endblock %}

{% block extra_js %}
<script>
let latestOrderId = {{ latest_order_id }};
let role = '{{ staff.role }}';

function pollUpdates() {
  fetch(`{% url 'staff_check_updates' %}?last_id=${latestOrderId}`)
    .then(r => r.json())
    .then(data => {
      // Nouvelle commande → notifier les cuisiniers
      if (data.new_count > 0 && (role === 'cuisinier' || role === 'coadmin')) {
        latestOrderId = data.latest_id;
        location.reload();
        return;
      }
      // Commande prête → notifier les serveurs
      if (data.ready_count > 0 && role === 'serveur') {
        location.reload();
        return;
      }
      // Statut changé → rafraîchir
      if (data.orders.some(o => hasStatusChanged(o))) {
        location.reload();
      }
    })
    .catch(() => {}); // silencieux si hors ligne
}

// Statuts actuellement affichés
const currentStatuses = {};
{% for order in orders %}
currentStatuses[{{ order.id }}] = '{{ order.status }}';
{% endfor %}

function hasStatusChanged(orderData) {
  const current = currentStatuses[orderData.id];
  return current !== undefined && current !== orderData.status;
}

setInterval(pollUpdates, 8000);
</script>
{% endblock %}
```

- [ ] **Étape 5 : Vérifier que les templates se chargent**

```bash
python -c "
import django, os, sys
sys.path.insert(0, '.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'main.settings'
django.setup()
from django.template.loader import get_template
for t in ['staff/base.html', 'staff/connexion.html', 'staff/orders/list.html']:
    get_template(t)
    print(f'OK: {t}')
"
```

Résultat attendu : `OK` pour les 3 templates

- [ ] **Étape 6 : Commit**

```bash
git add templates/staff/
git commit -m "feat: staff portal templates (login, orders list with polling)"
```

---

## Tâche 8 : Templates de gestion du staff (côté admin)

> **⚠️ Invoquer le skill `frontend-design`** avec ce brief avant de coder :
> Pages de gestion d'équipe dans le dashboard admin OpenFood (thème orange #f97316, fond blanc, Syne + DM Sans). Trois pages :
> 1. `list.html` — tableau des membres avec badge rôle coloré (coadmin=violet, cuisinier=orange, serveur=bleu), boutons éditer/supprimer, CTA "Ajouter un membre"
> 2. `create.html` — formulaire création membre (prénom, nom, identifiant, rôle select, password, confirm_password, toggle actif)
> 3. `update.html` — même formulaire pré-rempli + note "Laisser le mot de passe vide pour ne pas le modifier"
> Suivre le design system des autres pages admin : `bg-white rounded-2xl border border-slate-100 shadow-soft`, labels `text-[10px] uppercase tracking-wide`, inputs `px-4 py-3 rounded-xl`.

**Fichiers à créer :**
- `templates/admin_user/staff/list.html` (remplace le stub)
- `templates/admin_user/staff/create.html` (remplace le stub)
- `templates/admin_user/staff/update.html` (remplace le stub)

- [ ] **Étape 1 : Invoquer le skill frontend-design**

```
/frontend-design Brief : [brief ci-dessus]
```

- [ ] **Étape 2 : Implémenter `templates/admin_user/staff/list.html`**

```html
{% extends "admin_user/base.html" %}
{% block title %}Équipe – OpenFood{% endblock %}
{% block page_title %}Équipe{% endblock %}

{% block header_actions %}
<a href="{% url 'staff_create' %}"
   class="flex items-center gap-2 px-3 py-2 rounded-xl bg-primary text-white text-sm font-bold shadow-glow hover:bg-primary-dark transition-colors">
  <i class="ri-user-add-line"></i>
  <span class="hidden sm:block">Ajouter</span>
</a>
{% endblock %}

{% block content %}

{% if members %}
<!-- Stats rapides -->
<div class="grid grid-cols-3 gap-3 mb-6">
  {% with coadmin_count=members|length %}
  <div class="bg-white rounded-2xl border border-slate-100 shadow-soft p-4 text-center">
    <p class="font-display font-black text-2xl text-slate-900">{{ members|length }}</p>
    <p class="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mt-1">Total</p>
  </div>
  {% endwith %}
  <div class="bg-white rounded-2xl border border-slate-100 shadow-soft p-4 text-center">
    <p class="font-display font-black text-2xl text-amber-500">
      {{ members|dictsort:"role"|length }}
    </p>
    <p class="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mt-1">Actifs</p>
  </div>
  <div class="bg-white rounded-2xl border border-slate-100 shadow-soft p-4 text-center">
    <p class="font-display font-black text-2xl text-primary">{{ restaurant.name|truncatechars:8 }}</p>
    <p class="text-[10px] font-semibold text-slate-400 uppercase tracking-wide mt-1">Restaurant</p>
  </div>
</div>

<!-- Liste membres -->
<div class="bg-white rounded-2xl border border-slate-100 shadow-soft overflow-hidden">
  <div class="px-5 py-4 border-b border-slate-100 flex items-center gap-2.5">
    <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
      <i class="ri-team-line text-primary text-sm"></i>
    </div>
    <h2 class="font-display font-black text-slate-900 text-sm">Membres de l'équipe</h2>
  </div>

  <div class="divide-y divide-slate-50">
    {% for m in members %}
    <div class="flex items-center gap-4 px-5 py-4 hover:bg-slate-50/50 transition-colors">
      <!-- Avatar -->
      <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
        {% if m.role == 'coadmin' %}bg-violet-100{% elif m.role == 'cuisinier' %}bg-orange-100{% else %}bg-blue-100{% endif %}">
        <i class="text-sm
          {% if m.role == 'coadmin' %}ri-shield-user-line text-violet-600
          {% elif m.role == 'cuisinier' %}ri-fire-line text-orange-600
          {% else %}ri-user-star-line text-blue-600{% endif %}"></i>
      </div>

      <!-- Infos -->
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 flex-wrap">
          <p class="text-sm font-semibold text-slate-900">{{ m.get_full_name }}</p>
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold
            {% if m.role == 'coadmin' %}bg-violet-50 text-violet-700
            {% elif m.role == 'cuisinier' %}bg-orange-50 text-orange-700
            {% else %}bg-blue-50 text-blue-700{% endif %}">
            {{ m.get_role_display }}
          </span>
          {% if not m.is_active %}
          <span class="px-2 py-0.5 rounded-full text-[10px] font-bold bg-slate-100 text-slate-400">Inactif</span>
          {% endif %}
        </div>
        <p class="text-xs text-slate-400 mt-0.5">@{{ m.username }}</p>
      </div>

      <!-- Actions -->
      <div class="flex items-center gap-2 flex-shrink-0">
        {% if is_owner or m.role != 'coadmin' %}
        <a href="{% url 'staff_update' m.pk %}"
           class="p-2 rounded-xl text-slate-400 hover:text-primary hover:bg-primary/5 transition-colors">
          <i class="ri-edit-line text-sm"></i>
        </a>
        <form method="post" action="{% url 'staff_delete' m.pk %}"
              onsubmit="return confirm('Supprimer {{ m.get_full_name }} ?')">
          {% csrf_token %}
          <button type="submit" class="p-2 rounded-xl text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors">
            <i class="ri-delete-bin-line text-sm"></i>
          </button>
        </form>
        {% else %}
        <span class="text-xs text-slate-300 px-3">—</span>
        {% endif %}
      </div>
    </div>
    {% endfor %}
  </div>
</div>

{% else %}
<!-- État vide -->
<div class="bg-white rounded-2xl border border-slate-100 shadow-soft p-12 text-center">
  <div class="w-16 h-16 rounded-2xl bg-primary/10 flex items-center justify-center mx-auto mb-4">
    <i class="ri-team-line text-primary text-2xl"></i>
  </div>
  <h3 class="font-display font-black text-slate-900 text-lg mb-2">Aucun membre d'équipe</h3>
  <p class="text-sm text-slate-400 mb-6">Ajoutez des cuisiniers, serveurs ou co-administrateurs.</p>
  <a href="{% url 'staff_create' %}"
     class="inline-flex items-center gap-2 px-5 py-3 rounded-2xl bg-primary text-white text-sm font-bold shadow-glow hover:bg-primary-dark transition-colors">
    <i class="ri-user-add-line"></i> Ajouter un membre
  </a>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Étape 3 : Implémenter `templates/admin_user/staff/create.html`**

```html
{% extends "admin_user/base.html" %}
{% block title %}Ajouter un membre – OpenFood{% endblock %}
{% block page_title %}Nouveau membre{% endblock %}

{% block header_actions %}
<a href="{% url 'staff_list' %}"
   class="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">
  <i class="ri-arrow-left-line"></i>
  <span class="hidden sm:block">Équipe</span>
</a>
{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto">
  <div class="bg-white rounded-2xl border border-slate-100 shadow-soft overflow-hidden">
    <div class="px-6 py-5 border-b border-slate-100 flex items-center gap-3">
      <div class="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center flex-shrink-0">
        <i class="ri-user-add-line text-primary text-lg"></i>
      </div>
      <div>
        <h2 class="font-display font-black text-slate-900 text-base">Ajouter un membre</h2>
        <p class="text-xs text-slate-400 mt-0.5">{{ restaurant.name }}</p>
      </div>
    </div>

    <form method="post" class="p-6 space-y-5">
      {% csrf_token %}

      {% if messages %}
      {% for msg in messages %}
      <div class="px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-sm text-red-700 flex items-center gap-2">
        <i class="ri-error-warning-line flex-shrink-0"></i> {{ msg }}
      </div>
      {% endfor %}
      {% endif %}

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
            Prénom <span class="text-red-400">*</span>
          </label>
          <input type="text" name="first_name" required value="{{ form.first_name.value|default:'' }}"
                 class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
        </div>
        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
            Nom <span class="text-red-400">*</span>
          </label>
          <input type="text" name="last_name" required value="{{ form.last_name.value|default:'' }}"
                 class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
        </div>
      </div>

      <div>
        <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
          Identifiant <span class="text-red-400">*</span>
        </label>
        <input type="text" name="username" required value="{{ form.username.value|default:'' }}"
               class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
               placeholder="Ex : jean.chef">
        <p class="text-[10px] text-slate-400 mt-1.5">Unique dans ce restaurant · utilisé pour la connexion</p>
        {% if form.username.errors %}
        <p class="text-xs text-red-500 mt-1">{{ form.username.errors.0 }}</p>
        {% endif %}
      </div>

      <div>
        <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
          Rôle <span class="text-red-400">*</span>
        </label>
        <select name="role" required
                class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all appearance-none">
          <option value="cuisinier" {% if form.role.value == 'cuisinier' %}selected{% endif %}>Cuisinier</option>
          <option value="serveur"   {% if form.role.value == 'serveur' %}selected{% endif %}>Serveur</option>
          <option value="coadmin"   {% if form.role.value == 'coadmin' %}selected{% endif %}>Co-administrateur</option>
        </select>
      </div>

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
            Mot de passe <span class="text-red-400">*</span>
          </label>
          <input type="password" name="password" required
                 class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
        </div>
        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">
            Confirmer <span class="text-red-400">*</span>
          </label>
          <input type="password" name="confirm_password" required
                 class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
          {% if form.confirm_password.errors %}
          <p class="text-xs text-red-500 mt-1">{{ form.confirm_password.errors.0 }}</p>
          {% endif %}
        </div>
      </div>

      <!-- Toggle actif -->
      <div class="flex items-center justify-between p-4 rounded-xl bg-slate-50 border border-slate-100">
        <div>
          <p class="text-sm font-semibold text-slate-800">Compte actif</p>
          <p class="text-xs text-slate-400 mt-0.5">La personne peut se connecter</p>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" name="is_active" class="sr-only peer" checked>
          <div class="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-primary transition-colors duration-200 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all after:duration-200 peer-checked:after:translate-x-5"></div>
        </label>
      </div>

      <div class="flex gap-3 pt-1">
        <a href="{% url 'staff_list' %}"
           class="flex-1 py-3 text-center text-sm font-semibold text-slate-600 border border-slate-200 rounded-2xl hover:bg-slate-50 transition-colors">
          Annuler
        </a>
        <button type="submit"
                class="flex-1 py-3 text-sm font-bold text-white bg-primary rounded-2xl hover:bg-primary-dark transition-colors shadow-glow">
          <i class="ri-user-add-line mr-1"></i> Créer le compte
        </button>
      </div>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Étape 4 : Implémenter `templates/admin_user/staff/update.html`**

```html
{% extends "admin_user/base.html" %}
{% block title %}Modifier {{ member.get_full_name }} – OpenFood{% endblock %}
{% block page_title %}{{ member.get_full_name }}{% endblock %}

{% block header_actions %}
<a href="{% url 'staff_list' %}"
   class="flex items-center gap-2 px-3 py-2 rounded-xl border border-slate-200 text-sm font-medium text-slate-600 hover:bg-slate-50 transition-colors">
  <i class="ri-arrow-left-line"></i>
  <span class="hidden sm:block">Équipe</span>
</a>
{% endblock %}

{% block content %}
<div class="max-w-lg mx-auto">
  <div class="bg-white rounded-2xl border border-slate-100 shadow-soft overflow-hidden">
    <div class="px-6 py-5 border-b border-slate-100 flex items-center gap-3">
      <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0
        {% if member.role == 'coadmin' %}bg-violet-100{% elif member.role == 'cuisinier' %}bg-orange-100{% else %}bg-blue-100{% endif %}">
        <i class="text-lg
          {% if member.role == 'coadmin' %}ri-shield-user-line text-violet-600
          {% elif member.role == 'cuisinier' %}ri-fire-line text-orange-600
          {% else %}ri-user-star-line text-blue-600{% endif %}"></i>
      </div>
      <div class="flex-1 min-w-0">
        <h2 class="font-display font-black text-slate-900 text-base truncate">{{ member.get_full_name }}</h2>
        <p class="text-xs text-slate-400 mt-0.5">@{{ member.username }} · {{ member.get_role_display }}</p>
      </div>
      <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-[10px] font-bold flex-shrink-0
        {% if member.is_active %}bg-green-50 text-green-700{% else %}bg-slate-100 text-slate-500{% endif %}">
        <span class="w-1.5 h-1.5 rounded-full {% if member.is_active %}bg-green-500{% else %}bg-slate-400{% endif %}"></span>
        {% if member.is_active %}Actif{% else %}Inactif{% endif %}
      </span>
    </div>

    <form method="post" class="p-6 space-y-5">
      {% csrf_token %}

      {% if messages %}
      {% for msg in messages %}
      <div class="px-4 py-3 rounded-2xl bg-red-50 border border-red-100 text-sm text-red-700 flex items-center gap-2">
        <i class="ri-error-warning-line flex-shrink-0"></i> {{ msg }}
      </div>
      {% endfor %}
      {% endif %}

      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Prénom</label>
          <input type="text" name="first_name" required value="{{ form.first_name.value|default:member.first_name }}"
                 class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
        </div>
        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Nom</label>
          <input type="text" name="last_name" required value="{{ form.last_name.value|default:member.last_name }}"
                 class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
        </div>
      </div>

      <div>
        <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Identifiant</label>
        <input type="text" name="username" required value="{{ form.username.value|default:member.username }}"
               class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all">
        {% if form.username.errors %}
        <p class="text-xs text-red-500 mt-1">{{ form.username.errors.0 }}</p>
        {% endif %}
      </div>

      <div>
        <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Rôle</label>
        <select name="role" required
                class="w-full px-4 py-3 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all appearance-none">
          <option value="cuisinier" {% if form.role.value == 'cuisinier' %}selected{% endif %}>Cuisinier</option>
          <option value="serveur"   {% if form.role.value == 'serveur' %}selected{% endif %}>Serveur</option>
          <option value="coadmin"   {% if form.role.value == 'coadmin' %}selected{% endif %}>Co-administrateur</option>
        </select>
      </div>

      <!-- Mot de passe optionnel à l'édition -->
      <div class="p-4 rounded-xl bg-slate-50 border border-slate-100 space-y-3">
        <p class="text-xs font-semibold text-slate-500 flex items-center gap-1.5">
          <i class="ri-lock-line"></i> Mot de passe (optionnel)
        </p>
        <p class="text-[10px] text-slate-400">Laisser vide pour conserver le mot de passe actuel.</p>
        <div class="grid grid-cols-2 gap-3">
          <input type="password" name="password"
                 class="w-full px-4 py-2.5 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                 placeholder="Nouveau mot de passe">
          <input type="password" name="confirm_password"
                 class="w-full px-4 py-2.5 text-sm bg-white border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
                 placeholder="Confirmer">
        </div>
        {% if form.confirm_password.errors %}
        <p class="text-xs text-red-500">{{ form.confirm_password.errors.0 }}</p>
        {% endif %}
      </div>

      <!-- Toggle actif -->
      <div class="flex items-center justify-between p-4 rounded-xl bg-slate-50 border border-slate-100">
        <div>
          <p class="text-sm font-semibold text-slate-800">Compte actif</p>
          <p class="text-xs text-slate-400 mt-0.5">La personne peut se connecter</p>
        </div>
        <label class="relative inline-flex items-center cursor-pointer">
          <input type="checkbox" name="is_active" class="sr-only peer"
                 {% if form.is_active.value %}checked{% endif %}>
          <div class="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-primary transition-colors duration-200 after:content-[''] after:absolute after:top-0.5 after:left-0.5 after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all after:duration-200 peer-checked:after:translate-x-5"></div>
        </label>
      </div>

      <div class="flex gap-3 pt-1">
        <a href="{% url 'staff_list' %}"
           class="flex-1 py-3 text-center text-sm font-semibold text-slate-600 border border-slate-200 rounded-2xl hover:bg-slate-50 transition-colors">
          Annuler
        </a>
        <button type="submit"
                class="flex-1 py-3 text-sm font-bold text-white bg-primary rounded-2xl hover:bg-primary-dark transition-colors shadow-glow">
          <i class="ri-save-line mr-1"></i> Enregistrer
        </button>
      </div>
    </form>
  </div>
</div>
{% endblock %}
```

- [ ] **Étape 5 : Vérifier que les templates se chargent**

```bash
python -c "
import django, os, sys
sys.path.insert(0, '.')
os.environ['DJANGO_SETTINGS_MODULE'] = 'main.settings'
django.setup()
from django.template.loader import get_template
for t in ['admin_user/staff/list.html', 'admin_user/staff/create.html', 'admin_user/staff/update.html']:
    get_template(t)
    print(f'OK: {t}')
"
```

- [ ] **Étape 6 : Commit**

```bash
git add templates/admin_user/staff/
git commit -m "feat: admin staff management templates (list, create, update)"
```

---

## Tâche 9 : Intégration — lien login page + navigation admin

**Fichiers :**
- Modifier : `templates/auth/connexion.html`
- Modifier : `templates/admin_user/base.html`
- Modifier : `templates/admin_user/sidebar.html`

**Objectif :** Rendre l'ensemble cohérent et navigable.

- [ ] **Étape 1 : Ajouter le bouton discret "Connexion Staff" dans `templates/auth/connexion.html`**

Trouver la section du bas du formulaire de connexion (lien "Pas encore de compte ?") et ajouter après :

```html
<!-- Ajouter après le lien "Pas encore de compte" dans le formulaire de droite -->
<div class="mt-8 pt-6 border-t border-slate-100 text-center">
  <a href="{% url 'staff_login' %}"
     class="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-600 transition-colors">
    <i class="ri-team-line"></i>
    Connexion espace staff
  </a>
</div>
```

Pour localiser le bon endroit dans le fichier, chercher `"Pas encore de compte"` ou le bas du `<form>` de droite.

- [ ] **Étape 2 : Ajouter le lien "Équipe" dans le bottom nav de `templates/admin_user/base.html`**

Dans la section bottom nav du fichier `base.html`, il existe actuellement 6 onglets en grille `grid-cols-6`. Repérer les entrées existantes (dashboard, orders, menus, tables, customization, settings) et ajouter dans le tableau des URLs en début du block :

```django
{% url 'staff_list' as url_staff %}
```

Puis dans la grille du bottom nav, remplacer l'un des onglets moins utilisés (par exemple `customization`) ou ajouter un 7ème onglet si la grille est flexible. Si 6 est fixe, convertir en `grid-cols-6` → adapter.

Ajouter ce tab dans le bottom nav (même structure que les existants) :

```html
<a href="{{ url_staff }}"
   class="flex flex-col items-center gap-1 py-2 px-1 rounded-xl transition-colors
     {% if request.path|slice:':7' == '/equipe' %}text-primary bg-primary/10{% else %}text-slate-500 hover:text-slate-700{% endif %}">
  <i class="ri-team-line text-xl"></i>
  <span class="text-[10px] font-semibold">Équipe</span>
</a>
```

- [ ] **Étape 3 : Ajouter le lien "Équipe" dans `templates/admin_user/sidebar.html`**

Ajouter une entrée dans la liste de navigation de la sidebar, même structure que les entrées existantes :

```html
{% url 'staff_list' as url_staff %}
<a href="{{ url_staff }}"
   class="flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all duration-150
     {% if request.path|slice:':7' == '/equipe' %}
       bg-primary text-white shadow-glow
     {% else %}
       text-slate-400 hover:bg-white/8 hover:text-white
     {% endif %}">
  <i class="ri-team-line text-lg flex-shrink-0"></i>
  <span x-show="!collapsed" x-transition:enter="transition-opacity duration-200"
        class="text-sm font-semibold truncate">Équipe</span>
</a>
```

- [ ] **Étape 4 : Vérifier Django system check**

```bash
python manage.py check
```

Résultat attendu : `System check identified no issues (0 silenced).`

- [ ] **Étape 5 : Lancer tous les tests**

```bash
python manage.py test base.tests -v 2
```

Résultat attendu : tous les tests passent.

- [ ] **Étape 6 : Test de navigation manuel**

```bash
python manage.py runserver
```

Vérifier :
1. `/connexion/` → le lien "Connexion espace staff" est visible en bas du formulaire
2. Cliquer → `/staff/connexion/` charge la page sombre
3. Se connecter avec un compte cuisinier test
4. `/staff/commandes/` s'affiche avec les commandes actives
5. `/dashboard/` → la sidebar et le bottom nav montrent "Équipe"
6. `/equipe/` → la liste (vide) s'affiche
7. `/equipe/create/` → créer un cuisinier → apparaît dans la liste

- [ ] **Étape 7 : Commit final**

```bash
git add templates/auth/connexion.html templates/admin_user/base.html templates/admin_user/sidebar.html
git commit -m "feat: integrate staff nav link and staff login button on auth page"
```

---

## Revue du spec

**Couverture :**
| Exigence spec | Tâche |
|---------------|-------|
| Admin peut ajouter coadmin/cuisinier/serveur | Tâches 1, 6, 8 |
| Accès page commandes pour cuisinier | Tâche 5 |
| "En préparation par {nom}" visible par autres cuisiniers | Tâches 1 (champ), 5 (vue + polling), 7 (template) |
| Serveurs notifiés quand commande "prête" | Tâche 5 (`staff_check_updates` + polling JS Tâche 7) |
| Serveur marque "servie" → autres serveurs le voient | Tâches 5 + 7 (rechargement polling) |
| Templates gestion staff | Tâche 8 |
| Page connexion : bouton discret staff | Tâche 9 |
| Login via identifiant créé par admin | Tâches 1 (username), 4 (vue login) |
| Admin ET coadmin peuvent supprimer tout le monde | Tâche 6 (`admin_or_coadmin_required`) |
| Coadmin ne peut pas supprimer l'admin | Protégé nativement (admin = Django User ≠ StaffMember) ; coadmin ne peut pas supprimer d'autre coadmin |

**Scan placeholders :** aucun TBD ni "implement later" détecté.

**Cohérence des types :**
- `StaffMember.get_full_name()` → utilisé dans `staff_change_status` (Tâche 5) et les templates (Tâches 7, 8) ✓
- `request.managing_restaurant` → défini dans `admin_or_coadmin_required` (Tâche 3), utilisé dans Tâche 6 ✓
- `request.staff_member` → défini dans les deux décorateurs, `None` pour owner Django, instance `StaffMember` pour coadmin ✓
- `Order.preparing_by_name` → ajouté Tâche 1, écrit Tâche 5, affiché Tâche 7 ✓
- `staff_id` session key → écrit Tâche 4, lu Tâche 3, effacé Tâche 4 (logout) ✓
