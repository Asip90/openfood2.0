# base/staff_urls.py
from django.urls import path
from django.http import HttpResponse
from base.decorators import staff_required


def _stub(request, **kw):
    return HttpResponse('stub')


@staff_required()
def _protected_stub(request, **kw):
    return HttpResponse('stub')


urlpatterns = [
    path('connexion/',                  _stub,           name='staff_login'),
    path('deconnexion/',                _stub,           name='staff_logout'),
    path('commandes/',                  _protected_stub, name='staff_orders'),
    path('commandes/<int:pk>/statut/',  _protected_stub, name='staff_change_status'),
    path('commandes/check/',            _protected_stub, name='staff_check_updates'),
]
