# base/staff_urls.py
from django.urls import path
from django.http import HttpResponse
from base import staff_views


def _stub(request, **kw):
    from base.decorators import staff_required
    @staff_required()
    def protected_stub(req, **k):
        return HttpResponse('stub')
    return protected_stub(request, **kw)


urlpatterns = [
    path('connexion/',                  staff_views.staff_login,   name='staff_login'),
    path('deconnexion/',                staff_views.staff_logout,  name='staff_logout'),
    path('commandes/',                  _stub,                     name='staff_orders'),
    path('commandes/<int:pk>/statut/',  _stub,                     name='staff_change_status'),
    path('commandes/check/',            _stub,                     name='staff_check_updates'),
]
