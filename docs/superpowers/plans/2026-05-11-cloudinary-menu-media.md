# Cloudinary Migration + Multi-Media Menu Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate all image storage to Cloudinary (CDN URLs instead of local disk), allow each `MenuItem` to have up to 3 images and 1 video, and add an image carousel with scroll indicator in the customer item detail modal.

**Architecture:** Add `django-cloudinary-storage` as `DEFAULT_FILE_STORAGE` so all existing `ImageField`s automatically upload to Cloudinary without model changes. Add a new `MenuItemMedia` model using `CloudinaryField(resource_type='auto')` for the multi-media feature. Update `item_json` templatetag and the customer modal template.

**Tech Stack:** cloudinary 1.x, django-cloudinary-storage 0.3.x, Alpine.js 3.14 (existing), Tailwind CDN (existing)

---

## File Map

| File | Change |
|------|--------|
| `requirements.txt` | Add `cloudinary`, `django-cloudinary-storage` |
| `main/settings.py` | Add Cloudinary config + `DEFAULT_FILE_STORAGE` |
| `.env` | Add `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, `CLOUDINARY_API_SECRET` |
| `base/models.py` | Add `MenuItemMedia` model |
| `base/migrations/XXXX_add_menuitem_media.py` | Auto-generated |
| `base/views.py` | Update `menu_create` + `menu_update` to handle 3 images + 1 video |
| `base/templatetags/menu_extras.py` | Update `item_json` to include `images[]` + `video` |
| `customer/views.py` | Add `prefetch_related('media')` on item queries |
| `templates/admin_user/menus/create_menus.html` | Add multi-file inputs (image_1, image_2, image_3, video) |
| `templates/admin_user/menus/update_menu.html` | Add multi-file inputs + show existing media |
| `templates/customer/menu_detail_modal.html` | Replace single image with carousel + scroll indicator |
| `templates/customer/base.html` | Add `carouselIndex` + `resetCarousel()` to `cartStore()` |

---

## Task 1: Install packages and configure Cloudinary

**Files:**
- Modify: `requirements.txt`
- Modify: `main/settings.py`
- Modify: `.env` (instructions only — secrets never committed)

- [ ] **Step 1: Add packages to requirements.txt**

Add these two lines at the end of `requirements.txt`:
```
cloudinary==1.42.1
django-cloudinary-storage==0.3.0
```

- [ ] **Step 2: Install packages**

```bash
cd "/home/jey/Documents/projet /OpendFood"
pip install cloudinary==1.42.1 django-cloudinary-storage==0.3.0
```

Expected: both packages install without errors.

- [ ] **Step 3: Add Cloudinary config to settings.py**

In `main/settings.py`, add to `INSTALLED_APPS` (before `'django.contrib.staticfiles'`):
```python
INSTALLED_APPS = [
    'jazzmin',
    'corsheaders',
    "rest_framework",
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'cloudinary_storage',           # ← add here
    'django.contrib.staticfiles',
    'cloudinary',                   # ← add here
    'base',
    'accounts',
    'widget_tweaks',
    'customer'
]
```

Then add at the bottom of `main/settings.py`:
```python
# Cloudinary
import cloudinary
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ['CLOUDINARY_CLOUD_NAME'],
    'API_KEY': os.environ['CLOUDINARY_API_KEY'],
    'API_SECRET': os.environ['CLOUDINARY_API_SECRET'],
}
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
cloudinary.config(
    cloud_name=os.environ['CLOUDINARY_CLOUD_NAME'],
    api_key=os.environ['CLOUDINARY_API_KEY'],
    api_secret=os.environ['CLOUDINARY_API_SECRET'],
    secure=True,
)
```

- [ ] **Step 4: Add secrets to .env**

The user must add these three lines to their `.env` file (values obtained from https://console.cloudinary.com):
```
CLOUDINARY_CLOUD_NAME=your_cloud_name
CLOUDINARY_API_KEY=your_api_key
CLOUDINARY_API_SECRET=your_api_secret
```

- [ ] **Step 5: Verify settings load without error**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py check --deploy 2>&1 | grep -v "WARNINGS\|security"
```

Expected: no `ImproperlyConfigured` or `ModuleNotFoundError` errors.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt main/settings.py
git commit -m "feat: add Cloudinary storage backend"
```

---

## Task 2: Create MenuItemMedia model

**Files:**
- Modify: `base/models.py`
- Create: migration (auto-generated)

- [ ] **Step 1: Add MenuItemMedia model to base/models.py**

Add this class immediately after the `MenuItem` class (around line 224), before the `_hex_to_rgb` function:

```python
from cloudinary.models import CloudinaryField as _CloudinaryField

