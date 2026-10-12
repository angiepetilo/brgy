from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import FileSystemStorage

from apps.core.uploads import random_upload_to, validate_upload
from apps.core.validators import validate_ph_mobile

private_id_photo_storage = FileSystemStorage(
    location=settings.BASE_DIR / 'private_media' / 'id_photos',
    base_url=None
)


class Officer(models.Model):
    """
    Barangay Officer and Official entity.
    """
    POSITION_PUNONG_BARANGAY = 'Punong Barangay'
    POSITION_SECRETARY = 'Secretary'
    POSITION_TREASURER = 'Treasurer'
    POSITION_KAGAWAD = 'Kagawad'
    POSITION_SK_CHAIRPERSON = 'SK Chairperson'
    POSITION_PUROK_LEADER = 'Purok Leader'
    POSITION_BHW = 'BHW'
    POSITION_TANOD = 'Tanod'

    POSITION_CHOICES = [
        (POSITION_PUNONG_BARANGAY, 'Punong Barangay'),
        (POSITION_SECRETARY, 'Secretary'),
        (POSITION_TREASURER, 'Treasurer'),
        (POSITION_KAGAWAD, 'Kagawad'),
        (POSITION_SK_CHAIRPERSON, 'SK Chairperson'),
        (POSITION_PUROK_LEADER, 'Purok Leader'),
        (POSITION_BHW, 'BHW'),
        (POSITION_TANOD, 'Tanod'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='officer_roles'
    )
    position = models.CharField(max_length=50, choices=POSITION_CHOICES)
    committee = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        default='',
        help_text="e.g. Health, Peace and Order, Education, Infrastructure"
    )

    class Meta:
        ordering = ['position']
        verbose_name = 'Officer'
        verbose_name_plural = 'Officers'

    def __str__(self):
        user_name = self.user.get_full_name() if self.user else "Vacant"
        return f"{self.position} - {user_name}"


class Purok(models.Model):
    """
    Lookup table for Purok zones within the Barangay.
    """
    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="e.g. Purok 1, Purok 2 … Purok 7"
    )
    description = models.CharField(
        max_length=255,
        blank=True,
        default='',
        help_text="Optional zone description or boundary notes"
    )
    leader = models.ForeignKey(
        Officer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='led_puroks'
    )

    class Meta:
        ordering = ['name']
        verbose_name = 'Purok'
        verbose_name_plural = 'Puroks'

    def __str__(self):
        return self.name


