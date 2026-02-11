from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from wagtail import urls as wagtail_urls
from wagtail.admin import urls as wagtailadmin_urls
from wagtail.documents import urls as wagtaildocs_urls

from lms import views as lms_views
from search import views as search_views

from . import views

urlpatterns = [
    path("django-admin/", admin.site.urls),
    path("admin/", include(wagtailadmin_urls)),
    path("documents/", include(wagtaildocs_urls)),
    path("search/", search_views.search, name="search"),
    path("privacy/", views.privacy_policy, name="privacy_policy"),
    path("terms/", views.terms_and_conditions, name="terms_and_conditions"),
    path("parent-help/", views.parent_help, name="parent_help"),
    path("communications/", include("communications.urls")),
    path("portfolio/", include("portfolio.urls")),
    path("payments/", include("payments.urls")),
    path(
        "lms/course/<int:course_id>/feedback/",
        lms_views.submit_course_feedback,
        name="course_feedback",
    ),
    # Override upstream SCORM content view to guard against S3 URL failures
    path(
        "lms/scorm-content/<path:content_path>",
        lms_views.SafeRedirectScormContentView.as_view(),
        name="serve_scorm_content",
    ),
    path("lms/", include("wagtail_lms.urls")),
    # django-allauth authentication URLs - must be before Wagtail catch-all
    # Reserved path: avoid other "accounts/" URL patterns to prevent conflicts
]

urlpatterns += [
    path("accounts/", include("allauth.urls")),
]


if settings.DEBUG:
    from django.conf.urls.static import static
    from django.contrib.staticfiles.urls import staticfiles_urlpatterns

    from portfolio.views import serve_extracted_content

    # Add specific URL pattern for extracted portfolio content FIRST
    urlpatterns += [
        path(
            "media/portfolio_extracted/<int:document_id>/<path:file_path>",
            serve_extracted_content,
            name="portfolio_extracted_content",
        ),
    ]

    # Serve static and media files from development server
    urlpatterns += staticfiles_urlpatterns()
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

urlpatterns = urlpatterns + [
    # For anything not caught by a more specific rule above, hand over to
    # Wagtail's page serving mechanism. This should be the last pattern in
    # the list:
    path("", include(wagtail_urls)),
    # Alternatively, if you want Wagtail pages to be served from a subpath
    # of your site, rather than the site root:
    #    path("pages/", include(wagtail_urls)),
]
