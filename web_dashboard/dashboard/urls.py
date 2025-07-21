"""
URL configuration for the dashboard app.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('health/', views.health_check, name='health_check'),
]