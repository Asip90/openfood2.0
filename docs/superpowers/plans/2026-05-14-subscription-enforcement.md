# Subscription Enforcement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce subscription expiry across all plan-gated features, wire FedaPay URL to the environment variable already present in settings, and add a FedaPay webhook for reliable async payment confirmation.

**Architecture:** A single `get_effective_plan(restaurant)` helper returns the real plan if active, or the gratuit plan if expired — all existing limit/feature checks automatically become expiry-aware by switching to this helper. FedaPay URL is derived from `settings.FEDAPAY_ENV`. A new webhook view verifies the FedaPay HMAC signature and activates the plan asynchronously.

**Tech Stack:** Django 6, PostgreSQL, FedaPay REST API (sandbox/live toggle via env), `hmac`/`hashlib` stdlib for webhook signature verification.

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `base/services/subscription.py` | `get_effective_plan()` helper |
| Modify | `base/subscription_views.py` | Fix hardcoded URL, add webhook view |
| Modify | `base/views.py` | Use `get_effective_plan` in analytics & export |
| Modify | `base/staff_admin_views.py` | Use `get_effective_plan` for staff limit |
| Modify | `base/urls.py` | Register webhook URL |
| Modify | `main/settings.py` | Add `FEDAPAY_WEBHOOK_SECRET` |
| Modify | `main/.env` | Add `FEDAPAY_WEBHOOK_SECRET` placeholder |
| Modify | `base/tests.py` | Add subscription enforcement tests |

---

## Task 1: `get_effective_plan()` helper

**Files:**
- Create: `base/services/subscription.py`
- Modify: `base/tests.py`

- [ ] **Step 1: Write the failing tests**

Add at the bottom of `base/tests.py`:

```python
# ─── Subscription enforcement tests ──────────────────────────────────────────

from base.models import SubscriptionPlan
from base.services.subscription import get_effective_plan


def make_plan(plan_type='pro', analytics=True, max_items=0, max_tables=0, max_staff=0, price=9900):
    return SubscriptionPlan.objects.create(
        name=plan_type.capitalize(),
        plan_type=plan_type,
        price=price,
        analytics=analytics,
        advanced_analytics=(plan_type == 'max'),
        max_menu_items=max_items,
        max_tables=max_tables,
        max_staff=max_staff,
    )


class GetEffectivePlanTest(TestCase):

    def setUp(self):
        self.owner = make_user('subowner@test.com', 'Sub', 'Owner')
        self.restaurant = make_restaurant(self.owner)
        self.gratuit = make_plan('gratuit', analytics=False, price=0)
        self.pro = make_plan('pro', analytics=True, price=9900)

    def test_active_plan_is_returned(self):
        self.restaurant.subscription_plan = self.pro
        self.restaurant.subscription_end = timezone.now() + timedelta(days=10)
        self.restaurant.save()
        plan = get_effective_plan(self.restaurant)
        self.assertEqual(plan.plan_type, 'pro')

    def test_expired_plan_returns_gratuit(self):
        self.restaurant.subscription_plan = self.pro
        self.restaurant.subscription_end = timezone.now() - timedelta(seconds=1)
        self.restaurant.save()
        plan = get_effective_plan(self.restaurant)
        self.assertEqual(plan.plan_type, 'gratuit')

    def test_no_subscription_end_is_perpetual(self):
        self.restaurant.subscription_plan = self.pro
        self.restaurant.subscription_end = None
        self.restaurant.save()
        plan = get_effective_plan(self.restaurant)
        self.assertEqual(plan.plan_type, 'pro')

    def test_no_plan_returns_none(self):
        self.restaurant.subscription_plan = None
        self.restaurant.save()
        plan = get_effective_plan(self.restaurant)
        self.assertIsNone(plan)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /home/jey/Documents/projet\ /OpendFood
python manage.py test base.tests.GetEffectivePlanTest -v 2
```

Expected: `ImportError: cannot import name 'get_effective_plan'`

- [ ] **Step 3: Create the helper**

Create `base/services/subscription.py`:

```python
from django.utils import timezone
from base.models import SubscriptionPlan


def get_effective_plan(restaurant):
    """
    Returns the restaurant's subscription plan if active (not expired),
    otherwise returns the gratuit plan. Returns None if no plan exists at all.
    """
    plan = restaurant.subscription_plan
    if plan is None:
        return None

    if restaurant.subscription_end and restaurant.subscription_end < timezone.now():
        return SubscriptionPlan.objects.filter(plan_type='gratuit', is_active=True).first()

    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python manage.py test base.tests.GetEffectivePlanTest -v 2
```

