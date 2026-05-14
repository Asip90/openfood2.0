from django.urls import path
from accounts.views import *


urlpatterns = [

    path('connexion/', connexion, name="connexion"),
    path('inscription/', inscription, name="inscription"),
    path("verify-email/<uuid:token>/", verify_email, name="verify-email"),
    path("logout/", log_out, name="deconnexion"),
    path("mot-de-passe-oublie/", mot_de_passe_oublie, name="mot-de-passe-oublie"),
    path("reinitialiser-mot-de-passe/<uuid:token>/", reinitialiser_mot_de_passe, name="reinitialiser-mot-de-passe"),

]
