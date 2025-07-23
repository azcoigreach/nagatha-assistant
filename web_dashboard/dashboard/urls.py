"""
URL configuration for the dashboard app.
"""
from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.DashboardView.as_view(), name='index'),
    path('session/<uuid:session_id>/', views.session_detail, name='session_detail'),
    path('components/', views.ComponentsExampleView.as_view(), name='components_example'),
    path('health/', views.health_check, name='health_check'),
    
    # API endpoints
    path('api/send-message/', views.send_message, name='send_message'),
    path('api/send-message-nagatha-core/', views.send_message_nagatha_core, name='send_message_nagatha_core'),
    path('api/test-simple-task/', views.test_simple_task_api, name='test_simple_task_api'),
    path('api/test-minimal-orm/', views.test_minimal_orm_api, name='test_minimal_orm_api'),
    path('api/system-status/', views.system_status, name='system_status'),
    path('api/session-messages/<uuid:session_id>/', views.get_session_messages, name='get_session_messages'),
    path('api/task-status/<str:task_id>/', views.task_status, name='task_status'),
    path('api/user-preferences/', views.get_user_preferences, name='get_user_preferences'),
    path('api/update-preferences/', views.update_user_preferences, name='update_user_preferences'),
    path('api/test-theme/', views.test_theme_api, name='test_theme_api'),
]