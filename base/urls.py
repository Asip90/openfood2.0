from django.urls import path
from base.views import *
from base import staff_admin_views
from base import subscription_views


urlpatterns = [
    path('', home, name="home"),

    path("restaurant/create/", create_restaurant, name="create_restaurant"),

    # Dashboard
    path("dashboard/", dashboard, name="dashboard"),

    # Analytiques
    path("analytiques/", analytics_view, name="analytics"),

    # Commandes
    path("orders/check/", check_new_orders, name="check_new_orders"),
    path("orders/export-csv/", export_orders_csv, name="export_orders_csv"),
    path("orders/", orders_list, name="orders_list"),
    path("orders/create-manual-order/", create_manual_order, name="create_manual_order"),
    path("orders/<int:pk>/recu/", order_receipt, name="order_receipt"),
    path("orders/<int:pk>/", order_detail, name="order_detail"),
    path('orders/<int:order_id>/update/', update_order, name='update_order'),
    path('orders/<int:order_id>/delete/', delete_order, name='delete_order'),
    path("orders/<int:pk>/change-status/", order_change_status, name="order_change_status"),

    # Catégories
    path("categories/create/", create_category, name="create_category"),
    path("categories/create/modale/", create_category_modale, name="create_category_modale"),

    # Menus
    path("menus/", menus_list, name="menus_list"),
    path("menus/<int:pk>/update/", menu_update, name="menu_update"),
    path("menus/<int:pk>/delete/", menu_delete, name="menu_delete"),
    path("menus/create/", menu_create, name="menu_create"),
    path("menus/<int:pk>/change-availability/", change_menu_status, name="menu_toggle_availability"),

    # Tables
    path("tables/", tables_list, name="tables_list"),
    path("tables/create/", table_create, name="table_create"),
    path("tables/<int:table_id>/delete/", table_delete, name="table_delete"),
    path("tables/<int:table_id>/toggle_active/", table_toggle_active, name="table_toggle_active"),
    path("tables/<int:table_id>/regenerate_qr/", table_regenerate_qr, name="table_regenerate_qr"),
    path("tables/<int:table_id>/update/", table_update, name="table_update"),
    path("tables/qr-settings/", qr_settings_view, name="qr_settings"),

    # Personnalisation
    path("customization/", customization, name="customization"),
    path("customization/reset/", reset_customization, name="reset_customization"),

    # Paramètres restaurant
    path("settings/", restaurant_settings, name="restaurant_settings"),
    path("reglages/", settings_hub, name="settings_hub"),

    # PWA
    path("manifest/<slug:slug>.json", pwa_manifest, name="pwa_manifest"),

    # Équipe — invitation flow
    path('equipe/', staff_admin_views.staff_list, name='staff_list'),
    path('equipe/inviter/', staff_admin_views.staff_invite, name='staff_invite'),
    path('equipe/accepter/<uuid:token>/', staff_admin_views.staff_invite_accept, name='staff_invite_accept'),
    path('equipe/<int:pk>/supprimer/', staff_admin_views.staff_delete, name='staff_delete'),

    # Tarification
    path('tarifs/', subscription_views.pricing, name='pricing'),

    # Abonnements / FedaPay
    path('abonnement/<str:plan_type>/payer/', subscription_views.subscribe_initiate, name='subscribe_initiate'),
    path('abonnement/callback/<str:plan_type>/', subscription_views.subscribe_callback, name='subscribe_callback'),
    path('abonnement/statut/', subscription_views.subscription_status, name='subscription_status'),
]
