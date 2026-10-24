from django.apps import AppConfig


class HrConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "hr"
    label = "hr"
    verbose_name = "HR"

    def ready(self):
        # System checks (hr/checks.py) run on every manage.py command, so a convention broken by mistake stops the command with a message.
        from . import checks  # noqa: F401