class MenuItemMedia(models.Model):
    MEDIA_TYPE = [('image', 'Image'), ('video', 'Vidéo')]
    menu_item = models.ForeignKey(
        MenuItem, on_delete=models.CASCADE, related_name='media'
    )
    file = _CloudinaryField('media', resource_type='auto', blank=True)
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPE, default='image')
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['media_type', 'order']

    def __str__(self):
        return f"{self.menu_item.name} — {self.media_type} #{self.order}"

    @property
    def url(self):
        import cloudinary
        return cloudinary.CloudinaryImage(str(self.file)).build_url() if self.file else ''
```

Note: `_CloudinaryField` stores the Cloudinary public_id. The `.url` property builds the full CDN URL.

- [ ] **Step 2: Make migration**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py makemigrations base --name add_menuitem_media
```

Expected: `base/migrations/XXXX_add_menuitem_media.py` created.

- [ ] **Step 3: Run migration**

```bash
python manage.py migrate
```

Expected: migration applied with no errors.

- [ ] **Step 4: Verify model is accessible**

```bash
python manage.py shell -c "from base.models import MenuItemMedia; print('OK', MenuItemMedia._meta.fields)"
```

Expected: prints `OK` followed by field names.

- [ ] **Step 5: Commit**

```bash
git add base/models.py base/migrations/
git commit -m "feat: add MenuItemMedia model with Cloudinary support"
```

---

## Task 3: Update menu_create and menu_update views

**Files:**
- Modify: `base/views.py`

The views currently accept a single `image` file. We need to accept `image_1`, `image_2`, `image_3`, and `video` and create `MenuItemMedia` records for each.

- [ ] **Step 1: Add import for MenuItemMedia in base/views.py**

Near the top of `base/views.py`, find the line:
```python
from .models import SubscriptionPlan, PromoCode, PromoCodeUse, Restaurant, MenuItem, Order, OrderItem, RestaurantCustomization, QRSettings
```
Change it to:
```python
from .models import SubscriptionPlan, PromoCode, PromoCodeUse, Restaurant, MenuItem, MenuItemMedia, Order, OrderItem, RestaurantCustomization, QRSettings
```

- [ ] **Step 2: Replace menu_create view**

Find and replace the `menu_create` view (lines ~735–762):

```python
@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_create(request):
    restaurant = request.restaurant
    categories = Category.objects.filter(restaurant=restaurant)

    if request.method == "POST":
        plan = restaurant.subscription_plan
        if plan and plan.max_menu_items > 0:
            current_count = MenuItem.objects.filter(restaurant=restaurant).count()
            if current_count >= plan.max_menu_items:
                messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_menu_items} plats. Passez au plan supérieur pour en ajouter davantage.")
                return redirect("menus_list")

        menu_item = MenuItem.objects.create(
            restaurant=restaurant,
            category_id=request.POST.get("category"),
            name=request.POST.get("name"),
            price=request.POST.get("price"),
            description=request.POST.get("description"),
            is_available=True,
        )

        # Up to 3 images
        for i in range(1, 4):
            f = request.FILES.get(f"image_{i}")
            if f:
                MenuItemMedia.objects.create(
                    menu_item=menu_item, file=f, media_type='image', order=i
                )

        # 1 video
        video_f = request.FILES.get("video")
        if video_f:
            MenuItemMedia.objects.create(
                menu_item=menu_item, file=video_f, media_type='video', order=0
            )

        return redirect("menus_list")

    return render(request, "admin_user/menus/create_menus.html", {
        "restaurant": restaurant,
        "categories": categories
    })
```

- [ ] **Step 3: Replace menu_update view**

Find and replace the `menu_update` view (lines ~765–791):