class UserManager(BaseUserManager):
    """Custom manager for User model where email/username creation is cleanly handled."""

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError('The Username field must be set')
        if not email:
            email = f"{username}@example.com"
        else:
            email = self.normalize_email(email)
        if extra_fields.get('role') in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or extra_fields.get('is_approved') is True:
            extra_fields.setdefault('status', User.STATUS_ACTIVE)
            extra_fields.setdefault('is_approved', True)
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
        extra_fields.setdefault('role', User.ROLE_ADMIN)
        extra_fields.setdefault('status', User.STATUS_ACTIVE)
        extra_fields.setdefault('is_approved', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(username, email, password, **extra_fields)


class User(AbstractUser):
    """
    Extended User model representing Barangay staff, officers, and registered residents.
    """
    ROLE_RESIDENT = 'resident'
    ROLE_STAFF = 'staff'
    ROLE_ADMIN = 'admin'
    ROLE_KAPITAN = 'kapitan'

    ROLE_CHOICES = [
        (ROLE_RESIDENT, 'Resident'),
        (ROLE_STAFF, 'Staff'),
        (ROLE_ADMIN, 'Admin'),
        (ROLE_KAPITAN, 'Barangay Kapitan'),
    ]

    STATUS_PENDING = 'pending'
    STATUS_ACTIVE = 'active'
    STATUS_REJECTED = 'rejected'
    STATUS_DISABLED = 'disabled'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACTIVE, 'Active'),
        (STATUS_REJECTED, 'Rejected'),
        (STATUS_DISABLED, 'Disabled'),
    ]

    email = models.EmailField(unique=True, help_text="Required unique email address")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_RESIDENT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    rejection_reason = models.TextField(blank=True, default='')
    reviewed_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_users')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=False)
    temp_password_expires_at = models.DateTimeField(null=True, blank=True)

    # Legacy fields maintained for backward compatibility:
    is_approved = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=20, blank=True, default='', validators=[validate_ph_mobile])
    street_address = models.CharField(max_length=255, blank=True, default='')
    address = models.TextField(blank=True, default='')
    purok = models.ForeignKey(Purok, on_delete=models.SET_NULL, null=True, blank=True, related_name='legacy_users')
    occupation = models.CharField(max_length=120, blank=True, default='')
    date_of_birth = models.DateField(null=True, blank=True)
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)
    term_end = models.DateField(null=True, blank=True, help_text="End of appointment or elective term")
    department = models.CharField(max_length=100, blank=True, default='', help_text="Assigned department in the barangay")
    allowed_modules = models.JSONField(default=list, blank=True, help_text="Direct module permissions granted to staff")
    status_message = models.CharField(max_length=255, blank=True, default='')
    duty_status = models.CharField(max_length=20, blank=True, default='on_duty')
    duty_return_date = models.DateField(null=True, blank=True)
    duty_leave_reason = models.CharField(max_length=255, blank=True, default='')
    id_proof = models.ImageField(upload_to='id_proofs/', blank=True, null=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_legacy_users')

    objects = UserManager()

    class Meta:
        ordering = ['-date_joined']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        full_name = self.get_full_name()
        display_name = full_name if full_name else self.username
        return f"{display_name} ({self.get_role_display()})"

    @property
    def is_admin_user(self):
        return self.role == self.ROLE_ADMIN or self.is_superuser

    @property
    def is_staff_user(self):
        return self.role in [self.ROLE_ADMIN, self.ROLE_STAFF, self.ROLE_KAPITAN] or self.is_staff or self.is_superuser

    @property
    def is_kapitan_user(self):
        return self.role in [self.ROLE_STAFF, self.ROLE_KAPITAN]

    @property
    def is_resident_user(self):
        return self.role == self.ROLE_RESIDENT and not (self.is_staff or self.is_superuser)

    @property
    def initials(self):
        name = self.get_full_name() or self.username
        parts = name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name[:2].upper()

    def get_purok_display(self):
        if self.purok:
            return self.purok.name
        if hasattr(self, 'resident_profile') and self.resident_profile and self.resident_profile.purok:
            return self.resident_profile.purok.name
        return ''

    @property
    def purok_name(self):
        return self.get_purok_display()

    def save(self, *args, **kwargs):
        if self.role == self.ROLE_ADMIN:
            self.is_staff = True
        if self.is_approved and self.status == self.STATUS_PENDING:
            self.status = self.STATUS_ACTIVE
        elif self.status == self.STATUS_ACTIVE:
            self.is_approved = True
        is_disabled = (self.status == self.STATUS_DISABLED)
        super().save(*args, **kwargs)
        if is_disabled:
            try:
                from apps.chat.services import reassign_staff_open_concerns
                reassign_staff_open_concerns(self)
            except Exception:
                pass


class Household(models.Model):
    """
    Household entity representing families / residences in the barangay.
    """
    household_id = models.CharField(
        max_length=50,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Unique Household Reference Number (e.g. HH-2026-0001)"
    )
    household_number = models.CharField(max_length=50, blank=True, default='', help_text="Household Number (e.g. HM-2023-001)")
    household_family_name = models.CharField(max_length=150, blank=True, default='')
    street = models.CharField(max_length=255, blank=True, default='')
    sitio = models.CharField(max_length=100, blank=True, default='', help_text="Sitio / Zone name")
    ownership_status = models.CharField(max_length=50, blank=True, default='Owned')
    water_source = models.CharField(max_length=150, blank=True, default='Level 3 - Individual Connection')
    toilet_type = models.CharField(max_length=150, blank=True, default='A - Pour/flush type connected to septic tank')
    home_link = models.CharField(max_length=500, blank=True, default='', help_text="Google Maps or location link")

    # Legacy fields
    household_name = models.CharField(max_length=150, blank=True, default='')
    address = models.TextField(blank=True, default='')
    head = models.ForeignKey(
        'Resident',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='headed_households'
    )
    purok = models.ForeignKey(
        Purok,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='households'
    )

    # Primary representative / member details
    first_name = models.CharField(max_length=100, blank=True, default='')
    middle_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100, blank=True, default='')
    relationship = models.CharField(max_length=50, blank=True, default='Head')
    birthdate = models.DateField(null=True, blank=True)

    # Profiling / field visit metadata
    interviewed_by = models.CharField(max_length=150, blank=True, default='')
    reviewed_by = models.CharField(max_length=150, blank=True, default='')
    date_of_visit = models.DateField(null=True, blank=True)

    # Audit tracking
    encoded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='encoded_households'
    )
    date_and_time_encoded = models.DateTimeField(null=True, blank=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='updated_households'
    )
    date_updated = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['purok', 'household_family_name', '-created_at']
        verbose_name = 'Household'
        verbose_name_plural = 'Households'

    def __str__(self):
        name = self.household_family_name or self.household_name
        hid = f"[{self.household_id}] " if self.household_id else ""
        return f"{hid}{name} ({self.purok.name if self.purok else 'No Purok'})"

    @property
    def age(self):
        if not self.birthdate:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))

    @property
    def display_sitio(self):
        return self.sitio or (self.purok.name if self.purok else 'Ylaya')

    @property
    def display_household_number(self):
        return self.household_number or self.household_id or f"HM-2025-{self.id:03d}"

    @property
    def total_members_count(self):
        count = self.household_members.count()
        if count > 0:
            return count
        return 1 if (self.first_name or self.last_name) else 1

    def get_members_list(self):
        members = []
        for m in self.household_members.all():
            members.append({
                'id': m.id,
                'first_name': m.first_name,
                'last_name': m.last_name,
                'relationship': m.relationship or 'Member',
                'birthdate': m.birthdate.strftime('%Y-%m-%d') if m.birthdate else '',
                'age': m.age if m.age is not None else '',
                'is_pwd': bool(m.is_pwd),
                'is_solo_parent': bool(m.is_solo_parent),
                'is_4ps': bool(m.is_4ps),
                'is_senior': bool(m.is_senior),
            })
        if not members and (self.first_name or self.last_name):
            head_age = self.age
            members.append({
                'id': 0,
                'first_name': self.first_name,
                'last_name': self.last_name,
                'relationship': self.relationship or 'Head',
                'birthdate': self.birthdate.strftime('%Y-%m-%d') if self.birthdate else '',
                'age': head_age if head_age is not None else '',
                'is_pwd': False,
                'is_solo_parent': False,
                'is_4ps': False,
                'is_senior': bool(head_age is not None and head_age >= 60),
            })
        return members

    @property
    def members_json(self):
        import json
        return json.dumps(self.get_members_list())

    @property
    def encoded_by_name(self):
        if self.encoded_by:
            return self.encoded_by.get_full_name() or self.encoded_by.username
        return 'Staff Encoder'

    @property
    def updated_by_name(self):
        if self.updated_by:
            return self.updated_by.get_full_name() or self.updated_by.username
        return 'Staff Encoder'

    @property
    def display_date_encoded(self):
        dt = self.date_and_time_encoded or self.created_at
        if dt:
            from django.utils import timezone
            dt = timezone.localtime(dt)
            return dt.strftime("%B %d, %Y | %I:%M %p").replace(" 0", " ")
        return "--"

    @property
    def display_date_updated(self):
        dt = self.date_updated or self.updated_at
        if dt:
            from django.utils import timezone
            dt = timezone.localtime(dt)
            return dt.strftime("%B %d, %Y | %I:%M %p").replace(" 0", " ")
        return "--"

    def save(self, *args, **kwargs):
        from django.utils import timezone
        if not self.household_id:
            year = (self.date_of_visit or timezone.localdate()).year
            prefix = f"HH-{year}-"
            last_hh = Household.objects.filter(household_id__startswith=prefix).order_by('-household_id').first()
            if last_hh and last_hh.household_id:
                try:
                    num = int(last_hh.household_id.split('-')[-1]) + 1
                except (ValueError, IndexError):
                    num = Household.objects.count() + 1
            else:
                num = Household.objects.count() + 1
            self.household_id = f"HH-{year}-{num:04d}"

        if not self.household_number:
            self.household_number = self.household_id

        if not self.household_family_name:
            if self.last_name:
                self.household_family_name = f"{self.last_name} Family"
            elif self.household_name:
                self.household_family_name = self.household_name

        if not self.household_name:
            self.household_name = self.household_family_name or self.household_id

        if not self.address and self.street:
            self.address = self.street
        elif not self.street and self.address:
            self.street = self.address

        if not self.date_and_time_encoded:
            self.date_and_time_encoded = timezone.now()
        self.date_updated = timezone.now()

        super().save(*args, **kwargs)


