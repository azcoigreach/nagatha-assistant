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
    path('test-simple-task/', views.test_simple_task_api, name='test_simple_task_api'),
    path('user-preferences/', views.get_user_preferences, name='get_user_preferences'),
    path('user-preferences/update/', views.update_user_preferences, name='update_user_preferences'),
    path('test-theme/', views.test_theme_api, name='test_theme_api'),
]