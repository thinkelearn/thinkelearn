from django.apps import AppConfig


class LmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lms"

    def ready(self):
        import lms.signals  # noqa: F401
        from lms.wagtail_lms_admin import patch_wagtail_lms_viewset_group

        patch_wagtail_lms_viewset_group()
