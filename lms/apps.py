from django.apps import AppConfig


class LmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lms"

    def ready(self):
        import lms.signals  # noqa: F401
        from lms.wagtail_lms_admin import (
            patch_h5p_snippet_viewset,
            patch_wagtail_lms_viewset_group,
        )

        patch_wagtail_lms_viewset_group()
        patch_h5p_snippet_viewset()
        _patch_wagtail_lms_title_panels()
        _patch_lesson_page_parent_types()


def _patch_lesson_page_parent_types():
    """Allow LessonPage to be created under ExtendedCoursePage.

    Wagtail's page-type check is bidirectional: both parent.subpage_types and
    child.parent_page_types must agree. LessonPage.parent_page_types ships as
    ["wagtail_lms.CoursePage"] (exact class), which excludes ExtendedCoursePage
    even after we add "wagtail_lms.LessonPage" to ExtendedCoursePage.subpage_types.
    We patch parent_page_types here and clear the internal cache so Wagtail
    re-resolves the list on first use.
    """
    import logging

    from wagtail_lms.models import LessonPage

    logger = logging.getLogger(__name__)

    if "lms.ExtendedCoursePage" not in LessonPage.parent_page_types:
        LessonPage.parent_page_types = list(LessonPage.parent_page_types) + [
            "lms.ExtendedCoursePage"
        ]
        # Clear cached model list so Wagtail re-resolves on first use
        LessonPage._clean_parent_page_models = None
        logger.info(
            "Patched LessonPage.parent_page_types to include ExtendedCoursePage"
        )


def _patch_wagtail_lms_title_panels():
    """Replace TitleFieldPanel with FieldPanel for models without slug targets.

    wagtail-lms defines TitleFieldPanel("title") on snippet models that do not
    include a slug field. In this configuration, Wagtail renders the title
    widget with a w-sync controller and an empty target selector, which triggers
    a runtime querySelectorAll("") error in admin.
    """
    import logging

    from wagtail.admin.panels import FieldPanel, TitleFieldPanel
    from wagtail.admin.panels.model_utils import get_edit_handler
    from wagtail_lms.models import H5PActivity, SCORMPackage

    logger = logging.getLogger(__name__)

    patched_any = False
    for model in (SCORMPackage, H5PActivity):
        panels = list(getattr(model, "panels", []))
        updated_panels = []
        model_patched = False

        for panel in panels:
            if isinstance(panel, TitleFieldPanel) and panel.field_name == "title":
                updated_panels.append(FieldPanel("title"))
                model_patched = True
            else:
                updated_panels.append(panel)

        if model_patched:
            model.panels = updated_panels
            patched_any = True
            logger.info(
                "Patched %s.panels title field to use FieldPanel without w-sync",
                model.__name__,
            )

    if patched_any:
        # Ensure Wagtail rebuilds bound edit handlers from the patched panel defs.
        get_edit_handler.cache_clear()
