from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings


# =============================================================================
# 3NF FIX: Purok extracted as a standalone lookup/reference table.
# Previously, PUROK_CHOICES was duplicated inside both Household and User,
# violating 3NF (transitive dependency — label depends on code, not on PK).
# Now Purok is a single-source-of-truth table; all models FK into it.
# =============================================================================
class Purok(models.Model):
    """
    Lookup table for Purok zones within the Barangay.
    Centralises the purok domain so it is defined exactly once (3NF).
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="e.g. Purok 1, Purok 2 … Purok 7"
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional zone description or boundary notes"
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Purok'
        verbose_name_plural = 'Puroks'

    def __str__(self):
        return self.name


class Household(models.Model):
    """
    Represents a single residential household in the RBI (Registro ng Barangay Impormasyon).
    1NF  – every column is atomic; no repeating groups.
    2NF  – every non-key attribute depends fully on household_number (PK).
    3NF  – purok is a FK to the Purok lookup table; no transitive dependency.
    """
    household_number = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique Household Reference Number (e.g. HH-2026-001)"
    )
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_households',
        help_text="Designated head of the family/household"
    )
    # 1NF FIX: street_address is the *street-level* portion only (atomic).
    # The purok jurisdiction is stored in the FK below, not embedded here.
    street_address = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="House/Unit number and street name only (e.g. 12-B Rizal St.)"
    )
    purok = models.ForeignKey(
        Purok,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='households',
        help_text="Purok zone this household belongs to"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['household_number']
        verbose_name = 'Household Record'
        verbose_name_plural = 'Household Records (RBI)'

    def __init__(self, *args, **kwargs):
        if 'address' in kwargs and 'street_address' not in kwargs:
            kwargs['street_address'] = kwargs.pop('address')
        if 'purok' in kwargs and isinstance(kwargs['purok'], str):
            p_val = kwargs.pop('purok')
            if p_val:
                try:
                    kwargs['purok'], _ = Purok.objects.get_or_create(name=p_val)
                except Exception:
                    kwargs['purok'] = None
            else:
                kwargs['purok'] = None
        super().__init__(*args, **kwargs)

    @property
    def address(self):
        return self.street_address

    def __str__(self):
        head_name = self.head.get_full_name() if self.head else "Unassigned Head"
        purok_name = self.purok.name if self.purok else "No Purok"
        return f"{self.household_number} - {head_name} ({purok_name})"


class UserManager(BaseUserManager):
    """Custom manager for User model where email/username creation is cleanly handled."""

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        email = self.normalize_email(email) if email else ''
        user = self.model(username=username, email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_approved', True)
        extra_fields.setdefault('role', User.ROLE_ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Extended User model representing Barangay staff and registered residents.

    Normal-Form compliance:
    1NF – every field is atomic. The address is split into street_address (free
          text) + purok (FK). Demographic flags (is_pwd, is_senior, is_4ps) are
          separate boolean columns, not a comma-list.
    2NF – all attributes depend on the full primary key (id). No partial
          dependencies exist (this is a single-key table).
    3NF – purok FK eliminates the transitive dependency on the old PUROK_CHOICES
          CharField. duty_* fields belong functionally to this user's duty record;
          they are cohesive to the staff user entity.
    """

    ROLE_ADMIN = 'admin'
    ROLE_KAPITAN = 'kapitan'
    ROLE_RESIDENT = 'resident'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Barangay Administrator'),
        (ROLE_KAPITAN, 'Barangay Kapitan'),
        (ROLE_RESIDENT, 'Resident'),
    ]

    CIVIL_STATUS_SINGLE = 'Single'
    CIVIL_STATUS_MARRIED = 'Married'
    CIVIL_STATUS_WIDOWED = 'Widowed'
    CIVIL_STATUS_SEPARATED = 'Separated'

    CIVIL_STATUS_CHOICES = [
        (CIVIL_STATUS_SINGLE, 'Single'),
        (CIVIL_STATUS_MARRIED, 'Married'),
        (CIVIL_STATUS_WIDOWED, 'Widowed'),
        (CIVIL_STATUS_SEPARATED, 'Separated'),
    ]

    PUROK_CHOICES = [
        ('Purok 1', 'Purok 1'),
        ('Purok 2', 'Purok 2'),
        ('Purok 3', 'Purok 3'),
        ('Purok 4', 'Purok 4'),
        ('Purok 5', 'Purok 5'),
        ('Purok 6', 'Purok 6'),
        ('Purok 7', 'Purok 7'),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_RESIDENT,
        help_text='System role determining access permissions'
    )
    is_approved = models.BooleanField(
        default=False,
        help_text='Designates whether this resident has been verified and approved by a barangay administrator.'
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        help_text='Contact phone or mobile number'
    )

    # 1NF FIX: address is split into two atomic fields.
    # street_address holds the house/unit+street portion; purok is a FK lookup.
    street_address = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='House/Unit number and street name (e.g. 22 Mabini St.)'
    )
    # Legacy address field kept for backward compatibility during migration;
    # new code should read street_address + purok.
    address = models.TextField(
        blank=True,
        help_text='[LEGACY] Full residential address — use street_address + purok instead.'
    )
    # 3NF FIX: purok is now a FK to the Purok lookup table.
    purok = models.ForeignKey(
        Purok,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='residents',
        help_text='Purok jurisdiction inside the Barangay'
    )

    civil_status = models.CharField(
        max_length=20,
        choices=CIVIL_STATUS_CHOICES,
        default=CIVIL_STATUS_SINGLE,
        blank=True
    )
    occupation = models.CharField(
        max_length=120,
        blank=True,
        help_text='Primary occupation or livelihood'
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        help_text='Date of birth for age & demographic classification'
    )

    # Demographic & Welfare Flags
    # 1NF: each flag is a separate atomic boolean column — not a comma-list.
    is_pwd = models.BooleanField(
        default=False,
        verbose_name="PWD",
        help_text="Person with Disability"
    )
    is_senior = models.BooleanField(
        default=False,
        verbose_name="Senior Citizen",
        help_text="Senior Citizen (60+ years old)"
    )
    is_4ps = models.BooleanField(
        default=False,
        verbose_name="4Ps Beneficiary",
        help_text="Pantawid Pamilyang Pilipino Program (4Ps) beneficiary"
    )

    # Household association (RBI)
    household = models.ForeignKey(
        Household,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='members',
        help_text='Assigned Household folder'
    )

    # Avatar, Status Message & Staff Duty Roster
    avatar = models.ImageField(
        upload_to='avatars/',
        blank=True,
        null=True,
        help_text='Resident or staff avatar photo'
    )
    status_message = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Personal status message e.g. Available at Barangay Hall until 4 PM'
    )

    DUTY_ON = 'on_duty'
    DUTY_LEAVE = 'on_leave'
    DUTY_ABSENT = 'absent'
    DUTY_CHOICES = [
        (DUTY_ON, 'On-Duty'),
        (DUTY_LEAVE, 'On-Leave'),
        (DUTY_ABSENT, 'Absent'),
    ]

    duty_status = models.CharField(
        max_length=20,
        choices=DUTY_CHOICES,
        default=DUTY_ON,
        blank=True,
        help_text='Active officer roster duty status'
    )
    duty_return_date = models.DateField(
        null=True,
        blank=True,
        help_text='Expected return date if on leave'
    )
    duty_leave_reason = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text='Official reason for leave if on-leave'
    )

    id_proof = models.ImageField(
        upload_to='id_proofs/',
        blank=True,
        null=True,
        help_text='Scanned copy or photo of valid government ID or proof of residency'
    )
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text='Notes explaining rejection if verification was declined'
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_residents'
    )

    objects = UserManager()

    class Meta:
        ordering = ['-date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __init__(self, *args, **kwargs):
        if 'purok' in kwargs and isinstance(kwargs['purok'], str):
            p_val = kwargs.pop('purok')
            if p_val:
                try:
                    kwargs['purok'], _ = Purok.objects.get_or_create(name=p_val)
                except Exception:
                    kwargs['purok'] = None
            else:
                kwargs['purok'] = None
        super().__init__(*args, **kwargs)

    def __str__(self):
        full_name = self.get_full_name()
        display_name = full_name if full_name else self.username
        return f"{display_name} ({self.get_role_display()})"

    @property
    def purok_name(self):
        return self.purok.name if self.purok else ""

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser or self.is_staff

    @property
    def is_kapitan_user(self):
        return self.role == self.ROLE_KAPITAN

    @property
    def is_resident_user(self):
        return self.role == self.ROLE_RESIDENT

    @property
    def initials(self):
        name = self.get_full_name() or self.username
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name[:2].upper()

    @property
    def last_seen_formatted(self):
        if not self.last_login:
            return "Off"
        from django.utils import timezone
        diff = timezone.now() - self.last_login
        seconds = diff.total_seconds()
        if seconds < 3600:
            minutes = max(1, int(seconds // 60))
            return f"{minutes}m"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"{hours}h"
        else:
            days = int(seconds // 86400)
            return f"{days}d"

    def save(self, *args, **kwargs):
        # Auto-grant staff privileges for admin role
        if self.role == self.ROLE_ADMIN:
            self.is_staff = True
            self.is_approved = True
        elif self.role == self.ROLE_KAPITAN:
            self.is_approved = True
        super().save(*args, **kwargs)
