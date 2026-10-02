from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from apps.accounts.models import User, Household, Purok


@admin.register(Purok)
class PurokAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name',)


@admin.register(Household)
class HouseholdAdmin(admin.ModelAdmin):
    list_display = ('household_number', 'head', 'purok', 'street_address', 'created_at')
    list_filter = ('purok',)
    search_fields = ('household_number', 'head__first_name', 'head__last_name', 'head__username', 'street_address')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'purok', 'role', 'is_approved', 'is_senior', 'is_pwd', 'is_4ps')
    list_filter = ('role', 'is_approved', 'purok', 'is_senior', 'is_pwd', 'is_4ps', 'civil_status')
    search_fields = ('username', 'first_name', 'last_name', 'email', 'phone_number', 'household__household_number')
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Barangay Profile & Demographics (RBI)', {
            'fields': (
                'role', 'is_approved', 'phone_number', 'street_address', 'address', 'purok', 'civil_status',
                'occupation', 'date_of_birth', 'household', 'is_senior', 'is_pwd', 'is_4ps',
                'id_proof', 'rejection_reason', 'verified_at', 'verified_by'
            )
        }),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ('Barangay Demographics', {
            'fields': ('role', 'is_approved', 'phone_number', 'street_address', 'purok', 'civil_status', 'id_proof')
        }),
    )
