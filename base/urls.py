from django.urls import path
from django.views.generic import TemplateView
from base.views import *
from base import staff_admin_views
from base import push_views
from base import subscription_views
from base import landing_views
from base import blog_views
from base import cashier_views


urlpatterns = [
    path('', home, name="home"),

    # Service worker servi à la racine → scope '/' (push sur toutes les pages)
    path('sw.js', service_worker, name='service_worker'),

    # Landing pages géographiques
    path('benin/', landing_views.landing_pays, {'pays_slug': 'benin'}, name='landing_benin'),
    path('cote-divoire/', landing_views.landing_pays, {'pays_slug': 'cote-divoire'}, name='landing_cote_divoire'),
    path('senegal/', landing_views.landing_pays, {'pays_slug': 'senegal'}, name='landing_senegal'),
    path('mali/', landing_views.landing_pays, {'pays_slug': 'mali'}, name='landing_mali'),

    # Blog SEO
    path('blog/', blog_views.blog_index, name='blog_index'),
    path('blog/<slug:slug>/', blog_views.blog_detail, name='blog_detail'),

    # Pages légales et utilitaires
    path('contact/', TemplateView.as_view(template_name='home/contact.html'), name='contact'),
    path('aide/', TemplateView.as_view(template_name='home/aide.html'), name='aide'),
    path('confidentialite/', TemplateView.as_view(template_name='home/confidentialite.html'), name='confidentialite'),
    path('conditions/', TemplateView.as_view(template_name='home/conditions.html'), name='conditions'),
    path('mentions-legales/', TemplateView.as_view(template_name='home/mentions_legales.html'), name='mentions_legales'),

    path("restaurant/create/", create_restaurant, name="create_restaurant"),

    # Dashboard
    path("dashboard/", dashboard, name="dashboard"),

    # Analytiques
    path("analytiques/", analytics_view, name="analytics"),

    # Commandes
    path("orders/check/", check_new_orders, name="check_new_orders"),
    path("orders/export-csv/", export_orders_csv, name="export_orders_csv"),
    path("orders/partial/", orders_partial, name="orders_partial"),
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
    path("menus/ai-description/", menu_ai_description, name="menu_ai_description"),
    path("menus/<int:pk>/change-availability/", change_menu_status, name="menu_toggle_availability"),
    path("menus/<int:pk>/toggle-featured/", change_menu_featured, name="menu_toggle_featured"),

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

    # Support
    path("support/", support_contact, name="support_contact"),

    # Caisse / encaissement
    path("caisse/", cashier_views.cashier, name="cashier"),
    path("caisse/table/<int:table_id>/", cashier_views.cashier_table, name="cashier_table"),
    path("caisse/commande/<int:order_id>/encaisser/", cashier_views.mark_order_paid, name="mark_order_paid"),
    path("caisse/commande/<int:order_id>/annuler-encaissement/", cashier_views.mark_order_unpaid, name="mark_order_unpaid"),
    path("caisse/table/<int:table_id>/encaisser/", cashier_views.mark_table_paid, name="mark_table_paid"),

    # Clients
    path("clients/", customers_list, name="customers_list"),

    # Retours clients
    path("retours/", feedback_list, name="feedback_list"),

    # Affiches (générateur IA)
    path("affiches/", posters_studio, name="posters_studio"),
    path("affiches/generer/", posters_generate, name="posters_generate"),
    path("affiches/<int:poster_id>/raffiner/", posters_refine, name="posters_refine"),

    # PWA
    path("manifest/<slug:slug>.json", pwa_manifest, name="pwa_manifest"),

    # Équipe — invitation flow
    path('activite/', activity_list, name='activity_list'),
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
    path('abonnement/webhook/', subscription_views.fedapay_webhook, name='fedapay_webhook'),

    # Waiter Call API
    path('api/waiter-call/<str:table_token>/', create_waiter_call, name='create_waiter_call'),
    path('api/waiter-calls/pending/', list_waiter_calls, name='list_waiter_calls'),
    path('api/waiter-calls/<int:call_id>/claim/', claim_waiter_call, name='claim_waiter_call'),
    path('api/orders/ready/', list_ready_orders, name='list_ready_orders'),

    # Web Push API
    path('api/push/vapid-public-key/', push_views.vapid_public_key, name='push_vapid_key'),
    path('api/push/subscribe/', push_views.push_subscribe, name='push_subscribe'),
    path('api/push/unsubscribe/', push_views.push_unsubscribe, name='push_unsubscribe'),
]
