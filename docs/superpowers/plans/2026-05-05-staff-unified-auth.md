# Staff Unified Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer l'auth staff session-custom par une auth Django standard unifiée — un seul `/connexion/` pour tous (owner, coadmin, cuisinier, serveur), avec invitation par email et dashboard filtré par rôle.

**Architecture:** `StaffMember` devient un profil OneToOneField vers Django `User` ; les invitations utilisent un token UUID valable 7 jours ; après connexion, le user est routé vers un dashboard adapté à son rôle. Toutes les vues passent par `get_user_restaurant(user)` pour résoudre le restaurant et le rôle en une seule fonction.

**Tech Stack:** Django 4.x, custom User (email auth, email_verified), Tailwind CDN, AlpineJS, Remix Icons. Email via `send_mail` (déjà configuré dans `accounts/utils.py`).

---

## File Structure

| Fichier | Action | Responsabilité |
|---------|--------|----------------|
| `base/models.py` | Modifier | Remplacer StaffMember autonome par version liée à User ; ajouter StaffInvitation |
| `base/decorators.py` | Réécrire | `get_user_restaurant`, `restaurant_required(roles)`, `owner_or_coadmin_required` |
| `base/emails.py` | Créer | `send_staff_invitation_email` |
| `base/staff_admin_views.py` | Réécrire | staff_list, staff_invite, staff_invite_accept, staff_delete |
| `base/views.py` | Modifier | 17 appels `Restaurant.objects.filter(owner=…)` → `get_user_restaurant` ; dashboard branching ; order_change_status avec rôle |
| `accounts/views.py` | Modifier | `connexion` : router vers dashboard/create_restaurant selon rôle après login |
| `base/urls.py` | Modifier | Ajouter `/equipe/inviter/` et `/equipe/accepter/<token>/` ; supprimer routes staff session |
| `main/urls.py` | Modifier | Supprimer `path('staff/', include('base.staff_urls'))` |
| `base/tests.py` | Réécrire | Nouveaux tests Django-User-based |
| `templates/admin_user/base.html` | Modifier | Sidebar et bottom nav filtrés par rôle |
| `templates/admin_user/sidebar.html` | Modifier | Idem |
| `templates/admin_user/staff/list.html` | Réécrire | Formulaire invitation + liste membres |
| `templates/admin_user/staff/invite_accept.html` | Créer | Page d'acceptation invitation |
| `templates/auth/connexion.html` | Modifier | Supprimer lien "Connexion espace staff" |
| Supprimer | `base/staff_views.py`, `base/staff_urls.py`, `base/staff_forms.py`, `templates/staff/` | |

---

### Task 1: Refactor StaffMember + ajouter StaffInvitation + migration

**Files:**
- Modify: `base/models.py` (remplacer StaffMember, ajouter StaffInvitation)
- Create: migration auto-générée via `makemigrations`

- [ ] **Step 1 : Écrire le test qui échoue**

Dans `base/tests.py`, remplacer tout le contenu par :

```python
# base/tests.py
import uuid
from django.test import TestCase
from django.utils import timezone
from django.db import IntegrityError
from accounts.models import User
from base.models import Restaurant, StaffMember, StaffInvitation, SubscriptionPlan


def make_user(email='user@test.com', first='A', last='B'):
    return User.objects.create_user(
        email=email, password='pass123', first_name=first, last_name=last,
        email_verified=True,
    )


def make_restaurant(owner):
    return Restaurant.objects.create(
        owner=owner, name='TestResto', slug='testresto', subdomain='testresto',
        address='123 rue test', phone='0600000000', email='resto@test.com',
    )


class StaffMemberModelTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner@test.com', 'Owner', 'Admin')
        self.restaurant = make_restaurant(self.owner)

    def test_create_staff_member(self):
        staff_user = make_user('chef@test.com', 'Jean', 'Dupont')
        sm = StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='cuisinier'
        )
        self.assertEqual(sm.get_full_name(), 'Jean Dupont')
        self.assertEqual(sm.get_role_display(), 'Cuisinier')
        self.assertTrue(sm.is_active)

    def test_unique_user_per_restaurant(self):
        staff_user = make_user('chef2@test.com', 'Paul', 'Martin')
        StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='cuisinier'
        )
        with self.assertRaises(IntegrityError):
            StaffMember.objects.create(
                user=staff_user, restaurant=self.restaurant, role='serveur'
            )


class StaffInvitationModelTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner2@test.com', 'Owner', 'Two')
        self.restaurant = make_restaurant(self.owner)

    def test_invitation_is_valid(self):
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant,
            email='invite@test.com',
            role='cuisinier',
            created_by=self.owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        self.assertTrue(inv.is_valid())

    def test_expired_invitation_invalid(self):
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant,
            email='exp@test.com',
            role='serveur',
            created_by=self.owner,
            expires_at=timezone.now() - timezone.timedelta(seconds=1),
        )
        self.assertFalse(inv.is_valid())

    def test_accepted_invitation_invalid(self):
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant,
            email='done@test.com',
            role='cuisinier',
            created_by=self.owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
            accepted=True,
        )
        self.assertFalse(inv.is_valid())
```

- [ ] **Step 2 : Lancer le test — il doit échouer**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py test base.tests.StaffMemberModelTest base.tests.StaffInvitationModelTest -v 1
```
Attendu : `ImportError` ou `AttributeError` (StaffInvitation non défini, StaffMember sans champ `user`).

- [ ] **Step 3 : Modifier `base/models.py`**

Remplacer la classe `StaffMember` (lignes 319–353) et ajouter `StaffInvitation` juste après :

```python
class StaffMember(models.Model):
    ROLE_CHOICES = [
        ('coadmin', 'Co-administrateur'),
        ('cuisinier', 'Cuisinier'),
        ('serveur', 'Serveur'),
    ]

    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='staff_profile',
    )
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='staff'
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'restaurant')

    def get_full_name(self):
        return self.user.get_full_name()

    def get_role_display(self):
        return dict(self.ROLE_CHOICES).get(self.role, self.role)

    def __str__(self):
        return f"{self.get_full_name()} ({self.get_role_display()}) — {self.restaurant.name}"


class StaffInvitation(models.Model):
    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='invitations'
    )
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=StaffMember.ROLE_CHOICES)
    token = models.UUIDField(default=uuid.uuid4, unique=True)
    created_by = models.ForeignKey(
        'accounts.User', on_delete=models.SET_NULL, null=True, related_name='sent_invitations'
    )
    accepted = models.BooleanField(default=False)
    expires_at = models.DateTimeField()

    def is_valid(self):
        from django.utils import timezone
        return not self.accepted and self.expires_at > timezone.now()

    def __str__(self):
        return f"Invitation {self.email} → {self.restaurant.name} ({self.role})"
```

> Note : `uuid` est déjà importé en haut de `base/models.py` (ligne 15).

- [ ] **Step 4 : Générer et appliquer la migration**

```bash
python manage.py makemigrations base --name refactor_staffmember_add_invitation
python manage.py migrate
```

Attendu :
```
Migrations for 'base':
  base/migrations/0006_refactor_staffmember_add_invitation.py
    ...
Running migrations:
  Applying base.0006_refactor_staffmember_add_invitation... OK
```

- [ ] **Step 5 : Lancer les tests — ils doivent passer**

```bash
python manage.py test base.tests.StaffMemberModelTest base.tests.StaffInvitationModelTest -v 1
```
Attendu : `OK` (5 tests).

- [ ] **Step 6 : Commit**

```bash
git add base/models.py base/migrations/0006_refactor_staffmember_add_invitation.py base/tests.py
git commit -m "refactor: StaffMember linked to Django User + add StaffInvitation model"
```

---

### Task 2: `base/decorators.py` — helpers et décorateurs basés sur Django User

**Files:**
- Rewrite: `base/decorators.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `base/tests.py` :

