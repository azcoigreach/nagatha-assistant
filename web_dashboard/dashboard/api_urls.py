"""
API URL configuration for the dashboard app.
"""
from django.urls import path
from . import views

app_name = 'dashboard_api'

urlpatterns = [
    path('send-message/', views.send_message, name='send_message'),
    path('session/<uuid:session_id>/messages/', views.get_session_messages, name='session_messages'),
    path('system-status/', views.system_status, name='system_status'),
    path('task/<str:task_id>/status/', views.task_status, name='task_status'),
]