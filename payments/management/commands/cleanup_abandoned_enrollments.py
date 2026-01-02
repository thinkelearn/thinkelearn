from __future__ import annotations

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from payments.tasks import cleanup_abandoned_enrollments


class Command(BaseCommand):
    help = "Cancel pending enrollments that were abandoned during checkout."

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help="Age in hours after which pending enrollments are cancelled.",
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        cutoff = timezone.now() - timedelta(hours=hours)
        count = cleanup_abandoned_enrollments(cutoff=cutoff)
        self.stdout.write(
            self.style.SUCCESS(
                f"Cancelled {count} abandoned enrollments older than {hours} hours."
            )
        )
