"""Post-upgrade verification checks for wagtail-lms v0.11.0 migration."""

from __future__ import annotations

import json
from collections.abc import Iterable

from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
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
        """Return legacy course IDs that still have no SCORMLessonPage children.

        Uses 2 queries instead of 2N: one to fetch courses, one OR'd query for
        all direct SCORM lesson children.
        """
        ids = sorted(set(legacy_course_ids))
        if not ids:
            return []
        courses = list(
            CoursePage.objects.filter(pk__in=ids).only("id", "path", "depth")
        )
        if not courses:
            return []
        q = Q()
        for course in courses:
            q |= Q(path__startswith=course.path, depth=course.depth + 1)
        scorm_child_paths = set(
            SCORMLessonPage.objects.filter(q).values_list("path", flat=True)
        )
        return sorted(
            course.pk
            for course in courses
            if not any(p.startswith(course.path) for p in scorm_child_paths)
        )

    def _find_tree_numchild_mismatches(self) -> list[int]:
        """Return Page IDs whose numchild counters do not match actual children.

        Uses 1 query instead of N+1 by computing parent-child counts from the
        treebeard path field entirely in Python.
        """
        pages = list(
            Page.objects.only("id", "path", "depth", "numchild").order_by("path")
        )
        steplen = Page.steplen  # 4 for Wagtail

        actual_child_counts: dict[str, int] = {}
        for page in pages:
            parent_path = page.path[:-steplen]
            if parent_path:
                actual_child_counts[parent_path] = (
                    actual_child_counts.get(parent_path, 0) + 1
                )

        return [
            page.id
            for page in pages
            if actual_child_counts.get(page.path, 0) != page.numchild
        ]

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
