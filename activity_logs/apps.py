from django.apps import AppConfig


class ActivityLogsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'activity_logs'
    verbose_name = 'Registro de atividades'

    def ready(self):
        from . import signals  # noqa: F401
