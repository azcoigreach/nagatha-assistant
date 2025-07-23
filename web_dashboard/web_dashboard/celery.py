"""
Celery configuration for web_dashboard project.
"""
import os
import sys
from celery import Celery

# Set the Django settings module for the 'celery' program.
os.environ['DJANGO_SETTINGS_MODULE'] = os.getenv('DJANGO_SETTINGS_MODULE', 'web_dashboard.settings.development')

# Add the main Nagatha source directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

app = Celery('web_dashboard')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Also include the main Nagatha tasks
app.autodiscover_tasks(['nagatha_assistant'])


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')