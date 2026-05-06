from django.core.management.base import BaseCommand
from base.models import SubscriptionPlan, PromoCode


PLANS = [
    {
        'name': 'Gratuit',
        'plan_type': 'gratuit',
        'price': 0,
        'duration_days': 36500,  # 100 ans = permanent
        'max_menu_items': 5,
        'max_tables': 3,
        'max_staff': 0,
        'analytics': False,
        'advanced_analytics': False,
        'remove_branding': False,
        'priority_support': False,
    },
    {
        'name': 'Pro',
        'plan_type': 'pro',
        'price': 9900,
        'duration_days': 30,
        'max_menu_items': 0,   # 0 = illimité
        'max_tables': 20,
        'max_staff': 4,
        'analytics': True,
        'advanced_analytics': False,
        'remove_branding': False,
        'priority_support': False,
    },
    {
        'name': 'Max',
        'plan_type': 'max',
        'price': 19900,
        'duration_days': 30,
        'max_menu_items': 0,   # illimité
        'max_tables': 0,       # illimité
        'max_staff': 0,        # illimité
        'analytics': True,
        'advanced_analytics': True,
        'remove_branding': True,
        'priority_support': True,
    },
]

PROMO_CODES = [
    {
        'code': 'PREMIER',
        'plan_type': 'pro',
        'duration_days': 30,
        'max_uses': None,      # illimité
    },
    {
        'code': 'ELITE',
        'plan_type': 'max',
        'duration_days': 30,
        'max_uses': None,      # illimité
    },
]


class Command(BaseCommand):
    help = 'Crée les plans d\'abonnement et les codes promo de lancement'

    def handle(self, *args, **options):
        # Plans
        for data in PLANS:
            plan, created = SubscriptionPlan.objects.update_or_create(
                plan_type=data['plan_type'],
                defaults={**data, 'is_active': True},
            )
            status = 'créé' if created else 'mis à jour'
            self.stdout.write(f'  Plan {plan.name} ({plan.price} FCFA) — {status}')

        # Promo codes
        for pc in PROMO_CODES:
            plan = SubscriptionPlan.objects.get(plan_type=pc['plan_type'])
            obj, created = PromoCode.objects.update_or_create(
                code=pc['code'],
                defaults={
                    'plan': plan,
                    'duration_days': pc['duration_days'],
                    'max_uses': pc['max_uses'],
                    'is_active': True,
                },
            )
            status = 'créé' if created else 'mis à jour'
            self.stdout.write(f'  Code {obj.code} → {plan.name} — {status}')

        self.stdout.write(self.style.SUCCESS('\nSeed terminé avec succès.'))
