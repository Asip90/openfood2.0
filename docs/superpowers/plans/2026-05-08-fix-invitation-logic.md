# Fix Invitation Logic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix two bugs in the staff invitation flow — missing notification emails for existing users, and incorrect post-login redirection when a pending invitation exists.

**Architecture:** Two targeted fixes in three files. (1) Add a notification email for the "existing user" shortcut path in `staff_admin_views.py`. (2) Add a pending-invitation check in the login view so invited users are redirected to the acceptance URL instead of `create_restaurant`.

**Tech Stack:** Django, Python, Django's `send_mail`, existing `StaffInvitation` / `StaffMember` models.

---

## Root Cause Summary

### Bug 1 — No email when invited user already has an account

`base/staff_admin_views.py` lines 76-83:

```python
existing_user = User.objects.filter(email=email).first()
if existing_user:
    StaffMember.objects.create(
        user=existing_user, restaurant=restaurant, role=role
    )
    messages.success(...)
    return redirect('staff_list')   # ← returns here, no email ever sent
```

When the invited email already belongs to a registered user, the system skips the invitation token entirely and directly creates the `StaffMember`. No email is sent, so the person has no idea they've been added.

### Bug 2 — Post-login lands on `create_restaurant` instead of the restaurant dashboard

`accounts/views.py` lines 36-39:

```python
restaurant, role = get_user_restaurant(user)
if restaurant:
    return redirect("dashboard")
return redirect("create_restaurant")   # ← catches invited users who haven't accepted yet
```

If a new invited user registers through the normal `/inscription/` page (because they never received the invitation email), they are NOT added as `StaffMember`. On login, `get_user_restaurant` returns `(None, None)`, so they land on `create_restaurant` instead of being guided to accept their pending invitation.

---

## Files Touched

| File | Change |
|------|--------|
| `base/emails.py` | Add `send_staff_added_notification_email()` |
| `base/staff_admin_views.py` | Call the new email + wrap in try/except |
| `accounts/views.py` | Add pending-invitation check before `create_restaurant` redirect |

---

### Task 1: Add staff-added notification email function

**Files:**
- Modify: `base/emails.py`

- [ ] **Step 1: Write the failing test**

```python
# base/tests.py  (add to existing test file)
from unittest.mock import patch
from django.test import TestCase
from base.emails import send_staff_added_notification_email


class StaffAddedEmailTest(TestCase):
    @patch('base.emails.send_mail')
    def test_sends_email_to_existing_user(self, mock_send):
        class FakeRestaurant:
            name = "Chez Dupont"
        class FakeInvitation:
            restaurant = FakeRestaurant()
            role = 'serveur'
            email = 'emp@example.com'

        send_staff_added_notification_email(invitation=FakeInvitation())

        mock_send.assert_called_once()
        call_kwargs = mock_send.call_args
        assert 'emp@example.com' in call_kwargs[1]['recipient_list']
        assert 'Chez Dupont' in call_kwargs[1]['message']
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py test base.tests.StaffAddedEmailTest -v 2
```

Expected: `AttributeError: module 'base.emails' has no attribute 'send_staff_added_notification_email'`

- [ ] **Step 3: Add the function to `base/emails.py`**

Append after `send_staff_invitation_email`:

```python
def send_staff_added_notification_email(invitation) -> None:
    """
    Notify an existing user that they were directly added to a restaurant team.
    Called when the invited email already has an account (no token needed).
    """
    role_display = dict(invitation.restaurant.staff.model.ROLE_CHOICES).get(
        invitation.role, invitation.role
    )
    subject = f"Vous avez rejoint l'équipe de {invitation.restaurant.name} sur OpenFood"
    message = f"""Bonjour,

Vous avez été ajouté(e) à l'équipe de {invitation.restaurant.name} en tant que {role_display}.

Connectez-vous à OpenFood pour accéder à votre espace :
https://openfood.com/connexion/

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

- [ ] **Step 4: Run test to verify it passes**

```bash
python manage.py test base.tests.StaffAddedEmailTest -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add base/emails.py base/tests.py
git commit -m "feat: add send_staff_added_notification_email for direct staff additions"
```

---

### Task 2: Call the notification email + handle errors in `staff_invite`

**Files:**
- Modify: `base/staff_admin_views.py` lines 76-83

- [ ] **Step 1: Write the failing test**

```python
# base/tests.py  (append to existing test class or add new one)
from unittest.mock import patch, MagicMock
from django.test import TestCase, RequestFactory
from django.contrib.messages.storage.fallback import FallbackStorage
from accounts.models import User
from base.models import StaffMember, Restaurant, SubscriptionPlan


