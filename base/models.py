# models.py
# from tkinter import N
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.text import slugify
from django.core.validators import MinLengthValidator
import qrcode
from qrcode.constants import ERROR_CORRECT_H
from io import BytesIO
from django.core.files import File
from decimal import Decimal
from PIL import Image, ImageDraw, ImageOps


from accounts.models import User

import uuid
import random
import string

_SHORT_ID_CHARS = string.ascii_letters + string.digits  # base62


def _generate_table_token():
    return ''.join(random.choices(_SHORT_ID_CHARS, k=10))



class SubscriptionPlan(models.Model):
    PLAN_TYPES = [
        ('gratuit', 'Gratuit'),
        ('pro', 'Pro'),
        ('max', 'Max'),
    ]

    name = models.CharField(max_length=100)
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(default=30)

    # Limits — 0 means unlimited
    max_menu_items = models.IntegerField(default=5)
    max_tables = models.IntegerField(default=3)
    max_staff = models.IntegerField(default=0)

    # Features
    analytics = models.BooleanField(default=False)
    advanced_analytics = models.BooleanField(default=False)
    remove_branding = models.BooleanField(default=False)
    priority_support = models.BooleanField(default=False)
    custom_domain = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.price} FCFA)"

    def is_unlimited(self, field):
        return getattr(self, field) == 0


class PromoCode(models.Model):
    code = models.CharField(max_length=50, unique=True, db_index=True)
    plan = models.ForeignKey(
        SubscriptionPlan, on_delete=models.CASCADE, related_name='promo_codes'
    )
    duration_days = models.IntegerField(default=30)
    max_uses = models.IntegerField(null=True, blank=True)  # null = unlimited
    uses_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)  # null = never expires
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.code} → {self.plan.name}"

    def is_valid(self):
        from django.utils import timezone
        if not self.is_active:
            return False
        if self.expires_at and self.expires_at < timezone.now():
            return False
        if self.max_uses is not None and self.uses_count >= self.max_uses:
            return False
        return True


class PromoCodeUse(models.Model):
    promo_code = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name='uses')
    restaurant = models.ForeignKey('Restaurant', on_delete=models.CASCADE, related_name='promo_uses')
    used_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('promo_code', 'restaurant')



class Restaurant(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='restaurants')
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    # subdomain = models.CharField(max_length=100, unique=True, blank=True)
    subdomain = models.SlugField(unique=True,null=True, blank=True)
    
    # Info restaurant
    description = models.TextField(blank=True)
    address = models.CharField(max_length=300)
    phone = models.CharField(max_length=20)
    email = models.EmailField()
    
    # Images
    logo = models.ImageField(upload_to='restaurants/logos/', blank=True)
    cover_image = models.ImageField(upload_to='restaurants/covers/', blank=True)
    
    # Horaires
    opening_hours = models.JSONField(default=dict, blank=True)
    
    # Subscription
    subscription_plan = models.ForeignKey(SubscriptionPlan, on_delete=models.SET_NULL, null=True)
    subscription_start = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # QR Code
    qr_code = models.ImageField(upload_to='qrcodes/', blank=True)
    
    # Customization
    primary_color = models.CharField(max_length=7, default='#FF6B6B')
    secondary_color = models.CharField(max_length=7, default='#4ECDC4')
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            i = 1
            while Restaurant.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{i}"
                i += 1
            self.slug = slug

        if not self.subdomain:
            self.subdomain = self.slug
        super().save(*args, **kwargs)
        
        # Générer QR Code
        if not self.qr_code:
            self.generate_qr_code()
    
    def generate_qr_code(self):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        url = f"https://{self.subdomain}.votredomaine.com"
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color=self.primary_color, back_color="white")
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        filename = f'qr_{self.slug}.png'
        self.qr_code.save(filename, File(buffer), save=False)
        super().save(update_fields=['qr_code'])
    
    def __str__(self):
        return self.name


class Category(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(blank=True)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='categories/', blank=True)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name_plural = 'Categories'
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.restaurant.name} - {self.name}"

