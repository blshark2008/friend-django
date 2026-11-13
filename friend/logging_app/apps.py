from django.apps import AppConfig


class LoggingAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'logging_app'
    verbose_name = 'Журнал операций'

    def ready(self):
        import logging_app.signals  # noqa: F401
