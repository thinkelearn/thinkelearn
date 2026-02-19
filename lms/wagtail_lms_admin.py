"""Wagtail admin customizations for wagtail-lms integration."""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.urls import path, reverse
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSetGroup
from wagtail_lms.viewsets import (
    CourseEnrollmentViewSet,
    LMSViewSetGroup,
    SCORMAttemptViewSet,
    SCORMPackageViewSet,
)

from .scorm_upload import (
    finalize_upload_response,
    presigned_upload_response,
    s3_upload_enabled,
)

logger = logging.getLogger(__name__)


class SCORMPackageCreateView(generic.CreateView):
    """Create view with optional direct-to-S3 flow for SCORM packages."""

    template_name = "lms/wagtail_lms/scormpackage/create.html"
    presigned_upload_url_name = ""
    finalize_upload_url_name = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["s3_upload_enabled"] = s3_upload_enabled()
        context["presigned_upload_url"] = reverse(self.presigned_upload_url_name)
        context["finalize_upload_url"] = reverse(self.finalize_upload_url_name)
        return context


class SCORMPackageUploadViewSet(SCORMPackageViewSet):
    """SCORM package viewset with direct-to-S3 upload endpoints."""

    add_view_class = SCORMPackageCreateView

    def get_add_view_kwargs(self, **kwargs):
        return super().get_add_view_kwargs(
            presigned_upload_url_name=self.get_url_name("presigned_upload"),
            finalize_upload_url_name=self.get_url_name("finalize_upload"),
            **kwargs,
        )

    def get_urlpatterns(self):
        urlpatterns = super().get_urlpatterns()
        urlpatterns += [
            path(
                "presigned-upload/",
                self.presigned_upload_view,
                name="presigned_upload",
            ),
            path(
                "finalize-upload/",
                self.finalize_upload_view,
                name="finalize_upload",
            ),
        ]
        return urlpatterns

    def _has_add_permission(self, request) -> bool:
        return self.permission_policy.user_has_permission(request.user, "add")

    def presigned_upload_view(self, request):
        if not self._has_add_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return presigned_upload_response(request)

    def finalize_upload_view(self, request):
        if not self._has_add_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return finalize_upload_response(
            request,
            redirect_url_builder=lambda package: reverse(
                self.get_url_name("edit"), args=[package.pk]
            ),
        )


class LMSUploadViewSetGroup(ModelViewSetGroup):
    """LMS admin group with custom SCORM package upload viewset."""

    menu_label = LMSViewSetGroup.menu_label
    menu_icon = LMSViewSetGroup.menu_icon
    items = (SCORMPackageUploadViewSet, CourseEnrollmentViewSet, SCORMAttemptViewSet)


def patch_wagtail_lms_viewset_group() -> None:
    """Replace wagtail-lms SCORM package viewset with project custom version."""
    from wagtail_lms import wagtail_hooks

    group = getattr(wagtail_hooks, "lms_viewset_group", None)
    if group is None:
        logger.warning("wagtail_lms.wagtail_hooks.lms_viewset_group not found")
        return

    if not isinstance(group, ModelViewSetGroup):
        logger.warning("wagtail_lms lms_viewset_group is not a ModelViewSetGroup")
        return

    for index, registerable in enumerate(group.registerables):
        if type(registerable) is SCORMPackageUploadViewSet:
            return
        if type(registerable) is SCORMPackageViewSet:
            group.registerables[index] = SCORMPackageUploadViewSet()
            logger.info("Patched wagtail-lms SCORMPackage viewset for S3 upload flow")
            return

    logger.warning("Could not find wagtail-lms SCORMPackageViewSet to patch")
