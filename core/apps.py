from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Date years and email addresses are judged on every serializer (see validation_helpers).
        from .validation_helpers import install_global_checks

        install_global_checks()