class MenuItem(models.Model):
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='menu_items')
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='items')
    
    name = models.CharField(max_length=200)
    slug = models.SlugField(blank=True)
    description = models.TextField(blank=True)
    
    # Prix
    price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Images
    image = models.ImageField(upload_to='menu_items/', blank=True)
    
    # Info
    ingredients = models.TextField(blank=True)
    allergens = models.CharField(max_length=300, blank=True)
    is_vegetarian = models.BooleanField(default=False)
    is_vegan = models.BooleanField(default=False)
    is_spicy = models.BooleanField(default=False)
    
    # Stock
    is_available = models.BooleanField(default=True)
    preparation_time = models.IntegerField(help_text="Temps en minutes", default=15)
    
    order = models.IntegerField(default=0)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} - {self.price}€"


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
        if not self.file:
            return ''
        if self.media_type == 'video':
            return cloudinary.CloudinaryVideo(str(self.file)).build_url()
        return cloudinary.CloudinaryImage(str(self.file)).build_url()


from django.conf import settings


def _hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def _build_qr_background(size, qr_settings):
    """Retourne une image PIL de fond selon le type choisi."""
    if qr_settings.bg_type == 'image' and qr_settings.bg_image:
        try:
            bg = Image.open(qr_settings.bg_image.path).convert('RGB')
            bg = ImageOps.fit(bg, (size, size), Image.LANCZOS)
            return bg
        except Exception:
            pass  # fallback to color

    if qr_settings.bg_type == 'gradient':
        r1, g1, b1 = _hex_to_rgb(qr_settings.bg_gradient_from)
        r2, g2, b2 = _hex_to_rgb(qr_settings.bg_gradient_to)
        bg = Image.new('RGB', (size, size))
        draw = ImageDraw.Draw(bg)
        for i in range(size):
            ratio = i / size
            r = int(r1 + (r2 - r1) * ratio)
            g = int(g1 + (g2 - g1) * ratio)
            b = int(b1 + (b2 - b1) * ratio)
            draw.line([(i, 0), (i, size)], fill=(r, g, b))
        return bg

    # default: couleur unie
    return Image.new('RGB', (size, size), _hex_to_rgb(qr_settings.bg_color))


def _compose_qr_image(url, qr_settings, logo_path=None):
    """Génère le QR code final composé avec fond + logo optionnel."""
    size = qr_settings.output_size

    # 1. Générer le QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(url)
    qr.make(fit=True)

    qr_img = qr.make_image(fill_color=qr_settings.qr_color, back_color='white').convert('RGBA')

    # 2. Coller le logo au centre si demandé
    if qr_settings.show_logo and logo_path:
        try:
            logo = Image.open(logo_path).convert('RGBA')
            qr_w, qr_h = qr_img.size
            logo_size = int(qr_w * 0.22)
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)
            pos = ((qr_w - logo_size) // 2, (qr_h - logo_size) // 2)
            # Fond blanc circulaire derrière le logo
            white_bg = Image.new('RGBA', (logo_size, logo_size), (255, 255, 255, 255))
            qr_img.paste(white_bg, pos)
            qr_img.paste(logo, pos, logo)
        except Exception:
            pass

    # 3. Construire le fond
    bg = _build_qr_background(size, qr_settings).convert('RGBA')

    # 4. Redimensionner le QR à 78% du fond et le centrer
    scale = max(10, min(90, qr_settings.qr_scale)) / 100
    qr_display_size = int(size * scale)
    qr_img = qr_img.resize((qr_display_size, qr_display_size), Image.LANCZOS)
    offset = (size - qr_display_size) // 2
    bg.paste(qr_img, (offset, offset), qr_img)

    return bg.convert('RGB')


class Table(models.Model):
    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="tables"
    )
    number = models.CharField(max_length=20)
    capacity = models.IntegerField()
    qr_code = models.ImageField(
        upload_to="table_qrcodes/",
        blank=True,
        null=True
    )
    is_active = models.BooleanField(default=True)
    token = models.CharField(
        max_length=10,
        default=_generate_table_token,
        editable=False,
        unique=True
    )

    class Meta:
        unique_together = ("restaurant", "number")

    def generate_qr_code(self):
        subdomain = self.restaurant.subdomain or slugify(self.restaurant.name)
        base = settings.FRONTEND_BASE_URL.rstrip('/').removeprefix('https://').removeprefix('http://')
        url = f"https://{subdomain}.{base}/t/{self.token}"

        try:
            qr_settings = self.restaurant.qr_settings
        except Exception:
            qr_settings = None

        if qr_settings:
            logo_path = None
            if qr_settings.show_logo:
                try:
                    logo_path = self.restaurant.customization.logo.path
                except Exception:
                    try:
                        logo_path = self.restaurant.logo.path
                    except Exception:
                        pass
            img = _compose_qr_image(url, qr_settings, logo_path)
        else:
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

        buffer = BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        filename = f"table_{self.restaurant.slug}_{self.number}.png"
        self.qr_code.save(filename, File(buffer), save=False)

    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # Générer QR Code avant le save si la table est nouvelle
        if is_new and not self.qr_code:
            self.generate_qr_code()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Table {self.number} - {self.restaurant.name}"



