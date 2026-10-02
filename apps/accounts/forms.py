from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm

User = get_user_model()


class ResidentRegistrationForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
        help_text='Your login password will be emailed to this address once approved by the Barangay Administrator.'
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'username', 'email', 'phone_number', 'purok', 'street_address', 'id_proof']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. juandelacruz'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0912-345-6789'}),
            'purok': forms.Select(attrs={'class': 'form-control'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'House / Unit #, Street Name'}),
            'id_proof': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,application/pdf'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_unusable_password()  # No password yet; will be generated & emailed upon approval
        user.role = User.ROLE_RESIDENT
        user.is_approved = False  # Gated until admin approves
        if commit:
            user.save()
        return user


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username or Email'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'}))


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'status_message', 'avatar', 'duty_status', 'duty_return_date', 'duty_leave_reason']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Mobile Number'}),
            'status_message': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Available at Barangay Hall until 4 PM'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
            'duty_status': forms.Select(attrs={'class': 'form-control'}),
            'duty_return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'duty_leave_reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for leave (e.g. Official travel, Medical)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['duty_status'].required = False
        self.fields['duty_return_date'].required = False
        self.fields['duty_leave_reason'].required = False
        self.fields['status_message'].required = False
        self.fields['avatar'].required = False




class PersonalInfoForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'street_address', 'purok', 'civil_status', 'occupation']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'name@example.com'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '0912-345-6789'}),
            'street_address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'House / Unit #, Street Name'}),
            'purok': forms.Select(attrs={'class': 'form-control'}),
            'civil_status': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Occupation / Employment'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['street_address'].required = False
        self.fields['purok'].required = False
        self.fields['civil_status'].required = False
        self.fields['occupation'].required = False

    def save(self, commit=True):
        user = super().save(commit=False)
        if user.street_address and not user.address:
            user.address = user.street_address
        elif user.street_address:
            user.address = user.street_address
        if commit:
            user.save()
        return user


class DutyStatusForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['duty_status', 'status_message', 'duty_return_date', 'duty_leave_reason']
        widgets = {
            'duty_status': forms.Select(attrs={'class': 'form-control'}),
            'status_message': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Available at Barangay Hall until 5:00 PM'}),
            'duty_return_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'duty_leave_reason': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Reason for leave (e.g. Official travel, Medical)'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['duty_status'].required = False
        self.fields['status_message'].required = False
        self.fields['duty_return_date'].required = False
        self.fields['duty_leave_reason'].required = False


# Backward compatibility alias
SettingsForm = PersonalInfoForm

