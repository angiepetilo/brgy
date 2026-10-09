import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from apps.accounts.models import User, Resident
from apps.history.utils import log_activity


class Command(BaseCommand):
    help = "Deletes ID photo and personal details of rejected registrations after N days (default 90)."

    def add_arguments(self, parser):
        default_days = getattr(settings, 'REJECTED_REGISTRATION_RETENTION_DAYS', 90)
        parser.add_argument(
            '--days',
            type=int,
            default=default_days,
            help=f"Number of retention days before purging rejected data (default: {default_days})"
        )

    def handle(self, *args, **options):
        days = options['days']
        cutoff_date = timezone.now() - datetime.timedelta(days=days)

        rejected_users = User.objects.filter(
            status=User.STATUS_REJECTED,
            reviewed_at__lte=cutoff_date
        )

        count = 0
        for user in rejected_users:
            cleaned_items = []

            # 1. Clean ID photo and personal details from Resident profile if exists
            if hasattr(user, 'resident_profile') and user.resident_profile:
                res = user.resident_profile
                if res.id_photo:
                    try:
                        res.id_photo.delete(save=False)
                    except Exception:
                        pass
                    res.id_photo = None
                    cleaned_items.append("id_photo")
                if res.contact_no:
                    res.contact_no = ''
                    cleaned_items.append("contact_no")
                if res.address:
                    res.address = ''
                    cleaned_items.append("address")
                res.save()

            # 2. Clean User personal details
            if user.id_proof:
                try:
                    user.id_proof.delete(save=False)
                except Exception:
                    pass
                user.id_proof = None
                cleaned_items.append("id_proof")
            if user.phone_number:
                user.phone_number = ''
                cleaned_items.append("phone_number")
            if user.street_address or user.address:
                user.street_address = ''
                user.address = ''
                cleaned_items.append("address")
            user.save()

            # Log audit entry (no names in target_name or details)
            log_activity(
                actor=None,
                action='delete',
                action_type='RetentionPolicy',
                target_id=str(user.id),
                target_name=f"Rejected Registration #{user.id}",
                details=f"Purged ID photo and personal details for rejected registration #{user.id} older than {days} days ({', '.join(cleaned_items) if cleaned_items else 'already clean'})."
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Successfully processed {count} rejected registration(s) older than {days} days."))
