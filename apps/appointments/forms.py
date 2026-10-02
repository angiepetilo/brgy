from django import forms
from django.utils import timezone
from apps.appointments.models import Appointment, HealthCareService


class HealthCareServiceForm(forms.ModelForm):
    class Meta:
        model = HealthCareService
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Service name (e.g. Dental Cleaning)'}),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Detailed description of the service offered by the Barangay Health Center...'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AppointmentCreateForm(forms.ModelForm):
    class Meta:
        model = Appointment
        # 3NF: first_name/middle_name/last_name removed — applicant name is
        # derived from the resident FK (accounts.User), not stored redundantly.
        fields = [
            'category',
            'document_type', 'healthcare_service', 'purpose',
            'preferred_date', 'preferred_time_slot', 'supporting_id'
        ]
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control', 'id': 'appointment-category-select'}),
            'document_type': forms.Select(attrs={'class': 'form-control', 'id': 'document-type-select'}),
            'healthcare_service': forms.Select(attrs={'class': 'form-control', 'id': 'healthcare-service-select'}),
            'purpose': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'State purpose of request or symptoms/consultation notes...'
            }),
            'preferred_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'id': 'appointment-date-input',
            }),
            'preferred_time_slot': forms.Select(attrs={'class': 'form-control'}),
            'supporting_id': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*,application/pdf'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False
        self.fields['category'].initial = Appointment.CATEGORY_DOCUMENT
        self.fields['healthcare_service'].queryset = HealthCareService.objects.filter(is_active=True)
        self.fields['document_type'].required = False
        self.fields['healthcare_service'].required = False

    def clean_preferred_date(self):
        date = self.cleaned_data.get('preferred_date')
        if date and date < timezone.now().date():
            raise forms.ValidationError("Appointment date cannot be in the past.")
        return date

    def clean_category(self):
        cat = self.cleaned_data.get('category')
        if not cat:
            return Appointment.CATEGORY_DOCUMENT
        return cat

    def clean(self):
        cleaned_data = super().clean()
        cat = cleaned_data.get('category') or Appointment.CATEGORY_DOCUMENT
        cleaned_data['category'] = cat
        if cat == Appointment.CATEGORY_HEALTHCARE:
            if not cleaned_data.get('healthcare_service'):
                self.add_error('healthcare_service', 'Please select a health care service.')
        else:
            if not cleaned_data.get('document_type'):
                self.add_error('document_type', 'Please select a document type.')
        return cleaned_data


class AppointmentStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['status', 'admin_notes']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'admin_notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide instructions for resident (e.g. Bring 2 valid IDs and 2x2 photo, pickup window 2-4 PM) or rejection reason.'
            }),
        }
