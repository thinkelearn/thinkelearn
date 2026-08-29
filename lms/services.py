"""S3 presigned upload and SCORM package extraction services."""

from __future__ import annotations

import logging
import os
import tempfile
import uuid
import zipfile
from pathlib import PurePosixPath

import boto3
from botocore.exceptions import ClientError
from django.conf import settings
from django.db import models as django_models

logger = logging.getLogger(__name__)

# Maximum upload size: 500 MB
MAX_UPLOAD_BYTES = 500 * 1024 * 1024

SCORM_EXTRACTION_PENDING_PATH = "__scorm_extraction_pending__"
SCORM_EXTRACTION_FAILED_PATH = "__scorm_extraction_failed__"
SCORM_PROCESSING_STATUS_KEY = "processing_status"
SCORM_PROCESSING_ERROR_KEY = "processing_error"
SCORM_BACKGROUND_PROCESSING_REQUIRED_MESSAGE = (
    "SCORM background processing is not configured. Set REDIS_URL and run "
    "a Celery worker before using direct SCORM uploads."
)
SCORM_BACKGROUND_QUEUE_FAILED_MESSAGE = (
    "SCORM background processing could not be queued. Check REDIS_URL and "
    "the Celery worker."
)


def get_scorm_upload_prefix() -> str:
    """Return normalized SCORM upload prefix with a trailing slash."""
    raw_prefix = getattr(settings, "WAGTAIL_LMS_SCORM_UPLOAD_PATH", "scorm_packages/")
    normalized = str(PurePosixPath(str(raw_prefix or "scorm_packages/"))).strip()
    if normalized in {"", ".", "/"}:
        normalized = "scorm_packages"
    return normalized.rstrip("/") + "/"


def get_h5p_upload_prefix() -> str:
    """Return normalized H5P upload prefix with a trailing slash."""
    raw_prefix = getattr(settings, "WAGTAIL_LMS_H5P_UPLOAD_PATH", "h5p_packages/")
    normalized = str(PurePosixPath(str(raw_prefix or "h5p_packages/"))).strip()
    if normalized in {"", ".", "/"}:
        normalized = "h5p_packages"
    return normalized.rstrip("/") + "/"


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
    upload_prefix = get_scorm_upload_prefix()
    s3_key = str(PurePosixPath(upload_prefix) / f"{short_uuid}_{safe_filename}")

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
    browser_endpoint_url = getattr(settings, "AWS_S3_BROWSER_ENDPOINT_URL", None)
    if endpoint_url and browser_endpoint_url:
        url = url.replace(endpoint_url, browser_endpoint_url)

    return {
        "url": url,
        "fields": presigned["fields"],
        "s3_key": s3_key,
    }


def generate_h5p_presigned_post(filename: str) -> dict:
    """Generate a presigned POST URL for direct browser-to-S3 upload of H5P packages.

    Args:
        filename: Original filename from the browser (.h5p).

    Returns:
        Dict with 'url', 'fields', and 's3_key'.
    """
    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")

    safe_filename = os.path.basename(filename).strip()
    short_uuid = uuid.uuid4().hex[:8]
    upload_prefix = get_h5p_upload_prefix()
    s3_key = str(PurePosixPath(upload_prefix) / f"{short_uuid}_{safe_filename}")

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

    endpoint_url = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    browser_endpoint_url = getattr(settings, "AWS_S3_BROWSER_ENDPOINT_URL", None)
    if endpoint_url and browser_endpoint_url:
        url = url.replace(endpoint_url, browser_endpoint_url)

    return {
        "url": url,
        "fields": presigned["fields"],
        "s3_key": s3_key,
    }


