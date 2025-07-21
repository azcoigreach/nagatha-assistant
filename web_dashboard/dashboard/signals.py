"""
Django signals for the dashboard app.
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.contrib.auth.models import User
from .models import UserPreferences, Session
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=User)
def create_user_preferences(sender, instance, created, **kwargs):
    """Create user preferences when a new user is created."""
    if created:
        UserPreferences.objects.create(user=instance)
        logger.info(f"Created preferences for user {instance.username}")


@receiver(post_save, sender=Session)
def update_session_title(sender, instance, created, **kwargs):
    """Update session title if it's empty."""
    if created and not instance.title:
        # Generate a default title based on creation time
        title = f"Session {instance.created_at.strftime('%Y-%m-%d %H:%M')}"
        Session.objects.filter(id=instance.id).update(title=title)