```python
@restaurant_required(allowed_roles=['owner', 'coadmin', 'cuisinier'])
def menu_update(request, pk):
    restaurant = request.restaurant
    menu_item = get_object_or_404(MenuItem, pk=pk, restaurant=restaurant)

    if request.method == "POST":
        menu_item.name = request.POST.get("name")
        menu_item.price = request.POST.get("price")
        menu_item.description = request.POST.get("description")

        category_id = request.POST.get("category")
        if category_id:
            menu_item.category_id = category_id

        menu_item.save()

        # Replace images: delete existing images, re-create from form
        existing_images = menu_item.media.filter(media_type='image')
        any_new_image = any(request.FILES.get(f"image_{i}") for i in range(1, 4))
        if any_new_image:
            existing_images.delete()
            for i in range(1, 4):
                f = request.FILES.get(f"image_{i}")
                if f:
                    MenuItemMedia.objects.create(
                        menu_item=menu_item, file=f, media_type='image', order=i
                    )

        # Replace video if a new one is uploaded
        video_f = request.FILES.get("video")
        if video_f:
            menu_item.media.filter(media_type='video').delete()
            MenuItemMedia.objects.create(
                menu_item=menu_item, file=video_f, media_type='video', order=0
            )

        return redirect("menus_list")

    categories = Category.objects.filter(restaurant=restaurant)
    existing_images = list(menu_item.media.filter(media_type='image').order_by('order'))
    existing_video = menu_item.media.filter(media_type='video').first()

    return render(request, "admin_user/menus/update_menu.html", {
        "restaurant": restaurant,
        "menu_item": menu_item,
        "categories": categories,
        "existing_images": existing_images,
        "existing_video": existing_video,
    })
```

- [ ] **Step 4: Test manually**

Start the server and create a menu item with 2 images. Confirm `MenuItemMedia` records are created:
```bash
python manage.py shell -c "from base.models import MenuItemMedia; print(MenuItemMedia.objects.all())"
```

- [ ] **Step 5: Commit**

```bash
git add base/views.py
git commit -m "feat: menu create/update now accept up to 3 images and 1 video via Cloudinary"
```

---

## Task 4: Update admin menu templates

**Files:**
- Modify: `templates/admin_user/menus/create_menus.html`
- Modify: `templates/admin_user/menus/update_menu.html`

- [ ] **Step 1: Find the image input in create_menus.html**

Open `templates/admin_user/menus/create_menus.html`. Locate the single `<input type="file" name="image" ...>` element.

Replace it (and its surrounding label/wrapper) with:
```html
<!-- Media: jusqu'à 3 images -->
<div class="space-y-3">
  <label class="block text-sm font-medium text-gray-700">Images (max 3)</label>
  {% for i in "123" %}
  <div class="flex items-center gap-3">
    <span class="text-xs text-gray-400 w-16">Image {{ i }}</span>
    <input type="file" name="image_{{ i }}" accept="image/*"
           class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20">
  </div>
  {% endfor %}
</div>

<!-- Media: 1 vidéo optionnelle -->
<div class="mt-4">
  <label class="block text-sm font-medium text-gray-700 mb-1">Vidéo (optionnelle)</label>
  <input type="file" name="video" accept="video/*"
         class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200">
</div>
```

Also ensure the `<form>` tag has `enctype="multipart/form-data"`.

- [ ] **Step 2: Update update_menu.html**

Open `templates/admin_user/menus/update_menu.html`. Replace the single `<input type="file" name="image" ...>` with:

```html
<!-- Images existantes -->
{% if existing_images %}
<div class="mb-3">
  <p class="text-xs font-medium text-gray-500 mb-2">Images actuelles</p>
  <div class="flex gap-2 flex-wrap">
    {% for media in existing_images %}
    <img src="{{ media.url }}" class="h-20 w-20 object-cover rounded-xl border border-slate-100" alt="Image {{ forloop.counter }}">
    {% endfor %}
  </div>
</div>
{% endif %}

<!-- Remplacer les images -->
<div class="space-y-3">
  <label class="block text-sm font-medium text-gray-700">
    Nouvelles images (remplace les existantes si renseignées)
  </label>
  {% for i in "123" %}
  <div class="flex items-center gap-3">
    <span class="text-xs text-gray-400 w-16">Image {{ i }}</span>
    <input type="file" name="image_{{ i }}" accept="image/*"
           class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-primary/10 file:text-primary hover:file:bg-primary/20">
  </div>
  {% endfor %}
</div>

<!-- Vidéo -->
{% if existing_video %}
<div class="mt-3 mb-2">
  <p class="text-xs font-medium text-gray-500 mb-1">Vidéo actuelle</p>
  <video src="{{ existing_video.url }}" class="h-24 rounded-xl" controls muted></video>
</div>
{% endif %}
<div class="mt-3">
  <label class="block text-sm font-medium text-gray-700 mb-1">
    Nouvelle vidéo (remplace l'existante)
  </label>
  <input type="file" name="video" accept="video/*"
         class="block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-slate-100 file:text-slate-700 hover:file:bg-slate-200">
</div>
```

