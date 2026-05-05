# base/staff_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from base.models import StaffMember, Order
from base.staff_forms import StaffLoginForm
from base.decorators import staff_required, get_staff_from_session


def staff_login(request):
    """Staff portal login page."""
    if get_staff_from_session(request):
        return redirect('staff_orders')

    form = StaffLoginForm()
    error = None

    if request.method == 'POST':
        form = StaffLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            try:
                staff = StaffMember.objects.get(username=username, is_active=True)
                if staff.check_password(password):
                    request.session['staff_id'] = staff.id
                    request.session['staff_role'] = staff.role
                    return redirect('staff_orders')
                else:
                    error = "Identifiant ou mot de passe incorrect."
            except StaffMember.DoesNotExist:
                error = "Identifiant ou mot de passe incorrect."
            except StaffMember.MultipleObjectsReturned:
                error = "Identifiant ambigu. Contactez votre administrateur."

    return render(request, 'staff/connexion.html', {'form': form, 'error': error})


def staff_logout(request):
    """Staff portal logout."""
    request.session.pop('staff_id', None)
    request.session.pop('staff_role', None)
    return redirect('staff_login')
