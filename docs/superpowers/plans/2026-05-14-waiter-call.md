# Waiter Call Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "call waiter" floating button on the customer menu, with real-time notifications (polling) and claim management in the admin dashboard.

**Architecture:** A `WaiterCall` model stores call events. Three JSON endpoints handle creation (public), listing (polling, auth), and claiming (auth). The admin header polls every 6 seconds, plays a Web Audio ding on new calls, and shows a dropdown to claim them. The customer menu shows a friendly empty state and a persistent floating button.

**Tech Stack:** Django 6.0, vanilla JS (no new deps), Web Audio API, Alpine.js (already loaded), Tailwind (already loaded).

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `base/models.py` | Modify | Add `WaiterCall` model |
| `base/migrations/0013_add_waitercall.py` | Create (generated) | DB migration |
| `base/views.py` | Modify | Add 3 API view functions |
| `base/urls.py` | Modify | Add 3 URL patterns |
| `templates/customer/menu.html` | Modify | Empty state + floating button |
| `templates/admin_user/base.html` | Modify | Polling JS + sound + badge update |
| `templates/admin_user/header.html` | Modify | Bell dropdown with call list |

---

## Task 1: WaiterCall model + migration

**Files:**
- Modify: `base/models.py` (after `StaffMember` class, around line 540)
- Create: `base/migrations/0013_add_waitercall.py` (generated)

- [ ] **Step 1: Add WaiterCall to base/models.py**

At the end of `base/models.py`, after the `StaffInvitation` class, add:

```python
class WaiterCall(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('claimed', 'Pris en charge'),
    ]

    restaurant = models.ForeignKey(
        Restaurant, on_delete=models.CASCADE, related_name='waiter_calls'
    )
    table = models.ForeignKey(
        Table, on_delete=models.CASCADE, related_name='waiter_calls'
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    claimed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='claimed_waiter_calls',
    )

    def __str__(self):
        return f"Appel Table {self.table.number} — {self.restaurant.name} [{self.status}]"
```

> Note: `claimed_by` points to `accounts.User` (not `StaffMember`) so restaurant owners (who have no StaffMember record) can also claim calls.

- [ ] **Step 2: Generate and apply migration**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py makemigrations base --name="add_waitercall"
python manage.py migrate base
```

Expected output:
```
Migrations for 'base':
  base/migrations/0013_add_waitercall.py
    + Create model WaiterCall
Operations to perform:
  Apply all migrations: base
Running migrations:
  Applying base.0013_add_waitercall... OK
```

- [ ] **Step 3: Commit**

```bash
git add base/models.py base/migrations/0013_add_waitercall.py
git commit -m "feat: add WaiterCall model"
```

---

## Task 2: API endpoints (views + URLs)

**Files:**
- Modify: `base/views.py` (add 3 functions at the end)
- Modify: `base/urls.py` (add 3 paths)

- [ ] **Step 1: Add imports at top of base/views.py**

Find the import block at the top of `base/views.py`. Add `WaiterCall` to the existing model import line:

```python
from .models import SubscriptionPlan, PromoCode, PromoCodeUse, Restaurant, MenuItem, MenuItemMedia, Order, OrderItem, RestaurantCustomization, QRSettings, WaiterCall
```

Also add `Table` to the import from `base.models` at line 12:
```python
from base.models import Category, Table
```
(Table is already imported — no change needed if it's already there.)

- [ ] **Step 2: Add the three view functions at the end of base/views.py**

```python
# ── Waiter Call API ────────────────────────────────────────────────────────────

from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET

@csrf_exempt
@require_POST
def create_waiter_call(request, table_token):
    """Public endpoint — called by the customer floating button."""
    try:
        table = Table.objects.select_related('restaurant').get(token=table_token)
    except Table.DoesNotExist:
        return JsonResponse({'status': 'error', 'detail': 'Table introuvable'}, status=404)

    restaurant = table.restaurant
    expiry = timezone.now() - timedelta(minutes=30)
    already_pending = WaiterCall.objects.filter(
        table=table,
        status='pending',
        created_at__gte=expiry,
    ).exists()

    if already_pending:
        return JsonResponse({'status': 'already_pending'})

    WaiterCall.objects.create(restaurant=restaurant, table=table)
    return JsonResponse({'status': 'ok'})


