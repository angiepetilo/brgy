from django import forms
from apps.blotter.models import BlotterRecord, KPCase


class BlotterRecordForm(forms.ModelForm):
    class Meta:
        model = BlotterRecord
        fields = [
            'case_number', 'complainant_name', 'respondent_name',
            'incident_type', 'incident_location', 'incident_date',
            'narrative', 'status'
        ]
        widgets = {
            'case_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. BLOT-2026-0001'}),
            'complainant_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name of Complainant'}),
            'respondent_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name of Respondent / Accused'}),
            'incident_type': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Physical Assault, Noise Disturbance, Land Dispute'}),
            'incident_location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Exact Location / Purok / Street'}),
            'incident_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'narrative': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Factual narrative statement of the complaint and circumstance...'}),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }


class KPCaseForm(forms.ModelForm):
    class Meta:
        model = KPCase
        fields = ['hearing_date', 'mediator_notes', 'settlement_document', 'certificate_to_file_action']
        widgets = {
            'hearing_date': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'mediator_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Lupon Tagapamayapa arbitration proceedings, agreements, or failure of conciliation...'}),
            'settlement_document': forms.FileInput(attrs={'class': 'form-control', 'accept': 'application/pdf,image/*'}),
            'certificate_to_file_action': forms.CheckboxInput(attrs={'style': 'margin-right: 0.5rem;'}),
        }
