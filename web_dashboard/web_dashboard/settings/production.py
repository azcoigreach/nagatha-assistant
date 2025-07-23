"""
Production settings for web_dashboard project.
"""

from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = False

# Use environment variable for allowed hosts in production
ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

# Database - PostgreSQL for production
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('DB_NAME', 'nagatha_dashboard'),
        'USER': os.getenv('DB_USER', 'nagatha'),
        'PASSWORD': os.getenv('DB_PASSWORD', 'nagatha_password'),
        'HOST': os.getenv('DB_HOST', 'db'),
        'PORT': os.getenv('DB_PORT', '5432'),
    }
}

# Add django_celery_beat for Celery Beat functionality
INSTALLED_APPS += [
    'django_celery_beat',
]

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

# Cache (Redis) - Only for production
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/1",
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Celery Configuration - Only for production
CELERY_BROKER_URL = f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_RESULT_BACKEND = f"redis://{os.getenv('REDIS_HOST', 'redis')}:{os.getenv('REDIS_PORT', '6379')}/0"
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'

# Production logging with file output
LOG_DIR = os.getenv('LOG_DIR', '/app/logs')
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': os.path.join(LOG_DIR, 'django.log'),
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'nagatha_assistant': {
            'handlers': ['console', 'file'],
            'level': os.getenv('LOG_LEVEL', 'INFO'),
            'propagate': False,
        },
    },
}

# Security Settings for production
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False').lower() == 'true'
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings for production - more restrictive
CORS_ALLOWED_ORIGINS = os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if os.getenv('CORS_ALLOWED_ORIGINS') else []
CORS_ALLOW_CREDENTIALS = True