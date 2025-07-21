"""
Django admin configuration for the dashboard models.
"""
from django.contrib import admin
from .models import Session, Message, SystemStatus, UserPreferences, Task


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('nagatha_session_id', 'title', 'user', 'created_at', 'updated_at', 'is_active')
    list_filter = ('is_active', 'created_at', 'updated_at')
    search_fields = ('title', 'user__username')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-updated_at',)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ('session', 'message_type', 'content_preview', 'created_at')
    list_filter = ('message_type', 'created_at')
    search_fields = ('content', 'session__title')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)
    
    def content_preview(self, obj):
        return obj.content[:50] + ('...' if len(obj.content) > 50 else '')
    content_preview.short_description = 'Content Preview'


@admin.register(SystemStatus)
class SystemStatusAdmin(admin.ModelAdmin):
    list_display = ('timestamp', 'system_health', 'mcp_servers_connected', 'total_tools_available', 'active_sessions')
    list_filter = ('system_health', 'timestamp')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)


@admin.register(UserPreferences)
class UserPreferencesAdmin(admin.ModelAdmin):
    list_display = ('user', 'theme', 'language', 'notifications_enabled', 'updated_at')
    list_filter = ('theme', 'language', 'notifications_enabled')
    search_fields = ('user__username',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('task_name', 'status', 'user', 'session', 'progress', 'created_at', 'completed_at')
    list_filter = ('status', 'task_name', 'created_at')
    search_fields = ('task_name', 'description', 'user__username')
    readonly_fields = ('id', 'created_at', 'started_at', 'completed_at')
    ordering = ('-created_at',)