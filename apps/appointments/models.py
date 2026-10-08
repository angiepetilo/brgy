from django.db import models
from django.conf import settings


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Health Care Service'
        verbose_name_plural = 'Health Care Services'

    def __str__(self):
        return self.name

    def get_schedule_display(self):
        parts = []
        if self.available_date:
            parts.append(self.available_date)
        if self.available_time:
            parts.append(self.available_time)
        return " • ".join(parts) if parts else "Mon - Fri • 8:00 AM - 5:00 PM"


class DocumentType(models.Model):
    """
    Catalog of official clearance and certification document types offered by the Barangay.
    """
    name = models.CharField(max_length=150, unique=True, help_text='Name of the document type (e.g. Barangay Clearance)')
    code = models.CharField(max_length=50, blank=True, default='', help_text='Short code identifier')
    description = models.TextField(blank=True, default='', help_text='Description or purpose of this document')
    requirements_needed = models.TextField(blank=True, default='', help_text='Default requirements needed')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Document Type'
        verbose_name_plural = 'Document Types'

    def __str__(self):
        return self.name


class Appointment(models.Model):
    """
    Tracks document requests and health center appointment bookings.

    Normal-Form compliance:
    1NF – every column holds a single, atomic value.  preferred_time_slot uses
          a controlled vocabulary (choices), not a free-text range string.
    2NF – every non-key attribute depends on the whole PK (id), not a subset.
    3NF FIX – removed first_name / middle_name / last_name from this table.
          Those fields duplicated data already stored in the accounts.User
          record (resident FK), creating a transitive dependency:
          appointment.applicant_name → resident.id → accounts_user.
          The applicant name is now derived at query time via get_applicant_name().
    """
    CATEGORY_DOCUMENT = 'document'
    CATEGORY_HEALTHCARE = 'healthcare'

    CATEGORY_CHOICES = [
        (CATEGORY_DOCUMENT, 'Document Request'),
        (CATEGORY_HEALTHCARE, 'Health Care Request'),
    ]

    DOC_CLEARANCE = 'clearance'
    DOC_RESIDENCY = 'residency'
    DOC_INDIGENCY = 'indigency'
    DOC_NOA = 'noa'

    DOCUMENT_CHOICES = [
        (DOC_CLEARANCE, 'Barangay Clearance'),
        (DOC_RESIDENCY, 'Certificate of Residency'),
        (DOC_INDIGENCY, 'Certificate of Indigency'),
        (DOC_NOA, 'Notice of Award (NOA)'),
    ]

    STATUS_SUBMITTED = 'submitted'
    STATUS_UNDER_REVIEW = 'under_review'
    STATUS_APPROVED_SCHEDULED = 'approved_scheduled'
    STATUS_READY_FOR_PICKUP = 'ready_for_pickup'
    STATUS_COMPLETED = 'completed'
    STATUS_REJECTED = 'rejected'

    STATUS_CHOICES = [
        (STATUS_SUBMITTED, 'Submitted'),
        (STATUS_UNDER_REVIEW, 'Under Review'),
        (STATUS_APPROVED_SCHEDULED, 'Approved / Scheduled'),
        (STATUS_READY_FOR_PICKUP, 'Ready for Pickup'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_REJECTED, 'Rejected'),
    ]

    TIME_SLOT_MORNING = 'morning'
    TIME_SLOT_AFTERNOON = 'afternoon'
    TIME_SLOT_CHOICES = [
        (TIME_SLOT_MORNING, 'Morning (8:00 AM - 11:30 AM)'),
        (TIME_SLOT_AFTERNOON, 'Afternoon (1:00 PM - 4:30 PM)'),
    ]

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
    applicant_phone = models.CharField(max_length=20, blank=True, default='')

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

    document_type = models.CharField(
        max_length=150,
        choices=DOCUMENT_CHOICES,
        blank=True,
        default=DOC_CLEARANCE
    )
    purpose = models.TextField(
        help_text='State clearly the purpose of this request (e.g. Employment, Scholarship, Consultation notes)'
    )
    preferred_date = models.DateField(
        help_text='Selected date for processing or appointment'
    )
    preferred_time_slot = models.CharField(
        max_length=20,
        choices=TIME_SLOT_CHOICES,
        default=TIME_SLOT_MORNING
    )
    supporting_id = models.ImageField(
        upload_to='appointments/supporting_docs/',
        blank=True,
        null=True,
        help_text='Upload any supporting document or identification'
    )
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=STATUS_SUBMITTED
    )
    admin_notes = models.TextField(
        blank=True,
        help_text='Administrative remarks, scheduled instructions, or reasons for rejection'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_appointments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Appointment Request'
        verbose_name_plural = 'Appointment Requests'

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
        elif self.document_type:
            display_dict = dict(self.DOCUMENT_CHOICES)
            return display_dict.get(self.document_type, self.document_type)
        return "Appointment Request"

    def __str__(self):
        return f"{self.get_service_title()} - {self.get_applicant_name()} ({self.get_status_display()})"

    @property
    def badge_class(self):
        mapping = {
            self.STATUS_SUBMITTED: 'badge-secondary',
            self.STATUS_UNDER_REVIEW: 'badge-warning',
            self.STATUS_APPROVED_SCHEDULED: 'badge-info',
            self.STATUS_READY_FOR_PICKUP: 'badge-primary',
            self.STATUS_COMPLETED: 'badge-success',
            self.STATUS_REJECTED: 'badge-danger',
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
        on_delete=models.CASCADE,
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
        return f"{self.control_number} - {self.appointment.get_document_type_display()} to {self.issued_to.username}"
