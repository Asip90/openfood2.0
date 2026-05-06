# base/staff_admin_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import get_user_model

from base.models import StaffMember, StaffInvitation
from base.decorators import owner_or_coadmin_required, get_user_restaurant
from base.emails import send_staff_invitation_email

User = get_user_model()


@owner_or_coadmin_required
def staff_list(request):
    restaurant = request.restaurant
    members = StaffMember.objects.filter(restaurant=restaurant).select_related('user').order_by('role')
    pending_invitations = StaffInvitation.objects.filter(
        restaurant=restaurant, accepted=False,
        expires_at__gt=timezone.now(),
    ).order_by('-id')
    return render(request, 'admin_user/staff/list.html', {
        'members': members,
        'pending_invitations': pending_invitations,
        'restaurant': restaurant,
        'is_owner': request.user_role == 'owner',
    })


@owner_or_coadmin_required
def staff_invite(request):
    if request.method != 'POST':
        return redirect('staff_list')

    restaurant = request.restaurant
    email = request.POST.get('email', '').strip().lower()
    role = request.POST.get('role', '')

    valid_roles = [r[0] for r in StaffMember.ROLE_CHOICES]
    if role not in valid_roles:
        messages.error(request, "Rôle invalide.")
        return redirect('staff_list')

    # Coadmin cannot invite another coadmin
    if request.user_role == 'coadmin' and role == 'coadmin':
        messages.error(request, "Un co-administrateur ne peut pas inviter un autre co-administrateur.")
        return redirect('staff_list')

    if not email:
        messages.error(request, "Email requis.")
        return redirect('staff_list')

    # Check staff limit for current plan
    plan = restaurant.subscription_plan
    if plan and plan.max_staff > 0:
        current_staff = StaffMember.objects.filter(restaurant=restaurant).count()
        if current_staff >= plan.max_staff:
            messages.error(request, f"Votre plan {plan.name} est limité à {plan.max_staff} membres d'équipe. Passez au plan supérieur pour en ajouter davantage.")
            return redirect('staff_list')

    # Cannot invite yourself
    if email == request.user.email.lower():
        messages.error(request, "Vous ne pouvez pas vous inviter vous-même.")
        return redirect('staff_list')

    # Already a staff member in this restaurant?
    if StaffMember.objects.filter(restaurant=restaurant, user__email=email).exists():
        messages.error(request, "Cette personne fait déjà partie de votre équipe.")
        return redirect('staff_list')

    # Already a staff member in another restaurant?
    if StaffMember.objects.filter(user__email=email).exists():
        messages.error(request, "Cette personne fait déjà partie de l'équipe d'un autre restaurant.")
        return redirect('staff_list')

    # If user already exists in the system, create StaffMember directly
    existing_user = User.objects.filter(email=email).first()
    if existing_user:
        StaffMember.objects.create(
            user=existing_user, restaurant=restaurant, role=role
        )
        messages.success(request, f"{existing_user.first_name} {existing_user.last_name} a été ajouté(e) à l'équipe.")
        return redirect('staff_list')

    # New user: create invitation and send email
    invitation = StaffInvitation.objects.create(
        restaurant=restaurant,
        email=email,
        role=role,
        created_by=request.user,
        expires_at=timezone.now() + timezone.timedelta(days=7),
    )
    base_url = request.build_absolute_uri('/').rstrip('/')
    send_staff_invitation_email(base_url=base_url, invitation=invitation)
    messages.success(request, f"Invitation envoyée à {email}.")
    return redirect('staff_list')


def staff_invite_accept(request, token):
    """Public view (no login required). Handles invitation acceptance."""
    invitation = get_object_or_404(StaffInvitation, token=token)

    if not invitation.is_valid():
        return render(request, 'admin_user/staff/invite_accept.html', {
            'error': "Cette invitation a expiré ou a déjà été utilisée.",
        })

    # Case: user already logged in
    if request.user.is_authenticated:
        if request.user.email.lower() != invitation.email.lower():
            return render(request, 'admin_user/staff/invite_accept.html', {
                'error': "Vous êtes connecté avec un email différent de celui de l'invitation.",
                'invitation': invitation,
            })
        # Accept directly
        StaffMember.objects.get_or_create(
            user=request.user,
            restaurant=invitation.restaurant,
            defaults={'role': invitation.role},
        )
        invitation.accepted = True
        invitation.save(update_fields=['accepted'])
        messages.success(request, f"Vous avez rejoint l'équipe de {invitation.restaurant.name}.")
        return redirect('dashboard')

    # Case: user not logged in, existing account
    if User.objects.filter(email=invitation.email).exists():
        messages.info(request, "Connectez-vous pour rejoindre l'équipe.")
        return redirect(f"/connexion/?next=/equipe/accepter/{token}/")

    # Case: new user — show registration form
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        password = request.POST.get('password', '')

        if not first_name or not last_name or not password:
            return render(request, 'admin_user/staff/invite_accept.html', {
                'invitation': invitation,
                'error': "Tous les champs sont requis.",
            })

        new_user = User.objects.create_user(
            email=invitation.email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email_verified=True,
        )
        StaffMember.objects.create(
            user=new_user, restaurant=invitation.restaurant, role=invitation.role
        )
        invitation.accepted = True
        invitation.save(update_fields=['accepted'])
        messages.success(request, "Compte créé ! Connectez-vous pour accéder à votre espace.")
        return redirect('connexion')

    return render(request, 'admin_user/staff/invite_accept.html', {
        'invitation': invitation,
    })


@owner_or_coadmin_required
def staff_delete(request, pk):
    if request.method != 'POST':
        return redirect('staff_list')

    restaurant = request.restaurant
    member = get_object_or_404(StaffMember, pk=pk, restaurant=restaurant)

    # Coadmin cannot delete another coadmin
    if request.user_role == 'coadmin' and member.role == 'coadmin':
        messages.error(request, "Un co-administrateur ne peut pas supprimer un autre co-administrateur.")
        return redirect('staff_list')

    name = member.get_full_name()
    member.delete()
    messages.success(request, f"{name} a été retiré(e) de l'équipe.")
    return redirect('staff_list')
