"""
Settings package initialization.
"""

import os

# Set the Django settings module based on environment
# Only use DJANGO_ENV if DJANGO_SETTINGS_MODULE is not explicitly set
if not os.environ.get('DJANGO_SETTINGS_MODULE'):
    DJANGO_ENV = os.getenv('DJANGO_ENV', 'production')
    
    if DJANGO_ENV == 'development':
        from .development import *
    else:
        from .production import *