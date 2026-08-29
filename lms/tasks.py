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
from django.utils import timezone
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
            "SCORM package %s missing during extraction",
            package_id,
        )
        return

    if (
        package.extracted_path
        and package.extracted_path not in _SCORM_EXTRACTION_SENTINELS
    ):
        logger.info(
            "SCORM package %s already extracted at %s",
            package_id,
            package.extracted_path,
        )
        return

    try:
        _extract_scorm_package(package)
    except ValueError as exc:
        _mark_scorm_extraction_failed(package, str(exc))
        logger.warning(
            "SCORM package %s extraction rejected: %s",
            package_id,
            exc,
        )
    except Exception as exc:
        retries = getattr(self.request, "retries", 0)
        if retries >= self.max_retries:
            _mark_scorm_extraction_failed(package, str(exc))
            logger.exception(
                "SCORM package %s extraction failed permanently",
                package_id,
            )
            return

        countdown = min(300, 2 ** (retries + 1))
        logger.exception(
            "SCORM package %s extraction failed; retrying in %s seconds (attempt %s/%s)",
            package_id,
            countdown,
            retries + 1,
            self.max_retries,
        )
        raise self.retry(exc=exc, countdown=countdown) from exc


def _extract_scorm_package(package: SCORMPackage) -> None:
    """Stream a SCORM ZIP into configured storage and parse its manifest."""
    if not package.package_file:
        raise ValueError("SCORM package has no package file.")

    package_name = os.path.splitext(os.path.basename(package.package_file.name))[0]
    unique_dir = f"package_{package.id}_{package_name}"
    content_path = conf.WAGTAIL_LMS_SCORM_CONTENT_PATH.rstrip("/")
    extraction_root = posixpath.join(content_path, unique_dir)
    manifest_content: bytes | None = None

    logger.info(
        "Starting SCORM package %s extraction from %s into %s",
        package.pk,
        package.package_file.name,
        extraction_root,
    )
    _delete_storage_tree(extraction_root)

    try:
        with package.package_file.open("rb") as package_fh:
            with zipfile.ZipFile(package_fh, "r") as zip_ref:
                members = _safe_zip_members(zip_ref)

                for member, normalized_name in members:
                    storage_path = posixpath.join(
                        extraction_root,
                        normalized_name,
                    )

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

    if not _save_extracted_package_metadata(package):
        _delete_storage_tree(extraction_root)
        logger.warning(
            "SCORM package %s disappeared before extraction metadata could be saved; "
            "removed extracted files from %s",
            package.pk,
            extraction_root,
        )
        return

    logger.info(
        "SCORM package %s extracted to %s with %s files",
        package.pk,
        unique_dir,
        len(members),
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
    if default_storage.exists(path):
        default_storage.delete(path)


def _delete_storage_tree(path: str) -> None:
    try:
        dirs, files = default_storage.listdir(path)
    except FileNotFoundError:
        return
    except NotADirectoryError:
        _delete_if_present(path)
        return

    for filename in files:
        _delete_if_present(posixpath.join(path, filename))
    for dirname in dirs:
        _delete_storage_tree(posixpath.join(path, dirname))


def _save_extracted_package_metadata(package: SCORMPackage) -> bool:
    updated = SCORMPackage.objects.filter(pk=package.pk).update(
        extracted_path=package.extracted_path,
        launch_url=package.launch_url,
        manifest_data=package.manifest_data,
        title=package.title,
        version=package.version,
        updated_at=timezone.now(),
    )
    return updated > 0


def _mark_scorm_extraction_failed(package: SCORMPackage, error: str) -> None:
    package.extracted_path = SCORM_EXTRACTION_FAILED_PATH
    package.launch_url = ""
    package.manifest_data = {
        SCORM_PROCESSING_STATUS_KEY: "failed",
        SCORM_PROCESSING_ERROR_KEY: error[:1000],
    }
    updated = SCORMPackage.objects.filter(pk=package.pk).update(
        extracted_path=package.extracted_path,
        launch_url=package.launch_url,
        manifest_data=package.manifest_data,
        updated_at=timezone.now(),
    )
    if not updated:
        logger.warning(
            "SCORM package %s missing while recording extraction failure",
            package.pk,
        )
