from django import forms
from apps.finance.models import AssetInventory


class AssetInventoryForm(forms.ModelForm):
    class Meta:
        model = AssetInventory
        # 1NF fix: replaced composite 'remarks' with atomic fields:
        # location, custodian (FK), and maintenance_notes.
        fields = [
            'item_name', 'category', 'quantity', 'condition',
            'date_acquired', 'serial_number',
            'location', 'custodian', 'maintenance_notes'
        ]
        widgets = {
            'item_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Barangay Patrol Vehicle (Toyota Hilux)'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'date_acquired': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tag / Plate / Serial number'}),
            'location': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Barangay Hall Storage Room, Fire Station'}),
            'custodian': forms.Select(attrs={'class': 'form-control'}),
            'maintenance_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Maintenance history, repair logs, or general remarks...'}),
        }
