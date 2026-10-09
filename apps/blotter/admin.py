from django.contrib import admin

from apps.blotter.models import BlotterCase, BlotterHearing, BlotterParty


class BlotterPartyInline(admin.TabularInline):
    model = BlotterParty
    extra = 0
    raw_id_fields = ('resident',)


class BlotterHearingInline(admin.TabularInline):
    model = BlotterHearing
    extra = 0
    raw_id_fields = ('recorded_by',)


@admin.register(BlotterCase)
class BlotterCaseAdmin(admin.ModelAdmin):
    list_display = ('case_no', 'incident_type', 'status', 'purok', 'incident_date', 'filed_at', 'is_confidential')
    list_filter = ('status', 'incident_type', 'purok', 'is_confidential')
    search_fields = ('case_no', 'location', 'parties__full_name')
    readonly_fields = ('case_no', 'filed_at', 'settled_at', 'escalated_at', 'closed_at', 'created_at', 'updated_at')
    raw_id_fields = ('handled_by', 'recorded_by')
    inlines = [BlotterPartyInline, BlotterHearingInline]


@admin.register(BlotterParty)
class BlotterPartyAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'role', 'case', 'contact_no')
    list_filter = ('role',)
    search_fields = ('full_name', 'case__case_no')
    raw_id_fields = ('case', 'resident')


@admin.register(BlotterHearing)
class BlotterHearingAdmin(admin.ModelAdmin):
    list_display = ('case', 'scheduled_at', 'complainant_attended', 'respondent_attended')
    raw_id_fields = ('case', 'recorded_by')