```python
from django.test import RequestFactory
from base.decorators import get_user_restaurant, restaurant_required


class GetUserRestaurantTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner3@test.com', 'Owner', 'Three')
        self.restaurant = make_restaurant(self.owner)

    def test_owner_returns_owner_role(self):
        restaurant, role = get_user_restaurant(self.owner)
        self.assertEqual(restaurant, self.restaurant)
        self.assertEqual(role, 'owner')

    def test_staff_returns_staff_role(self):
        staff_user = make_user('staff3@test.com', 'Staff', 'Three')
        StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='cuisinier'
        )
        restaurant, role = get_user_restaurant(staff_user)
        self.assertEqual(restaurant, self.restaurant)
        self.assertEqual(role, 'cuisinier')

    def test_no_restaurant_returns_none(self):
        lonely = make_user('alone@test.com', 'No', 'Resto')
        restaurant, role = get_user_restaurant(lonely)
        self.assertIsNone(restaurant)
        self.assertIsNone(role)

    def test_inactive_staff_ignored(self):
        staff_user = make_user('inactive@test.com', 'In', 'Active')
        StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='serveur', is_active=False
        )
        restaurant, role = get_user_restaurant(staff_user)
        self.assertIsNone(restaurant)
        self.assertIsNone(role)
```

- [ ] **Step 2 : Lancer le test — il doit échouer**

