import zoneinfo
import datetime
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.appointments.models import Appointment
from apps.history.utils import send_templated_email


class Command(BaseCommand):
    help = "Dispatches reminder emails (via outbox) to approved appointments scheduled for tomorrow in Asia/Manila."

    def add_arguments(self, parser):
        parser.add_argument(
            '--target-date',
            type=str,
            default='',
            help='Optional explicit date in YYYY-MM-DD format for testing or manual runs.'
        )

    def handle(self, *args, **options):
        target_date_str = options.get('target_date')
        if target_date_str:
            target_date = datetime.date.fromisoformat(target_date_str)
        else:
            # Compute tomorrow in Asia/Manila timezone
            manila_tz = zoneinfo.ZoneInfo("Asia/Manila")
            now_manila = timezone.now().astimezone(manila_tz)
            target_date = now_manila.date() + datetime.timedelta(days=1)

        # Skip appointments that are NOT approved, or already reminded
        appointments = Appointment.objects.filter(
            status=Appointment.STATUS_APPROVED,
            appt_date=target_date,
            reminder_sent_at__isnull=True
        ).select_related('resident', 'healthcare_service', 'document_type')

        count = 0
        for apt in appointments:
            target_email = apt.get_applicant_email()
            if not target_email:
                continue

            first_name = 'Resident'
            if hasattr(apt.resident, 'first_name') and apt.resident.first_name:
                first_name = apt.resident.first_name
            elif hasattr(apt.resident, 'resident_profile') and apt.resident.resident_profile and apt.resident.resident_profile.first_name:
                first_name = apt.resident.resident_profile.first_name

            requirements_line = ''
            reqs = apt.get_requirements_display() if hasattr(apt, 'get_requirements_display') else ''
            if reqs:
                requirements_line = f" and required documents: {reqs}"

            ctx = {
                'first_name': first_name,
                'service': apt.get_service_title(),
                'date': apt.appt_date.strftime('%B %d, %Y'),
                'time_window': apt.get_time_window_display(),
                'reference_no': apt.reference_no,
                'requirements_line': requirements_line,
            }

            # Must use the outbox (send_templated_email queues it)
            send_templated_email(
                template_name='appt_reminder.txt',
                to_email=target_email,
                context=ctx,
                ref_table='Appointment',
                ref_id=str(apt.id)
            )

            # Set reminder_sent_at so it runs only once per appointment
            apt.reminder_sent_at = timezone.now()
            apt.save(update_fields=['reminder_sent_at'])
            count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully queued reminders for {count} approved appointment(s) scheduled for {target_date} (Asia/Manila)."
            )
        )
