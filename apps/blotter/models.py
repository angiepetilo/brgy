"""
Blotter (Katarungang Pambarangay) records.

A BlotterCase moves through a fixed set of statuses (TRANSITIONS). Only
apps.blotter.services changes a status; it also stamps settled_at,
escalated_at and closed_at (closed_at is set on every terminal status so
monthly settlement rates have a closure month for dismissed and withdrawn
cases too).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.core.validators import validate_ph_mobile


class BlotterCase(models.Model):
    CASE_NO_PREFIX = 'BLT'

    TYPE_DISPUTE = 'dispute'
    TYPE_NOISE = 'noise'
    TYPE_THEFT = 'theft'
    TYPE_PHYSICAL_INJURY = 'physical_injury'
    TYPE_PROPERTY_DAMAGE = 'property_damage'
    TYPE_DOMESTIC = 'domestic'
    TYPE_THREAT = 'threat'
    TYPE_TRESPASSING = 'trespassing'
    TYPE_OTHER = 'other'
    INCIDENT_TYPE_CHOICES = [
        (TYPE_DISPUTE, 'Dispute'),
        (TYPE_NOISE, 'Noise complaint'),
        (TYPE_THEFT, 'Theft'),
        (TYPE_PHYSICAL_INJURY, 'Physical injury'),
        (TYPE_PROPERTY_DAMAGE, 'Property damage'),
        (TYPE_DOMESTIC, 'Domestic'),
        (TYPE_THREAT, 'Threat'),
        (TYPE_TRESPASSING, 'Trespassing'),
        (TYPE_OTHER, 'Other'),
    ]

    STATUS_FILED = 'filed'
    STATUS_UNDER_MEDIATION = 'under_mediation'
    STATUS_SETTLED = 'settled'
    STATUS_ESCALATED = 'escalated'
    STATUS_DISMISSED = 'dismissed'
    STATUS_WITHDRAWN = 'withdrawn'
    STATUS_CHOICES = [
        (STATUS_FILED, 'Filed'),
        (STATUS_UNDER_MEDIATION, 'Under mediation'),
        (STATUS_SETTLED, 'Settled'),
        (STATUS_ESCALATED, 'Escalated'),
        (STATUS_DISMISSED, 'Dismissed'),
        (STATUS_WITHDRAWN, 'Withdrawn'),
    ]

    TERMINAL = frozenset({STATUS_SETTLED, STATUS_ESCALATED, STATUS_DISMISSED, STATUS_WITHDRAWN})
    TRANSITIONS = {
        STATUS_FILED: (STATUS_UNDER_MEDIATION, STATUS_DISMISSED, STATUS_WITHDRAWN),
        STATUS_UNDER_MEDIATION: (STATUS_SETTLED, STATUS_ESCALATED, STATUS_WITHDRAWN),
        STATUS_SETTLED: (),
        STATUS_ESCALATED: (),
        STATUS_DISMISSED: (),
        STATUS_WITHDRAWN: (),
    }

    case_no = models.CharField(max_length=20, unique=True, editable=False)
    incident_type = models.CharField(max_length=30, choices=INCIDENT_TYPE_CHOICES)
    incident_date = models.DateField()
    incident_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=255)
    purok = models.ForeignKey(
        'accounts.Purok', on_delete=models.SET_NULL, null=True, blank=True, related_name='blotter_cases',
    )
    narrative = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_FILED, db_index=True)
    filed_at = models.DateTimeField(auto_now_add=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    escalated_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True, default='')
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='blotter_cases_handled',
    )
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='blotter_cases_recorded',
    )
    is_confidential = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-filed_at', '-id']
        verbose_name = 'Blotter Case'
        verbose_name_plural = 'Blotter Cases'
        indexes = [
            models.Index(fields=['status', 'filed_at']),
            models.Index(fields=['purok', 'status']),
        ]

    def __str__(self):
        return self.case_no or 'New blotter case'

    def clean(self):
        if self.incident_date and self.incident_date > timezone.localdate():
            raise ValidationError({'incident_date': 'The incident date cannot be in the future.'})

    @property
    def is_terminal(self):
        return self.status in self.TERMINAL

    @property
    def next_statuses(self):
        return self.TRANSITIONS.get(self.status, ())

    @classmethod
    def status_label(cls, code):
        return dict(cls.STATUS_CHOICES).get(code, code)


class BlotterParty(models.Model):
    ROLE_COMPLAINANT = 'complainant'
    ROLE_RESPONDENT = 'respondent'
    ROLE_WITNESS = 'witness'
    ROLE_CHOICES = [
        (ROLE_COMPLAINANT, 'Complainant'),
        (ROLE_RESPONDENT, 'Respondent'),
        (ROLE_WITNESS, 'Witness'),
    ]

    case = models.ForeignKey(BlotterCase, on_delete=models.CASCADE, related_name='parties')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    resident = models.ForeignKey(
        'accounts.Resident', on_delete=models.SET_NULL, null=True, blank=True, related_name='blotter_parties',
    )
    full_name = models.CharField(max_length=200)
    address = models.CharField(max_length=255, blank=True, default='')
    contact_no = models.CharField(max_length=20, blank=True, default='', validators=[validate_ph_mobile])

    class Meta:
        ordering = ['case', 'role', 'id']
        verbose_name = 'Blotter Party'
        verbose_name_plural = 'Blotter Parties'

    def __str__(self):
        return f'{self.full_name} ({self.get_role_display()})'


class BlotterHearing(models.Model):
    case = models.ForeignKey(BlotterCase, on_delete=models.CASCADE, related_name='hearings')
    scheduled_at = models.DateTimeField()
    outcome_notes = models.TextField(blank=True, default='')
    complainant_attended = models.BooleanField(default=False)
    respondent_attended = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='blotter_hearings_recorded',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['scheduled_at', 'id']
        verbose_name = 'Blotter Hearing'
        verbose_name_plural = 'Blotter Hearings'

    def __str__(self):
        return f'{self.case.case_no} hearing {self.scheduled_at:%Y-%m-%d %H:%M}'
