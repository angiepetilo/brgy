from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.accounts.models import User, Purok, Resident, Household
from apps.accounts.services import anonymize_resident_service


@admin.register(Purok)
class PurokAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.action(description="Archive & Anonymize selected residents (Data Privacy Act Request)")
def archive_and_anonymize_resident_action(modeladmin, request, queryset):
    count = 0
    for resident in queryset:
        anonymize_resident_service(resident, request.user)
        count += 1
    messages.success(
        request,
        f"Successfully archived and anonymized {count} resident record(s) with audit logging."
    )


@admin.register(Resident)
class ResidentAdmin(admin.ModelAdmin):
    list_display = ('id', 'first_name', 'last_name', 'purok', 'gender', 'civil_status', 'needs_attention', 'consent_recorded', 'is_archived', 'created_at')
    list_filter = ('is_archived', 'gender', 'civil_status', 'is_pwd', 'is_solo_parent', 'is_4ps', 'needs_attention', 'consent_recorded', 'purok')
    search_fields = ('first_name', 'last_name', 'contact_no', 'address')
    actions = [archive_and_anonymize_resident_action]
    readonly_fields = ('created_at', 'updated_at', 'needs_recorded_at', 'needs_recorded_by')


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('id', 'household_name', 'head', 'purok', 'created_at')
    search_fields = ('household_name', 'address')
    list_filter = ('purok',)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'purok', 'role', 'status', 'is_approved')
    list_filter = ('role', 'status', 'is_approved', 'purok')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Barangay Profile & Demographics', {
            'fields': (
                'role', 'status', 'is_approved', 'phone_number', 'street_address', 'address', 'purok',
                'occupation', 'date_of_birth',
                'id_proof', 'rejection_reason', 'verified_at', 'verified_by'
            )
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Barangay Demographics', {
            'fields': ('role', 'status', 'is_approved', 'phone_number', 'street_address', 'purok', 'id_proof')
        }),
    )
