import os
import django
from datetime import timedelta, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from apps.accounts.models import User, Household, Purok, Resident
from apps.appointments.models import Appointment, DocumentType, IssuedDocumentLog
from apps.communications.models import Announcement
from apps.chat.models import Message, Notification


def purok_for(name):
    purok, _ = Purok.objects.get_or_create(name=name)
    return purok


def seed():
    print("Seeding initial Barangay system data & extended official records...")

    # 1. Admin User
    admin_user, created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@barangay.gov.ph',
            'first_name': 'Rodrigo',
            'last_name': 'Admin',
            'role': User.ROLE_ADMIN,
            'is_approved': True,
            'is_staff': True,
            'is_superuser': True,
            'phone_number': '0917-111-2222',
            'address': 'Barangay Hall, Main District',
            'purok': purok_for('Purok 1'),
            'occupation': 'Barangay Secretary',
        }
    )
    if created:
        admin_user.set_password('admin123')
        admin_user.save()
        print("Created Admin user: admin / admin123")
    else:
        print("Admin user already exists.")

    # 2. Kapitan User
    kapitan_user, created = User.objects.get_or_create(
        username='kapitan',
        defaults={
            'email': 'kapitan@barangay.gov.ph',
            'first_name': 'Hon. Ernesto',
            'last_name': 'Valenzuela',
            'role': User.ROLE_KAPITAN,
            'is_approved': True,
            'phone_number': '0917-555-8888',
            'address': 'Barangay Executive Quarters, Zone 1',
            'purok': purok_for('Purok 1'),
            'occupation': 'Punong Barangay / Public Servant',
        }
    )
    if created:
        kapitan_user.set_password('kapitan123')
        kapitan_user.save()
        print("Created Kapitan user: kapitan / kapitan123")
    else:
        print("Kapitan user already exists.")

    # 3. Approved Resident (Maria Santos)
    maria_user, created = User.objects.get_or_create(
        username='maria',
        defaults={
            'email': 'maria.santos@gmail.com',
            'first_name': 'Maria',
            'last_name': 'Santos',
            'role': User.ROLE_RESIDENT,
            'is_approved': True,
            'phone_number': '0928-444-5555',
            'address': 'Block 12 Lot 4, Sunflower St., Purok Maharlika',
            'purok': purok_for('Purok 2'),
            'occupation': 'Customer Support Associate',
            'date_of_birth': date(1996, 5, 14),
            'verified_at': timezone.now(),
            'verified_by': admin_user,
        }
    )
    if created:
        maria_user.set_password('resident123')
        maria_user.save()
        print("Created Approved Resident: maria / resident123")
    else:
        print("Maria user already exists.")

    # 4. Pending Resident (Juan Dela Cruz)
    juan_user, created = User.objects.get_or_create(
        username='juan',
        defaults={
            'email': 'juan.delacruz@gmail.com',
            'first_name': 'Juan',
            'last_name': 'Dela Cruz',
            'role': User.ROLE_RESIDENT,
            'is_approved': False,
            'phone_number': '0919-777-6666',
            'address': 'Unit 3B, Jasmine Condominiums, Purok Pag-asa',
            'purok': purok_for('Purok 4'),
            'occupation': 'Electrician',
            'date_of_birth': date(1988, 11, 23),
        }
    )
    if created:
        juan_user.set_password('resident123')
        juan_user.save()
        print("Created Pending Resident: juan / resident123")
    else:
        print("Juan user already exists.")

    # 5. Senior Citizen Resident (Pedro Penduko)
    pedro_user, created = User.objects.get_or_create(
        username='pedro',
        defaults={
            'email': 'pedro.penduko@gmail.com',
            'first_name': 'Pedro',
            'last_name': 'Penduko',
            'role': User.ROLE_RESIDENT,
            'is_approved': True,
            'phone_number': '0920-111-3333',
            'address': '104 Acacia Ave, Purok 1',
            'purok': purok_for('Purok 1'),
            'occupation': 'Retired Carpenter',
            'date_of_birth': date(1955, 3, 10),
            'verified_at': timezone.now(),
            'verified_by': admin_user,
        }
    )
    if created:
        pedro_user.set_password('resident123')
        pedro_user.save()
        print("Created Senior Resident: pedro / resident123")

    # 6. 4Ps Program Beneficiary Resident (Elena Reyes)
    elena_user, created = User.objects.get_or_create(
        username='elena',
        defaults={
            'email': 'elena.reyes@gmail.com',
            'first_name': 'Elena',
            'last_name': 'Reyes',
            'role': User.ROLE_RESIDENT,
            'is_approved': True,
            'phone_number': '0930-888-9999',
            'address': 'Lot 8 Riverside Purok 3',
            'purok': purok_for('Purok 3'),
            'occupation': 'Sari-Sari Store Owner',
            'date_of_birth': date(1982, 8, 20),
            'verified_at': timezone.now(),
            'verified_by': admin_user,
        }
    )
    if created:
        elena_user.set_password('resident123')
        elena_user.save()
        print("Created 4Ps Resident: elena / resident123")

    # 6b. Resident profiles: Resident is the single source of demographics.
    # Seniors are derived from birthdate (Pedro, b. 1955), so nothing is stored for them.
    demographics = [
        (maria_user, {'gender': 'female', 'civil_status': 'single', 'is_solo_parent': True}),
        (juan_user, {'gender': 'male', 'civil_status': 'married'}),
        (pedro_user, {'gender': 'male', 'civil_status': 'widowed', 'is_pwd': True}),
        (elena_user, {'gender': 'female', 'civil_status': 'married', 'is_4ps': True}),
    ]
    for user, values in demographics:
        if not user.date_of_birth:
            continue
        Resident.objects.update_or_create(
            user=user,
            defaults={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'birthdate': user.date_of_birth,
                'contact_no': user.phone_number,
                'address': user.address,
                'purok': user.purok,
                **values,
            },
        )
    print("Created sample Resident profiles with demographics.")
    # 7. Households (RBI)
    hh1, _ = Household.objects.get_or_create(
        household_name='Santos Family Residence',
        defaults={
            'address': 'Block 12 Lot 4, Sunflower St.',
        }
    )
    hh2, _ = Household.objects.get_or_create(
        household_name='Dela Cruz Family Residence',
        defaults={
            'address': 'Unit 3B, Jasmine Condominiums',
        }
    )
    hh3, _ = Household.objects.get_or_create(
        household_name='Penduko Family Residence',
        defaults={
            'address': '104 Acacia Ave',
        }
    )
    print("Created sample Households.")

    # 9. Announcements
    if not Announcement.objects.exists():
        Announcement.objects.create(
            title="Free Barangay Medical & Dental Mission This Saturday",
            category=Announcement.CATEGORY_HEALTH,
            content=(
                "### Free Public Health Services\n\n"
                "The Barangay Council in partnership with the City Health Office will be conducting a comprehensive medical mission.\n\n"
                "**Services Offered:**\n"
                "- General Medical Consultation\n"
                "- Free Tooth Extraction and Cleaning\n"
                "- Blood Pressure & Blood Sugar Screening\n"
                "- Free Maintenance Medicines for Senior Citizens\n\n"
                "**Date & Venue:**\n"
                "Saturday, 8:00 AM to 3:00 PM at the Barangay Multi-Purpose Covered Court.\n\n"
                "*Please bring your Barangay ID or valid government ID for registration.*"
            ),
            is_pinned=True,
            author=admin_user,
        )

        Announcement.objects.create(
            title="Barangay Clean-Up Drive & Dengue Prevention Advisory",
            category=Announcement.CATEGORY_GENERAL,
            content=(
                "In line with our ongoing anti-dengue 4S campaign, all residents are invited to participate in the community clean-up drive.\n\n"
                "1. **Search and Destroy** mosquito breeding sites.\n"
                "2. **Self-protection** measures.\n"
                "3. **Seek early consultation** for fevers persisting over 2 days.\n"
                "4. **Say yes to fogging** during impending outbreaks.\n\n"
                "Barangay Tanods will be assisting every Purok starting 6:00 AM."
            ),
            is_pinned=False,
            author=kapitan_user,
        )
        print("Created sample Announcements.")

    # 10. Document Appointments & Completed Clearance with QR
    clearance_type, _ = DocumentType.objects.get_or_create(
        code='clearance',
        defaults={'name': 'Barangay Clearance', 'fee': 0, 'is_active': True},
    )
    apt_completed, created_apt = Appointment.objects.get_or_create(
        resident=maria_user,
        document_type=clearance_type,
        defaults={
            'purpose': 'Local Employment Requirement (Call Center Support Specialist)',
            'appt_date': timezone.localdate() - timedelta(days=1),
            'time_window': Appointment.TIME_SLOT_MORNING,
            'fee_at_booking': clearance_type.fee,
            'status': Appointment.STATUS_COMPLETED,
            'admin_notes': 'Clearance verified, signed and released.',
            'processed_by': admin_user,
        }
    )
    if created_apt or not hasattr(apt_completed, 'issued_log'):
        apt_completed.status = Appointment.STATUS_COMPLETED
        apt_completed.save()  # Triggers signal for IssuedDocumentLog & QR code generation!
        print("Created Completed Clearance with automated QR code log.")

    print("\n--- SEED COMPLETE ---")
    print("Test Accounts Available:")
    print("1. Admin:     admin   / admin123")
    print("2. Kapitan:   kapitan / kapitan123")
    print("3. Approved:  maria   / resident123 (Head of HH-2026-001, Purok 2)")
    print("4. Pending:   juan    / resident123 (Purok 4)")
    print("5. Senior:    pedro   / resident123 (Senior Citizen & PWD, Purok 1)")
    print("6. 4Ps:       elena   / resident123 (4Ps Beneficiary, Purok 3)")


if __name__ == '__main__':
    seed()