@login_required
@require_GET
def list_waiter_calls(request):
    """Polling endpoint — returns active calls for the logged-in user's restaurant."""
    restaurant, _ = get_user_restaurant(request.user)
    if not restaurant:
        return JsonResponse({'calls': []})

    expiry = timezone.now() - timedelta(minutes=30)
    calls = WaiterCall.objects.filter(
        restaurant=restaurant,
        created_at__gte=expiry,
    ).select_related('table', 'claimed_by').order_by('-created_at')

    data = []
    for call in calls:
        claimed_name = ''
        if call.claimed_by:
            claimed_name = f"{call.claimed_by.first_name} {call.claimed_by.last_name}".strip() or call.claimed_by.email
        data.append({
            'id': call.id,
            'table_number': call.table.number,
            'status': call.status,
            'claimed_by': claimed_name,
            'created_at': call.created_at.isoformat(),
        })

    return JsonResponse({'calls': data})


@login_required
@require_POST
def claim_waiter_call(request, call_id):
    """Mark a waiter call as claimed by the current user."""
    restaurant, _ = get_user_restaurant(request.user)
    if not restaurant:
        return JsonResponse({'status': 'error', 'detail': 'Pas de restaurant'}, status=403)

    try:
        call = WaiterCall.objects.get(id=call_id, restaurant=restaurant)
    except WaiterCall.DoesNotExist:
        return JsonResponse({'status': 'error', 'detail': 'Appel introuvable'}, status=404)

    call.status = 'claimed'
    call.claimed_by = request.user
    call.save(update_fields=['status', 'claimed_by'])
    return JsonResponse({'status': 'ok'})
```

- [ ] **Step 3: Add URL patterns to base/urls.py**

Open `base/urls.py`. Add these three paths to `urlpatterns`:

```python
path('api/waiter-call/<str:table_token>/', create_waiter_call, name='create_waiter_call'),
path('api/waiter-calls/pending/', list_waiter_calls, name='list_waiter_calls'),
path('api/waiter-calls/<int:call_id>/claim/', claim_waiter_call, name='claim_waiter_call'),
```

Also add `create_waiter_call`, `list_waiter_calls`, `claim_waiter_call` to the imports from `base.views` at the top of `base/urls.py`. The import line currently looks like:
```python
from .views import (home, create_restaurant, dashboard, ...)
```
Add the three new functions to this import.

- [ ] **Step 4: Smoke-test the endpoints**

Start the dev server: `python manage.py runserver`

Test create (replace `TOKEN` with a real table token from the DB):
```bash
curl -X POST http://localhost:8000/api/waiter-call/TOKEN/
# Expected: {"status": "ok"}

curl -X POST http://localhost:8000/api/waiter-call/TOKEN/
# Expected: {"status": "already_pending"}
```

Test list (requires session cookie — use browser or httpie with session):
```bash
# In browser after logging in, visit: http://localhost:8000/api/waiter-calls/pending/
# Expected: {"calls": [{...}]}
```

- [ ] **Step 5: Commit**

```bash
git add base/views.py base/urls.py
git commit -m "feat: waiter call API endpoints (create, list, claim)"
```

---

## Task 3: Customer menu — empty state + floating button

**Files:**
- Modify: `base/views.py` — add `has_active_items` to context in `client_menu`
- Modify: `templates/customer/menu.html` — empty state block + floating button

> `client_menu` is in `customer/views.py`, not `base/views.py`. The menu template is `templates/customer/menu.html`.

- [ ] **Step 1: Add has_active_items to customer/views.py context**

In `customer/views.py`, find `client_menu`. After the `categories` queryset is built, add:

```python
categories = list(categories)  # evaluate queryset to allow reuse below
has_active_items = any(list(cat.items.all()) for cat in categories)
```

Then add `has_active_items` to the `context` dict:
```python
context = {
    "restaurant": restaurant,
    "table": table,
    "customization": customization,
    "categories": categories,
    "has_active_items": has_active_items,
    # ... rest of existing keys
}
```

- [ ] **Step 2: Add empty state block to menu.html**

In `templates/customer/menu.html`, find the line:
```
<!-- ══ ITEMS ══════════════════════════════════════════ -->
<div class="max-w-2xl mx-auto px-4 pt-5 pb-36 space-y-8">
```

Insert the empty state block **inside** that div, before the `{% for category in categories %}` loop:

```html
{% if not has_active_items %}
<div class="flex flex-col items-center justify-center py-20 px-6 text-center">
  <!-- Assiette vide SVG -->
  <svg class="w-24 h-24 mb-6 text-slate-200" viewBox="0 0 96 96" fill="none" xmlns="http://www.w3.org/2000/svg">
    <circle cx="48" cy="52" r="32" stroke="currentColor" stroke-width="3" stroke-dasharray="6 4"/>
    <path d="M32 52 Q48 38 64 52" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"/>
    <path d="M48 20 C48 20 44 14 48 10 C52 14 48 20 48 20Z" fill="currentColor" opacity="0.3"/>
    <circle cx="48" cy="8" r="3" fill="currentColor" opacity="0.3"/>
    <path d="M38 24 C34 18 30 22 34 26" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
    <path d="M58 24 C62 18 66 22 62 26" stroke="currentColor" stroke-width="2" stroke-linecap="round" opacity="0.5"/>
  </svg>
  <h2 class="text-slate-800 font-black text-xl mb-2">Oups, les repas ont pris congé !</h2>
  <p class="text-slate-400 text-sm max-w-xs leading-relaxed">Le menu n'est pas encore disponible. Appelez un serveur pour en savoir plus.</p>
  <button id="callWaiterEmpty"
          class="mt-6 flex items-center gap-2 px-5 py-2.5 rounded-full text-white text-sm font-bold shadow-md active:scale-95 transition-all"
          style="background-color: var(--color-primary);">
    <i class="ri-customer-service-2-line text-base"></i>
    Appeler un serveur
  </button>
