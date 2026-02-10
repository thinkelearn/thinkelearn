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
    safe_filename = os.path.basename(filename).strip()
    short_uuid = uuid.uuid4().hex[:8]
    s3_key = f"scorm_packages/{short_uuid}_{safe_filename}"

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

    Downloads the ZIP from S3 for pre-validation (is_zipfile + path traversal),
    then delegates extraction and manifest parsing to wagtail-lms's save().

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
    s3_client = _get_s3_client()

    try:
        # Download ZIP to a temp file for validation
        with tempfile.NamedTemporaryFile(suffix=".zip", delete=False) as tmp:
            tmp_path = tmp.name
            s3_client.download_file(bucket_name, s3_key, tmp_path)

        # Validate ZIP format
        if not zipfile.is_zipfile(tmp_path):
            raise ValueError("Uploaded file is not a valid ZIP archive.")

        # Pre-check for path traversal (raise ValueError for admin UX;
        # wagtail-lms also skips unsafe paths but only logs warnings)
        with zipfile.ZipFile(tmp_path, "r") as zf:
            for member in zf.namelist():
                member_path = os.path.normpath(member)
                if member_path.startswith("..") or os.path.isabs(member_path):
                    raise ValueError(f"ZIP contains unsafe path: {member}")

        # Create package — save() triggers extract_package() which handles
        # extraction via default_storage and manifest parsing
        package = SCORMPackage(
            title=title,
            description=description,
        )
        package.package_file.name = s3_key
        package.save()

        logger.info("Created SCORM package %s from S3 key %s", package.id, s3_key)
        return package

    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)
