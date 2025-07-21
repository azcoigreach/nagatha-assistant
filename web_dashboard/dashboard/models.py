"""
Django models for the Nagatha Dashboard.

These models provide web-specific functionality and interface with the
existing Nagatha Assistant core through the adapter layer.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import uuid


class Session(models.Model):
    """Web representation of a Nagatha session."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nagatha_session_id = models.IntegerField(unique=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f"Session {self.nagatha_session_id or 'New'}: {self.title or 'Untitled'}"


class Message(models.Model):
    """Web representation of a message."""
    MESSAGE_TYPES = [
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
        ('error', 'Error'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, related_name='messages')
    content = models.TextField()
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='user')
    created_at = models.DateTimeField(default=timezone.now)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"{self.message_type}: {self.content[:50]}..."


class SystemStatus(models.Model):
    """System status information for the dashboard."""
    timestamp = models.DateTimeField(default=timezone.now)
    mcp_servers_connected = models.IntegerField(default=0)
    total_tools_available = models.IntegerField(default=0)
    active_sessions = models.IntegerField(default=0)
    system_health = models.CharField(max_length=20, default='unknown')
    cpu_usage = models.FloatField(null=True, blank=True)
    memory_usage = models.FloatField(null=True, blank=True)
    disk_usage = models.FloatField(null=True, blank=True)
    additional_metrics = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Status at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"


class UserPreferences(models.Model):
    """User preferences for the dashboard."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard_preferences')
    theme = models.CharField(max_length=20, default='light', choices=[
        ('light', 'Light'),
        ('dark', 'Dark'),
        ('auto', 'Auto'),
    ])
    language = models.CharField(max_length=10, default='en')
    notifications_enabled = models.BooleanField(default=True)
    auto_refresh_interval = models.IntegerField(default=30)  # seconds
    preferences = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Preferences for {self.user.username}"


class Task(models.Model):
    """Background task tracking."""
    TASK_STATUS = [
        ('pending', 'Pending'),
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    celery_task_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    session = models.ForeignKey(Session, on_delete=models.CASCADE, null=True, blank=True)
    task_name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=TASK_STATUS, default='pending')
    progress = models.IntegerField(default=0)  # 0-100
    result = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.task_name} ({self.status})"