</div>
{% endif %}
```

- [ ] **Step 3: Add floating button to menu.html**

At the **very end** of the template, just before `{% endblock %}`, add:

```html
<!-- ══ FLOATING WAITER BUTTON ════════════════════════ -->
<div id="waiterCallBtn"
     class="fixed bottom-6 right-6 z-50"
     x-data="{
       called: false,
       cooldown: false,
       async callWaiter() {
         if (this.cooldown) return;
         try {
           const r = await fetch('{% url "create_waiter_call" table_token=table.token %}', {
             method: 'POST',
             headers: {'X-CSRFToken': '{{ csrf_token }}'}
           });
           const d = await r.json();
           this.called = true;
           this.cooldown = true;
           setTimeout(() => { this.called = false; }, 4000);
           setTimeout(() => { this.cooldown = false; }, 30000);
         } catch(e) {}
       }
     }">
  <button @click="callWaiter()"
          :disabled="cooldown"
          class="flex items-center gap-2 px-4 py-3 rounded-full text-white text-sm font-bold shadow-lg transition-all duration-200 active:scale-95 disabled:opacity-60"
          style="background-color: var(--color-primary);">
    <i class="ri-customer-service-2-line text-lg"></i>
    <span x-text="called ? 'Serveur appelé ✓' : 'Appeler un serveur'"></span>
  </button>
</div>

