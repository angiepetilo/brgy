from django import forms
from apps.communications.models import Announcement


class AnnouncementForm(forms.ModelForm):
    title = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Post Title / Headline (optional)'})
    )
    category = forms.CharField(
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    audience_type = forms.ChoiceField(
        choices=Announcement.AUDIENCE_CHOICES,
        required=False,
        initial=Announcement.AUDIENCE_EVERYONE,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    purok = forms.ModelChoiceField(
        queryset=None,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    valid_until = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'})
    )
    image = forms.ImageField(
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )

    class Meta:
        model = Announcement
        fields = ['title', 'category', 'audience_type', 'purok', 'valid_until', 'content', 'image', 'is_pinned']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Write announcement or update details (supports **bold**, lists, etc.)...',
                'required': 'required'
            }),
            'is_pinned': forms.CheckboxInput(attrs={'style': 'margin-right: 0.5rem;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import Purok
        self.fields['purok'].queryset = Purok.objects.all()

    def clean_image(self):
        img = self.cleaned_data.get('image')
        if img:
            from apps.communications.services import validate_post_image
            try:
                validate_post_image(img)
            except ValueError as e:
                raise forms.ValidationError(str(e))
        return img

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
