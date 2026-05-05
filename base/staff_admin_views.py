# base/staff_admin_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from base.models import StaffMember
from base.staff_forms import StaffMemberForm
from base.decorators import admin_or_coadmin_required


@admin_or_coadmin_required
def staff_list(request):
    restaurant = request.managing_restaurant
    members = StaffMember.objects.filter(restaurant=restaurant).order_by('role', 'first_name')
    return render(request, 'admin_user/staff/list.html', {
        'members': members,
        'restaurant': restaurant,
        'is_owner': request.staff_member is None,
    })


@admin_or_coadmin_required
def staff_create(request):
    restaurant = request.managing_restaurant
    form = StaffMemberForm()

    if request.method == 'POST':
        form = StaffMemberForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Coadmin cannot create another coadmin
            if request.staff_member and cd['role'] == 'coadmin':
                messages.error(request, "Un co-administrateur ne peut pas créer un autre co-administrateur.")
                return render(request, 'admin_user/staff/create.html', {
                    'form': form, 'restaurant': restaurant
                })
            if not cd.get('password'):
                messages.error(request, "Un mot de passe est requis à la création.")
                return render(request, 'admin_user/staff/create.html', {
                    'form': form, 'restaurant': restaurant
                })
            if StaffMember.objects.filter(restaurant=restaurant, username=cd['username']).exists():
                form.add_error('username', "Cet identifiant est déjà utilisé dans ce restaurant.")
                return render(request, 'admin_user/staff/create.html', {
                    'form': form, 'restaurant': restaurant
                })
            member = StaffMember(
                restaurant=restaurant,
                first_name=cd['first_name'],
                last_name=cd['last_name'],
                username=cd['username'],
                role=cd['role'],
                is_active=cd.get('is_active', True),
            )
            member.set_password(cd['password'])
            member.save()
            messages.success(request, f"Compte créé pour {member.get_full_name()}.")
            return redirect('staff_list')

    return render(request, 'admin_user/staff/create.html', {
        'form': form, 'restaurant': restaurant
    })


@admin_or_coadmin_required
def staff_update(request, pk):
    restaurant = request.managing_restaurant
    member = get_object_or_404(StaffMember, pk=pk, restaurant=restaurant)

    # Coadmin cannot edit another coadmin
    if request.staff_member and member.role == 'coadmin':
        messages.error(request, "Action non autorisée.")
        return redirect('staff_list')

    form = StaffMemberForm(initial={
        'first_name': member.first_name,
        'last_name': member.last_name,
        'username': member.username,
        'role': member.role,
        'is_active': member.is_active,
    })

    if request.method == 'POST':
        form = StaffMemberForm(data=request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Coadmin cannot promote to coadmin role
            if request.staff_member and cd['role'] == 'coadmin':
                messages.error(request, "Un co-administrateur ne peut pas attribuer le rôle co-administrateur.")
                return render(request, 'admin_user/staff/update.html', {
                    'form': form, 'member': member, 'restaurant': restaurant
                })
            member.first_name = cd['first_name']
            member.last_name = cd['last_name']
            member.username = cd['username']
            member.role = cd['role']
            member.is_active = cd.get('is_active', True)
            if cd.get('password'):
                member.set_password(cd['password'])
            member.save()
            messages.success(request, f"Compte de {member.get_full_name()} mis à jour.")
            return redirect('staff_list')

    return render(request, 'admin_user/staff/update.html', {
        'form': form, 'member': member, 'restaurant': restaurant
    })


@admin_or_coadmin_required
def staff_delete(request, pk):
    restaurant = request.managing_restaurant
    member = get_object_or_404(StaffMember, pk=pk, restaurant=restaurant)

    # Coadmin cannot delete another coadmin
    if request.staff_member and member.role == 'coadmin':
        messages.error(request, "Un co-administrateur ne peut pas supprimer un autre co-administrateur.")
        return redirect('staff_list')

    if request.method == 'POST':
        name = member.get_full_name()
        member.delete()
        messages.success(request, f"{name} a été supprimé.")
    return redirect('staff_list')
