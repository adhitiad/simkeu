from django.apps import AppConfig


class PlatformAppConfig(AppConfig):
    name = "apps.platform_app"
    label = "platform"
    default_auto_field = "django.db.models.BigAutoField"
