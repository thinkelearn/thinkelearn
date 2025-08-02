import os
import zipfile

from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt
from wagtail.documents.models import Document

from .models import ShowcasePage


@xframe_options_exempt
def package_viewer(request, page_id, document_id):
    """
    View for displaying packaged learning content (Rise, Storyline, etc.)
    Extracts ZIP files and serves the main index.html in an iframe
    """
    page = get_object_or_404(ShowcasePage, pk=page_id)
    document = get_object_or_404(Document, pk=document_id)

    # Check if document belongs to this page's content
    page_documents = []
    for section in page.content_sections:
        if section.block_type == "packaged_content":
            if (
                section.value.get("package_file")
                and section.value["package_file"].id == document.id
            ):
                page_documents.append(document)

    if document not in page_documents:
        raise Http404("Document not found in this page")

    # Check if file is a ZIP
    if not document.file.name.lower().endswith(".zip"):
        return HttpResponse("File must be a ZIP archive", status=400)

    # Create extraction path based on document ID
    extract_path = os.path.join(
        settings.MEDIA_ROOT, "showcase_extracted", str(document.id)
    )

    # Extract if not already extracted or if ZIP is newer
    if not os.path.exists(extract_path) or os.path.getmtime(
        document.file.path
    ) > os.path.getmtime(extract_path):
        try:
            # Clean existing extraction
            if os.path.exists(extract_path):
                import shutil

                shutil.rmtree(extract_path)

            os.makedirs(extract_path, exist_ok=True)

            # Extract ZIP file
            with zipfile.ZipFile(document.file.path, "r") as zip_ref:
                # Security check - prevent path traversal
                for member in zip_ref.namelist():
                    if os.path.isabs(member) or ".." in member:
                        continue
                    zip_ref.extract(member, extract_path)

        except (zipfile.BadZipFile, PermissionError) as e:
            return HttpResponse(f"Error extracting ZIP file: {str(e)}", status=500)

    # Find index.html or similar entry point
    possible_entries = ["index.html", "index.htm", "main.html", "start.html"]
    entry_file = None
    entry_dir = ""

    # First, check the root directory
    for entry in possible_entries:
        entry_path = os.path.join(extract_path, entry)
        if os.path.exists(entry_path):
            entry_file = entry
            entry_dir = ""
            break

    # If not found in root, check common subdirectories
    if not entry_file:
        common_subdirs = ["content", "src", "dist", "build", "web"]
        for subdir in common_subdirs:
            subdir_path = os.path.join(extract_path, subdir)
            if os.path.exists(subdir_path) and os.path.isdir(subdir_path):
                for entry in possible_entries:
                    entry_path = os.path.join(subdir_path, entry)
                    if os.path.exists(entry_path):
                        entry_file = entry
                        entry_dir = subdir + "/"
                        break
                if entry_file:
                    break

    # If still not found, look for any HTML files recursively
    if not entry_file:
        for root, _dirs, files in os.walk(extract_path):
            html_files = [f for f in files if f.lower().endswith(".html")]
            if html_files:
                # Calculate relative path from extract_path
                rel_root = os.path.relpath(root, extract_path)
                if rel_root == ".":
                    entry_dir = ""
                else:
                    entry_dir = rel_root.replace(os.sep, "/") + "/"
                entry_file = html_files[0]
                break

        if not entry_file:
            return HttpResponse("No HTML entry point found in the package", status=400)

    # Serve the content via URL
    content_url = (
        f"{settings.MEDIA_URL}showcase_extracted/{document.id}/{entry_dir}{entry_file}"
    )

    context = {
        "page": page,
        "document": document,
        "content_url": content_url,
        "entry_file": entry_file,
    }

    return render(request, "showcase/package_viewer.html", context)


def serve_extracted_content(request, document_id, file_path):
    """
    Serve extracted package content files
    """
    document = get_object_or_404(Document, pk=document_id)
    extract_path = os.path.join(
        settings.MEDIA_ROOT, "showcase_extracted", str(document.id)
    )

    # Normalize the file path to prevent path traversal
    file_path = file_path.replace("\\", "/")
    full_path = os.path.join(extract_path, file_path)
    full_path = os.path.normpath(full_path)

    # Security check - ensure the resolved path is within the extract directory
    if not full_path.startswith(extract_path):
        raise Http404("Access denied")

    if not os.path.exists(full_path):
        raise Http404(f"File not found: {file_path}")

    # Determine content type based on file extension
    file_ext = os.path.splitext(file_path)[1].lower()
    content_type_map = {
        ".html": "text/html",
        ".htm": "text/html",
        ".css": "text/css",
        ".js": "application/javascript",
        ".json": "application/json",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".svg": "image/svg+xml",
        ".ico": "image/x-icon",
        ".woff": "font/woff",
        ".woff2": "font/woff2",
        ".ttf": "font/ttf",
        ".otf": "font/otf",
        ".mp4": "video/mp4",
        ".mp3": "audio/mpeg",
        ".pdf": "application/pdf",
        ".xml": "application/xml",
        ".txt": "text/plain",
    }

    content_type = content_type_map.get(file_ext, "application/octet-stream")

    try:
        with open(full_path, "rb") as f:
            response = HttpResponse(f.read(), content_type=content_type)
            # Add CORS headers for cross-origin requests within the iframe
            response["Access-Control-Allow-Origin"] = "*"
            response["Access-Control-Allow-Methods"] = "GET"
            response["Access-Control-Allow-Headers"] = "Content-Type"
            # Allow iframe embedding for showcase content
            response["X-Frame-Options"] = "SAMEORIGIN"
            # Remove content security policy restrictions that might block iframe content
            if "X-Content-Security-Policy" in response:
                del response["X-Content-Security-Policy"]
            if "Content-Security-Policy" in response:
                del response["Content-Security-Policy"]
            return response
    except OSError as e:
        raise Http404(f"Cannot read file: {file_path}") from e
