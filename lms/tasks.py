from __future__ import annotations

import io
import logging
import os
import posixpath
import zipfile

from celery import shared_task
from django.core.files import File
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models as django_models
from wagtail_lms import conf
from wagtail_lms.models import SCORMPackage

from .services import (
    SCORM_EXTRACTION_FAILED_PATH,
    SCORM_EXTRACTION_PENDING_PATH,
    SCORM_PROCESSING_ERROR_KEY,
    SCORM_PROCESSING_STATUS_KEY,
)

logger = logging.getLogger(__name__)

_SCORM_EXTRACTION_SENTINELS = {
    SCORM_EXTRACTION_PENDING_PATH,
    SCORM_EXTRACTION_FAILED_PATH,
}


@shared_task(bind=True, max_retries=5)
def extract_scorm_package(self, package_id: int) -> None:
    """Extract a SCORM package outside the web request/response cycle."""
    try:
        package = SCORMPackage.objects.get(pk=package_id)
    except SCORMPackage.DoesNotExist:
        logger.warning(
            "SCORM package missing during extraction",
            extra={"package_id": package_id},
        )
        return

    if (
        package.extracted_path
        and package.extracted_path not in _SCORM_EXTRACTION_SENTINELS
    ):
        logger.info(
            "SCORM package already extracted",
            extra={"package_id": package_id, "extracted_path": package.extracted_path},
        )
        return

    try:
        _extract_scorm_package(
            package,
            overwrite_existing=bool(getattr(self.request, "retries", 0)),
        )
    except ValueError as exc:
        _mark_scorm_extraction_failed(package, str(exc))
        logger.warning(
            "SCORM package extraction rejected",
            extra={"package_id": package_id, "error": str(exc)},
        )
    except Exception as exc:
        retries = getattr(self.request, "retries", 0)
        if retries >= self.max_retries:
            _mark_scorm_extraction_failed(package, str(exc))
            logger.exception(
                "SCORM package extraction failed permanently",
                extra={"package_id": package_id},
            )
            return

        countdown = min(300, 2 ** (retries + 1))
        logger.exception(
            "SCORM package extraction failed; retrying",
            extra={
                "package_id": package_id,
                "retry": retries + 1,
                "countdown": countdown,
            },
        )
        raise self.retry(exc=exc, countdown=countdown) from exc


def _extract_scorm_package(
    package: SCORMPackage,
    *,
    overwrite_existing: bool = False,
) -> None:
    """Stream a SCORM ZIP into configured storage and parse its manifest."""
    if not package.package_file:
        raise ValueError("SCORM package has no package file.")

    package_name = os.path.splitext(os.path.basename(package.package_file.name))[0]
    unique_dir = f"package_{package.id}_{package_name}"
    content_path = conf.WAGTAIL_LMS_SCORM_CONTENT_PATH.rstrip("/")
    manifest_content: bytes | None = None

    try:
        with package.package_file.open("rb") as package_fh:
            with zipfile.ZipFile(package_fh, "r") as zip_ref:
                members = _safe_zip_members(zip_ref)

                for member, normalized_name in members:
                    storage_path = posixpath.join(
                        content_path,
                        unique_dir,
                        normalized_name,
                    )
                    if overwrite_existing:
                        _delete_if_present(storage_path)

                    with zip_ref.open(member, "r") as member_fh:
                        if normalized_name == "imsmanifest.xml":
                            manifest_content = member_fh.read()
                            default_storage.save(
                                storage_path,
                                ContentFile(manifest_content),
                            )
                        else:
                            default_storage.save(
                                storage_path,
                                File(
                                    member_fh, name=posixpath.basename(normalized_name)
                                ),
                            )
    except zipfile.BadZipFile as exc:
        raise ValueError("Uploaded file is not a valid ZIP archive.") from exc

    package.extracted_path = unique_dir
    if manifest_content is not None:
        package.parse_manifest(io.BytesIO(manifest_content))
    else:
        package.manifest_data = {
            SCORM_PROCESSING_STATUS_KEY: "completed",
            "warning": "imsmanifest.xml was not found in the SCORM package.",
        }

    django_models.Model.save(
        package,
        update_fields=[
            "extracted_path",
            "launch_url",
            "manifest_data",
            "title",
            "version",
            "updated_at",
        ],
    )


def _safe_zip_members(zip_ref: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    """Return non-directory ZIP members after rejecting unsafe paths."""
    members = []
    for member in zip_ref.infolist():
        if member.is_dir():
            continue

        normalized = member.filename.replace("\\", "/")
        normalized = posixpath.normpath(normalized)
        if (
            normalized == "."
            or normalized.startswith("/")
            or normalized.startswith("..")
            or "/../" in normalized
        ):
            raise ValueError(f"ZIP contains unsafe path: {member.filename}")

        members.append((member, normalized))
    return members


def _delete_if_present(path: str) -> None:
    try:
        default_storage.delete(path)
    except FileNotFoundError:
        pass


def _mark_scorm_extraction_failed(package: SCORMPackage, error: str) -> None:
    package.extracted_path = SCORM_EXTRACTION_FAILED_PATH
    package.launch_url = ""
    package.manifest_data = {
        SCORM_PROCESSING_STATUS_KEY: "failed",
        SCORM_PROCESSING_ERROR_KEY: error[:1000],
    }
    django_models.Model.save(
        package,
        update_fields=["extracted_path", "launch_url", "manifest_data", "updated_at"],
    )
