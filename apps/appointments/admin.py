from django.contrib import admin
from apps.appointments.models import Appointment, IssuedDocumentLog, HealthCareService


@admin.register(HealthCareService)
class HealthCareServiceAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'description')


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'resident', 'document_type', 'appt_date', 'time_window', 'status', 'created_at')
    list_filter = ('status', 'document_type', 'time_window')
    search_fields = ('resident__username', 'resident__first_name', 'resident__last_name', 'purpose')
    readonly_fields = ('status', 'processed_by', 'processed_at', 'rejection_reason', 'created_at', 'updated_at')


@admin.register(IssuedDocumentLog)
class IssuedDocumentLogAdmin(admin.ModelAdmin):
    list_display = ('control_number', 'appointment', 'issued_to', 'issued_by', 'issued_at')
    search_fields = ('control_number', 'issued_to__username', 'issued_to__first_name', 'issued_to__last_name')
    list_filter = ('issued_at', 'appointment__document_type')
    readonly_fields = ('issued_at',)
