from django.urls import path, include
# from . import views
from django.urls import path
from .views import *
urlpatterns = [
    path("api/customer/", include("customer.api.urls")),

    path("t/<str:table_token>/", client_menu, name="client_menu"),

    # Panier (AJAX)
    path("t/<str:table_token>/cart/", update_cart, name="update_cart"),

    # Checkout
    path("t/<str:table_token>/checkout/", checkout, name="checkout"),

    # Confirmation + suivi (token non devinable — pas l'id séquentiel)
    path("order/<uuid:public_token>/confirmation/", order_confirmation, name="order_confirmation"),
    path("order/<uuid:public_token>/status/", order_status, name="order_status"),
    path("order/<uuid:public_token>/feedback/", submit_feedback, name="submit_feedback"),
    path("order/<uuid:public_token>/push-subscribe/", customer_push_subscribe, name="customer_push_subscribe"),

    # Mes commandes du jour (device-based, sans compte)
    path("mes-commandes/", my_orders, name="my_orders"),
    path("mes-commandes/rechercher/", my_orders_by_phone, name="my_orders_by_phone"),
    path('item/<str:item_id>/details/', get_item_details, name='get_item_details'),
    path("t/<str:table_token>/chat/", chat_assistant, name="chat_assistant"),
    path("api/customer/menu/<str:table_token>/", menu_api),

]

# from django.urls import path
# from . import views

# urlpatterns = [
#     path('t/<str:table_token>/', views.client_menu, name='client_menu'),
#     path('update_cart/<str:table_token>/', views.update_cart, name='update_cart'),
#     path('checkout/<str:table_token>/', views.checkout, name='checkout'),
#     path('confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
#     path('item/<str:item_id>/details/', views.get_item_details, name='get_item_details'),
# ]