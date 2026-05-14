from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponse

from .models import User


def send_verification_email(request, user):
    token = user.email_token

    verification_url = request.build_absolute_uri(
        reverse("verify-email", args=[str(token)])
    )

    subject = "Vérification de votre email"
    message = f"""
Bonjour {user.first_name},

Merci pour votre inscription.

Cliquez sur le lien ci-dessous pour vérifier votre adresse email :
{verification_url}

Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )


def send_password_reset_email(request, user):
    import uuid
    from django.utils import timezone

    user.password_reset_token = uuid.uuid4()
    user.password_reset_token_created_at = timezone.now()
    user.save(update_fields=["password_reset_token", "password_reset_token_created_at"])

    reset_url = request.build_absolute_uri(
        reverse("reinitialiser-mot-de-passe", args=[str(user.password_reset_token)])
    )

    subject = "Réinitialisation de votre mot de passe"
    message = f"""Bonjour {user.first_name},

Vous avez demandé à réinitialiser votre mot de passe OpenFood.

Cliquez sur le lien ci-dessous pour choisir un nouveau mot de passe (valable 1 heure) :
{reset_url}

Si vous n'êtes pas à l'origine de cette demande, ignorez ce message.
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=True,
    )
