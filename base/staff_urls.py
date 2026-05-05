# base/staff_urls.py
from django.urls import path
from base import staff_views

urlpatterns = [
    path('connexion/',                  staff_views.staff_login,         name='staff_login'),
    path('deconnexion/',                staff_views.staff_logout,        name='staff_logout'),
    path('commandes/',                  staff_views.staff_orders,        name='staff_orders'),
    path('commandes/<int:pk>/statut/',  staff_views.staff_change_status, name='staff_change_status'),
    path('commandes/check/',            staff_views.staff_check_updates, name='staff_check_updates'),
]
