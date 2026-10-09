from django.db import models
from django.conf import settings

from apps.core.storage import PrivateMediaStorage
from apps.core.uploads import random_upload_to, validate_upload
from apps.core.validators import validate_ph_mobile


def private_supporting_storage():
    """Storage for Appointment.supporting_id: PRIVATE_MEDIA_ROOT, served only by appointments:supporting_id."""
    return PrivateMediaStorage()


class HealthCareService(models.Model):
    """
    Available health care services offered by the Barangay Health Center.

    NF compliance:
    1NF – each column is atomic (name, description are single-valued).
    2NF – all attributes depend fully on the PK (id).
    3NF – no transitive dependencies; is_active depends on the service, not
          on any non-key attribute.
    """
    name = models.CharField(max_length=150, help_text='Name of the health care service')
    description = models.TextField(blank=True, help_text='Detailed description of the health service offered')
    available_date = models.CharField(max_length=120, blank=True, default='', help_text='Days or dates available (e.g. Mon, Wed, Fri or 2026-10-15)')
    available_time = models.CharField(max_length=120, blank=True, default='', help_text='Operating hours or time window (e.g. 8:00 AM - 12:00 PM)')
    is_active = models.BooleanField(default=True, help_text='Designates whether this service is active and bookable')
    is_free = models.BooleanField(default=True, help_text='Designates whether this service is completely free on this day and time')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Health Care Service'
        verbose_name_plural = 'Health Care Services'

    def __str__(self):
        free_badge = " (Free)" if self.is_free else ""
        return f"{self.name}{free_badge}"

    def get_schedule_display(self):
        parts = []
        if self.available_date:
            parts.append(self.available_date)
        if self.available_time:
            parts.append(self.available_time)
        return " • ".join(parts) if parts else "Mon - Fri • 8:00 AM - 5:00 PM"


class HealthSchedule(models.Model):
    """
    Capacity and availability schedule for Health Care Services by date and time window.
    """
    health_service = models.ForeignKey(
        HealthCareService,
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    service_date = models.DateField(null=True, blank=True, help_text='Date of schedule')
    time_window = models.CharField(
        max_length=20,
        choices=[
            ('morning', 'Morning (8:00 AM - 11:30 AM)'),
            ('afternoon', 'Afternoon (1:00 PM - 4:30 PM)'),
        ],
        default='morning'
    )
    capacity = models.PositiveIntegerField(default=20, help_text='Max slots available')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['service_date', 'time_window']
        verbose_name = 'Health Schedule'
        verbose_name_plural = 'Health Schedules'
        unique_together = [('health_service', 'service_date', 'time_window')]

    @property
    def service(self):
        return self.health_service

    def __str__(self):
        return f"{self.health_service.name} - {self.service_date} ({self.time_window})"


class DocumentType(models.Model):
    """
    Catalog of official clearance and certification document types offered by the Barangay.
    """
    name = models.CharField(max_length=150, unique=True, help_text='Name of the document type (e.g. Barangay Clearance)')
    code = models.CharField(max_length=50, blank=True, default='', help_text='Short code identifier')
    description = models.TextField(blank=True, default='', help_text='Description or purpose of this document')
    requirements_needed = models.TextField(blank=True, default='', help_text='Default requirements needed')
    fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, help_text='Fee for this document type')
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Document Type'
        verbose_name_plural = 'Document Types'

    def __str__(self):
        return f"{self.name} (₱{self.fee})"


class Requirement(models.Model):
    """
    Checklist of required documents or items needed for a specific DocumentType.
    """
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name='requirements')
    name = models.CharField(max_length=200, help_text='Name of the required document or item')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Requirement'
        verbose_name_plural = 'Requirements'

    def __str__(self):
        return f"{self.document_type.name} - {self.name}"