def create_h5p_activity_from_s3_key(s3_key: str, title: str, description: str = ""):
    """Create an H5PActivity from an already-uploaded S3 object.

    Downloads the .h5p file from S3 for pre-validation (is_zipfile + path
    traversal), then delegates extraction and h5p.json parsing to
    wagtail-lms's save().

    Args:
        s3_key: The S3 object key where the .h5p package was uploaded.
        title: Activity title.
        description: Activity description.

    Returns:
        The created H5PActivity instance.

    Raises:
        ValueError: If the package is invalid or contains path traversal.
    """
    from wagtail_lms.models import H5PActivity

    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    s3_client = _get_s3_client()

    try:
        with tempfile.NamedTemporaryFile(suffix=".h5p", delete=False) as tmp:
            tmp_path = tmp.name
            s3_client.download_file(bucket_name, s3_key, tmp_path)

        if not zipfile.is_zipfile(tmp_path):
            raise ValueError("Uploaded file is not a valid H5P (ZIP) archive.")

        try:
            with zipfile.ZipFile(tmp_path, "r") as zf:
                for member in zf.namelist():
                    parts = PurePosixPath(member).parts
                    if ".." in parts or (parts and parts[0].startswith("/")):
                        raise ValueError(f"H5P package contains unsafe path: {member}")
        except zipfile.BadZipFile as exc:
            raise ValueError("Uploaded file is not a valid H5P (ZIP) archive.") from exc

        activity = H5PActivity(
            title=title,
            description=description,
        )
        activity.package_file.name = s3_key
        activity.save()

        logger.info("Created H5P activity %s from S3 key %s", activity.id, s3_key)
        return activity

    finally:
        if "tmp_path" in locals() and os.path.exists(tmp_path):
            os.unlink(tmp_path)


def create_package_from_s3_key(s3_key: str, title: str, description: str = ""):
    """Create a SCORMPackage from an already-uploaded S3 object.

    Direct-to-S3 uploads can be large, especially SCORM packages with HLS video
    segments. Keep the finalize request short by creating the database record
    here and queueing extraction/manifest parsing for a Celery worker.

    Args:
        s3_key: The S3 object key where the ZIP was uploaded.
        title: Package title.
        description: Package description.

    Returns:
        The created SCORMPackage instance.

    Raises:
        ValueError: If the uploaded object is missing or violates upload limits.
    """
    from wagtail_lms.models import SCORMPackage

    bucket_name = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
    s3_client = _get_s3_client()

    try:
        head = s3_client.head_object(Bucket=bucket_name, Key=s3_key)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            raise ValueError("Uploaded file was not found in S3.") from exc
        raise

    content_length = head.get("ContentLength", 0)
    if content_length <= 0:
        raise ValueError("Uploaded file is empty.")
    if content_length > MAX_UPLOAD_BYTES:
        raise ValueError("Uploaded file exceeds the 500 MB size limit.")

    package = SCORMPackage(
        title=title,
        description=description,
        extracted_path=SCORM_EXTRACTION_PENDING_PATH,
        manifest_data={SCORM_PROCESSING_STATUS_KEY: "queued"},
    )
    package.package_file.name = s3_key

    # wagtail-lms extracts in SCORMPackage.save(); direct-S3 finalization must
    # only persist the row so the HTTP worker is not tied up unzipping to S3.
    django_models.Model.save(package, force_insert=True)
    try:
        queue_scorm_package_extraction(package.pk)
    except RuntimeError:
        package.delete()
        logger.exception(
            "Failed to queue SCORM package extraction",
            extra={"package_id": package.pk, "s3_key": s3_key},
        )
        raise
    except Exception as exc:
        package.delete()
        logger.exception(
            "Failed to queue SCORM package extraction",
            extra={"package_id": package.pk, "s3_key": s3_key},
        )
        raise RuntimeError(SCORM_BACKGROUND_QUEUE_FAILED_MESSAGE) from exc

    logger.info(
        "Created SCORM package %s from S3 key %s and queued extraction",
        package.id,
        s3_key,
    )
    return package


def queue_scorm_package_extraction(package_id: int) -> None:
    """Queue background SCORM extraction for a package."""
    from .tasks import extract_scorm_package

    if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        raise RuntimeError(SCORM_BACKGROUND_PROCESSING_REQUIRED_MESSAGE)

    extract_scorm_package.apply_async(args=[package_id], retry=False)
