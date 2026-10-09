from django import forms
from django.contrib.auth import authenticate
from django.utils import timezone
from django.db.models import Q

from apps.accounts.models import User, Resident, Purok
from apps.accounts.services import calculate_age
from apps.core.uploads import validate_upload
from apps.core.validators import ph_mobile_widget_attrs, validate_ph_mobile


class ResidentRegistrationForm(forms.Form):
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'})
    )
    middle_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Middle Name (Optional)'})
    )
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'})
    )
    birthdate = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date',
            'min': '1900-01-01',
            'max': '9999-12-31'
        }),
        help_text="You must be at least 18 years old to register."
    )
    # No max_length: the validator gives the one clear 11-digit message, and the
    # widget keeps maxlength=11 (a form max_length would overwrite it).
    contact_no = forms.CharField(
        required=True,
        validators=[validate_ph_mobile],
        widget=forms.TextInput(attrs=ph_mobile_widget_attrs(**{'class': 'form-control'})),
        help_text="11 digits, starting with 09 (e.g. 09171234567).",
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
        help_text="Login credentials will be sent to this email upon verification."
    )
    purok = forms.ModelChoiceField(
        queryset=Purok.objects.all(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        empty_label="-- Select Purok Jurisdiction --"
    )
    address = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'House / Unit #, Street Name'})
    )
    gender = forms.ChoiceField(
        choices=[('', '-- Select --')] + Resident.GENDER_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    civil_status = forms.ChoiceField(
        choices=[('', '-- Select --')] + list(Resident.CIVIL_STATUS_CHOICES),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    is_solo_parent = forms.BooleanField(
        required=False,
        label='Solo Parent',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_pwd = forms.BooleanField(
        required=False,
        label='Person with Disability (PWD)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    is_4ps = forms.BooleanField(
        required=False,
        label='4Ps Beneficiary',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    id_photo = forms.FileField(
        required=True,
        validators=[validate_upload],
        widget=forms.FileInput(attrs={'accept': 'image/*,application/pdf'}),
        help_text="Upload a clear photo of your valid Government ID or proof of residency."
    )
    privacy_consent = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input', 'id': 'privacyConsentCheckbox'}),
        error_messages={'required': 'You must agree to the privacy notice to submit your registration.'}
    )

    def clean_birthdate(self):
        birthdate = self.cleaned_data.get('birthdate')
        if not birthdate:
            raise forms.ValidationError("Birthdate is required.")
        today = timezone.localdate()
        if birthdate > today:
            raise forms.ValidationError("Birthdate cannot be in the future.")
        if birthdate.year < 1900 or birthdate.year > 9999 or len(str(abs(birthdate.year))) != 4:
            raise forms.ValidationError("Please enter a valid birthdate.")
        age = calculate_age(birthdate)
        if age < 18:
            raise forms.ValidationError("This portal is for residents 18 and above.")
        return birthdate

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError("Email is required.")
        user = User.objects.filter(email__iexact=email).first()
        if user:
            if user.status == User.STATUS_REJECTED:
                # Allowed to sign up again
                pass
            elif user.status == User.STATUS_PENDING:
                raise forms.ValidationError("An account with this email is currently pending verification.")
            elif user.status == User.STATUS_ACTIVE:
                raise forms.ValidationError("An active account with this email already exists. Please log in.")
            elif user.status == User.STATUS_DISABLED:
                raise forms.ValidationError("This account has been disabled. Please contact the Barangay Office.")
        return email


class UserLoginForm(forms.Form):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username or Email Address'}),
        label="Username or Email"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}),
        label="Password"
    )

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        username_or_email = cleaned_data.get('username', '').strip()
        password = cleaned_data.get('password')

        _generic = "Invalid email/username or password."

        if username_or_email and password:
            # Step 1: resolve the username (without revealing whether it exists)
            user_obj = User.objects.filter(
                Q(username__iexact=username_or_email) | Q(email__iexact=username_or_email)
            ).first()

            # Step 2: always authenticate, even for unknown identifiers, so the
            # user_login_failed signal fires (brute-force counters) and the
            # password hasher runs (similar timing for known/unknown users).
            user = authenticate(
                self.request,
                username=user_obj.username if user_obj else username_or_email,
                password=password,
            )
            if not user or not user_obj:
                # Wrong password â€” generic message, no account status revealed
                raise forms.ValidationError(_generic)

            # Step 3: password is correct â€” now surface account-state messages
            if user_obj.temp_password_expires_at and timezone.now() > user_obj.temp_password_expires_at:
                raise forms.ValidationError(
                    "Your temporary password has expired. Please contact the Barangay Office."
                )

            if user.status == User.STATUS_PENDING:
                raise forms.ValidationError(
                    "Your account is pending verification. Please wait for an approval email."
                )
            elif user.status == User.STATUS_REJECTED:
                reason = user.rejection_reason or "Verification documents incomplete"
                raise forms.ValidationError(
                    f"Your registration was rejected: {reason}. You may register again."
                )
            elif user.status == User.STATUS_DISABLED:
                raise forms.ValidationError(
                    "This account has been disabled. Please contact the Barangay Administrator."
                )

            self.user_cache = user
        return cleaned_data

    def get_user(self):
        return getattr(self, 'user_cache', None)


class ForcePasswordChangeForm(forms.Form):
    """
    Used when must_change_password=True (temporary password flow).
    Enforces all AUTH_PASSWORD_VALIDATORS plus must-differ-from-temp rule.
    """
    new_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter new password (min. 8 characters)'}),
        min_length=8,
        label="New Password"
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm new password'}),
        min_length=8,
        label="Confirm Password"
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._user = user

    def clean_new_password(self):
        from django.contrib.auth.password_validation import validate_password
        password = self.cleaned_data.get('new_password')
        if password:
            # Run all configured password validators
            validate_password(password, user=self._user)
            if self._user and self._user.check_password(password):
                raise forms.ValidationError("New password must differ from your temporary password.")
        return password

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('new_password')
        p2 = cleaned_data.get('confirm_password')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords do not match.")
        return cleaned_data


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'status_message', 'avatar', 'duty_status', 'duty_return_date', 'duty_leave_reason']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs=ph_mobile_widget_attrs(**{'class': 'form-control'})),
            'status_message': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Available at Barangay Hall until 4 PM'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'duty_status': forms.Select(attrs={'class': 'form-control'}),
            'duty_return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'duty_leave_reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for leave'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['duty_status'].required = False
        self.fields['duty_return_date'].required = False
        self.fields['duty_leave_reason'].required = False
        self.fields['status_message'].required = False
        self.fields['avatar'].required = False
        # The model column allows 20 characters; the input itself takes 11 digits.
        self.fields['phone_number'].widget.attrs['maxlength'] = '11'
