"""Post-upgrade verification checks for wagtail-lms v0.11.0 migration."""

from __future__ import annotations

import json
from collections.abc import Iterable

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from wagtail.models import Page, Revision
from wagtail_lms.models import CoursePage, SCORMLessonPage


class Command(BaseCommand):
    help = (
        "Validate wagtail-lms 0.11.0 migration outcomes: stale content types, "
        "legacy SCORM course migration coverage, and page tree consistency."
    )

    def handle(self, *args, **options):
        failures: list[str] = []

        stale_content_types = ContentType.objects.filter(
            app_label="wagtail_lms",
            model__in=["lessonpage", "lessoncompletion"],
        )
        if stale_content_types.exists():
            stale_list = ", ".join(
                f"{ct.app_label}.{ct.model}" for ct in stale_content_types
            )
            failures.append(
                "Stale wagtail_lms content types still present after migration: "
                f"{stale_list}"
            )

        legacy_course_ids = self._find_legacy_scorm_course_ids()
        missing_scorm_lesson_ids = self._find_courses_missing_scorm_lessons(
            legacy_course_ids
        )
        if missing_scorm_lesson_ids:
            failures.append(
                "Legacy SCORM courses missing SCORMLessonPage children: "
                + ", ".join(str(course_id) for course_id in missing_scorm_lesson_ids)
            )

        mismatched_numchild_ids = self._find_tree_numchild_mismatches()
        if mismatched_numchild_ids:
            failures.append(
                "Wagtail tree numchild mismatches detected for Page IDs: "
                + ", ".join(str(page_id) for page_id in mismatched_numchild_ids[:20])
                + (" (truncated)" if len(mismatched_numchild_ids) > 20 else "")
            )

        if failures:
            raise CommandError("\n".join(failures))

        self.stdout.write(
            self.style.SUCCESS(
                "wagtail-lms upgrade checks passed: no stale content types, "
                "legacy SCORM courses mapped, and page tree is consistent."
            )
        )

    def _find_legacy_scorm_course_ids(self) -> set[int]:
        """Infer legacy CoursePage IDs that previously had a non-null scorm_package."""
        course_ids = set(CoursePage.objects.values_list("pk", flat=True))
        if not course_ids:
            return set()

        course_id_strings = {str(course_id) for course_id in course_ids}
        revision_qs = (
            Revision.objects.filter(object_id__in=course_id_strings)
            .only("object_id", "content")
            .order_by("id")
        )

        legacy_ids: set[int] = set()
        for revision in revision_qs.iterator():
            payload = self._to_mapping(revision.content)
            if not payload:
                continue

            scorm_package_value = payload.get("scorm_package")
            if scorm_package_value in (None, "", 0, "0"):
                continue

            try:
                revision_course_id = int(revision.object_id)
            except (TypeError, ValueError):
                continue

            if revision_course_id in course_ids:
                legacy_ids.add(revision_course_id)

        return legacy_ids

    def _find_courses_missing_scorm_lessons(
        self, legacy_course_ids: Iterable[int]
    ) -> list[int]:
        """Return legacy course IDs that still have no SCORMLessonPage children."""
        missing_course_ids: list[int] = []

        for course_id in sorted(set(legacy_course_ids)):
            try:
                course = CoursePage.objects.get(pk=course_id)
            except CoursePage.DoesNotExist:
                continue

            has_scorm_lesson = SCORMLessonPage.objects.child_of(course).exists()
            if not has_scorm_lesson:
                missing_course_ids.append(course_id)

        return missing_course_ids

    def _find_tree_numchild_mismatches(self) -> list[int]:
        """Return Page IDs whose numchild counters do not match actual children."""
        mismatched: list[int] = []
        pages = Page.objects.only("id", "numchild")

        for page in pages.iterator():
            actual_children = page.get_children().count()
            if actual_children != page.numchild:
                mismatched.append(page.id)

        return mismatched

    def _to_mapping(self, content: object) -> dict[str, object]:
        """Convert revision content payload to a dictionary safely."""
        if isinstance(content, dict):
            return content

        if isinstance(content, str):
            try:
                decoded = json.loads(content)
            except json.JSONDecodeError:
                return {}
            return decoded if isinstance(decoded, dict) else {}

        return {}