class HouseholdMember(models.Model):
    """
    Individual family/household member records belonging to a Household.
    """
    household = models.ForeignKey(
        Household,
        on_delete=models.CASCADE,
        related_name='household_members'
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    relationship = models.CharField(max_length=50, default='Member')
    birthdate = models.DateField(null=True, blank=True)
    is_pwd = models.BooleanField(default=False)
    is_solo_parent = models.BooleanField(default=False)
    is_4ps = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['id']
        verbose_name = 'Household Member'
        verbose_name_plural = 'Household Members'

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.relationship})"

    @property
    def age(self):
        if not self.birthdate:
            return None
        from datetime import date
        today = date.today()
        return today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))

    @property
    def is_senior(self):
        age = self.age
        return age is not None and age >= 60


class Resident(models.Model):
    """
    Separate Resident profile entity.
    A Resident can exist without a User (staff may register families who never sign up).

    Resident is the single source of demographics. Seniors are never stored:
    `is_senior` is derived from `birthdate` (age >= SENIOR_AGE).
    """
    SENIOR_AGE = 60

    GENDER_MALE = 'male'
    GENDER_FEMALE = 'female'
    GENDER_OTHER = 'other'
    GENDER_CHOICES = [
        (GENDER_MALE, 'Male'),
        (GENDER_FEMALE, 'Female'),
        (GENDER_OTHER, 'Other'),
    ]

    CIVIL_SINGLE = 'single'
    CIVIL_MARRIED = 'married'
    CIVIL_WIDOWED = 'widowed'
    CIVIL_SEPARATED = 'separated'
    CIVIL_DIVORCED = 'divorced'
    CIVIL_STATUS_CHOICES = [
        (CIVIL_SINGLE, 'Single'),
        (CIVIL_MARRIED, 'Married'),
        (CIVIL_WIDOWED, 'Widowed'),
        (CIVIL_SEPARATED, 'Separated'),
        (CIVIL_DIVORCED, 'Divorced'),
    ]

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True, default='')
    last_name = models.CharField(max_length=100)
    birthdate = models.DateField(help_text="Used to compute age dynamically on the server")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True, default='')
    civil_status = models.CharField(max_length=20, choices=CIVIL_STATUS_CHOICES, default=CIVIL_SINGLE)
    is_solo_parent = models.BooleanField(default=False)
    is_pwd = models.BooleanField(default=False)
    is_4ps = models.BooleanField(default=False)
    contact_no = models.CharField(max_length=20, blank=True, default='', validators=[validate_ph_mobile])
    address = models.TextField(blank=True, default='')
    purok = models.ForeignKey(Purok, on_delete=models.SET_NULL, null=True, blank=True, related_name='residents')
    household = models.ForeignKey(
        Household,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='members'
    )
    id_photo = models.FileField(
        storage=private_id_photo_storage, upload_to=random_upload_to('id'), blank=True, null=True,
        validators=[validate_upload],
        help_text="Resident identity document (stored in private storage)",
    )
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resident_profile'
    )
    assigned_officer = models.ForeignKey(
        Officer,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_residents'
    )
    is_archived = models.BooleanField(default=False, db_index=True)

    # Needs Attention attributes
    needs_attention = models.BooleanField(default=False, db_index=True)
    needs_category = models.CharField(max_length=100, blank=True, default='')
    needs_categories = models.CharField(max_length=150, blank=True, default='', help_text="senior, pwd, low_income, other")
    needs_notes = models.TextField(blank=True, default='')
    needs_recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_needs'
    )
    needs_recorded_at = models.DateTimeField(null=True, blank=True)
    consent_recorded = models.BooleanField(default=False)
    consent_recorded_date = models.DateField(null=True, blank=True)
    no_consent_reason = models.TextField(blank=True, default='', help_text="Reason for recording needs without consent")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        verbose_name = 'Resident'
        verbose_name_plural = 'Residents'
        indexes = [
            models.Index(fields=['purok', 'needs_attention']),
            models.Index(fields=['needs_attention']),
            models.Index(fields=['is_archived']),
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['birthdate']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return self.get_full_name()

    def get_full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p]).strip()

    @property
    def age(self):
        if not self.birthdate:
            return None
        today = timezone.localdate()
        return today.year - self.birthdate.year - ((today.month, today.day) < (self.birthdate.month, self.birthdate.day))

    @property
    def is_minor(self):
        return self.age is not None and self.age < 18

    @property
    def is_senior(self):
        """Derived from birthdate, never stored. Queryset twin: selectors.seniors()."""
        age = self.age
        return age is not None and age >= self.SENIOR_AGE

    @property
    def sector_labels(self):
        """Human-readable special sectors this resident belongs to."""
        labels = []
        if self.is_senior:
            labels.append('Senior')
        if self.is_pwd:
            labels.append('PWD')
        if self.is_solo_parent:
            labels.append('Solo Parent')
        if self.is_4ps:
            labels.append('4Ps')
        return labels

    @property
    def id_photo_protected_url(self):
        if not self.id_photo:
            return ''
        from django.urls import reverse
        return reverse('accounts:serve_id_photo', kwargs={'resident_id': self.id})


