import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.chat.models import Notification


class Command(BaseCommand):
    help = "Purges read notifications older than N days (default 90 days)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=90,
            help='Retention days for read notifications (default 90).'
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - datetime.timedelta(days=days)

        deleted_count, _ = Notification.objects.filter(
            is_read=True,
            created_at__lt=cutoff
        ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully purged {deleted_count} read notification(s) older than {days} days."
            )
        )
