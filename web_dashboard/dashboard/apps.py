from django.apps import AppConfig


class DashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'dashboard'
    verbose_name = 'Nagatha Dashboard'

    def ready(self):
        # Import signals here to ensure they are connected
        try:
            import dashboard.signals  # noqa F401
        except ImportError:
            pass