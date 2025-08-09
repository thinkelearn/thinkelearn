from django.urls import path

from . import views

app_name = "portfolio"

urlpatterns = [
    path(
        "package/<int:page_id>/<int:document_id>/",
        views.package_viewer,
        name="package_viewer",
    ),
    path(
        "content/<int:document_id>/<path:file_path>",
        views.serve_extracted_content,
        name="serve_content",
    ),
]