Expected: `OK` — 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add base/services/subscription.py base/tests.py
git commit -m "feat: add get_effective_plan helper with expiry enforcement"
```

---

## Task 2: Enforce expiry in analytics and CSV export

**Files:**
- Modify: `base/views.py` (lines 277–285 and 420–427)

- [ ] **Step 1: Write failing tests**

Add to `base/tests.py`:

```python
class AnalyticsExpiryTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = make_user('anaowner@test.com', 'Ana', 'Owner')
        self.restaurant = make_restaurant(self.owner)
        self.gratuit = make_plan('gratuit', analytics=False, price=0)
        self.pro = make_plan('pro', analytics=True, price=9900)
        self.client.force_login(self.owner)

    def test_active_pro_can_access_analytics(self):
        self.restaurant.subscription_plan = self.pro
        self.restaurant.subscription_end = timezone.now() + timedelta(days=10)
        self.restaurant.save()
        resp = self.client.get(reverse('analytics'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context.get('access_denied', True))

    def test_expired_pro_is_denied_analytics(self):
        self.restaurant.subscription_plan = self.pro
        self.restaurant.subscription_end = timezone.now() - timedelta(seconds=1)
        self.restaurant.save()
        resp = self.client.get(reverse('analytics'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['access_denied'])
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test base.tests.AnalyticsExpiryTest -v 2
```

Expected: `FAIL` — `test_expired_pro_is_denied_analytics` fails because expiry is not currently checked.

- [ ] **Step 3: Update `analytics_view`**

In `base/views.py`, add the import at the top of the file (after the existing imports):

```python
from base.services.subscription import get_effective_plan
```

Then update `analytics_view` (around line 277):

```python
def analytics_view(request):
    restaurant = request.restaurant
    plan = get_effective_plan(restaurant)

    if not plan or not plan.analytics:
        return render(request, "admin_user/analytics/index.html", {
            "restaurant": restaurant,
            "access_denied": True,
        })
    # ... rest of view unchanged
```

And update `export_orders_csv` (around line 420):

```python
def export_orders_csv(request):
    import csv
    restaurant = request.restaurant
    plan = get_effective_plan(restaurant)

    if not plan or not plan.advanced_analytics:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Accès réservé au plan Max.")
    # ... rest of view unchanged
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python manage.py test base.tests.AnalyticsExpiryTest -v 2
```

Expected: `OK` — 2 tests pass.

- [ ] **Step 5: Run full test suite**

```bash
python manage.py test base -v 1
```

Expected: all pre-existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add base/views.py base/tests.py
git commit -m "feat: enforce subscription expiry in analytics and CSV export"
```

---

## Task 3: Enforce expiry on plan limits (menu items, tables, staff)

**Files:**
- Modify: `base/views.py` (lines ~786, ~1083)
- Modify: `base/staff_admin_views.py` (line ~54)

- [ ] **Step 1: Write failing tests**

Add to `base/tests.py`:

```python
class PlanLimitsExpiryTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = make_user('limowner@test.com', 'Lim', 'Owner')
        self.restaurant = make_restaurant(self.owner)
        self.gratuit = make_plan('gratuit', analytics=False, max_items=5, max_tables=3, price=0)
        self.pro = make_plan('pro', analytics=True, max_items=0, max_tables=0, price=9900)
        # Put restaurant on expired pro (unlimited items)
        self.restaurant.subscription_plan = self.pro
        self.restaurant.subscription_end = timezone.now() - timedelta(seconds=1)
        self.restaurant.save()
        self.client.force_login(self.owner)
        # Create a category for menu item creation
        from base.models import Category
        self.category = Category.objects.create(
            restaurant=self.restaurant, name='Test Cat', order=1
        )

    def _fill_menu_items(self, count):
        from base.models import MenuItem
        for i in range(count):
            MenuItem.objects.create(
                restaurant=self.restaurant,
                category=self.category,
                name=f'Plat {i}',
                price=1000,
            )

    def test_expired_pro_enforces_gratuit_menu_limit(self):
        # Fill up to gratuit limit (5 items)
        self._fill_menu_items(5)
        resp = self.client.post(reverse('menu_item_create'), {
            'name': 'Plat de trop',
            'price': '1500',
            'category': self.category.pk,
            'description': '',
        })
        # Should be blocked — redirect back with error message
        from base.models import MenuItem
        self.assertEqual(MenuItem.objects.filter(restaurant=self.restaurant).count(), 5)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python manage.py test base.tests.PlanLimitsExpiryTest.test_expired_pro_enforces_gratuit_menu_limit -v 2
```

Expected: `FAIL` — currently uses raw `restaurant.subscription_plan` (Pro, unlimited), so the 6th item is created.

- [ ] **Step 3: Update menu item creation in `base/views.py`**

Find the block around line 786 (inside `menu_item_create` view). Replace:

```python
plan = restaurant.subscription_plan
if plan and plan.max_menu_items > 0:
    current_count = MenuItem.objects.filter(restaurant=restaurant).count()
    if current_count >= plan.max_menu_items:
        messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_menu_items} plats. Passez au plan supérieur pour en ajouter davantage.")
```

With:

```python
plan = get_effective_plan(restaurant)
if plan and plan.max_menu_items > 0:
    current_count = MenuItem.objects.filter(restaurant=restaurant).count()
    if current_count >= plan.max_menu_items:
        messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_menu_items} plats. Passez au plan supérieur pour en ajouter davantage.")
```

Find the block around line 1083 (inside `create_table` view). Replace:

```python
plan = restaurant.subscription_plan
if plan and plan.max_tables > 0:
    current_count = Table.objects.filter(restaurant=restaurant).count()
    if current_count >= plan.max_tables:
        messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_tables} tables. Passez au plan supérieur pour en créer davantage.")
```

With:

```python
plan = get_effective_plan(restaurant)
if plan and plan.max_tables > 0:
    current_count = Table.objects.filter(restaurant=restaurant).count()
    if current_count >= plan.max_tables:
        messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_tables} tables. Passez au plan supérieur pour en créer davantage.")
```

- [ ] **Step 4: Update staff invite in `base/staff_admin_views.py`**

In `base/staff_admin_views.py`, add the import at the top:

```python
from base.services.subscription import get_effective_plan
```

Find line ~54. Replace:

```python
plan = restaurant.subscription_plan
if plan and plan.max_staff > 0:
    current_staff = StaffMember.objects.filter(restaurant=restaurant).count()
    if current_staff >= plan.max_staff:
        messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_staff} membres d'équipe. Passez au plan supérieur pour en ajouter davantage.")
```

With:

```python
plan = get_effective_plan(restaurant)
if plan and plan.max_staff > 0:
    current_staff = StaffMember.objects.filter(restaurant=restaurant).count()
    if current_staff >= plan.max_staff:
        messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_staff} membres d'équipe. Passez au plan supérieur pour en ajouter davantage.")
```

- [ ] **Step 5: Run tests**

```bash
python manage.py test base.tests.PlanLimitsExpiryTest -v 2
```

Expected: `OK`.

- [ ] **Step 6: Run full test suite**

```bash
python manage.py test base -v 1
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add base/views.py base/staff_admin_views.py base/tests.py
git commit -m "feat: enforce subscription expiry on menu/table/staff plan limits"
```

---

## Task 4: Fix FedaPay hardcoded sandbox URL

**Files:**
- Modify: `base/subscription_views.py` (line 16)

`settings.FEDAPAY_ENV` already exists (default `'sandbox'`). The fix is one line.

- [ ] **Step 1: Write failing test**

Add to `base/tests.py`:

```python
from unittest.mock import patch
import base.subscription_views as sub_views


class FedapayUrlTest(TestCase):

    @override_settings(FEDAPAY_ENV='live')
    def test_live_env_uses_live_url(self):
        from importlib import reload
        reload(sub_views)
        self.assertIn('api.fedapay.com', sub_views.FEDAPAY_BASE)
        self.assertNotIn('sandbox', sub_views.FEDAPAY_BASE)

    @override_settings(FEDAPAY_ENV='sandbox')
    def test_sandbox_env_uses_sandbox_url(self):
        from importlib import reload
        reload(sub_views)
        self.assertIn('sandbox', sub_views.FEDAPAY_BASE)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python manage.py test base.tests.FedapayUrlTest -v 2
```

Expected: `FAIL` — `test_live_env_uses_live_url` fails because URL is hardcoded.

- [ ] **Step 3: Fix the URL in `base/subscription_views.py`**

Replace line 16:

```python
FEDAPAY_BASE = 'https://sandbox-api.fedapay.com/v1'  # switch to api.fedapay.com for live
```

With:

```python
from django.conf import settings as _settings
FEDAPAY_BASE = (
    'https://api.fedapay.com/v1'
    if getattr(_settings, 'FEDAPAY_ENV', 'sandbox') == 'live'
    else 'https://sandbox-api.fedapay.com/v1'
)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python manage.py test base.tests.FedapayUrlTest -v 2
```

Expected: `OK`.

- [ ] **Step 5: Run full test suite**

```bash
python manage.py test base -v 1
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add base/subscription_views.py base/tests.py
git commit -m "fix: derive FedaPay base URL from FEDAPAY_ENV setting"
```

---

## Task 5: FedaPay webhook for async payment confirmation

**Files:**
- Modify: `base/subscription_views.py` — add `fedapay_webhook` view
- Modify: `base/urls.py` — register webhook route
- Modify: `main/settings.py` — add `FEDAPAY_WEBHOOK_SECRET`
- Modify: `main/.env` — add placeholder

FedaPay sends a POST to your webhook URL with a JSON body and an `X-FEDAPAY-SIGNATURE` header containing `HMAC-SHA256(secret, raw_body)`. The view verifies the signature, checks `transaction.status == 'approved'`, and activates the plan.

- [ ] **Step 1: Add `FEDAPAY_WEBHOOK_SECRET` to settings and env**

In `main/settings.py`, after the existing FedaPay keys (around line 112):

```python
FEDAPAY_WEBHOOK_SECRET = os.getenv('FEDAPAY_WEBHOOK_SECRET', '')
```

In `main/.env`, add:

```
FEDAPAY_WEBHOOK_SECRET=your_webhook_secret_here
```

- [ ] **Step 2: Write failing webhook tests**

Add to `base/tests.py`:

```python
import hashlib
import hmac
import json
from django.test import Client, TestCase, override_settings
from django.urls import reverse


class FedapayWebhookTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.owner = make_user('webhookowner@test.com', 'Web', 'Hook')
        self.restaurant = make_restaurant(self.owner)
        self.gratuit = make_plan('gratuit', analytics=False, price=0)
        self.pro = make_plan('pro', analytics=True, price=9900)
        self.restaurant.subscription_plan = self.gratuit
        self.restaurant.save()
        self.secret = 'testsecret'

    def _sign(self, body: bytes, secret: str) -> str:
        return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def _post(self, payload: dict, secret='testsecret'):
        body = json.dumps(payload).encode()
        sig = self._sign(body, secret)
        return self.client.post(
            reverse('fedapay_webhook'),
            data=body,
            content_type='application/json',
            HTTP_X_FEDAPAY_SIGNATURE=sig,
        )

    @override_settings(FEDAPAY_WEBHOOK_SECRET='testsecret')
    def test_approved_payment_activates_plan(self):
        payload = {
            'name': 'transaction.approved',
            'data': {
                'object': {
                    'status': 'approved',
                    'metadata': {
                        'restaurant_id': self.restaurant.pk,
                        'plan_type': 'pro',
                    },
                }
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.subscription_plan.plan_type, 'pro')

    @override_settings(FEDAPAY_WEBHOOK_SECRET='testsecret')
    def test_bad_signature_returns_400(self):
        payload = {'name': 'transaction.approved', 'data': {}}
        resp = self._post(payload, secret='wrongsecret')
        self.assertEqual(resp.status_code, 400)
        # Plan must not change
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.subscription_plan.plan_type, 'gratuit')

    @override_settings(FEDAPAY_WEBHOOK_SECRET='testsecret')
    def test_non_approved_status_does_not_activate(self):
        payload = {
            'name': 'transaction.declined',
            'data': {
                'object': {
                    'status': 'declined',
                    'metadata': {
                        'restaurant_id': self.restaurant.pk,
                        'plan_type': 'pro',
                    },
                }
            },
        }
        resp = self._post(payload)
        self.assertEqual(resp.status_code, 200)
        self.restaurant.refresh_from_db()
        self.assertEqual(self.restaurant.subscription_plan.plan_type, 'gratuit')
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python manage.py test base.tests.FedapayWebhookTest -v 2
```

Expected: `NoReverseMatch` for `fedapay_webhook` — URL doesn't exist yet.

- [ ] **Step 4: Add the webhook view to `base/subscription_views.py`**

Add these imports at the top of `base/subscription_views.py` (after existing imports):

```python
import hashlib
import hmac
import json
```

Add this view at the end of `base/subscription_views.py`:

```python
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse, HttpResponseBadRequest


@csrf_exempt
def fedapay_webhook(request):
    if request.method != 'POST':
        return HttpResponseBadRequest('Method not allowed')

    secret = settings.FEDAPAY_WEBHOOK_SECRET
    if not secret:
        logger.error('FEDAPAY_WEBHOOK_SECRET not configured')
        return HttpResponseBadRequest('Webhook not configured')

    raw_body = request.body
    received_sig = request.headers.get('X-Fedapay-Signature', '')
    expected_sig = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()

    if not hmac.compare_digest(received_sig, expected_sig):
        logger.warning('FedaPay webhook: invalid signature')
        return HttpResponseBadRequest('Invalid signature')

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest('Invalid JSON')

    obj = payload.get('data', {}).get('object', {})
    status = obj.get('status')
    metadata = obj.get('metadata', {})
    restaurant_id = metadata.get('restaurant_id')
    plan_type = metadata.get('plan_type')

    if status != 'approved' or not restaurant_id or not plan_type:
        return HttpResponse('OK')

    try:
        from base.models import Restaurant
        restaurant = Restaurant.objects.get(pk=restaurant_id)
        plan = SubscriptionPlan.objects.filter(plan_type=plan_type, is_active=True).first()
        if not plan:
            logger.error('FedaPay webhook: plan_type=%s not found', plan_type)
            return HttpResponse('OK')

        now = timezone.now()
        if (restaurant.subscription_plan == plan
                and restaurant.subscription_end
                and restaurant.subscription_end > now):
            new_end = restaurant.subscription_end + timedelta(days=plan.duration_days)
        else:
            new_end = now + timedelta(days=plan.duration_days)

        restaurant.subscription_plan = plan
        restaurant.subscription_start = now
        restaurant.subscription_end = new_end
        restaurant.save(update_fields=['subscription_plan', 'subscription_start', 'subscription_end'])
        logger.info('FedaPay webhook: activated %s for restaurant %s until %s', plan_type, restaurant_id, new_end)
    except Exception as e:
        logger.error('FedaPay webhook processing error: %s', e)

    return HttpResponse('OK')
```

- [ ] **Step 5: Register the webhook URL in `base/urls.py`**

In `base/urls.py`, add the import and URL alongside the other subscription paths (around line 72):

```python
from base.subscription_views import fedapay_webhook

# inside urlpatterns:
path('abonnement/webhook/', fedapay_webhook, name='fedapay_webhook'),
```

- [ ] **Step 6: Update `subscribe_initiate` to pass metadata to FedaPay**

In `base/subscription_views.py`, in the `subscribe_initiate` view, the `payload` dict sent to FedaPay must include `metadata` so the webhook knows which restaurant and plan to activate. Find the payload block (around line 91) and add `metadata`:

```python
payload = {
    'description': f'OpenFood — Plan {plan.name} (1 mois)',
    'amount': plan.price,
    'currency': {'iso': 'XOF'},
    'callback_url': callback_url,
    'metadata': {
        'restaurant_id': restaurant.pk,
        'plan_type': plan_type,
    },
    'customer': {
        'email': request.user.email,
        'firstname': request.user.first_name or 'Client',
        'lastname': request.user.last_name or 'OpenFood',
    },
}
```

- [ ] **Step 7: Run webhook tests**

```bash
python manage.py test base.tests.FedapayWebhookTest -v 2
```

Expected: `OK` — 3 tests pass.

- [ ] **Step 8: Run full test suite**

```bash
python manage.py test base -v 1
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add base/subscription_views.py base/urls.py main/settings.py main/.env base/tests.py
git commit -m "feat: add FedaPay webhook for async payment confirmation with HMAC verification"
```

---

## Final verification

- [ ] **Run all tests one last time**

```bash
python manage.py test base -v 2
```

Expected: all tests pass, no warnings about missing migrations.

- [ ] **Check for unapplied migrations**

```bash
python manage.py migrate --check
```

Expected: no output (no pending migrations — all changes are code-only, no model changes).

- [ ] **System check**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`