class Appointment(models.Model):
    """
    Tracks document requests and health center appointment bookings.

    Normal-Form compliance:
    1NF – every column holds a single, atomic value.  time_window uses
          a controlled vocabulary (choices), not a free-text range string.
    2NF – every non-key attribute depends on the whole PK (id), not a subset.
    3NF FIX – removed first_name / middle_name / last_name from this table.
          Those fields duplicated data already stored in the accounts.User
          record (resident FK), creating a transitive dependency:
          appointment.applicant_name → resident.id → accounts_user.
          The applicant name is now derived at query time via get_applicant_name().

    Canonical columns (no mirrored duplicates): appt_date, time_window, purpose,
    healthcare_service, document_type, admin_notes and rejection_reason.
    """
    CATEGORY_DOCUMENT = 'document'
    CATEGORY_HEALTHCARE = 'healthcare'

    CATEGORY_CHOICES = [
        (CATEGORY_DOCUMENT, 'Document Request'),
        (CATEGORY_HEALTHCARE, 'Health Care Request'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_APPROVED = 'approved'
    STATUS_COMPLETED = 'completed'
    STATUS_REJECTED = 'rejected'
    STATUS_NO_SHOW = 'no_show'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_APPROVED, 'Approved'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_NO_SHOW, 'No-Show'),
    ]

    TIME_SLOT_MORNING = 'morning'
    TIME_SLOT_AFTERNOON = 'afternoon'
    TIME_SLOT_CHOICES = [
        (TIME_SLOT_MORNING, 'Morning (8:00 AM - 11:30 AM)'),
        (TIME_SLOT_AFTERNOON, 'Afternoon (1:00 PM - 4:30 PM)'),
    ]

    reference_no = models.CharField(
        max_length=40,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
        help_text="Unique appointment reference number (e.g. APT-2026-0001)"
    )
    resident = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text='The registered resident who submitted this request'
    )
    # Direct applicant fields captured from public booking modal
    applicant_first_name = models.CharField(max_length=100, blank=True, default='')
    applicant_middle_name = models.CharField(max_length=100, blank=True, default='')
    applicant_last_name = models.CharField(max_length=100, blank=True, default='')
    applicant_age = models.PositiveIntegerField(null=True, blank=True)
    applicant_address = models.CharField(max_length=255, blank=True, default='')
    applicant_email = models.EmailField(blank=True, default='')
    applicant_phone = models.CharField(
        max_length=20, blank=True, default='', validators=[validate_ph_mobile],
        help_text='11-digit mobile number, 09XXXXXXXXX',
    )

    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_DOCUMENT
    )
    healthcare_service = models.ForeignKey(
        HealthCareService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments'
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='appointments',
        help_text='Requested document (null for health care appointments)'
    )
    purpose = models.TextField(
        help_text='State clearly the purpose of this request (e.g. Employment, Scholarship, Consultation notes)'
    )
    appt_date = models.DateField(
        db_index=True,
        help_text='Selected date for processing or appointment'
    )
    time_window = models.CharField(
        max_length=20,
        choices=TIME_SLOT_CHOICES,
        default=TIME_SLOT_MORNING
    )
    # Private: stored under PRIVATE_MEDIA_ROOT and streamed only by the
    # permission-checked appointments:supporting_id view (never /media/).
    supporting_id = models.FileField(
        storage=private_supporting_storage,
        upload_to=random_upload_to('appointments/supporting_docs'),
        validators=[validate_upload],
        blank=True,
        null=True,
        help_text='Supporting document or ID (JPG, PNG, WEBP or PDF, max 5 MB)'
    )
    fee_at_booking = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text='Fee captured at the time of booking'
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    admin_notes = models.TextField(
        blank=True,
        help_text='Staff remarks or instructions for the applicant (not the rejection reason)'
    )
    rejection_reason = models.TextField(
        blank=True,
        default='',
        help_text='Reason shown to the applicant when the request is rejected'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_appointments'
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Appointment Request'
        verbose_name_plural = 'Appointment Requests'
        indexes = [
            models.Index(fields=['status', 'appt_date'], name='appt_status_date_idx'),
            models.Index(fields=['appt_date', 'time_window'], name='appt_date_window_idx'),
        ]

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.reference_no:
            year = (self.appt_date or timezone.localdate()).year
            last_ref = Appointment.objects.filter(reference_no__startswith=f"APT-{year}-").order_by('-reference_no').values_list('reference_no', flat=True).first()
            if last_ref:
                try:
                    num = int(last_ref.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    num = 1
            else:
                max_existing = Appointment.objects.filter(reference_no__isnull=False).count()
                num = max_existing + 1
            self.reference_no = f"APT-{year}-{num:04d}"

        super().save(*args, **kwargs)

    def get_applicant_name(self):
        parts = [self.applicant_first_name, self.applicant_middle_name, self.applicant_last_name]
        combined = " ".join([p for p in parts if p]).strip()
        if combined:
            return combined
        if self.resident:
            return self.resident.get_full_name() or self.resident.username
        return "Public Applicant"

    def get_applicant_email(self):
        if self.applicant_email:
            return self.applicant_email
        if self.resident and self.resident.email:
            return self.resident.email
        return ""

    def get_applicant_phone(self):
        if self.applicant_phone:
            return self.applicant_phone
        if self.resident and self.resident.phone_number:
            return self.resident.phone_number
        return ""

    def get_applicant_address(self):
        if self.applicant_address:
            return self.applicant_address
        if self.resident:
            return self.resident.street_address or self.resident.address or ""
        return ""

    def get_applicant_age(self):
        if self.applicant_age:
            return self.applicant_age
        return ""

    def get_service_title(self):
        if self.category == self.CATEGORY_HEALTHCARE and self.healthcare_service:
            return self.healthcare_service.name
        elif self.document_type_id:
            return self.document_type.name
        return "Appointment Request"

    def __str__(self):
        return f"{self.get_service_title()} - {self.get_applicant_name()} ({self.get_status_display()})"

    @property
    def badge_class(self):
        mapping = {
            self.STATUS_PENDING: 'badge-warning',
            self.STATUS_APPROVED: 'badge-primary',
            self.STATUS_COMPLETED: 'badge-success',
            self.STATUS_REJECTED: 'badge-danger',
            self.STATUS_NO_SHOW: 'badge-secondary',
        }
        return mapping.get(self.status, 'badge-secondary')


class IssuedDocumentLog(models.Model):
    """
    Permanent audit log of officially issued clearances & certificates.

    NF compliance:
    1NF – all columns are atomic and single-valued.
    2NF – all non-key attributes depend fully on the OneToOne PK (appointment).
    3NF – control_number is a unique identifier for this log entry, not a
          transitive dependency through appointment.
    """
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name='issued_log'
    )
    control_number = models.CharField(
        max_length=60,
        unique=True,
        help_text="Official clearance tracking ID (e.g. BRGY-2026-0001)"
    )
    issued_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="received_documents"
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="issued_documents"
    )
    issued_at = models.DateTimeField(auto_now_add=True)
    qr_code = models.ImageField(upload_to='qr_codes/', blank=True, null=True)

    class Meta:
        ordering = ['-issued_at']
        verbose_name = 'Issued Document Clearance Log'
        verbose_name_plural = 'Issued Document Clearance Logs'

    def __str__(self):
        recipient = self.issued_to.username if self.issued_to else 'N/A'
        return f"{self.control_number} - {self.appointment.get_service_title()} to {recipient}"