Also ensure the `<form>` tag has `enctype="multipart/form-data"`.

- [ ] **Step 3: Commit**

```bash
git add templates/admin_user/menus/create_menus.html templates/admin_user/menus/update_menu.html
git commit -m "feat: admin menu forms accept up to 3 images and 1 video"
```

---

## Task 5: Update item_json templatetag

**Files:**
- Modify: `base/templatetags/menu_extras.py`

- [ ] **Step 1: Update item_json to expose images[] and video**

Replace the full content of `base/templatetags/menu_extras.py`:

```python
import json
from django import template

register = template.Library()

@register.filter
def item_json(item):
    media_qs = list(item.media.all())  # pre-fetched via prefetch_related

    images = [
        m.url
        for m in media_qs
        if m.media_type == 'image'
    ][:3]

    # Fallback: keep backward compatibility with old MenuItem.image field
    if not images and item.image:
        images = [item.image.url]

    video_media = next((m for m in media_qs if m.media_type == 'video'), None)

    return json.dumps({
        'id': str(item.id),
        'name': item.name,
        'description': item.description or '',
        'price': str(item.price),
        'discount_price': str(item.discount_price) if item.discount_price else None,
        'image': images[0] if images else None,   # backward compat
        'images': images,                           # new: array of up to 3
        'video': video_media.url if video_media else None,  # new
        'is_vegetarian': getattr(item, 'is_vegetarian', False),
        'is_vegan': getattr(item, 'is_vegan', False),
        'is_spicy': getattr(item, 'is_spicy', False),
        'preparation_time': getattr(item, 'preparation_time', None),
        'allergens': getattr(item, 'allergens', '') or '',
        'ingredients': getattr(item, 'ingredients', '') or '',
    })
```

- [ ] **Step 2: Add prefetch_related('media') in customer view**

Open `customer/views.py`. Find where `MenuItem` objects are fetched for the menu page. Look for a queryset like:
```python
MenuItem.objects.filter(...)
```
Add `.prefetch_related('media')` to it to avoid N+1 queries. For example:
```python
MenuItem.objects.filter(
    restaurant=restaurant, is_available=True
).select_related('category').prefetch_related('media')
```

- [ ] **Step 3: Commit**

```bash
git add base/templatetags/menu_extras.py customer/views.py
git commit -m "feat: item_json exposes images[] and video from Cloudinary media"
```

---

## Task 6: Customer modal — carousel + scroll indicator

**Files:**
- Modify: `templates/customer/base.html`
- Modify: `templates/customer/menu_detail_modal.html`

### Part A: Add carousel state to cartStore() in base.html

- [ ] **Step 1: Add carouselIndex to cartStore()**

In `templates/customer/base.html`, inside the `cartStore()` function, add `carouselIndex: 0` to the data object (after `modalQuantity: 1`):

```javascript
modalQuantity: 1,
carouselIndex: 0,
```

- [ ] **Step 2: Reset carousel in openModal()**

Inside `openModal(item)`:
```javascript
openModal(item) {
  this.modalItem = item;
  this.modalQuantity = 1;
  this.carouselIndex = 0;   // ← add this line
  this.modalOpen = true;
  document.body.classList.add('overflow-hidden');
},
```

### Part B: Replace modal hero section with carousel

- [ ] **Step 3: Replace the hero image section in menu_detail_modal.html**

Find and replace the entire media section (the two `<template x-if>` blocks for hero image and placeholder) with:

