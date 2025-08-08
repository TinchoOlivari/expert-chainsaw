from django.urls import path
from . import views

app_name = 'payment_instructions'

urlpatterns = [
    # Operator interface
    path('', views.operator_dashboard, name='operator_dashboard'),
    path('login/', views.operator_login, name='operator_login'),
    path('logout/', views.operator_logout, name='operator_logout'),
    
    # AJAX endpoints
    path('search-alias/', views.search_alias, name='search_alias'),
    path('create-payment/', views.create_payment, name='create_payment'),
] 