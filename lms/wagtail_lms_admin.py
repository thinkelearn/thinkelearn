"""Wagtail admin viewset overrides for wagtail-lms integration."""

from __future__ import annotations

from django.http import JsonResponse
from django.urls import path, reverse
from wagtail.admin.views import generic
from wagtail_lms.viewsets import (
    H5PActivitySnippetViewSet,
    H5PActivityViewSet,
    SCORMPackageViewSet,
)

from .h5p_upload import h5p_finalize_upload_response, h5p_presigned_upload_response
from .scorm_upload import (
    finalize_upload_response,
    presigned_upload_response,
    s3_upload_enabled,
)


class S3UploadCreateView(generic.CreateView):
    """Base create view with optional direct-to-S3 flow."""

    presigned_upload_url_name = ""
    finalize_upload_url_name = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["s3_upload_enabled"] = s3_upload_enabled()
        if context["s3_upload_enabled"]:
            context["presigned_upload_url"] = reverse(self.presigned_upload_url_name)
            context["finalize_upload_url"] = reverse(self.finalize_upload_url_name)
        return context


class SCORMPackageCreateView(S3UploadCreateView):
    """Create view with optional direct-to-S3 flow for SCORM packages."""

    template_name = "lms/wagtail_lms/scormpackage/create.html"


class H5PActivityCreateView(S3UploadCreateView):
    """Create view with optional direct-to-S3 flow for H5P activities."""

    template_name = "lms/wagtail_lms/h5pactivity/create.html"


class H5PActivitySnippetCreateView(S3UploadCreateView):
    """Create view with optional direct-to-S3 flow for H5P snippets."""

    template_name = "lms/wagtail_lms/h5pactivity/create.html"


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
                "presigned-upload/", self.presigned_upload_view, name="presigned_upload"
            ),
            path("finalize-upload/", self.finalize_upload_view, name="finalize_upload"),
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


class H5PActivityUploadViewSet(H5PActivityViewSet):
    """H5P activity viewset with direct-to-S3 upload endpoints."""

    add_view_class = H5PActivityCreateView

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
                "presigned-upload/", self.presigned_upload_view, name="presigned_upload"
            ),
            path("finalize-upload/", self.finalize_upload_view, name="finalize_upload"),
        ]
        return urlpatterns

    def _has_add_permission(self, request) -> bool:
        return self.permission_policy.user_has_permission(request.user, "add")

    def presigned_upload_view(self, request):
        if not self._has_add_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return h5p_presigned_upload_response(request)

    def finalize_upload_view(self, request):
        if not self._has_add_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return h5p_finalize_upload_response(
            request,
            redirect_url_builder=lambda activity: reverse(
                self.get_url_name("edit"), args=[activity.pk]
            ),
        )


class H5PActivitySnippetUploadViewSet(H5PActivitySnippetViewSet):
    """H5P snippet viewset with direct-to-S3 upload endpoints."""

    add_view_class = H5PActivitySnippetCreateView

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
                "presigned-upload/", self.presigned_upload_view, name="presigned_upload"
            ),
            path("finalize-upload/", self.finalize_upload_view, name="finalize_upload"),
        ]
        return urlpatterns

    def _has_add_permission(self, request) -> bool:
        return self.permission_policy.user_has_permission(request.user, "add")

    def presigned_upload_view(self, request):
        if not self._has_add_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return h5p_presigned_upload_response(request)

    def finalize_upload_view(self, request):
        if not self._has_add_permission(request):
            return JsonResponse({"error": "Permission denied"}, status=403)
        return h5p_finalize_upload_response(
            request,
            redirect_url_builder=lambda activity: reverse(
                self.get_url_name("edit"), args=[activity.pk]
            ),
        )
