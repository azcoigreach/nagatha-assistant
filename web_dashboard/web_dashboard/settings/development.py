"""
Development settings for web_dashboard project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

# Allow all hosts in development (use specific hosts in production)
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,0.0.0.0').split(',')

# Database - Use SQLite for development
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Add django_celery_beat for Celery Beat functionality
INSTALLED_APPS += [
    'django_celery_beat',
]

# Cache (Redis) - For development
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Celery Configuration - For development
CELERY_BROKER_URL = f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_RESULT_BACKEND = f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Celery Beat Configuration
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Celery Beat Scheduled Tasks for Nagatha Integration
CELERY_BEAT_SCHEDULE = {
    # MCP Server Health Checks - Every 5 minutes
    'check-mcp-servers-health': {
        'task': 'dashboard.nagatha_celery_integration.check_mcp_servers_health',
        'schedule': 300.0,  # 5 minutes
    },
    
    # Memory Cleanup and Maintenance - Every hour
    'cleanup-memory-and-maintenance': {
        'task': 'dashboard.nagatha_celery_integration.cleanup_memory_and_maintenance',
        'schedule': 3600.0,  # 1 hour
    },
    
    # Usage Metrics Tracking - Every 15 minutes
    'track-usage-metrics': {
        'task': 'dashboard.nagatha_celery_integration.track_usage_metrics',
        'schedule': 900.0,  # 15 minutes
    },
    
    # Scheduled Tasks and Reminders - Every minute
    'process-scheduled-tasks': {
        'task': 'dashboard.nagatha_celery_integration.process_scheduled_tasks',
        'schedule': 60.0,  # 1 minute
    },
    
    # System Status Refresh - Every 2 minutes
    'refresh-system-status': {
        'task': 'dashboard.refresh_system_status',
        'schedule': 120.0,  # 2 minutes
    },
    
    # Data Cleanup - Every 6 hours
    'cleanup-old-data': {
        'task': 'dashboard.cleanup_old_data',
        'schedule': 21600.0,  # 6 hours
    },
}

# CORS settings for development
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

CORS_ALLOW_CREDENTIALS = True

# Simple logging for development
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'nagatha_assistant': {
            'handlers': ['console'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# Development-specific settings
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# For development, disable some security features
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False