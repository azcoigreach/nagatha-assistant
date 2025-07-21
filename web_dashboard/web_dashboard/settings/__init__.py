"""
Settings package initialization.
"""

import os

# Set the Django settings module based on environment
DJANGO_ENV = os.getenv('DJANGO_ENV', 'production')

if DJANGO_ENV == 'development':
    from .development import *
else:
    from .production import *