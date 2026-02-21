"""Wagtail admin customizations for wagtail-lms integration."""

from __future__ import annotations

import logging

from django.http import JsonResponse
from django.urls import path, reverse
from wagtail.admin.views import generic
from wagtail.admin.viewsets.model import ModelViewSetGroup
from wagtail_lms.viewsets import (
    H5PActivityViewSet,
    SCORMPackageViewSet,
)

from .h5p_upload import (
    h5p_finalize_upload_response,
    h5p_presigned_upload_response,
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
        s3_enabled = s3_upload_enabled()
        context["s3_upload_enabled"] = s3_enabled
        if s3_enabled:
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


class H5PActivityCreateView(generic.CreateView):
    """Create view with optional direct-to-S3 flow for H5P activities."""

    template_name = "lms/wagtail_lms/h5pactivity/create.html"
    presigned_upload_url_name = ""
    finalize_upload_url_name = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        s3_enabled = s3_upload_enabled()
        context["s3_upload_enabled"] = s3_enabled
        if s3_enabled:
            context["presigned_upload_url"] = reverse(self.presigned_upload_url_name)
            context["finalize_upload_url"] = reverse(self.finalize_upload_url_name)
        return context


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


class H5PActivitySnippetCreateView(generic.CreateView):
    """Create view for the @register_snippet entry point.

    H5PActivity is registered both via @register_snippet (URL:
    /admin/snippets/wagtail_lms/h5pactivity/add/) AND via the LMS
    ModelViewSetGroup (URL: /admin/h5pactivity/add/).  The snippet entry
    uses Wagtail's default form which tries a direct storage write — this
    breaks when S3 is configured but the upload body limit applies.

    This view replaces the snippet's add_view_class so both entry points
    use the same S3 presigned upload form.  The presigned/finalize API
    calls are forwarded to the LMS viewset's own endpoints (url namespace
    "h5pactivity"), keeping the permission check and redirect logic in one
    place.
    """

    template_name = "lms/wagtail_lms/h5pactivity/create.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        s3_enabled = s3_upload_enabled()
        context["s3_upload_enabled"] = s3_enabled
        if s3_enabled:
            context["presigned_upload_url"] = reverse("h5pactivity:presigned_upload")
            context["finalize_upload_url"] = reverse("h5pactivity:finalize_upload")
        return context


def patch_h5p_snippet_viewset() -> None:
    """Replace the add_view_class on the @register_snippet viewset for H5PActivity.

    H5PActivity is decorated with @register_snippet which creates a standard
    SnippetViewSet at /admin/snippets/wagtail_lms/h5pactivity/.  That viewset's
    default create view writes directly to storage, which fails with NoSuchBucket
    when S3 is configured.

    We swap in H5PActivitySnippetCreateView so the Snippets admin entry uses the
    same S3 presigned upload form as the LMS menu entry.  The change happens
    before Django resolves any URL patterns (all URL conf is lazy), so the
    patched class is picked up on the first request.
    """
    from wagtail.admin.viewsets import viewsets as viewset_registry
    from wagtail_lms.models import H5PActivity

    for vs in viewset_registry.viewsets:
        model = getattr(vs, "model", None)
        if model is H5PActivity and not isinstance(vs, H5PActivityUploadViewSet):
            vs.add_view_class = H5PActivitySnippetCreateView
            logger.info(
                "Patched H5PActivity snippet viewset add_view_class for S3 upload flow"
            )
            return

    logger.warning("Could not find @register_snippet viewset for H5PActivity to patch")


def patch_wagtail_lms_viewset_group() -> None:
    """Replace wagtail-lms viewsets with project custom versions."""
    from wagtail_lms import wagtail_hooks

    # This intentionally patches upstream wagtail-lms module state in-place.
    # If upstream changes its hook registration implementation, this may no-op.
    # Revisit this integration on wagtail-lms upgrades.
    group = getattr(wagtail_hooks, "lms_viewset_group", None)
    if group is None:
        logger.warning("wagtail_lms.wagtail_hooks.lms_viewset_group not found")
        return

    if not isinstance(group, ModelViewSetGroup):
        logger.warning("wagtail_lms lms_viewset_group is not a ModelViewSetGroup")
        return

    replacements = {
        SCORMPackageViewSet: SCORMPackageUploadViewSet,
        H5PActivityViewSet: H5PActivityUploadViewSet,
    }

    patched = set()
    for index, registerable in enumerate(group.registerables):
        upstream_type = type(registerable)
        if upstream_type in replacements:
            replacement_cls = replacements[upstream_type]
            group.registerables[index] = replacement_cls()
            logger.info(
                "Patched wagtail-lms %s viewset for S3 upload flow",
                upstream_type.__name__,
            )
            patched.add(upstream_type)
        elif any(issubclass(upstream_type, cls) for cls in replacements.values()):
            # Already patched (our custom subclass is already in place)
            patched.add(upstream_type)

    for upstream_type in replacements:
        if upstream_type not in patched:
            logger.warning(
                "Could not find wagtail-lms %s to patch", upstream_type.__name__
            )
