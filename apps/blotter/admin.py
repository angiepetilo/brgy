from django.contrib import admin
from apps.blotter.models import BlotterRecord, KPCase


class KPCaseInline(admin.StackedInline):
    model = KPCase
    extra = 0


@admin.register(BlotterRecord)
class BlotterRecordAdmin(admin.ModelAdmin):
    list_display = ('case_number', 'complainant_name', 'respondent_name', 'incident_type', 'incident_date', 'status', 'created_at')
    list_filter = ('status', 'incident_date')
    search_fields = ('case_number', 'complainant_name', 'respondent_name', 'incident_location', 'narrative')
    inlines = [KPCaseInline]


@admin.register(KPCase)
class KPCaseAdmin(admin.ModelAdmin):
    list_display = ('blotter', 'hearing_date', 'certificate_to_file_action', 'created_at')
    list_filter = ('certificate_to_file_action', 'hearing_date')
    search_fields = ('blotter__case_number', 'blotter__complainant_name', 'mediator_notes')