```html
<!-- Media carousel -->
<div x-show="modalItem && (modalItem.images?.length || modalItem.video)"
     class="w-full relative overflow-hidden" style="height: 240px;">

  <!-- Carousel track -->
  <div class="flex h-full transition-transform duration-300 ease-out"
       :style="'transform: translateX(-' + (carouselIndex * 100) + '%)'">

    <!-- Images -->
    <template x-for="(img, idx) in (modalItem?.images || [])" :key="idx">
      <div class="w-full h-full flex-shrink-0 relative">
        <img :src="img" :alt="modalItem?.name"
             class="w-full h-full object-cover">
        <div class="absolute inset-0"
             style="background: linear-gradient(to top, rgba(0,0,0,0.35) 0%, transparent 55%);"></div>
      </div>
    </template>

    <!-- Video (last slide) -->
    <template x-if="modalItem?.video">
      <div class="w-full h-full flex-shrink-0 bg-black flex items-center justify-center relative">
        <video :src="modalItem.video"
               class="w-full h-full object-contain"
               controls playsinline preload="metadata">
        </video>
      </div>
    </template>

  </div>

  <!-- Scroll indicator dots -->
  <div class="absolute bottom-3 left-0 right-0 flex justify-center gap-1.5 z-10"
       x-show="(modalItem?.images?.length || 0) + (modalItem?.video ? 1 : 0) > 1">
    <template x-for="(_, idx) in [...(modalItem?.images || []), ...(modalItem?.video ? [1] : [])]" :key="idx">
      <button @click="carouselIndex = idx"
              class="rounded-full transition-all duration-200"
              :class="carouselIndex === idx
                ? 'w-5 h-1.5 bg-white'
                : 'w-1.5 h-1.5 bg-white/50'">
      </button>
    </template>
  </div>

  <!-- Prev / Next arrows (only if > 1 slide) -->
  <template x-if="(modalItem?.images?.length || 0) + (modalItem?.video ? 1 : 0) > 1">
    <div>
      <button @click="carouselIndex = Math.max(0, carouselIndex - 1)"
              x-show="carouselIndex > 0"
              class="absolute left-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/30 backdrop-blur-sm flex items-center justify-center text-white z-10 active:scale-90">
        <i class="ri-arrow-left-s-line text-lg"></i>
      </button>
      <button @click="carouselIndex = Math.min((modalItem?.images?.length || 0) + (modalItem?.video ? 1 : 0) - 1, carouselIndex + 1)"
              x-show="carouselIndex < (modalItem?.images?.length || 0) + (modalItem?.video ? 1 : 0) - 1"
              class="absolute right-2 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full bg-black/30 backdrop-blur-sm flex items-center justify-center text-white z-10 active:scale-90">
        <i class="ri-arrow-right-s-line text-lg"></i>
      </button>
    </div>
  </template>

</div>

<!-- Placeholder when no media -->
<template x-if="!modalItem || (!modalItem.images?.length && !modalItem.video)">
  <div class="w-full h-32 flex items-center justify-center"
       style="background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);">
    <i class="ri-restaurant-line text-5xl text-slate-200"></i>
  </div>
</template>
```

- [ ] **Step 4: Commit**

```bash
git add templates/customer/base.html templates/customer/menu_detail_modal.html
git commit -m "feat: customer modal carousel with scroll indicator and video support"
```

---

## Task 7: End-to-end test

- [ ] **Step 1: Start the dev server**

```bash
cd "/home/jey/Documents/projet /OpendFood"
python manage.py runserver
```

- [ ] **Step 2: Test image upload to Cloudinary**

1. Go to admin → create a menu item → upload 2 images + 1 video
2. Submit the form
3. Verify `MenuItemMedia.objects.count()` returns 3 in the shell
4. Check that `.url` properties return `https://res.cloudinary.com/...` URLs

```bash
python manage.py shell -c "
from base.models import MenuItemMedia
for m in MenuItemMedia.objects.all()[:5]:
    print(m.media_type, m.url[:60])
"
```

- [ ] **Step 3: Test customer-facing carousel**

1. Open a customer menu URL (e.g. http://le-festival-des-rois.localhost:8000/t/...)
2. Click a menu item that has 2+ images
3. Verify: carousel slides, dots highlight correctly, arrows appear/disappear at edges
4. Verify: video slide plays when navigated to
5. Verify: single-image items show no dots/arrows

- [ ] **Step 4: Test backward compatibility**

Open a menu item that has the old `MenuItem.image` (no `MenuItemMedia` records). Verify it still shows the image in the modal (via the `images` fallback in `item_json`).

---

## Notes

- **Existing media files**: Files already on local disk are NOT auto-migrated to Cloudinary. New uploads go to Cloudinary. Old `MenuItem.image` values pointing to local paths will continue to work as long as `MEDIA_ROOT` is accessible. Once all items are updated via the admin, old files can be removed.
- **QR codes**: Generated programmatically and saved via `ImageField.save()`. With `DEFAULT_FILE_STORAGE` set to Cloudinary, these will also upload automatically — but `Image.open(qr_settings.bg_image.path)` in `base/models.py:239` uses `.path` which is not available for Cloudinary-stored files. This line needs a fix: use `qr_settings.bg_image.read()` or `requests.get(qr_settings.bg_image.url)` instead of `.path`. Flag this as a follow-up if QR generation is tested.
- **Video upload limits**: Cloudinary free tier allows videos up to 100MB. Add server-side size validation in the view if needed.
