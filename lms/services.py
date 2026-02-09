"""S3 presigned upload and SCORM package extraction services."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
import zipfile

import boto3
from django.conf import settings

logger = logging.getLogger(__name__)

# Maximum upload size: 500 MB
MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def _get_s3_client():
    """Create a boto3 S3 client using Django settings."""
    kwargs = {
        "region_name": getattr(settings, "AWS_S3_REGION_NAME", "ca-central-1"),
        "aws_access_key_id": getattr(settings, "AWS_ACCESS_KEY_ID", None),
        "aws_secret_access_key": getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
    }
    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    return boto3.client("s3", **kwargs)


def generate_presigned_post(filename: str) -> dict:
    """Generate a presigned POST URL for direct browser-to-S3 upload.

    Args:
        filename: Original filename from the browser.

    Returns:
        Dict with 'url', 'fields', and 's3_key'.
    """
    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")

    # Generate unique S3 key to prevent collisions
    short_uuid = uuid.uuid4().hex[:8]
    s3_key = f"scorm_packages/{short_uuid}_{filename}"

    s3_client = _get_s3_client()

    presigned = s3_client.generate_presigned_post(
        Bucket=bucket_name,
        Key=s3_key,
        Conditions=[
            {"Content-Type": "application/zip"},
            ["content-length-range", 1, MAX_UPLOAD_BYTES],
        ],
        Fields={"Content-Type": "application/zip"},
        ExpiresIn=3600,
    )

    url = presigned["url"]

    # Rewrite the URL for browser access (e.g. Docker: minio:9000 -> localhost:9000)
    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    presigned_url = getattr(settings, "AWS_S3_PRESIGNED_URL", None)
    if endpoint_url and presigned_url:
        url = url.replace(endpoint_url, presigned_url)

    return {
        "url": url,
        "fields": presigned["fields"],
        "s3_key": s3_key,
    }


def create_package_from_s3_key(s3_key: str, title: str, description: str = ""):
    """Create a SCORMPackage from an already-uploaded S3 object.

    Downloads the ZIP from S3, validates it, extracts it locally, and
    parses the SCORM manifest.

    Args:
        s3_key: The S3 object key where the ZIP was uploaded.
        title: Package title.
        description: Package description.

    Returns:
        The created SCORMPackage instance.

    Raises:
        ValueError: If the ZIP is invalid or contains path traversal.
    """
    from wagtail_lms.models import SCORMPackage

    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")

    # Create the package with a sentinel extracted_path so wagtail-lms's
    # save() skips its own extract_package() (which calls .path and fails on S3).
    # The sentinel works because save() checks:
    #   if self.package_file and not self.extracted_path:
    # With "__pending__" set, `not self.extracted_path` is False.
    package = SCORMPackage(
        title=title,
        description=description,
        extracted_path="__pending__",
    )
    package.package_file.name = s3_key
    package.save()

    s3_client = _get_s3_client()

    try:
        # Download ZIP to a temp file
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name
            s3_client.download_file(bucket_name, s3_key, tmp_path)

        # Validate ZIP
        if not zipfile.is_zipfile(tmp_path):
            package.delete()
            raise ValueError("Uploaded file is not a valid ZIP archive.")

        # Check for path traversal attacks
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for member in zf.namelist():
                # Normalize and reject any path that escapes the extraction dir
                member_path = os.path.normpath(member)
                if member_path.startswith("..") or os.path.isabs(member_path):
                    package.delete()
                    raise ValueError(f"ZIP contains unsafe path: {member}")

        # Build extraction directory
        package_name = os.path.splitext(os.path.basename(s3_key))[0]
        unique_dir = f"package_{package.id}_{package_name}"
        extract_dir = os.path.join(settings.MEDIA_ROOT, "scorm_content", unique_dir)
        os.makedirs(extract_dir, exist_ok=True)

        # Extract
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(extract_dir)

        package.extracted_path = unique_dir

        # Parse manifest (reuse wagtail-lms's method)
        manifest_path = os.path.join(extract_dir, "imsmanifest.xml")
        if os.path.exists(manifest_path):
            package.parse_manifest(manifest_path)

        package.save()
        logger.info("Created SCORM package %s from S3 key %s", package.id, s3_key)
        return package

    except Exception:
        # Clean up on any error after package creation
        if package.pk:
            try:
                package.delete()
            except Exception:
                logger.exception(
                    "Failed to clean up package %s after extraction error",
                    package.pk,
                )
        raise
    finally:
        # Clean up temp file
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
