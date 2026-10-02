from django import forms
from apps.communications.models import KapitanStatus, Announcement


class KapitanStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = KapitanStatus
        fields = ['status', 'leave_reason', 'return_date']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control', 'id': 'status-selector'}),
            'leave_reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'State reason for leave (e.g. Official City Council meeting, Medical leave, Official travel)'
            }),
            'return_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        leave_reason = cleaned_data.get('leave_reason')
        return_date = cleaned_data.get('return_date')

        if status == KapitanStatus.STATUS_ON_LEAVE:
            if not leave_reason or not leave_reason.strip():
                self.add_error('leave_reason', 'Leave reason is required when setting status to On Leave.')
            if not return_date:
                self.add_error('return_date', 'Expected return date is required when setting status to On Leave.')

        return cleaned_data


class AnnouncementForm(forms.ModelForm):
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Post Title / Headline (optional)'})
    )
    category = forms.CharField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )

    class Meta:
        model = Announcement
        fields = ['title', 'category', 'content', 'image', 'is_pinned']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Write announcement or update details (supports **bold**, lists, etc.)...',
                'required': 'required'
            }),
            'is_pinned': forms.CheckboxInput(attrs={'style': 'margin-right: 0.5rem;'}),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            content = self.cleaned_data.get('content', '').strip()
            first_line = content.split('\n')[0].strip() if content else 'Barangay Update'
            title = first_line[:60] if len(first_line) <= 60 else first_line[:57] + '...'
        return title

    def clean_category(self):
        cat = self.cleaned_data.get('category', '').strip()
        if not cat:
            return Announcement.CATEGORY_ANNOUNCEMENT
        
        normalized = cat.lower().replace(' ', '_')
        valid_choices = [c[0] for c in Announcement.CATEGORY_CHOICES]
        if normalized in valid_choices:
            return normalized
        if 'emergency' in normalized or 'alert' in normalized:
            return Announcement.CATEGORY_EMERGENCY
        if 'event' in normalized:
            return Announcement.CATEGORY_EVENT
        if 'scholarship' in normalized:
            return Announcement.CATEGORY_SCHOLARSHIP
        if 'donation' in normalized:
            return Announcement.CATEGORY_DONATION
        if 'legislative' in normalized or 'ordinance' in normalized:
            return Announcement.CATEGORY_LEGISLATIVE
        if 'health' in normalized:
            return Announcement.CATEGORY_HEALTH
        
        return Announcement.CATEGORY_ANNOUNCEMENT




class LegislativeRecordForm(forms.ModelForm):
    class Meta:
        from apps.communications.models import LegislativeRecord
        model = LegislativeRecord
        fields = ['title', 'category', 'document_number', 'date_approved', 'pdf_file', 'summary', 'is_public']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Title of Measure'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'document_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Barangay Ordinance No. 2026-05'}),
            'date_approved': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'pdf_file': forms.FileInput(attrs={'class': 'form-control', 'accept': 'application/pdf'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Summary of policy, penalties, or appropriations enacted...'}),
            'is_public': forms.CheckboxInput(attrs={'style': 'margin-right: 0.5rem;'}),
        }

