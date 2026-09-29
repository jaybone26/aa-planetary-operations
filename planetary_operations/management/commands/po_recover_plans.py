"""Release abandoned plan slots after a worker outage."""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from planetary_operations.models import Plan


class Command(BaseCommand):
    help = "Mark queued/running plans older than 15 minutes failed after a worker outage."

    def handle(self, *args, **options):
        count = Plan.objects.filter(
            status__in=[Plan.Status.PENDING, Plan.Status.RUNNING],
            updated_at__lt=timezone.now() - timedelta(minutes=15),
        ).update(
            status=Plan.Status.FAILED,
            updated_at=timezone.now(),
            error="The worker did not finish this calculation. Use Adjust & build a copy to try again.",
        )
        self.stdout.write(self.style.SUCCESS(f"Recovered {count} abandoned plans."))
