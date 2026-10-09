"""
Forms for the Blotter pages and the JSON API (the API validates with the same forms).
Business rules (minimum parties, scope, transitions) live in apps.blotter.services.
"""
from django import forms
from django.forms import BaseFormSet, formset_factory

from apps.accounts.models import Resident
from apps.blotter import policies, selectors
from apps.blotter.models import BlotterCase, BlotterHearing, BlotterParty
from apps.core.validators import ph_mobile_widget_attrs

PARTY_PREFIX = 'parties'


class BlotterCaseForm(forms.ModelForm):
    class Meta:
        model = BlotterCase
        fields = [
            'incident_type', 'incident_date', 'incident_time', 'location', 'purok',
            'narrative', 'handled_by', 'is_confidential',
        ]
        widgets = {
            'incident_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'incident_time': forms.TimeInput(attrs={'type': 'time'}, format='%H:%M'),
            'narrative': forms.Textarea(attrs={'rows': 6}),
        }
        labels = {
            'incident_time': 'Incident time (optional)',
            'handled_by': 'Handling officer (optional)',
            'is_confidential': 'Confidential case',
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['purok'].queryset = selectors.puroks_for(user)
        self.fields['handled_by'].queryset = selectors.handler_choices()
        self.fields['handled_by'].label_from_instance = lambda u: u.get_full_name() or u.username
        if not policies.can(user, 'view_confidential'):
            # Only users who can read confidential cases may create or change them.
            del self.fields['is_confidential']
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault('class', 'form-control')


class BlotterPartyForm(forms.ModelForm):
    resident = forms.ModelChoiceField(
        queryset=Resident.objects.filter(is_archived=False), required=False, widget=forms.HiddenInput,
    )

    class Meta:
        model = BlotterParty
        fields = ['role', 'full_name', 'address', 'contact_no', 'resident']
        widgets = {'contact_no': forms.TextInput(attrs=ph_mobile_widget_attrs(autocomplete='off'))}
        labels = {'contact_no': 'Mobile number (optional)'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = [('', 'Select role')] + list(BlotterParty.ROLE_CHOICES)
        for name, field in self.fields.items():
            if not isinstance(field.widget, forms.HiddenInput):
                field.widget.attrs.setdefault('class', 'form-control')

    # A row counts as filled in when it has a name, address, number or resident link;
    # the pre-selected role alone does not make a row "changed".
    CONTENT_FIELDS = ('full_name', 'address', 'contact_no', 'resident')

    def has_changed(self):
        if not self.is_bound:
            return super().has_changed()
        return any(str(self.data.get(self.add_prefix(name)) or '').strip() for name in self.CONTENT_FIELDS)


class BasePartyFormSet(BaseFormSet):
    def _construct_form(self, i, **kwargs):
        form = super()._construct_form(i, **kwargs)
        # Blank rows are skipped; services.create_case demands a complainant and a respondent.
        form.empty_permitted = True
        form.use_required_attribute = False
        return form


PartyFormSet = formset_factory(BlotterPartyForm, formset=BasePartyFormSet, extra=1)

DEFAULT_PARTY_ROWS = [
    {'role': BlotterParty.ROLE_COMPLAINANT},
    {'role': BlotterParty.ROLE_RESPONDENT},
]


def party_formset(data=None):
    return PartyFormSet(data, prefix=PARTY_PREFIX, initial=None if data is not None else DEFAULT_PARTY_ROWS)


def filled_parties(formset):
    """cleaned_data of the rows the user actually filled in."""
    return [f.cleaned_data for f in formset.forms if f.has_changed() and f.cleaned_data]


class TransitionForm(forms.Form):
    to_status = forms.ChoiceField(choices=BlotterCase.STATUS_CHOICES)
    notes = forms.CharField(required=False, max_length=4000, widget=forms.Textarea(attrs={'rows': 3}))


class HearingForm(forms.ModelForm):
    scheduled_at = forms.DateTimeField(
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M', '%Y-%m-%dT%H:%M:%S'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}, format='%Y-%m-%dT%H:%M'),
    )

    class Meta:
        model = BlotterHearing
        fields = ['scheduled_at', 'outcome_notes', 'complainant_attended', 'respondent_attended']
        widgets = {'outcome_notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})}
