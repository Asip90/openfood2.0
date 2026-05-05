from django.test import TestCase
from django.contrib.auth.hashers import check_password
from django.db import IntegrityError
from accounts.models import User
from base.models import Restaurant, Order, StaffMember, SubscriptionPlan
from base.staff_forms import StaffLoginForm, StaffMemberForm


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
        s = StaffMember(
            restaurant=self.restaurant, first_name='A', last_name='B',
            username='chef', role='cuisinier',
        )
        s.set_password('x')
        s.save()
        with self.assertRaises(IntegrityError):
            StaffMember.objects.create(
                restaurant=self.restaurant, first_name='C', last_name='D',
                username='chef', role='serveur', password='y'
            )

    def test_str_representation(self):
        staff = StaffMember(
            restaurant=self.restaurant,
            first_name='Jean', last_name='Dupont', role='cuisinier',
            username='jean',
        )
        staff.set_password('pass')
        staff.save()
        self.assertIn('Jean Dupont', str(staff))
        self.assertIn(self.restaurant.name, str(staff))

    def test_order_has_preparing_by_name(self):
        order = Order(
            restaurant=self.restaurant,
            order_type='dine_in',
            status='preparing',
            preparing_by_name='Jean Dupont',
        )
        order.save()
        self.assertEqual(Order.objects.get(pk=order.pk).preparing_by_name, 'Jean Dupont')


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
