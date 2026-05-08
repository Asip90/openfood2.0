from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.utils import timezone
from datetime import timedelta

from base.decorators import get_user_restaurant
from base.models import StaffInvitation
from .utils import send_verification_email, send_password_reset_email
from .models import User


def connexion(request):
    if request.method == "POST":
        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.error(request, "Email ou mot de passe incorrect.")
            return redirect("connexion")

        if not user.email_verified:
            messages.error(
                request,
                "Votre email n'est pas encore vérifié. Vérifiez votre boîte mail."
            )
            return redirect("connexion")

        login(request, user)

        next_url = request.GET.get('next') or request.POST.get('next')
        if next_url and next_url.startswith('/'):
            return redirect(next_url)

        restaurant, role = get_user_restaurant(user)
        if restaurant:
            return redirect("dashboard")

        pending = StaffInvitation.objects.filter(
            email=user.email.lower(),
            accepted=False,
            expires_at__gt=timezone.now(),
        ).order_by('-expires_at').first()
        if pending:
            return redirect('staff_invite_accept', token=pending.token)

        return redirect("create_restaurant")

    next_url = request.GET.get('next', '')
    return render(request, "auth/connexion.html", {'next': next_url})


def inscription(request):
    if request.method == "POST":
        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email")
        password = request.POST.get("password")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Cet email existe déjà.")
            return redirect("inscription")

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True
        )

        send_verification_email(request, user)

        messages.success(
            request,
            "Compte créé avec succès. Vérifiez votre email pour activer votre compte."
        )
        return redirect("connexion")

    return render(request, "auth/inscription.html")


def verify_email(request, token):
    user = get_object_or_404(User, email_token=token)

    if user.email_verified:
        messages.info(request, "Votre email est déjà vérifié.")
        return redirect("connexion")

    user.email_verified = True
    user.email_token = None
    user.save()

    messages.success(request, "Email vérifié avec succès 🎉")
    return redirect("connexion")


def log_out(request):
    logout(request)
    return redirect("connexion")


def mot_de_passe_oublie(request):
    if request.method == "POST":
        email = request.POST.get("email", "").strip()
        try:
            user = User.objects.get(email=email)
            send_password_reset_email(request, user)
        except User.DoesNotExist:
            pass  # Ne pas révéler si l'email existe

        messages.success(
            request,
            "Si cet email est associé à un compte, vous recevrez un lien de réinitialisation dans quelques minutes."
        )
        return redirect("mot-de-passe-oublie")

    return render(request, "auth/mot_de_passe_oublie.html")


def reinitialiser_mot_de_passe(request, token):
    user = get_object_or_404(User, password_reset_token=token)

    # Token valable 1 heure
    if user.password_reset_token_created_at:
        expiry = user.password_reset_token_created_at + timedelta(hours=1)
        if timezone.now() > expiry:
            user.password_reset_token = None
            user.password_reset_token_created_at = None
            user.save(update_fields=["password_reset_token", "password_reset_token_created_at"])
            messages.error(request, "Ce lien a expiré. Veuillez faire une nouvelle demande.")
            return redirect("mot-de-passe-oublie")

    if request.method == "POST":
        password = request.POST.get("password", "")
        password_confirm = request.POST.get("password_confirm", "")

        if len(password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return render(request, "auth/reinitialiser_mot_de_passe.html", {"token": token})

        if password != password_confirm:
            messages.error(request, "Les mots de passe ne correspondent pas.")
            return render(request, "auth/reinitialiser_mot_de_passe.html", {"token": token})

        user.set_password(password)
        user.password_reset_token = None
        user.password_reset_token_created_at = None
        user.save()

        messages.success(request, "Mot de passe modifié avec succès. Vous pouvez vous connecter.")
        return redirect("connexion")

    return render(request, "auth/reinitialiser_mot_de_passe.html", {"token": token})