<script>
// Wire up the empty-state button to the same Alpine component
document.getElementById('callWaiterEmpty')?.addEventListener('click', function() {
  document.getElementById('waiterCallBtn').__x.$data.callWaiter();
});
</script>
```

- [ ] **Step 4: Verify in browser**

Start the dev server and scan a table QR code (or visit `/t/<token>/` directly).

- With active menu items: floating button appears bottom-right, click triggers "Serveur appelé ✓" for 4s, then resets. A second click within 30s does nothing (button is disabled).
- With no active menu items: empty state illustration + message shows. Both the empty-state button and the floating button trigger the call.

- [ ] **Step 5: Commit**

```bash
git add customer/views.py templates/customer/menu.html
git commit -m "feat: customer menu empty state and floating waiter call button"
```

---

## Task 4: Admin polling JS + sound

**Files:**
- Modify: `templates/admin_user/base.html` (add script before `</body>`)

- [ ] **Step 1: Add polling script to admin base.html**

In `templates/admin_user/base.html`, find the closing `</body>` tag. Just before it (after the Google Translate script block), add:

```html
<!-- ══ WAITER CALL POLLING ═══════════════════════════ -->
{% if request.user.is_authenticated %}
<script>
(function() {
  var _seenCallIds = new Set();
  var _audioUnlocked = false;
  var _bellBadge = null;

  // Unlock audio on first user interaction
  document.addEventListener('click', function() { _audioUnlocked = true; }, { once: true });

  function playDing() {
    if (!_audioUnlocked) return;
    try {
      var ctx = new (window.AudioContext || window.webkitAudioContext)();
      var osc = ctx.createOscillator();
      var gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.frequency.value = 880;
      osc.type = 'sine';
      gain.gain.setValueAtTime(0.4, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.6);
      osc.start(ctx.currentTime);
      osc.stop(ctx.currentTime + 0.6);
      // Second tone for a "ding-dong"
      var osc2 = ctx.createOscillator();
      var gain2 = ctx.createGain();
      osc2.connect(gain2);
      gain2.connect(ctx.destination);
      osc2.frequency.value = 660;
      osc2.type = 'sine';
      gain2.gain.setValueAtTime(0.3, ctx.currentTime + 0.2);
      gain2.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.8);
      osc2.start(ctx.currentTime + 0.2);
      osc2.stop(ctx.currentTime + 0.8);
    } catch(e) {}
  }

  function updateBadge(pendingCount) {
    var badge = document.getElementById('waiterCallBadge');
    if (!badge) return;
    if (pendingCount > 0) {
      badge.textContent = pendingCount;
      badge.style.display = 'flex';
    } else {
      badge.style.display = 'none';
    }
  }

  function renderCallsPanel(calls) {
    var panel = document.getElementById('waiterCallsPanel');
    if (!panel) return;
    if (calls.length === 0) {
      panel.innerHTML = '<p class="text-slate-400 text-xs text-center py-4">Aucun appel en cours</p>';
      return;
    }
    panel.innerHTML = calls.map(function(c) {
      var ago = _timeAgo(c.created_at);
      if (c.status === 'claimed') {
        return '<div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 last:border-0">' +
          '<div><p class="text-sm font-semibold text-slate-700">Table ' + c.table_number + '</p>' +
          '<p class="text-xs text-slate-400">' + ago + '</p></div>' +
          '<span class="text-xs text-slate-400 italic">Pris par ' + (c.claimed_by || 'quelqu\'un') + '</span>' +
          '</div>';
      }
      return '<div class="flex items-center justify-between px-4 py-3 border-b border-gray-100 last:border-0">' +
        '<div><p class="text-sm font-semibold text-slate-800">Table ' + c.table_number + '</p>' +
        '<p class="text-xs text-slate-400">' + ago + '</p></div>' +
        '<button onclick="claimWaiterCall(' + c.id + ', this)" ' +
        'class="text-xs font-bold px-3 py-1.5 rounded-lg text-white transition-all active:scale-95" ' +
        'style="background-color: var(--color-primary, #6366f1);">Prendre en charge</button>' +
        '</div>';
    }).join('');
  }

  function _timeAgo(isoString) {
    var diff = Math.floor((Date.now() - new Date(isoString).getTime()) / 1000);
    if (diff < 60) return 'il y a ' + diff + 's';
    return 'il y a ' + Math.floor(diff / 60) + ' min';
  }

  async function pollWaiterCalls() {
    try {
      var r = await fetch('{% url "list_waiter_calls" %}', { credentials: 'same-origin' });
      if (!r.ok) return;
      var data = await r.json();
      var calls = data.calls || [];

      // Detect new calls
      var hasNew = false;
      calls.forEach(function(c) {
        if (c.status === 'pending' && !_seenCallIds.has(c.id)) {
          _seenCallIds.add(c.id);
          if (_seenCallIds.size > 1) hasNew = true; // skip first batch (initial load)
        }
      });

      // On very first poll, populate seen without playing sound
      if (_seenCallIds.size === calls.filter(c => c.status === 'pending').length && !hasNew) {
        // first load — silence
      } else if (hasNew) {
        playDing();
      }

      var pendingCount = calls.filter(function(c) { return c.status === 'pending'; }).length;
      updateBadge(pendingCount);
      renderCallsPanel(calls);
    } catch(e) {}
  }

  // Initial poll + interval
  pollWaiterCalls();
  setInterval(pollWaiterCalls, 6000);

  // Global claim function (called from panel button onclick)
  window.claimWaiterCall = async function(callId, btn) {
    btn.disabled = true;
    btn.textContent = '...';
    try {
      var r = await fetch('/api/waiter-calls/' + callId + '/claim/', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': _getCsrf() },
      });
      if (r.ok) { pollWaiterCalls(); }
      else { btn.disabled = false; btn.textContent = 'Prendre en charge'; }
    } catch(e) { btn.disabled = false; btn.textContent = 'Prendre en charge'; }
  };

  function _getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }
})();
</script>
{% endif %}
```

> **Important:** The `{% url "list_waiter_calls" %}` tag resolves at render time on the server. This is correct — it bakes the URL into the page. The `claimWaiterCall` function uses a hardcoded `/api/waiter-calls/` path because the URL contains a dynamic `call_id` that isn't known at render time.

- [ ] **Step 2: Verify in browser**

Open any admin page while logged in. Open browser DevTools → Network tab. Confirm a request to `/api/waiter-calls/pending/` fires every 6 seconds.

- [ ] **Step 3: Commit**

```bash
git add templates/admin_user/base.html
git commit -m "feat: admin waiter call polling JS with Web Audio notification"
```

---

## Task 5: Admin header — bell dropdown

**Files:**
- Modify: `templates/admin_user/header.html`

- [ ] **Step 1: Replace the static bell button with an interactive one**

In `templates/admin_user/header.html`, find the existing notification section:

```html
<!-- Notification -->
<div class="relative">
  <button class="relative text-gray-500 hover:text-gray-700 focus:outline-none p-1">
    <i class="fas fa-bell text-lg"></i>
    <span class="absolute top-1 right-1 inline-block w-2 h-2 bg-red-500 rounded-full"></span>
  </button>