class StaffInviteExistingUserEmailTest(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        # Owner
        self.owner = User.objects.create_user(
            email='owner@example.com', password='pass12345',
            first_name='Owner', last_name='Test', email_verified=True,
        )
        # Restaurant
        self.restaurant = Restaurant.objects.create(
            owner=self.owner, name='Test Resto', address='123 rue test'
        )
        # Existing staff candidate
        self.candidate = User.objects.create_user(
            email='candidate@example.com', password='pass12345',
            first_name='Jean', last_name='Dupont', email_verified=True,
        )

    @patch('base.staff_admin_views.send_staff_invitation_email')
    @patch('base.staff_admin_views.send_staff_added_notification_email')
    def test_sends_notification_to_existing_user(self, mock_notify, mock_invite):
        from base import staff_admin_views
        request = self.factory.post('/equipe/inviter/', {
            'email': 'candidate@example.com',
            'role': 'serveur',
        })
        request.user = self.owner
        request.restaurant = self.restaurant
        request.user_role = 'owner'
        # attach messages middleware
        setattr(request, 'session', {})
        messages_storage = FallbackStorage(request)
        setattr(request, '_messages', messages_storage)

        staff_admin_views.staff_invite(request)

        mock_notify.assert_called_once()
        mock_invite.assert_not_called()   # no invitation token for existing users
        assert StaffMember.objects.filter(user=self.candidate, restaurant=self.restaurant).exists()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python manage.py test base.tests.StaffInviteExistingUserEmailTest -v 2
```

Expected: `AssertionError` — `mock_notify` was never called.

- [ ] **Step 3: Update `staff_invite` in `base/staff_admin_views.py`**

Change the import line at the top of the file:

```python
# Before
from base.emails import send_staff_invitation_email

# After
from base.emails import send_staff_invitation_email, send_staff_added_notification_email
```

Replace lines 76-83 (the existing-user fast-path):

```python
    # If user already exists in the system, create StaffMember and notify them
    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        StaffMember.objects.create(
            user=existing_user, restaurant=restaurant, role=role
        )
        try:
            # Build a lightweight object for the email helper
            class _Notif:
                pass
            notif = _Notif()
            notif.restaurant = restaurant
            notif.role = role
            notif.email = email
            send_staff_added_notification_email(invitation=notif)
        except Exception:
            pass  # Email failure must not block the action
        messages.success(request, f"{existing_user.first_name} {existing_user.last_name} a été ajouté(e) à l'équipe.")
        return redirect('staff_list')
```

Also wrap the invitation email (new-user path) in a try/except so an SMTP failure doesn't produce a 500 page (lines 86-95):

```python
    # New user: create invitation and send email
    invitation = StaffInvitation.objects.create(
        restaurant=restaurant,
        email=email,
        role=role,
        created_by=request.user,
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    base_url = request.build_absolute_uri('/').rstrip('/')
    try:
        send_staff_invitation_email(base_url=base_url, invitation=invitation)
    except Exception:
        pass  # Email failure must not block the action
    messages.success(request, f"Invitation envoyée à {email}.")
    return redirect('staff_list')
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python manage.py test base.tests.StaffInviteExistingUserEmailTest -v 2
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add base/staff_admin_views.py base/tests.py
git commit -m "fix: notify existing users when directly added to team, handle SMTP errors gracefully"
```

---

### Task 3: Redirect to pending invitation at login instead of `create_restaurant`

**Files:**
- Modify: `accounts/views.py`

**Context:** When a user logs in, the current flow is:
1. Check `next` param → redirect there
2. Check `get_user_restaurant` → redirect to dashboard or create_restaurant

The fix adds step 2.5: if the user has no restaurant but has a pending `StaffInvitation`, redirect them to the acceptance URL so the invitation flow can complete.

- [ ] **Step 1: Write the failing test**

```python
# accounts/tests.py  (create if it doesn't exist)
from django.test import TestCase, Client
from django.urls import reverse
from accounts.models import User
from base.models import Restaurant, StaffInvitation
from django.utils import timezone


class ConnexionPendingInvitationTest(TestCase):
    def setUp(self):
        self.client = Client()
        # Owner
        owner = User.objects.create_user(
            email='owner@example.com', password='pass12345',
            first_name='Owner', last_name='Test', email_verified=True,
        )
        self.restaurant = Restaurant.objects.create(
            owner=owner, name='Test Resto', address='123 rue test'
        )
        # New invited user (no account yet → we create them here for the test)
        self.invited_user = User.objects.create_user(
            email='invited@example.com', password='pass12345',
            first_name='Jean', last_name='Dupont', email_verified=True,
        )
        # Pending invitation for this user
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
        # No restaurant, no valid invitation → create_restaurant
        self.assertRedirects(response, reverse('create_restaurant'), fetch_redirect_response=False)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test accounts.tests.ConnexionPendingInvitationTest -v 2
```

Expected: Both tests fail because the login currently redirects to `create_restaurant`, not the invitation URL.

- [ ] **Step 3: Update `accounts/views.py` — add the import and the invitation check**

Add the import at the top (after existing imports):

```python
from base.models import StaffInvitation
```

Replace lines 36-39 in the `connexion` view:

```python
        # Before
        restaurant, role = get_user_restaurant(user)
        if restaurant:
            return redirect("dashboard")
        return redirect("create_restaurant")
```

```python
        # After
        restaurant, role = get_user_restaurant(user)
        if restaurant:
            return redirect("dashboard")

        # Check for a pending invitation for this email before sending to create_restaurant
        pending = StaffInvitation.objects.filter(
            email=user.email.lower(),
            accepted=False,
            expires_at__gt=timezone.now(),
        ).order_by('-expires_at').first()
        if pending:
            return redirect('staff_invite_accept', token=pending.token)

        return redirect("create_restaurant")
```

Also add the missing `timezone` import (it is already imported at the top of `accounts/views.py`).

- [ ] **Step 4: Run tests to verify they pass**

```bash
python manage.py test accounts.tests.ConnexionPendingInvitationTest -v 2
```

Expected: `OK` (both tests pass)

- [ ] **Step 5: Run the full test suite to check for regressions**

```bash
python manage.py test accounts base -v 2
```

Expected: All tests pass.

- [ ] **Step 6: Commit**

```bash
git add accounts/views.py accounts/tests.py
git commit -m "fix: redirect to pending invitation accept page on login instead of create_restaurant"
```

---

## Manual Verification Checklist

After all tasks:

- [ ] **Existing-user invite path**: Invite an email that already has an account → person receives "you've been added" email → they log in → land on **dashboard** (already have a StaffMember).
- [ ] **New-user invite path**: Invite a brand-new email → person receives invitation email → they click the link → fill registration form → log in → land on **dashboard**.
- [ ] **New-user who skips email**: Invite a brand-new email → person registers via the normal `/inscription/` page → logs in → redirected to `/equipe/accepter/{token}/` → fills registration form (shown as existing account) → accepts invitation → dashboard.
- [ ] **SMTP failure**: Temporarily break SMTP credentials → invite someone → no 500 page, system shows success message and continues.
- [ ] **Expired invitation**: Login with a user whose invitation has expired → NOT redirected to invitation page → lands on `create_restaurant`.