class StaffAssignment(models.Model):
    """
    StaffAssignment: scope of authority for staff officers.
    scope_type: purok or service_area (e.g. Health, Documents).
    """
    SCOPE_PUROK = 'purok'
    SCOPE_SERVICE_AREA = 'service_area'
    SCOPE_TYPE_CHOICES = [
        (SCOPE_PUROK, 'Purok Jurisdiction'),
        (SCOPE_SERVICE_AREA, 'Service Area'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='staff_assignments'
    )
    officer = models.ForeignKey(
        Officer,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='officer_assignments'
    )
    scope_type = models.CharField(max_length=30, choices=SCOPE_TYPE_CHOICES)
    scope_value = models.CharField(
        max_length=100,
        help_text="e.g. Purok 1, Health, Documents, Peace and Order"
    )
    term_end = models.DateField(null=True, blank=True, help_text="End of assignment term")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['user', 'scope_type', 'scope_value']
        verbose_name = 'Staff Assignment'
        verbose_name_plural = 'Staff Assignments'

    def __str__(self):
        return f"{self.user} - {self.get_scope_type_display()}: {self.scope_value}"


class PermissionRule(models.Model):
    """
    PermissionRule: Action-level permission rule per officer position.
    Actions and modules are discovered automatically from code registry.
    """
    officer = models.ForeignKey(
        Officer,
        on_delete=models.CASCADE,
        related_name='permission_rules'
    )
    module = models.CharField(max_length=50, help_text="e.g. appointments, communications, accounts")
    action = models.CharField(max_length=50, help_text="e.g. view, create, edit, approve, reject, delete, message, post_category")
    allowed = models.BooleanField(default=True)

    class Meta:
        ordering = ['officer', 'module', 'action']
        unique_together = [('officer', 'module', 'action')]
        verbose_name = 'Permission Rule'
        verbose_name_plural = 'Permission Rules'

    def __str__(self):
        status = "Allowed" if self.allowed else "Denied"
        return f"{self.officer.position} | {self.module}.{self.action} -> {status}"


class BarangayInfo(models.Model):
    """
    Official Barangay Information editable by Admin in System module.
    Emails and templates read from this model.
    """
    name = models.CharField(max_length=150, default='Barangay Poblacion')
    address = models.TextField(blank=True, default='Barangay Hall, Main Street')
    city = models.CharField(max_length=100, blank=True, default='')
    province = models.CharField(max_length=100, blank=True, default='')
    contact_no = models.CharField(max_length=50, blank=True, default='(02) 8123-4567')
    emergency_hotline = models.CharField(max_length=100, blank=True, default='911 / (02) 8123-4567', help_text="Official emergency hotline")
    show_available_services = models.BooleanField(default=True, help_text="Show Available Services & Consultations on public portal")
    office_hours = models.CharField(max_length=120, blank=True, default='Monday - Friday, 8:00 AM - 5:00 PM')
    venue = models.CharField(max_length=150, blank=True, default='Barangay Session Hall')
    logo = models.ImageField(upload_to='barangay/', blank=True, null=True)

    # Standard Operating Windows for Appointments
    morning_window_start = models.CharField(max_length=20, blank=True, default='8:00 AM')
    morning_window_end = models.CharField(max_length=20, blank=True, default='11:30 AM')
    afternoon_window_start = models.CharField(max_length=20, blank=True, default='1:00 PM')
    afternoon_window_end = models.CharField(max_length=20, blank=True, default='4:30 PM')
    operating_days = models.CharField(max_length=150, blank=True, default='Monday to Friday (excluding official holidays)')
    slot_capacity_per_window = models.PositiveIntegerField(default=20)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Barangay Information'
        verbose_name_plural = 'Barangay Information'

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(id=1)
        return obj

    def __str__(self):
        return self.name