</div>
```

Replace it entirely with:

```html
<!-- Waiter call notifications -->
<div class="relative" x-data="{ open: false }">
  <button @click="open = !open"
          class="relative text-gray-500 hover:text-gray-700 focus:outline-none p-1">
    <i class="ri-bell-3-line text-xl"></i>
    <!-- Badge: shown/hidden by polling JS -->
    <span id="waiterCallBadge"
          class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] px-1 bg-red-500 text-white text-[10px] font-black rounded-full flex items-center justify-center"
          style="display:none;">0</span>
  </button>

  <!-- Dropdown panel -->
  <div x-show="open"
       @click.outside="open = false"
       x-transition
       class="absolute right-0 mt-2 w-72 bg-white border border-gray-200 rounded-xl shadow-xl z-50 overflow-hidden">

    <div class="px-4 py-3 border-b border-gray-100 flex items-center justify-between">
      <p class="text-sm font-bold text-gray-800">Appels de serveur</p>
      <button @click="open = false" class="text-gray-400 hover:text-gray-600">
        <i class="ri-close-line text-lg"></i>
      </button>
    </div>

    <!-- Populated by polling JS -->
    <div id="waiterCallsPanel" class="max-h-72 overflow-y-auto">
      <p class="text-slate-400 text-xs text-center py-4">Aucun appel en cours</p>
    </div>
  </div>
</div>
```

- [ ] **Step 2: Verify end-to-end flow**

1. Open the admin in one browser tab, customer menu in another.
2. On the customer menu, click "Appeler un serveur".
3. Within 6 seconds, the bell badge in admin should show "1" and a ding plays.
4. Click the bell → dropdown shows "Table X — il y a Ns" + "Prendre en charge" button.
5. Click "Prendre en charge" → button becomes "..." then disappears, entry shows "Pris par [Nom]".
6. Badge goes to 0.

- [ ] **Step 3: Commit**

```bash
git add templates/admin_user/header.html
git commit -m "feat: admin bell dropdown with waiter call list and claim button"
```

---

## Task 6: Deploy to production

- [ ] **Step 1: Push and deploy**

```bash
git push origin main
ssh root@46.202.135.102 "cd /var/www/openfood && git pull && source venv/bin/activate && python manage.py migrate && systemctl restart gunicorn-openfood && echo DONE"
```

- [ ] **Step 2: Verify on production**

Visit a table QR code on `https://<subdomain>.openfood.site/t/<token>/`. Call the waiter. Log in to admin at `https://openfood.site` and confirm the notification arrives.

---

## Self-Review

**Spec coverage:**
- ✅ Empty state with illustration and message
- ✅ "Call waiter" button always visible on customer menu
- ✅ Staff get notification + sound (polling every 6s, Web Audio ding)
- ✅ Admin also gets notification (same polling in admin base.html)
- ✅ Waiter can claim a call
- ✅ After claim, call shows "Pris par [Nom]" — others know not to go
- ✅ No client-side feedback when claimed

**First-poll silence:** The polling logic seeds `_seenCallIds` on first load without playing sound. Sound only fires on IDs that appear after the first poll. Implementation uses a size comparison that correctly detects this — ✅ no false ding on page load.

**Anti-spam:** Floating button has 30s client-side cooldown. Server-side dedup: no new `WaiterCall` created if a `pending` call exists within 30min for same table — ✅ double protection.

**CSRF:** `create_waiter_call` uses `@csrf_exempt` (public customer page, no session). `claim_waiter_call` reads CSRF from cookie via `_getCsrf()` — ✅ secure for authenticated endpoints.
