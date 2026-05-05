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


COOK_ALLOWED_STATUSES = {'preparing', 'ready', 'cancelled'}
SERVER_ALLOWED_STATUSES = {'delivered'}
COADMIN_ALLOWED_STATUSES = {'pending', 'confirmed', 'preparing', 'ready', 'delivered', 'cancelled'}


@staff_required(roles=['cuisinier', 'serveur', 'coadmin'])
def staff_orders(request):
    """Main orders view for staff portal."""
    staff = request.staff_member
    restaurant = staff.restaurant

    active_orders = Order.objects.filter(
        restaurant=restaurant,
        status__in=['pending', 'confirmed', 'preparing', 'ready'],
    ).prefetch_related('items__menu_item').order_by('created_at')

    latest = Order.objects.filter(restaurant=restaurant).order_by('-id').first()
    latest_order_id = latest.id if latest else 0

    return render(request, 'staff/orders/list.html', {
        'orders': active_orders,
        'staff': staff,
        'latest_order_id': latest_order_id,
        'ready_count': active_orders.filter(status='ready').count(),
    })


@staff_required(roles=['cuisinier', 'serveur', 'coadmin'])
def staff_change_status(request, pk):
    """Change order status based on staff role permissions."""
    if request.method != 'POST':
        return redirect('staff_orders')

    staff = request.staff_member
    restaurant = staff.restaurant
    order = get_object_or_404(Order, pk=pk, restaurant=restaurant)

    new_status = request.POST.get('status', '').strip()

    if staff.role == 'cuisinier':
        allowed = COOK_ALLOWED_STATUSES
    elif staff.role == 'serveur':
        allowed = SERVER_ALLOWED_STATUSES
    else:
        allowed = COADMIN_ALLOWED_STATUSES

    if new_status not in allowed:
        return redirect('staff_orders')

    order.status = new_status
    if new_status == 'preparing':
        order.preparing_by_name = staff.get_full_name()
    order.save(update_fields=['status', 'preparing_by_name', 'updated_at'])
    return redirect('staff_orders')


@staff_required(roles=['cuisinier', 'serveur', 'coadmin'])
def staff_check_updates(request):
    """
    Polling JSON endpoint.
    GET param: last_id (last known order id)
    Returns: new orders count, active order statuses, ready count
    """
    staff = request.staff_member
    restaurant = staff.restaurant
    last_id = int(request.GET.get('last_id', 0))

    new_orders_qs = Order.objects.filter(restaurant=restaurant, id__gt=last_id)

    active_orders = list(
        Order.objects.filter(
            restaurant=restaurant,
            status__in=['pending', 'confirmed', 'preparing', 'ready'],
        ).values('id', 'order_number', 'status', 'preparing_by_name', 'updated_at')
    )

    # Make updated_at JSON-serializable
    for o in active_orders:
        if o['updated_at']:
            o['updated_at'] = o['updated_at'].isoformat()

    latest_new = new_orders_qs.order_by('-id').first()

    return JsonResponse({
        'new_count': new_orders_qs.count(),
        'orders': active_orders,
        'ready_count': Order.objects.filter(restaurant=restaurant, status='ready').count(),
        'latest_id': latest_new.id if latest_new else last_id,
    })
