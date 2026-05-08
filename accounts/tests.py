from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from base.models import Restaurant, StaffInvitation
from django.utils import timezone


class ConnexionPendingInvitationTest(TestCase):
    def setUp(self):
        self.client = Client()
        owner = User.objects.create_user(
            email='owner@example.com', password='pass12345',
            first_name='Owner', last_name='Test', email_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=owner, name='Test Resto', address='123 rue test'
        )
        self.invited_user = User.objects.create_user(
            email='invited@example.com', password='pass12345',
            first_name='Jean', last_name='Dupont', email_verified=True,
        )
        self.invitation = StaffInvitation.objects.create(
            restaurant=self.restaurant,
            email='invited@example.com',
            role='serveur',
            created_by=owner,
            expires_at=timezone.now() + timezone.timedelta(days=7),
        )

    def test_login_redirects_to_invitation_accept_when_pending(self):
        response = self.client.post(reverse('connexion'), {
            'email': 'invited@example.com',
            'password': 'pass12345',
        })
        expected_url = f'/equipe/accepter/{self.invitation.token}/'
        self.assertRedirects(response, expected_url, fetch_redirect_response=False)

    def test_expired_invitation_does_not_redirect(self):
        self.invitation.expires_at = timezone.now() - timezone.timedelta(days=1)
        self.invitation.save()
        response = self.client.post(reverse('connexion'), {
            'email': 'invited@example.com',
            'password': 'pass12345',
        })
        self.assertRedirects(response, reverse('create_restaurant'), fetch_redirect_response=False)