class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('confirmed', 'Confirmée'),
        ('preparing', 'En préparation'),
        ('ready', 'Prête'),
        ('delivered', 'Livrée'),
        ('cancelled', 'Annulée'),
    ]
    
    ORDER_TYPE_CHOICES = [
        ('dine_in', 'Sur place'),
        ('takeaway', 'À emporter'),
        ('delivery', 'Livraison'),
    ]
    
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name='orders')
    table = models.ForeignKey(Table, on_delete=models.SET_NULL, null=True, blank=True)
    order_number = models.CharField(max_length=20, unique=True, blank=True)
    
    # Client info
    customer_name = models.CharField(max_length=200, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)
    
    # Order details
    order_type = models.CharField(max_length=20, choices=ORDER_TYPE_CHOICES, default='dine_in')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Prix
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    notes = models.TextField(blank=True)
    preparing_by_name = models.CharField(max_length=150, blank=True, default='')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_number:
            self.order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def calculate_total(self):
        self.subtotal = sum(
            (item.get_total() for item in self.items.all()),
            Decimal("0.00")
        )
        self.tax = Decimal("0.00")
        self.total = self.subtotal
        self.save(update_fields=["subtotal", "tax", "total"])

        
    def __str__(self):
        return f"{self.order_number} - {self.restaurant.name}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    
    quantity = models.IntegerField(default=1)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    
    def get_total(self):
        return self.price * self.quantity
    
    def save(self, *args, **kwargs):
        if not self.price:
            self.price = self.menu_item.discount_price or self.menu_item.price
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.menu_item.name} x{self.quantity}"

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
        return f"{self.user.first_name} {self.user.last_name}".strip()

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


class Payment(models.Model):
    PAYMENT_METHOD = [
        ('cash', 'Espèces'),
        ('card', 'Carte bancaire'),
        ('mobile', 'Paiement mobile'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'En attente'),
        ('completed', 'Complété'),
        ('failed', 'Échoué'),
    ]
    
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=200, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Payment {self.order.order_number} - {self.amount}FCFA"
    
    
class RestaurantCustomization(models.Model):
    FONT_CHOICES = [
        ('inter', 'Inter'),
        ('poppins', 'Poppins'),
        ('montserrat', 'Montserrat'),
        ('roboto', 'Roboto'),
    ]

    restaurant = models.OneToOneField(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="customization"
    )

    # 🎨 Couleurs
    primary_color = models.CharField(
        max_length=7,
        default="#16a34a",
        help_text="Couleur principale (ex: #16a34a)"
    )
    secondary_color = models.CharField(
        max_length=7,
        default="#f97316",
        help_text="Couleur secondaire"
    )

    # 🖼️ Branding
    logo = models.ImageField(
        upload_to="restaurants/customization/logos/",
        blank=True,
        null=True
    )
    cover_image = models.ImageField(
        upload_to="restaurants/customization/covers/",
        blank=True,
        null=True
    )

    # 🔤 Typographie
    font_family = models.CharField(
        max_length=50,
        choices=FONT_CHOICES,
        default="poppins"
    )

    # 🔄 Options futures
    use_custom_theme = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Customisation - {self.restaurant.name}"


class QRSettings(models.Model):
    BG_TYPE_CHOICES = [
        ('color',    'Couleur unie'),
        ('gradient', 'Dégradé'),
        ('image',    'Image'),
    ]

    restaurant        = models.OneToOneField(Restaurant, on_delete=models.CASCADE, related_name='qr_settings')
    bg_type           = models.CharField(max_length=10, choices=BG_TYPE_CHOICES, default='color')
    bg_color          = models.CharField(max_length=7, default='#ffffff')
    bg_gradient_from  = models.CharField(max_length=7, default='#f97316')
    bg_gradient_to    = models.CharField(max_length=7, default='#ea580c')
    bg_gradient_angle = models.IntegerField(default=135)
    bg_image          = models.ImageField(upload_to='qr_backgrounds/', blank=True, null=True)
    qr_color          = models.CharField(max_length=7, default='#000000')
    show_logo         = models.BooleanField(default=False)
    output_size       = models.IntegerField(default=600)
    qr_scale          = models.IntegerField(default=60, help_text="Taille du QR en % de l'image (10–90)")

    def __str__(self):
        return f"QR Settings - {self.restaurant.name}"
