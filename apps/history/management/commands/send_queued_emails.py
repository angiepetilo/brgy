import datetime
import logging
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from apps.history.models import EmailLog
from apps.history.utils import sanitize_audit_details

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Dispatches queued outbox emails with retry backoff (up to 3 attempts)."

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Bypass retry delays and attempt to send all queued emails immediately.'
        )

    def handle(self, *args, **options):
        force = options.get('force', False)
        now = timezone.now()

        # Secret emails are never handled by the outbox
        queued_emails = EmailLog.objects.filter(
            status=EmailLog.STATUS_QUEUED,
            is_secret=False,
            attempts__lt=3
        ).order_by('created_at')

        total = queued_emails.count()
        sent_count = 0
        failed_count = 0
        skipped_count = 0

        for item in queued_emails:
            # Check retry delay (1m after 1st attempt, 5m after 2nd attempt)
            if not force and item.attempts > 0 and item.last_attempt_at:
                delay = datetime.timedelta(minutes=1 if item.attempts == 1 else 5)
                if (now - item.last_attempt_at) < delay:
                    skipped_count += 1
                    continue

            try:
                send_mail(
                    subject=item.subject,
                    message=item.body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[item.recipient],
                    fail_silently=False,
                )
                item.status = EmailLog.STATUS_SENT
                item.error_message = ''
                item.attempts += 1
                item.last_attempt_at = timezone.now()
                item.save(update_fields=['status', 'error_message', 'attempts', 'last_attempt_at'])
                sent_count += 1
            except Exception as exc:
                clean_err = sanitize_audit_details(str(exc))
                item.attempts += 1
                item.last_attempt_at = timezone.now()
                item.error_message = clean_err
                if item.attempts >= 3:
                    item.status = EmailLog.STATUS_FAILED
                else:
                    item.status = EmailLog.STATUS_QUEUED
                item.save(update_fields=['status', 'error_message', 'attempts', 'last_attempt_at'])
                failed_count += 1
                logger.warning(f"Error sending queued email #{item.id} to {item.recipient} (attempt {item.attempts}): {clean_err}")

        self.stdout.write(
            self.style.SUCCESS(
                f"send_queued_emails completed. Total: {total}, Sent: {sent_count}, Failed/Retrying: {failed_count}, Waiting backoff: {skipped_count}"
            )
        )