```bash
python manage.py test base.tests.GetUserRestaurantTest -v 1
```
Attendu : `ImportError` (`get_user_restaurant` n'existe pas encore).

- [ ] **Step 3 : Réécrire `base/decorators.py`**

```python
# base/decorators.py
from functools import wraps
from django.shortcuts import redirect
from base.models import Restaurant


def get_user_restaurant(user):
    """
    Returns (restaurant, role) for a Django User.
    role is 'owner' for restaurant owners, or the StaffMember role string.
    Returns (None, None) if the user has no associated restaurant.
    """
    if hasattr(user, 'staff_profile') and user.staff_profile.is_active:
        sp = user.staff_profile
        return sp.restaurant, sp.role
    restaurant = Restaurant.objects.filter(owner=user).first()
    if restaurant:
        return restaurant, 'owner'
    return None, None


def restaurant_required(allowed_roles=None):
    """
    Decorator that:
    1. Requires authentication (redirects to 'connexion' if not).
    2. Resolves (restaurant, role) via get_user_restaurant.
    3. Redirects to 'create_restaurant' if no restaurant found.
    4. Redirects to 'dashboard' if role not in allowed_roles (when specified).
    5. Sets request.restaurant and request.user_role for the view.

    Usage:
        @restaurant_required()                              # any role
        @restaurant_required(['owner', 'coadmin'])          # restricted
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('connexion')
            restaurant, role = get_user_restaurant(request.user)
            if not restaurant:
                return redirect('create_restaurant')
            if allowed_roles and role not in allowed_roles:
                return redirect('dashboard')
            request.restaurant = restaurant
            request.user_role = role
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def owner_or_coadmin_required(view_func):
    """Shortcut decorator for owner + coadmin only views."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('connexion')
        restaurant, role = get_user_restaurant(request.user)
        if not restaurant:
            return redirect('create_restaurant')
        if role not in ('owner', 'coadmin'):
            return redirect('dashboard')
        request.restaurant = restaurant
        request.user_role = role
        return view_func(request, *args, **kwargs)
    return wrapper
```

- [ ] **Step 4 : Lancer les tests**

```bash
python manage.py test base.tests.GetUserRestaurantTest -v 1
```
Attendu : `OK` (4 tests).

- [ ] **Step 5 : Commit**

```bash
git add base/decorators.py base/tests.py
git commit -m "feat: get_user_restaurant helper + restaurant_required decorator"
```

---

### Task 3: `base/emails.py` — envoi email invitation staff

**Files:**
- Create: `base/emails.py`

- [ ] **Step 1 : Écrire le test**

Ajouter dans `base/tests.py` :

```python
from django.test import override_settings
from django.core import mail
from base.emails import send_staff_invitation_email
from base.models import StaffInvitation


class StaffInvitationEmailTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner4@test.com', 'Owner', 'Four')
        self.restaurant = make_restaurant(self.owner)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sends_invitation_email(self):
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant,
            email='newstaff@test.com',
            role='cuisinier',
            created_by=self.owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        send_staff_invitation_email(base_url='http://testserver', invitation=inv)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('newstaff@test.com', mail.outbox[0].to)
        self.assertIn(str(inv.token), mail.outbox[0].body)
        self.assertIn(self.restaurant.name, mail.outbox[0].body)
```

- [ ] **Step 2 : Lancer le test — il doit échouer**

```bash
python manage.py test base.tests.StaffInvitationEmailTest -v 1
```
Attendu : `ImportError` (`send_staff_invitation_email` non définie).

- [ ] **Step 3 : Créer `base/emails.py`**

```python
# base/emails.py
from django.core.mail import send_mail
from django.conf import settings


def send_staff_invitation_email(base_url: str, invitation) -> None:
    """
    Send invitation email to invitation.email.
    base_url: scheme + host, e.g. 'https://app.openfood.com'
    """
    accept_url = f"{base_url}/equipe/accepter/{invitation.token}/"
    role_display = dict(invitation.restaurant.staff.model.ROLE_CHOICES).get(
        invitation.role, invitation.role
    )
    subject = f"Invitation à rejoindre {invitation.restaurant.name} sur OpenFood"
    message = f"""Bonjour,

{invitation.restaurant.name} vous invite à rejoindre leur équipe en tant que {role_display}.

Cliquez sur le lien ci-dessous pour créer votre compte (valable 7 jours) :
{accept_url}

Si vous avez déjà un compte OpenFood, connectez-vous puis cliquez sur ce lien.

— L'équipe OpenFood
"""
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )
```

- [ ] **Step 4 : Lancer le test**

```bash
python manage.py test base.tests.StaffInvitationEmailTest -v 1
```
Attendu : `OK` (1 test).

- [ ] **Step 5 : Commit**

```bash
git add base/emails.py base/tests.py
git commit -m "feat: send_staff_invitation_email helper"
```

---

### Task 4: Mise à jour de `accounts/views.py::connexion` — routing post-login par rôle

**Files:**
- Modify: `accounts/views.py` (fonction `connexion` uniquement)

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `base/tests.py` :

```python
from django.test import Client
from django.urls import reverse


class ConnectionRoutingTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = make_user('owner5@test.com', 'Owner', 'Five')
        self.restaurant = make_restaurant(self.owner)

    def _login(self, email, password='pass123'):
        return self.client.post(reverse('connexion'), {
            'email': email, 'password': password,
        })

    def test_owner_redirects_to_dashboard(self):
        resp = self._login('owner5@test.com')
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)

    def test_cuisinier_redirects_to_dashboard(self):
        chef_user = make_user('chef5@test.com', 'Chef', 'Five')
        StaffMember.objects.create(
            user=chef_user, restaurant=self.restaurant, role='cuisinier'
        )
        resp = self._login('chef5@test.com')
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)

    def test_no_restaurant_user_redirects_to_create(self):
        lonely = make_user('lonely5@test.com', 'Lonely', 'Five')
        resp = self._login('lonely5@test.com')
        self.assertRedirects(resp, reverse('create_restaurant'), fetch_redirect_response=False)
```

- [ ] **Step 2 : Lancer les tests — ils doivent échouer**

```bash
python manage.py test base.tests.ConnectionRoutingTest -v 1
```
Attendu : tests `test_cuisinier_redirects_to_dashboard` et `test_no_restaurant_user_redirects_to_create` échouent (redirection incorrecte).

- [ ] **Step 3 : Modifier `accounts/views.py::connexion`**

Remplacer les imports en haut du fichier pour ajouter :

```python
from base.decorators import get_user_restaurant
```

Remplacer la fonction `connexion` entière :

```python
def connexion(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Email ou mot de passe incorrect.")
            return redirect("connexion")

        if not user.email_verified:
            messages.error(
                request,
                "Votre email n'est pas encore vérifié. Vérifiez votre boîte mail."
            )
            return redirect("connexion")

        login(request, user)

        restaurant, role = get_user_restaurant(user)
        if restaurant:
            return redirect("dashboard")
        return redirect("create_restaurant")

    return render(request, "auth/connexion.html")
```

- [ ] **Step 4 : Lancer les tests**

```bash
python manage.py test base.tests.ConnectionRoutingTest -v 1
```
Attendu : `OK` (3 tests).

- [ ] **Step 5 : Commit**

```bash
git add accounts/views.py base/tests.py
git commit -m "feat: connexion routes to dashboard or create_restaurant based on user role"
```

---

### Task 5: Mise à jour de `base/views.py` — `get_user_restaurant` dans toutes les vues

**Files:**
- Modify: `base/views.py`

**But :** Remplacer les 17 occurrences de `Restaurant.objects.filter(owner=request.user).first()` et `request.user.restaurants.first()` par `get_user_restaurant(request.user)[0]`, et remplacer `@login_required` par `@restaurant_required()` (ou la variante avec rôles).

- [ ] **Step 1 : Écrire les tests d'accès**

Ajouter dans `base/tests.py` :

```python
class RoleAccessTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = make_user('owner6@test.com', 'Owner', 'Six')
        self.restaurant = make_restaurant(self.owner)
        self.chef_user = make_user('chef6@test.com', 'Chef', 'Six')
        self.chef = StaffMember.objects.create(
            user=self.chef_user, restaurant=self.restaurant, role='cuisinier'
        )
        self.server_user = make_user('server6@test.com', 'Server', 'Six')
        self.server = StaffMember.objects.create(
            user=self.server_user, restaurant=self.restaurant, role='serveur'
        )

    def test_cuisinier_cannot_access_tables(self):
        self.client.force_login(self.chef_user)
        resp = self.client.get(reverse('tables_list'))
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)

    def test_cuisinier_cannot_access_equipe(self):
        self.client.force_login(self.chef_user)
        resp = self.client.get(reverse('staff_list'))
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)

    def test_serveur_cannot_access_menus(self):
        self.client.force_login(self.server_user)
        resp = self.client.get(reverse('menus_list'))
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)

    def test_serveur_can_access_tables(self):
        self.client.force_login(self.server_user)
        resp = self.client.get(reverse('tables_list'))
        self.assertEqual(resp.status_code, 200)

    def test_owner_can_access_all(self):
        self.client.force_login(self.owner)
        for url_name in ['orders_list', 'menus_list', 'tables_list', 'staff_list']:
            resp = self.client.get(reverse(url_name))
            self.assertNotEqual(resp.status_code, 302, f"{url_name} returned redirect for owner")
```

- [ ] **Step 2 : Lancer — ils doivent échouer**

```bash
python manage.py test base.tests.RoleAccessTest -v 1
```
Attendu : les tests échouent (les vues n'utilisent pas encore `restaurant_required`).

- [ ] **Step 3 : Ajouter l'import dans `base/views.py`**

En haut de `base/views.py`, remplacer la ligne :
```python
from django.contrib.auth.decorators import login_required
```
par :
```python
from django.contrib.auth.decorators import login_required
from base.decorators import get_user_restaurant, restaurant_required, owner_or_coadmin_required
```

- [ ] **Step 4 : Modifier `check_new_orders` (ligne 53)**

```python
@login_required
def check_new_orders(request):
    restaurant, role = get_user_restaurant(request.user)

    if not restaurant:
        return JsonResponse({"latest_order_id": None, "error": "Restaurant not found"}, status=404)

    latest_order_in_db = Order.objects.filter(restaurant=restaurant).order_by('-created_at', '-id').first()
    # ... reste identique, utiliser `restaurant` au lieu de `Restaurant.objects.filter(owner=request.user).first()`
```

> Conserver le corps exact de la fonction, remplacer seulement la ligne de résolution du restaurant.

- [ ] **Step 5 : Modifier `dashboard` (ligne 141)**

```python
@login_required
def dashboard(request):
    user = request.user
    restaurant, role = get_user_restaurant(user)

    if not restaurant:
        return render(request, "admin_user/no_restaurant.html")

    # Le reste du contexte (stats, graphiques) reste identique
    # Passer `role` au template pour adapter l'affichage
    context = {
        # ... (toutes les clés existantes)
        "role": role,
        "restaurant": restaurant,
    }
    return render(request, "admin_user/index.html", context)
```

- [ ] **Step 6 : Remplacer le décorateur et la résolution restaurant dans TOUTES les vues suivantes**

Pour chaque vue ci-dessous, remplacer `@login_required` par le décorateur approprié **et** remplacer `Restaurant.objects.filter(owner=request.user).first()` (ou `request.user.restaurants.first()`) par `request.restaurant` (grâce au décorateur).

**Vues accessibles à tous les rôles :**
```python
@restaurant_required()     # remplace @login_required
def orders_list(request):
    restaurant = request.restaurant  # au lieu de Restaurant.objects.filter(...)

@restaurant_required()
def create_manual_order(request):
    restaurant = request.restaurant

@restaurant_required()
def update_order(request, order_id):
    restaurant = request.restaurant

@restaurant_required()
def delete_order(request, order_id):
    restaurant = request.restaurant

@restaurant_required()
def order_detail(request, pk):
    restaurant = request.restaurant
```

**Vues cuisinier + owner + coadmin (pas serveur) :**
```python
@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menus_list(request):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_create(request):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_update(request, pk):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def change_menu_status(request, pk):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_delete(request, pk):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def create_category(request):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def create_category_modale(request):
    restaurant = request.restaurant
```

**Vues serveur + owner + coadmin (pas cuisinier) :**
```python
@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def tables_list(request):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def table_create(request):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def table_delete(request, table_id):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def table_toggle_active(request, table_id):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def table_regenerate_qr(request, table_id):
    restaurant = request.restaurant

@restaurant_required(allowed_roles=['owner', 'coadmin', 'serveur'])
def table_update(request, table_id):
    restaurant = request.restaurant
```

**Vues owner + coadmin seulement :**
```python
@owner_or_coadmin_required
def customization(request):
    restaurant = request.restaurant

@owner_or_coadmin_required
def reset_customization(request):
    restaurant = request.restaurant

@owner_or_coadmin_required
def restaurant_settings(request):
    restaurant = request.restaurant
```

- [ ] **Step 7 : Mettre à jour `order_change_status` — ajouter logique rôle + `preparing_by_name`**

```python
COOK_STATUSES = {'preparing', 'ready', 'cancelled'}
SERVER_STATUSES = {'delivered'}
OWNER_STATUSES = {s[0] for s in Order.STATUS_CHOICES}

@restaurant_required()
def order_change_status(request, pk):
    restaurant = request.restaurant
    role = request.user_role
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)
    new_status = request.POST.get("status")

    # Determine allowed statuses by role
    if role in ('owner', 'coadmin'):
        allowed = OWNER_STATUSES
    elif role == 'cuisinier':
        allowed = COOK_STATUSES
    elif role == 'serveur':
        allowed = SERVER_STATUSES
    else:
        allowed = set()

    if new_status not in allowed:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Action non autorisée.'}, status=403)
        messages.error(request, "Action non autorisée.")
        return redirect("orders_list")

    update_fields = ['status']
    order.status = new_status

    if new_status == 'preparing':
        order.preparing_by_name = request.user.get_full_name()
        update_fields.append('preparing_by_name')
    elif new_status in ('ready', 'delivered', 'cancelled'):
        order.preparing_by_name = ''
        update_fields.append('preparing_by_name')

    order.save(update_fields=update_fields)
    status_display = dict(Order.STATUS_CHOICES).get(new_status, new_status)

    if is_ajax:
        return JsonResponse({'ok': True, 'status': new_status, 'status_display': status_display})

    messages.success(request, f"Commande #{order.order_number} → {status_display}")
    return redirect("orders_list")
```

- [ ] **Step 8 : Lancer les tests**

```bash
python manage.py test base.tests.RoleAccessTest base.tests.ConnectionRoutingTest -v 1
```
Attendu : `OK`.

- [ ] **Step 9 : Vérifier qu'aucune régression globale**

```bash
python manage.py check
python manage.py test base -v 1
```

- [ ] **Step 10 : Commit**

```bash
git add base/views.py
git commit -m "feat: replace login_required with restaurant_required + role-based view access"
```

---

### Task 6: Invitation views — `base/staff_admin_views.py`

**Files:**
- Rewrite: `base/staff_admin_views.py`

- [ ] **Step 1 : Écrire les tests**

Ajouter dans `base/tests.py` :

```python
from django.core import mail as django_mail


class InvitationViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = make_user('owner7@test.com', 'Owner', 'Seven')
        self.restaurant = make_restaurant(self.owner)
        self.client.force_login(self.owner)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_send_invitation_creates_invitation_and_sends_email(self):
        resp = self.client.post(reverse('staff_invite'), {
            'email': 'newchef@test.com',
            'role': 'cuisinier',
        })
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertEqual(StaffInvitation.objects.count(), 1)
        self.assertEqual(len(django_mail.outbox), 1)
        self.assertIn('newchef@test.com', django_mail.outbox[0].to)

    def test_accept_invitation_new_user(self):
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant, email='brand@new.com', role='serveur',
            created_by=self.owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        self.client.logout()
        resp = self.client.post(reverse('staff_invite_accept', args=[inv.token]), {
            'first_name': 'Brand',
            'last_name': 'New',
            'password': 'securepass123',
        })
        self.assertRedirects(resp, reverse('connexion'), fetch_redirect_response=False)
        new_user = User.objects.get(email='brand@new.com')
        self.assertTrue(new_user.email_verified)
        self.assertTrue(StaffMember.objects.filter(user=new_user).exists())
        inv.refresh_from_db()
        self.assertTrue(inv.accepted)

    def test_accept_invitation_existing_logged_in_user(self):
        existing = make_user('existing@test.com', 'Ex', 'Isting')
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant, email='existing@test.com', role='cuisinier',
            created_by=self.owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        self.client.force_login(existing)
        resp = self.client.get(reverse('staff_invite_accept', args=[inv.token]))
        self.assertRedirects(resp, reverse('dashboard'), fetch_redirect_response=False)
        self.assertTrue(StaffMember.objects.filter(user=existing).exists())
        inv.refresh_from_db()
        self.assertTrue(inv.accepted)

    def test_expired_token_shows_error(self):
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant, email='exp@test.com', role='cuisinier',
            created_by=self.owner,
            expires_at=timezone.now() - timezone.timedelta(seconds=1),
        )
        self.client.logout()
        resp = self.client.get(reverse('staff_invite_accept', args=[inv.token]))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'expir')

    def test_owner_can_delete_staff(self):
        staff_user = make_user('deleteme@test.com', 'Del', 'Me')
        sm = StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='cuisinier'
        )
        resp = self.client.post(reverse('staff_delete', args=[sm.pk]))
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertFalse(StaffMember.objects.filter(pk=sm.pk).exists())

    def test_coadmin_cannot_delete_owner_staff(self):
        coadmin_user = make_user('coadmin7@test.com', 'Co', 'Admin')
        StaffMember.objects.create(
            user=coadmin_user, restaurant=self.restaurant, role='coadmin'
        )
        other_coadmin_user = make_user('coadmin7b@test.com', 'Co', 'Admin2')
        other_sm = StaffMember.objects.create(
            user=other_coadmin_user, restaurant=self.restaurant, role='coadmin'
        )
        self.client.force_login(coadmin_user)
        resp = self.client.post(reverse('staff_delete', args=[other_sm.pk]))
        # coadmin cannot delete another coadmin
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertTrue(StaffMember.objects.filter(pk=other_sm.pk).exists())
```

- [ ] **Step 2 : Lancer les tests — ils doivent échouer**

```bash
python manage.py test base.tests.InvitationViewTest -v 1
```
Attendu : `ImportError` ou 404 (vues pas encore écrites / URLs pas encore définies).

- [ ] **Step 3 : Réécrire `base/staff_admin_views.py`**

```python
# base/staff_admin_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model

from base.models import StaffMember, StaffInvitation
from base.decorators import owner_or_coadmin_required, get_user_restaurant
from base.emails import send_staff_invitation_email

User = get_user_model()


@owner_or_coadmin_required
def staff_list(request):
    restaurant = request.restaurant
    members = StaffMember.objects.filter(restaurant=restaurant).select_related('user').order_by('role')
    pending_invitations = StaffInvitation.objects.filter(
        restaurant=restaurant, accepted=False,
        expires_at__gt=timezone.now(),
    ).order_by('-id')
    return render(request, 'admin_user/staff/list.html', {
        'members': members,
        'pending_invitations': pending_invitations,
        'restaurant': restaurant,
        'is_owner': request.user_role == 'owner',
    })


@owner_or_coadmin_required
def staff_invite(request):
    if request.method != 'POST':
        return redirect('staff_list')

    restaurant = request.restaurant
    email = request.POST.get('email', '').strip().lower()
    role = request.POST.get('role', '')

    valid_roles = [r[0] for r in StaffMember.ROLE_CHOICES]
    if role not in valid_roles:
        messages.error(request, "Rôle invalide.")
        return redirect('staff_list')

    # Coadmin cannot invite another coadmin
    if request.user_role == 'coadmin' and role == 'coadmin':
        messages.error(request, "Un co-administrateur ne peut pas inviter un autre co-administrateur.")
        return redirect('staff_list')

    if not email:
        messages.error(request, "Email requis.")
        return redirect('staff_list')

    # Already a staff member in this restaurant?
    if StaffMember.objects.filter(restaurant=restaurant, user__email=email).exists():
        messages.error(request, "Cette personne fait déjà partie de l'équipe.")
        return redirect('staff_list')

    # If user already exists in the system, just create StaffMember directly and send notification
    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        StaffMember.objects.create(
            user=existing_user, restaurant=restaurant, role=role
        )
        messages.success(request, f"{existing_user.get_full_name()} a été ajouté(e) à l'équipe.")
        return redirect('staff_list')

    # New user: create invitation
    invitation = StaffInvitation.objects.create(
        restaurant=restaurant,
        email=email,
        role=role,
        created_by=request.user,
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    base_url = request.build_absolute_uri('/').rstrip('/')
    send_staff_invitation_email(base_url=base_url, invitation=invitation)
    messages.success(request, f"Invitation envoyée à {email}.")
    return redirect('staff_list')


def staff_invite_accept(request, token):
    """Public view (no login required). Handles invitation acceptance."""
    invitation = get_object_or_404(StaffInvitation, token=token)

    if not invitation.is_valid():
        return render(request, 'admin_user/staff/invite_accept.html', {
            'error': "Cette invitation a expiré ou a déjà été utilisée.",
        })

    # Case: user already logged in
    if request.user.is_authenticated:
        if request.user.email.lower() != invitation.email.lower():
            return render(request, 'admin_user/staff/invite_accept.html', {
                'error': "Vous êtes connecté avec un email différent de celui de l'invitation.",
                'invitation': invitation,
            })
        # Accept directly
        StaffMember.objects.get_or_create(
            user=request.user,
            restaurant=invitation.restaurant,
            defaults={'role': invitation.role},
        )
        invitation.accepted = True
        invitation.save(update_fields=['accepted'])
        messages.success(request, f"Vous avez rejoint l'équipe de {invitation.restaurant.name}.")
        return redirect('dashboard')

    # Case: user not logged in, existing account
    if User.objects.filter(email=invitation.email).exists():
        messages.info(request, "Connectez-vous pour rejoindre l'équipe.")
        return redirect(f"/connexion/?next=/equipe/accepter/{token}/")

    # Case: new user — show registration form
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '')

        if not first_name or not last_name or not password:
            return render(request, 'admin_user/staff/invite_accept.html', {
                'invitation': invitation,
                'error': "Tous les champs sont requis.",
            })

        new_user = User.objects.create_user(
            email=invitation.email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email_verified=True,  # validated by admin invitation
        )
        StaffMember.objects.create(
            user=new_user, restaurant=invitation.restaurant, role=invitation.role
        )
        invitation.accepted = True
        invitation.save(update_fields=['accepted'])
        messages.success(request, "Compte créé ! Connectez-vous pour accéder à votre espace.")
        return redirect('connexion')

    return render(request, 'admin_user/staff/invite_accept.html', {
        'invitation': invitation,
    })


@owner_or_coadmin_required
def staff_delete(request, pk):
    if request.method != 'POST':
        return redirect('staff_list')

    restaurant = request.restaurant
    member = get_object_or_404(StaffMember, pk=pk, restaurant=restaurant)

    # Coadmin cannot delete another coadmin
    if request.user_role == 'coadmin' and member.role == 'coadmin':
        messages.error(request, "Un co-administrateur ne peut pas supprimer un autre co-administrateur.")
        return redirect('staff_list')

    name = member.get_full_name()
    member.delete()
    messages.success(request, f"{name} a été retiré(e) de l'équipe.")
    return redirect('staff_list')
```

- [ ] **Step 4 : Lancer les tests (avec URLs déjà définies — cf. Task 7)**

```bash
python manage.py test base.tests.InvitationViewTest -v 1
```
Attendu : `OK` (6 tests).

- [ ] **Step 5 : Commit**

```bash
git add base/staff_admin_views.py base/tests.py
git commit -m "feat: staff invitation views (invite, accept, delete, list)"
```

---

### Task 7: Mise à jour des URLs — `base/urls.py` et `main/urls.py`

**Files:**
- Modify: `base/urls.py`
- Modify: `main/urls.py`

- [ ] **Step 1 : Mettre à jour `base/urls.py`**

Remplacer la section "Équipe" et les imports :

```python
from django import views
from django.urls import path
from base.views import *
from base import staff_admin_views

urlpatterns = [
    path('', home, name="home"),

    path("restaurant/create/", create_restaurant, name="create_restaurant"),
    path("dashboard/", dashboard, name="dashboard"),

    # Commandes
    path("orders/check/", check_new_orders, name="check_new_orders"),
    path("orders/", orders_list, name="orders_list"),
    path("orders/create-manual-order/", create_manual_order, name="create_manual_order"),
    path("orders/<int:pk>/", order_detail, name="order_detail"),
    path('orders/<int:order_id>/update/', update_order, name='update_order'),
    path('orders/<int:order_id>/delete/', delete_order, name='delete_order'),
    path("orders/<int:pk>/change-status/", order_change_status, name="order_change_status"),

    # Catégories
    path("categories/create/", create_category, name="create_category"),
    path("categories/create/modale/", create_category_modale, name="create_category_modale"),

    # Menus
    path("menus/", menus_list, name="menus_list"),
    path("menus/<int:pk>/update/", menu_update, name="menu_update"),
    path("menus/<int:pk>/delete/", menu_delete, name="menu_delete"),
    path("menus/create/", menu_create, name="menu_create"),
    path("menus/<int:pk>/change-availability/", change_menu_status, name="menu_toggle_availability"),

    # Tables
    path("tables/", tables_list, name="tables_list"),
    path("tables/create/", table_create, name="table_create"),
    path("tables/<int:table_id>/delete/", table_delete, name="table_delete"),
    path("tables/<int:table_id>/toggle_active/", table_toggle_active, name="table_toggle_active"),
    path("tables/<int:table_id>/regenerate_qr/", table_regenerate_qr, name="table_regenerate_qr"),
    path("tables/<int:table_id>/update/", table_update, name="table_update"),

    # Personnalisation
    path("customization/", customization, name="customization"),
    path("customization/reset/", reset_customization, name="reset_customization"),

    # Paramètres restaurant
    path("settings/", restaurant_settings, name="restaurant_settings"),

    # PWA
    path("manifest/<slug:slug>.json", pwa_manifest, name="pwa_manifest"),

    # Équipe (staff management — invitation flow)
    path('equipe/', staff_admin_views.staff_list, name='staff_list'),
    path('equipe/inviter/', staff_admin_views.staff_invite, name='staff_invite'),
    path('equipe/accepter/<uuid:token>/', staff_admin_views.staff_invite_accept, name='staff_invite_accept'),
    path('equipe/<int:pk>/supprimer/', staff_admin_views.staff_delete, name='staff_delete'),
]
```

- [ ] **Step 2 : Mettre à jour `main/urls.py`**

Supprimer la ligne `path('staff/', include('base.staff_urls'))` :

```python
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('robots.txt', TemplateView.as_view(template_name='robots.txt', content_type='text/plain')),
    path('llms.txt', TemplateView.as_view(template_name='llms.txt', content_type='text/plain')),
    path('', include('accounts.urls')),
    path('', include('base.urls')),
    path('', include('customer.urls')),
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

- [ ] **Step 3 : Vérifier que le système démarre**

```bash
python manage.py check
```
Attendu : `System check identified no issues (0 silenced).`

- [ ] **Step 4 : Lancer tous les tests**

```bash
python manage.py test base -v 1
```
Attendu : `OK`.

- [ ] **Step 5 : Commit**

```bash
git add base/urls.py main/urls.py
git commit -m "feat: update URLs — invitation routes, remove staff session URLs"
```

---

### Task 8: Templates admin — sidebar et bottom nav filtrés par rôle

**Files:**
- Modify: `templates/admin_user/sidebar.html`
- Modify: `templates/admin_user/base.html`

**Contexte :** Le `role` doit être disponible dans tous les templates admin. La façon la plus propre est un **context processor** qui injecte `user_role` et `restaurant` automatiquement dans tout template.

- [ ] **Step 1 : Créer `base/context_processors.py`**

```python
# base/context_processors.py
from base.decorators import get_user_restaurant


def restaurant_context(request):
    """
    Injects `restaurant` and `user_role` into every template context
    for authenticated users with a restaurant.
    """
    if not request.user.is_authenticated:
        return {}
    restaurant, role = get_user_restaurant(request.user)
    return {
        'restaurant': restaurant,
        'user_role': role,
    }
```

- [ ] **Step 2 : Enregistrer le context processor dans `settings.py`**

Dans `TEMPLATES[0]['OPTIONS']['context_processors']`, ajouter :
```python
'base.context_processors.restaurant_context',
```

La liste complète doit ressembler à :
```python
'context_processors': [
    'django.template.context_processors.debug',
    'django.template.context_processors.request',
    'django.contrib.auth.context_processors.auth',
    'django.contrib.messages.context_processors.messages',
    'base.context_processors.restaurant_context',
],
```

- [ ] **Step 3 : Mettre à jour `templates/admin_user/sidebar.html`**

Remplacer le contenu entier du fichier par :

```html
{% url 'dashboard'           as url_dashboard %}
{% url 'orders_list'         as url_orders    %}
{% url 'menus_list'          as url_menus     %}
{% url 'tables_list'         as url_tables    %}
{% url 'customization'       as url_custom    %}
{% url 'restaurant_settings' as url_settings  %}
{% url 'staff_list'          as url_staff     %}

{% with current=request.path %}

<!-- Tableau de bord — tous les rôles -->
<a href="{{ url_dashboard }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_dashboard %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-dashboard-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Tableau de bord
  </span>
</a>

<!-- Commandes — tous les rôles -->
<a href="{{ url_orders }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_orders %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-shopping-bag-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Commandes
  </span>
</a>

<!-- Menu — owner, coadmin, cuisinier -->
{% if user_role in 'owner,coadmin,cuisinier' or not user_role %}
<a href="{{ url_menus }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_menus %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-restaurant-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Menu
  </span>
</a>
{% endif %}

<!-- Tables — owner, coadmin, serveur -->
{% if user_role in 'owner,coadmin,serveur' or not user_role %}
<a href="{{ url_tables }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_tables %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-table-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Tables
  </span>
</a>
{% endif %}

<!-- Personnalisation, Équipe, Paramètres — owner + coadmin uniquement -->
{% if user_role == 'owner' or user_role == 'coadmin' or not user_role %}

<a href="{{ url_custom }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_custom %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-palette-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Personnalisation
  </span>
</a>

<a href="{{ url_staff }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_staff %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-team-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Équipe
  </span>
</a>

<a href="{{ url_settings }}"
   class="group flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150
          {% if current == url_settings %}bg-primary text-white shadow-glow{% else %}text-slate-400 hover:bg-white/8 hover:text-white{% endif %}">
  <i class="ri-settings-3-line text-lg flex-shrink-0"></i>
  <span class="truncate" x-show="sidebarOpen !== false"
        x-transition:enter="transition duration-150" x-transition:enter-start="opacity-0" x-transition:enter-end="opacity-100">
    Paramètres
  </span>
</a>

{% endif %}

{% endwith %}
```

> **Note :** Le filtre `in` de Django compare si une chaîne est une sous-chaîne. Utiliser `{% if user_role == 'owner' or user_role == 'coadmin' or user_role == 'cuisinier' %}` au lieu de `in 'owner,coadmin,...'` pour être explicite et sûr.

- [ ] **Step 4 : Corriger le sidebar — utiliser des conditions `or` explicites**

Le `{% if user_role in 'owner,coadmin,cuisinier' %}` de Django fonctionne comme `'owner' in 'owner,coadmin,cuisinier'` (substring check), ce qui marche accidentellement. Utiliser la forme correcte :

```html
{% if user_role == 'owner' or user_role == 'coadmin' or user_role == 'cuisinier' %}
```
pour le bloc Menu, et :
```html
{% if user_role == 'owner' or user_role == 'coadmin' or user_role == 'serveur' %}
```
pour le bloc Tables.

Appliquer cette correction dans le fichier créé au Step 3.

- [ ] **Step 5 : Mettre à jour le bottom nav dans `templates/admin_user/base.html`**

Dans la section bottom nav (environ ligne 204), remplacer les entrées Menu, Tables, Personnalisation, Équipe, Paramètres par des versions conditionnelles. Conserver le même pattern de classe que l'existant :

```html
{% url 'staff_list' as url_staff %}

<!-- Menu — owner, coadmin, cuisinier -->
{% if user_role == 'owner' or user_role == 'coadmin' or user_role == 'cuisinier' %}
<a href="{{ url_menus }}" class="flex flex-col items-center justify-center gap-1 transition-colors
          {% if current == url_menus %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}">
  <div class="relative w-7 h-7 flex items-center justify-center">
    {% if current == url_menus %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
    <i class="ri-restaurant-line text-[1.15rem] leading-none relative"></i>
  </div>
  <span class="text-[9.5px] font-semibold leading-none">Menu</span>
</a>
{% endif %}

<!-- Tables — owner, coadmin, serveur -->
{% if user_role == 'owner' or user_role == 'coadmin' or user_role == 'serveur' %}
<a href="{{ url_tables }}" class="flex flex-col items-center justify-center gap-1 transition-colors
          {% if current == url_tables %}text-primary{% else %}text-slate-400 active:text-primary{% endif %}">
  <div class="relative w-7 h-7 flex items-center justify-center">
    {% if current == url_tables %}<span class="absolute inset-0 bg-primary/10 rounded-xl"></span>{% endif %}
    <i class="ri-table-line text-[1.15rem] leading-none relative"></i>
  </div>
  <span class="text-[9.5px] font-semibold leading-none">Tables</span>
</a>
{% endif %}
```

Faire de même pour Personnalisation, Équipe, Paramètres — uniquement si `user_role == 'owner' or user_role == 'coadmin'`.

Changer `grid-cols-7` en `grid-cols-5` (le nombre de colonnes dépend du rôle) — ou garder `grid-cols-7` et laisser les éléments manquants se rétracte naturellement. Le plus propre : conserver une grille fixe adaptée au rôle avec un `{% if %}` sur la grille entière. Pour simplifier, utiliser `grid-cols-5` comme base (tous les rôles voient au moins : Dashboard, Commandes, + 3 variables).

- [ ] **Step 6 : Vérifier visuellement**

```bash
python manage.py runserver
```

Se connecter en tant que cuisinier et vérifier que le sidebar ne montre que : Dashboard, Commandes, Menu.

- [ ] **Step 7 : Commit**

```bash
git add base/context_processors.py templates/admin_user/sidebar.html templates/admin_user/base.html
git commit -m "feat: role-based sidebar and bottom nav"
```

---

### Task 9: Templates staff management — liste + formulaire d'invitation + page d'acceptation

**Files:**
- Rewrite: `templates/admin_user/staff/list.html`
- Create: `templates/admin_user/staff/invite_accept.html`

- [ ] **Step 1 : Réécrire `templates/admin_user/staff/list.html`**

```html
{% extends "admin_user/base.html" %}
{% block title %}Équipe{% endblock %}
{% block page_title %}Équipe{% endblock %}

{% block content %}

<!-- Formulaire d'invitation -->
<div class="bg-white rounded-2xl border border-slate-100 shadow-soft overflow-hidden mb-6">
  <div class="px-5 py-4 border-b border-slate-100 flex items-center gap-2.5">
    <div class="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
      <i class="ri-user-add-line text-primary text-sm"></i>
    </div>
    <h2 class="font-display font-black text-slate-900 text-sm">Inviter un membre</h2>
  </div>
  <form method="post" action="{% url 'staff_invite' %}" class="p-5">
    {% csrf_token %}
    <div class="grid sm:grid-cols-3 gap-3">
      <div class="sm:col-span-2">
        <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Email</label>
        <input type="email" name="email" required placeholder="colleague@email.com"
               class="w-full px-4 py-2.5 text-sm bg-white border border-slate-200 rounded-xl transition-all focus:outline-none focus:border-primary">
      </div>
      <div>
        <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Rôle</label>
        <select name="role"
                class="w-full px-4 py-2.5 text-sm bg-white border border-slate-200 rounded-xl transition-all focus:outline-none focus:border-primary appearance-none">
          {% if is_owner %}
          <option value="coadmin">Co-administrateur</option>
          {% endif %}
          <option value="cuisinier">Cuisinier</option>
          <option value="serveur">Serveur</option>
        </select>
      </div>
    </div>
    <div class="mt-3">
      <button type="submit"
              class="px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-bold shadow-glow hover:bg-primary-dark transition-all">
        <i class="ri-send-plane-line mr-2"></i>Envoyer l'invitation
      </button>
    </div>
  </form>
</div>

<!-- Invitations en attente -->
{% if pending_invitations %}
<div class="bg-amber-50 rounded-2xl border border-amber-100 overflow-hidden mb-6">
  <div class="px-5 py-3 border-b border-amber-100 flex items-center gap-2">
    <i class="ri-time-line text-amber-500 text-sm"></i>
    <h3 class="text-sm font-semibold text-amber-800">Invitations en attente</h3>
  </div>
  <div class="divide-y divide-amber-100">
    {% for inv in pending_invitations %}
    <div class="px-5 py-3 flex items-center justify-between">
      <div>
        <p class="text-sm font-medium text-slate-800">{{ inv.email }}</p>
        <p class="text-xs text-slate-500">{{ inv.get_role_display }} · expire {{ inv.expires_at|date:"d/m/Y" }}</p>
      </div>
      <span class="text-[10px] font-bold uppercase tracking-widest px-2 py-1 bg-amber-100 text-amber-700 rounded-lg">En attente</span>
    </div>
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- Membres actifs -->
{% if members %}
<div class="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
  {% for m in members %}
  <div class="bg-white rounded-2xl border border-slate-100 shadow-soft overflow-hidden">
    <div class="px-5 py-4 flex items-center gap-3 border-b border-slate-50">
      <div class="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0 font-bold text-sm
        {% if m.role == 'cuisinier' %}bg-orange-50 text-primary
        {% elif m.role == 'serveur' %}bg-blue-50 text-blue-600
        {% else %}bg-violet-50 text-violet-600{% endif %}">
        {{ m.user.first_name|first|upper }}{{ m.user.last_name|first|upper }}
      </div>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold text-slate-900 truncate">{{ m.get_full_name }}</p>
        <p class="text-xs text-slate-400 truncate">{{ m.user.email }}</p>
      </div>
      {% if m.is_active %}
      <span class="w-2 h-2 rounded-full bg-green-400 flex-shrink-0" title="Actif"></span>
      {% else %}
      <span class="w-2 h-2 rounded-full bg-slate-300 flex-shrink-0" title="Inactif"></span>
      {% endif %}
    </div>
    <div class="px-5 py-3 flex items-center justify-between">
      <span class="px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-widest
        {% if m.role == 'cuisinier' %}bg-orange-50 text-primary border border-orange-100
        {% elif m.role == 'serveur' %}bg-blue-50 text-blue-600 border border-blue-100
        {% else %}bg-violet-50 text-violet-600 border border-violet-100{% endif %}">
        {{ m.get_role_display }}
      </span>
      {% if is_owner or m.role != 'coadmin' %}
      <form method="post" action="{% url 'staff_delete' m.pk %}" onsubmit="return confirm('Retirer {{ m.get_full_name|escapejs }} de l\'équipe ?')">
        {% csrf_token %}
        <button type="submit"
                class="p-2 rounded-xl text-slate-400 hover:text-red-500 hover:bg-red-50 transition-colors"
                title="Retirer">
          <i class="ri-user-unfollow-line text-sm"></i>
        </button>
      </form>
      {% endif %}
    </div>
  </div>
  {% endfor %}
</div>

{% else %}
<div class="flex flex-col items-center justify-center py-20 text-center">
  <div class="w-16 h-16 rounded-2xl bg-slate-100 flex items-center justify-center mb-4">
    <i class="ri-team-line text-2xl text-slate-400"></i>
  </div>
  <p class="text-slate-600 font-semibold">Aucun membre dans l'équipe</p>
  <p class="text-slate-400 text-sm mt-1">Invitez vos cuisiniers et serveurs par email ci-dessus.</p>
</div>
{% endif %}

{% endblock %}
```

- [ ] **Step 2 : Créer `templates/admin_user/staff/invite_accept.html`**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Rejoindre l'équipe – OpenFood</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://cdn.jsdelivr.net/npm/remixicon@4.2.0/fonts/remixicon.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Syne:wght@700;800;900&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      theme: {
        extend: {
          colors: { primary: { DEFAULT: '#f97316', dark: '#ea580c' } },
          fontFamily: {
            display: ['Syne', 'system-ui', 'sans-serif'],
            sans: ['DM Sans', 'system-ui', 'sans-serif'],
          },
        }
      }
    }
  </script>
  <style>
    .font-display { font-family: 'Syne', system-ui, sans-serif; }
    .field { @apply w-full px-4 py-3 text-sm bg-slate-50 border border-slate-200 rounded-xl transition-all focus:outline-none focus:border-primary; }
  </style>
</head>
<body class="min-h-screen bg-slate-50 flex items-center justify-center px-4 font-sans">
  <div class="w-full max-w-md">

    <!-- Logo -->
    <div class="flex justify-center mb-8">
      <a href="/" class="inline-flex items-center gap-2">
        <div class="w-9 h-9 rounded-xl bg-primary flex items-center justify-center">
          <i class="ri-restaurant-2-line text-white"></i>
        </div>
        <span class="font-display font-black text-slate-900 text-xl">Open<span class="text-primary">Food</span></span>
      </a>
    </div>

    {% if error %}
    <!-- Error state -->
    <div class="bg-white rounded-3xl border border-slate-100 shadow-sm p-8 text-center">
      <div class="w-14 h-14 rounded-2xl bg-red-50 flex items-center justify-center mx-auto mb-4">
        <i class="ri-error-warning-line text-red-500 text-2xl"></i>
      </div>
      <h1 class="font-display font-black text-slate-900 text-xl mb-2">Invitation invalide</h1>
      <p class="text-slate-500 text-sm mb-6">{{ error }}</p>
      <a href="{% url 'connexion' %}"
         class="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-primary text-white text-sm font-bold">
        <i class="ri-login-box-line"></i>Se connecter
      </a>
    </div>

    {% elif invitation %}
    <!-- Registration form for new user -->
    <div class="bg-white rounded-3xl border border-slate-100 shadow-sm overflow-hidden">
      <div class="bg-primary/5 border-b border-primary/10 px-7 py-5 text-center">
        <p class="text-xs font-semibold text-primary uppercase tracking-widest mb-1">Invitation</p>
        <h1 class="font-display font-black text-slate-900 text-xl">
          Rejoignez {{ invitation.restaurant.name }}
        </h1>
        <p class="text-slate-500 text-sm mt-1">
          Rôle : <span class="font-semibold text-slate-700">{{ invitation.get_role_display }}</span>
        </p>
      </div>

      <form method="post" class="p-7 space-y-4">
        {% csrf_token %}

        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Prénom</label>
            <input type="text" name="first_name" required class="field" placeholder="Jean">
          </div>
          <div>
            <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Nom</label>
            <input type="text" name="last_name" required class="field" placeholder="Dupont">
          </div>
        </div>

        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Email</label>
          <input type="email" value="{{ invitation.email }}" disabled
                 class="w-full px-4 py-3 text-sm bg-slate-100 border border-slate-200 rounded-xl text-slate-500 cursor-not-allowed">
        </div>

        <div>
          <label class="block text-[10px] font-semibold text-slate-400 uppercase tracking-wide mb-1.5">Choisissez un mot de passe</label>
          <input type="password" name="password" required minlength="8" class="field" placeholder="••••••••">
        </div>

        <button type="submit"
                class="w-full py-3.5 rounded-2xl bg-primary text-white text-sm font-bold shadow-[0_4px_16px_rgba(249,115,22,.3)] hover:bg-primary-dark transition-all">
          <i class="ri-team-line mr-2"></i>Créer mon compte et rejoindre l'équipe
        </button>
      </form>
    </div>

    {% endif %}
  </div>
</body>
</html>
```

- [ ] **Step 3 : Vérifier la page d'acceptation via le navigateur**

```bash
python manage.py runserver
```

Créer manuellement une invitation via le shell Django :
```python
# python manage.py shell
from django.utils import timezone
from base.models import StaffInvitation, Restaurant
from accounts.models import User

owner = User.objects.first()
resto = Restaurant.objects.first()
inv = StaffInvitation.objects.create(
    restaurant=resto, email='test@accept.com', role='cuisinier',
    created_by=owner, expires_at=timezone.now() + timezone.timedelta(days=7)
)
print(f"/equipe/accepter/{inv.token}/")
```

Visiter l'URL dans le navigateur (non connecté) et vérifier que le formulaire s'affiche correctement.

- [ ] **Step 4 : Commit**

```bash
git add templates/admin_user/staff/
git commit -m "feat: staff management templates (invite form, member list, accept page)"
```

---

### Task 10: Mettre à jour `templates/auth/connexion.html` et gérer le `?next` pour l'invitation

**Files:**
- Modify: `templates/auth/connexion.html`
- Modify: `accounts/views.py` (gérer le `?next` param)

- [ ] **Step 1 : Supprimer le lien "Connexion espace staff" de `connexion.html`**

Retirer le bloc ajouté précédemment :
```html
<!-- Staff portal link -->
<div class="mt-6 text-center">
  <a href="{% url 'staff_login' %}" ...>Connexion espace staff</a>
</div>
```

- [ ] **Step 2 : Gérer le `?next` dans `accounts/views.py::connexion`**

Remplacer le redirect post-login pour prendre en compte un `?next` passé par l'invitation :

```python
def connexion(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Email ou mot de passe incorrect.")
            return redirect("connexion")

        if not user.email_verified:
            messages.error(request, "Votre email n'est pas encore vérifié. Vérifiez votre boîte mail.")
            return redirect("connexion")

        login(request, user)

        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        restaurant, role = get_user_restaurant(user)
        if restaurant:
            return redirect("dashboard")
        return redirect("create_restaurant")

    next_url = request.GET.get('next', '')
    return render(request, "auth/connexion.html", {'next': next_url})
```

- [ ] **Step 3 : Ajouter le champ `next` caché dans `templates/auth/connexion.html`**

Dans le formulaire de connexion, ajouter après `{% csrf_token %}` :
```html
{% if next %}<input type="hidden" name="next" value="{{ next }}">{% endif %}
```

- [ ] **Step 4 : Tester le flow complet d'invitation**

Scénario :
1. Admin invite `existing@test.com` via la page Équipe
2. L'utilisateur existant clique sur le lien d'invitation → redirigé vers `/connexion/?next=/equipe/accepter/<token>/`
3. Il se connecte → redirigé vers `/equipe/accepter/<token>/`
4. Vue `staff_invite_accept` : user connecté + bon email → StaffMember créé → redirect dashboard

```bash
python manage.py test base.tests.InvitationViewTest -v 1
```
Attendu : `OK`.

- [ ] **Step 5 : Commit**

```bash
git add templates/auth/connexion.html accounts/views.py
git commit -m "feat: connexion handles ?next for invitation flow, remove staff portal link"
```

---

### Task 11: Cleanup — supprimer les fichiers de l'ancien portail staff

**Files:**
- Delete: `base/staff_views.py`
- Delete: `base/staff_urls.py`
- Delete: `base/staff_forms.py`
- Delete: `templates/staff/` (répertoire entier)
- Delete: `templates/admin_user/staff/create.html` (création via invitation désormais)
- Delete: `templates/admin_user/staff/update.html` (profil géré par l'user lui-même)

- [ ] **Step 1 : Supprimer les fichiers**

```bash
rm "/home/jey/Documents/projet /OpendFood/base/staff_views.py"
rm "/home/jey/Documents/projet /OpendFood/base/staff_urls.py"
rm "/home/jey/Documents/projet /OpendFood/base/staff_forms.py"
rm -r "/home/jey/Documents/projet /OpendFood/templates/staff/"
rm "/home/jey/Documents/projet /OpendFood/templates/admin_user/staff/create.html"
rm "/home/jey/Documents/projet /OpendFood/templates/admin_user/staff/update.html"
```

- [ ] **Step 2 : Vérifier qu'aucun import ne référence ces fichiers**

```bash
cd "/home/jey/Documents/projet /OpendFood"
grep -rn "staff_views\|staff_urls\|staff_forms\|StaffLoginForm\|StaffMemberForm\|staff_login\|staff_logout\|staff_orders\|staff_change_status\|staff_check_updates" --include="*.py" .
```
Attendu : aucune ligne (tous les imports sont supprimés).

- [ ] **Step 3 : Vérifier les templates**

```bash
grep -rn "staff_login\|staff_logout\|staff_orders" --include="*.html" "/home/jey/Documents/projet /OpendFood/templates/"
```
Attendu : aucune ligne.

- [ ] **Step 4 : Lancer tous les tests**

```bash
python manage.py test base -v 1
python manage.py check
```
Attendu : `OK`, `0 issues`.

- [ ] **Step 5 : Commit final**

```bash
git add -A
git commit -m "cleanup: remove old staff session portal (views, urls, forms, templates)"
```

---

## Self-Review

### 1. Spec coverage

| Requirement | Task |
|-------------|------|
| Un seul `/connexion/` pour tous | Task 4 |
| Staff = Django User + StaffMember (OneToOneField) | Task 1 |
| Invitation par email (token UUID, 7j) | Task 3, 6 |
| Routing post-login par rôle | Task 4 |
| Dashboard filtré par rôle | Task 5 (contexte `role` passé au template) |
| Sidebar/nav filtrés | Task 8 |
| Cuisinier : Dashboard + Commandes + Menu | Task 5, 8 |
| Serveur : Dashboard + Commandes + Tables | Task 5, 8 |
| Coadmin : tout sauf supprimer owner | Task 6 |
| Invitation : user existant → liaison directe | Task 6 (staff_invite) |
| Invitation : nouvel user → formulaire | Task 6 (staff_invite_accept) |
| `preparing_by_name` mis à jour | Task 5 (order_change_status) |
| Suppression portail staff | Task 11 |
| Context processor `restaurant`/`user_role` | Task 8 |

### 2. Placeholder scan

Aucun placeholder trouvé. Chaque step contient du code complet.

### 3. Type consistency

- `get_user_restaurant` retourne `(Restaurant | None, str | None)` — utilisé de façon cohérente dans Tasks 2, 4, 5, 8.
- `request.restaurant` et `request.user_role` sont définis par `restaurant_required` et consommés dans les vues — cohérent.
- `StaffInvitation.token` est un `UUIDField` — l'URL pattern utilise `<uuid:token>` — cohérent.
- `send_staff_invitation_email(base_url, invitation)` — appelé en Task 6 avec `base_url=request.build_absolute_uri('/').rstrip('/')` — cohérent avec la définition en Task 3.
