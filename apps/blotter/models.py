from django.db import models
from django.conf import settings


class BlotterRecord(models.Model):
    """
    Blotter incident record filed at the Barangay.

    Normal-Form compliance:
    1NF – all columns hold single, atomic values.  Complainant and respondent
          identities are stored as separate FK + name fields to support both
          registered residents (FK) and unregistered persons (plain name).
    2NF – every non-key attribute depends fully on case_number / id (single-key
          table, so 2NF is automatically satisfied).
    3NF FIX – split the old complainant_name / respondent_name plain-text
          columns.  When the person is a registered User we store the FK and
          derive the name from the User record (no duplication).  When they are
          NOT registered we store only the plain-text name.  This removes the
          transitive dependency:  blotter.complainant_name → User.full_name.
    """

    STATUS_OPEN = 'Open'
    STATUS_SETTLED = 'Settled'
    STATUS_REFERRED = 'Referred to Court'

    STATUS_CHOICES = [
        (STATUS_OPEN, 'Open'),
        (STATUS_SETTLED, 'Settled'),
        (STATUS_REFERRED, 'Referred to Court'),
    ]

    case_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="e.g. BLOT-2026-0001"
    )

    # --- Complainant identity (3NF fix) ---
    # FK used when the complainant is a registered system User.
    complainant_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blotter_complaints',
        help_text="Link to registered resident account (if applicable)"
    )
    # Plain-text field used only when the complainant is NOT a registered user.
    complainant_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full name of Complainant (for unregistered persons only)"
    )

    # --- Respondent identity (3NF fix) ---
    respondent_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='blotter_respondents',
        help_text="Link to registered resident account (if applicable)"
    )
    respondent_name = models.CharField(
        max_length=200,
        blank=True,
        help_text="Full name of Respondent (for unregistered persons only)"
    )

    incident_type = models.CharField(
        max_length=150,
        help_text="e.g. Physical Injury, Property Damage, Neighborhood Altercation, Unjust Vexation"
    )
    incident_location = models.CharField(max_length=255)
    incident_date = models.DateTimeField(
        help_text="Date and time when the incident took place"
    )
    narrative = models.TextField(
        help_text="Detailed statement and factual account of the complaint"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default=STATUS_OPEN
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='logged_blotters'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Blotter Incident Record'
        verbose_name_plural = 'Blotter Incident Records'

    def get_complainant_display(self):
        """Single-source display name — prefers User full_name over free-text."""
        if self.complainant_user:
            return self.complainant_user.get_full_name() or self.complainant_user.username
        return self.complainant_name or "Unknown Complainant"

    def get_respondent_display(self):
        """Single-source display name — prefers User full_name over free-text."""
        if self.respondent_user:
            return self.respondent_user.get_full_name() or self.respondent_user.username
        return self.respondent_name or "Unknown Respondent"

    def __str__(self):
        return (
            f"{self.case_number}: "
            f"{self.get_complainant_display()} vs. {self.get_respondent_display()} "
            f"({self.status})"
        )

    @property
    def badge_class(self):
        mapping = {
            self.STATUS_OPEN: 'badge-danger',
            self.STATUS_SETTLED: 'badge-success',
            self.STATUS_REFERRED: 'badge-warning',
        }
        return mapping.get(self.status, 'badge-secondary')


class KPCase(models.Model):
    """
    Katarungang Pambarangay (KP) Conciliation & Mediation Proceedings.

    NF compliance:
    1NF – all columns are atomic; settlement_document is a file reference (not
          an embedded binary blob or comma-list).
    2NF – fully satisfied; single PK.
    3NF – all attributes depend on blotter (the entity key), not on each other.
    """
    blotter = models.OneToOneField(
        BlotterRecord,
        on_delete=models.CASCADE,
        related_name='kp_case'
    )
    hearing_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled date and time of mediation hearing"
    )
    mediator_notes = models.TextField(
        blank=True,
        help_text="Notes and agreements recorded by Lupon Tagapamayapa / Barangay Kapitan"
    )
    settlement_document = models.FileField(
        upload_to='kp_docs/',
        blank=True,
        null=True,
        help_text="Scanned Amicable Settlement or Kasunduan document"
    )
    certificate_to_file_action = models.BooleanField(
        default=False,
        help_text="Check if conciliation failed and Certificate to File Action (CFA) was issued for court filing"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Katarungang Pambarangay Case'
        verbose_name_plural = 'Katarungang Pambarangay Cases'

    def __str__(self):
        return f"KP Case for {self.blotter.case_number}"
