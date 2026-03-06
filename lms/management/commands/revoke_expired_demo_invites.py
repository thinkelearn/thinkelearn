"""
Management command: revoke_expired_demo_invites

Finds all ClientDemoInvite records that are expired or deactivated, then
revokes the CourseEnrollment records that were created by those invites
(i.e. ClientDemoEnrollment.revoke_on_expiry=True).

Pre-existing enrollments (revoke_on_expiry=False) are never touched.

Intended to be run on a schedule (e.g. daily cron or Railway scheduled task).

Usage:
    docker-compose exec web python manage.py revoke_expired_demo_invites
    docker-compose exec web python manage.py revoke_expired_demo_invites --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Q
from django.utils import timezone


class Command(BaseCommand):
    help = "Revoke enrollments created by expired or inactive demo invites."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would be revoked without making any changes.",
        )

    def handle(self, *args, **options):
        from wagtail_lms.models import CourseEnrollment

        from lms.models import ClientDemoEnrollment, ClientDemoInvite

        dry_run = options["dry_run"]

        expired_invites = ClientDemoInvite.objects.filter(
            Q(is_active=False) | Q(expires_at__lt=timezone.now())
        )

        if not expired_invites.exists():
            self.stdout.write("No expired or inactive invites found.")
            return

        total_revoked = 0

        for invite in expired_invites:
            to_revoke = ClientDemoEnrollment.objects.filter(
                invite=invite, revoke_on_expiry=True
            ).select_related("user", "course")

            if not to_revoke.exists():
                continue

            self.stdout.write(
                f"Invite '{invite}' — processing revocable enrollment(s)."
            )

            if not dry_run:
                with transaction.atomic():
                    for demo_enrollment in to_revoke:
                        # Skip deletion if another active/non-expired invite still
                        # grants this user access to the same course.
                        still_covered = (
                            ClientDemoEnrollment.objects.filter(
                                user=demo_enrollment.user,
                                course=demo_enrollment.course,
                                invite__is_active=True,
                            )
                            .exclude(invite=invite)
                            .filter(
                                Q(invite__expires_at__isnull=True)
                                | Q(invite__expires_at__gte=timezone.now())
                            )
                            .exists()
                        )

                        if still_covered:
                            self.stdout.write(
                                f"  Skipped (another active invite covers this): "
                                f"{demo_enrollment.user} from '{demo_enrollment.course}'"
                            )
                            continue

                        CourseEnrollment.objects.filter(
                            user=demo_enrollment.user,
                            course=demo_enrollment.course,
                        ).delete()
                        self.stdout.write(
                            f"  Revoked: {demo_enrollment.user} from "
                            f"'{demo_enrollment.course}'"
                        )
                        total_revoked += 1

                    to_revoke.delete()
            else:
                total_revoked += to_revoke.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f"Dry run complete — {total_revoked} enrollment(s) would be revoked."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Done — {total_revoked} enrollment(s) revoked.")
            )
