# base/emails.py
from django.core.mail import send_mail
from django.conf import settings


def send_staff_invitation_email(base_url: str, invitation) -> None:
    """
    Send invitation email to invitation.email.
    base_url: scheme + host, e.g. 'https://app.openfood.com'
    """
    accept_url = f"{base_url}/equipe/accepter/{invitation.token}/"
    role_display = dict(invitation.restaurant.staff.model.ROLE_CHOICES).get(
        invitation.role, invitation.role
    )
    subject = f"Invitation à rejoindre {invitation.restaurant.name} sur OpenFood"
    message = f"""Bonjour,

{invitation.restaurant.name} vous invite à rejoindre leur équipe en tant que {role_display}.

Cliquez sur le lien ci-dessous pour créer votre compte (valable 7 jours) :
{accept_url}

Si vous avez déjà un compte OpenFood, connectez-vous puis cliquez sur ce lien.

— L'équipe OpenFood
"""
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invitation.email],
        fail_silently=False,
    )
