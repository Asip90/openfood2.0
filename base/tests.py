# base/tests.py
import uuid
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.db import IntegrityError
from django.urls import reverse
from django.core import mail as django_mail
from accounts.models import User
from base.models import Restaurant, StaffMember, StaffInvitation


def make_user(email='user@test.com', first='A', last='B'):
    return User.objects.create_user(
        email=email, password='pass123', first_name=first, last_name=last,
        email_verified=True,
    )


def make_restaurant(owner):
    uid = owner.pk or owner.email
    return Restaurant.objects.create(
        owner=owner, name=f'TestResto-{uid}',
        slug=f'testresto-{uid}', subdomain=f'testresto-{uid}',
        address='123 rue test', phone='0600000000', email='resto@test.com',
    )


# ─── Task 1: Model tests ───────────────────────────────────────────────────────

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


# ─── Task 2: Decorator tests ───────────────────────────────────────────────────

class GetUserRestaurantTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner3@test.com', 'Owner', 'Three')
        self.restaurant = make_restaurant(self.owner)

    def test_owner_returns_owner_role(self):
        from base.decorators import get_user_restaurant
        restaurant, role = get_user_restaurant(self.owner)
        self.assertEqual(restaurant, self.restaurant)
        self.assertEqual(role, 'owner')

    def test_staff_returns_staff_role(self):
        from base.decorators import get_user_restaurant
        staff_user = make_user('staff3@test.com', 'Staff', 'Three')
        StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='cuisinier'
        )
        restaurant, role = get_user_restaurant(staff_user)
        self.assertEqual(restaurant, self.restaurant)
        self.assertEqual(role, 'cuisinier')

    def test_no_restaurant_returns_none(self):
        from base.decorators import get_user_restaurant
        lonely = make_user('alone@test.com', 'No', 'Resto')
        restaurant, role = get_user_restaurant(lonely)
        self.assertIsNone(restaurant)
        self.assertIsNone(role)

    def test_inactive_staff_ignored(self):
        from base.decorators import get_user_restaurant
        staff_user = make_user('inactive@test.com', 'In', 'Active')
        StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='serveur', is_active=False
        )
        restaurant, role = get_user_restaurant(staff_user)
        self.assertIsNone(restaurant)
        self.assertIsNone(role)


# ─── Task 3: Email tests ───────────────────────────────────────────────────────

class StaffInvitationEmailTest(TestCase):

    def setUp(self):
        self.owner = make_user('owner4@test.com', 'Owner', 'Four')
        self.restaurant = make_restaurant(self.owner)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_sends_invitation_email(self):
        from base.emails import send_staff_invitation_email
        inv = StaffInvitation.objects.create(
            restaurant=self.restaurant,
            email='newstaff@test.com',
            role='cuisinier',
            created_by=self.owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )
        send_staff_invitation_email(base_url='http://testserver', invitation=inv)
        self.assertEqual(len(django_mail.outbox), 1)
        self.assertIn('newstaff@test.com', django_mail.outbox[0].to)
        self.assertIn(str(inv.token), django_mail.outbox[0].body)
        self.assertIn(self.restaurant.name, django_mail.outbox[0].body)


# ─── Task 4: Connexion routing tests ──────────────────────────────────────────

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


# ─── Task 5: Role access tests ────────────────────────────────────────────────

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


# ─── Task 6: Invitation view tests ────────────────────────────────────────────

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

    def test_cannot_invite_self(self):
        resp = self.client.post(reverse('staff_invite'), {
            'email': self.owner.email,
            'role': 'cuisinier',
        })
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertEqual(StaffInvitation.objects.count(), 0)
        self.assertEqual(StaffMember.objects.count(), 0)

    def test_cannot_invite_existing_staff_member(self):
        staff_user = make_user('alreadyin@test.com', 'Already', 'In')
        StaffMember.objects.create(
            user=staff_user, restaurant=self.restaurant, role='cuisinier'
        )
        resp = self.client.post(reverse('staff_invite'), {
            'email': 'alreadyin@test.com',
            'role': 'serveur',
        })
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertEqual(StaffMember.objects.filter(user=staff_user).count(), 1)

    def test_cannot_invite_staff_of_another_restaurant(self):
        other_owner = make_user('otherowner@test.com', 'Other', 'Owner')
        other_restaurant = make_restaurant(other_owner)
        staff_user = make_user('elsewhere@test.com', 'Work', 'Elsewhere')
        StaffMember.objects.create(
            user=staff_user, restaurant=other_restaurant, role='cuisinier'
        )
        resp = self.client.post(reverse('staff_invite'), {
            'email': 'elsewhere@test.com',
            'role': 'serveur',
        })
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertFalse(StaffMember.objects.filter(user=staff_user, restaurant=self.restaurant).exists())

    def test_coadmin_cannot_delete_other_coadmin(self):
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
        self.assertRedirects(resp, reverse('staff_list'), fetch_redirect_response=False)
        self.assertTrue(StaffMember.objects.filter(pk=other_sm.pk).exists())
