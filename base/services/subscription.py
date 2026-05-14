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
