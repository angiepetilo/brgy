import os
import django
from datetime import timedelta, date

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.utils import timezone
from apps.accounts.models import User, Household
from apps.appointments.models import Appointment, IssuedDocumentLog
from apps.communications.models import KapitanStatus, Announcement, LegislativeRecord
from apps.chat.models import Message, Notification
from apps.blotter.models import BlotterRecord, KPCase
from apps.finance.models import AssetInventory


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
            'purok': 'Purok 1',
            'civil_status': 'Married',
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
            'purok': 'Purok 1',
            'civil_status': 'Married',
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
            'purok': 'Purok 2',
            'civil_status': 'Single',
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
            'purok': 'Purok 4',
            'civil_status': 'Married',
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
            'purok': 'Purok 1',
            'civil_status': 'Widowed',
            'occupation': 'Retired Carpenter',
            'date_of_birth': date(1955, 3, 10),
            'is_senior': True,
            'is_pwd': True,
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
            'purok': 'Purok 3',
            'civil_status': 'Married',
            'occupation': 'Sari-Sari Store Owner',
            'date_of_birth': date(1982, 8, 20),
            'is_4ps': True,
            'verified_at': timezone.now(),
            'verified_by': admin_user,
        }
    )
    if created:
        elena_user.set_password('resident123')
        elena_user.save()
        print("Created 4Ps Resident: elena / resident123")

    # 7. Households (RBI)
    hh1, _ = Household.objects.get_or_create(
        household_number='HH-2026-001',
        defaults={
            'head': maria_user,
            'address': 'Block 12 Lot 4, Sunflower St.',
            'purok': 'Purok 2',
        }
    )
    hh2, _ = Household.objects.get_or_create(
        household_number='HH-2026-002',
        defaults={
            'head': juan_user,
            'address': 'Unit 3B, Jasmine Condominiums',
            'purok': 'Purok 4',
        }
    )
    hh3, _ = Household.objects.get_or_create(
        household_number='HH-2026-003',
        defaults={
            'head': pedro_user,
            'address': '104 Acacia Ave',
            'purok': 'Purok 1',
        }
    )
    # Link household FK
    if not maria_user.household:
        maria_user.household = hh1
        maria_user.save()
    if not juan_user.household:
        juan_user.household = hh2
        juan_user.save()
    if not pedro_user.household:
        pedro_user.household = hh3
        pedro_user.save()
    print("Created sample Households.")

    # 8. Kapitan Status
    if not KapitanStatus.objects.exists():
        KapitanStatus.objects.create(
            status=KapitanStatus.STATUS_ON_DUTY,
            updated_by=kapitan_user,
        )
        print("Created initial Kapitan Status: On Duty")

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
    apt_completed, created_apt = Appointment.objects.get_or_create(
        resident=maria_user,
        document_type=Appointment.DOC_CLEARANCE,
        defaults={
            'purpose': 'Local Employment Requirement (Call Center Support Specialist)',
            'preferred_date': timezone.now().date() - timedelta(days=1),
            'preferred_time_slot': Appointment.TIME_SLOT_MORNING,
            'status': Appointment.STATUS_COMPLETED,
            'admin_notes': 'Clearance verified, signed and released.',
            'processed_by': admin_user,
        }
    )
    if created_apt or not hasattr(apt_completed, 'issued_log'):
        apt_completed.status = Appointment.STATUS_COMPLETED
        apt_completed.save()  # Triggers signal for IssuedDocumentLog & QR code generation!
        print("Created Completed Clearance with automated QR code log.")

    # 11. Peace & Order / Blotter Cases & KP Mediation
    if not BlotterRecord.objects.exists():
        b1 = BlotterRecord.objects.create(
            case_number='BLOT-2026-0001',
            complainant_name='Ricardo Dalisay',
            respondent_name='Joaquin Tuazon',
            incident_type='Excessive Noise & Public Disturbance',
            incident_location='Corner Daisy St., Purok 2',
            incident_date=timezone.now() - timedelta(days=2),
            narrative='Complainant reported respondent playing loud videoke sound system past 1:00 AM despite multiple neighbor requests to lower volume.',
            status=BlotterRecord.STATUS_OPEN,
            created_by=admin_user,
        )
        KPCase.objects.create(
            blotter=b1,
            hearing_date=timezone.now() + timedelta(days=3),
            mediator_notes='First conciliation hearing set before the Punong Barangay.',
            certificate_to_file_action=False,
        )

        b2 = BlotterRecord.objects.create(
            case_number='BLOT-2026-0002',
            complainant_name='Tomas Alcantara',
            respondent_name='Felipe Morales',
            incident_type='Boundary Fence Encroachment',
            incident_location='Lot 5 Block 3, Purok 1',
            incident_date=timezone.now() - timedelta(days=14),
            narrative='Dispute regarding 0.8 meter overhang fence constructed along common pathway boundary.',
            status=BlotterRecord.STATUS_SETTLED,
            created_by=admin_user,
        )
        KPCase.objects.create(
            blotter=b2,
            hearing_date=timezone.now() - timedelta(days=7),
            mediator_notes='Both parties entered into an Amicable Settlement (Kasunduan). Respondent agreed to adjust fence boundary within 30 days.',
            certificate_to_file_action=False,
        )

        b3 = BlotterRecord.objects.create(
            case_number='BLOT-2026-0003',
            complainant_name='Gloria Diaz',
            respondent_name='Mark Anthony',
            incident_type='Unjust Vexation & Property Damage',
            incident_location='Purok 4 Commercial Center',
            incident_date=timezone.now() - timedelta(days=21),
            narrative='Repeated verbal threats and deliberate damage to retail storefront gate.',
            status=BlotterRecord.STATUS_REFERRED,
            created_by=admin_user,
        )
        KPCase.objects.create(
            blotter=b3,
            hearing_date=timezone.now() - timedelta(days=10),
            mediator_notes='Three conciliation notices served. Respondent failed to appear without justifiable cause. Conciliation terminated.',
            certificate_to_file_action=True,
        )
        print("Created sample Blotter and KP Mediation records.")

    # 12. Legislative Records (Transparency Portal)
    if not LegislativeRecord.objects.exists():
        LegislativeRecord.objects.create(
            title="Comprehensive Anti-Littering and Solid Waste Segregation Ordinance of 2026",
            category=LegislativeRecord.CATEGORY_ORDINANCE,
            document_number="Barangay Ordinance No. 2026-01",
            date_approved=date(2026, 1, 15),
            summary="Mandating household source segregation of biodegradable and recyclable wastes, imposing penalties for improper garbage disposal on waterways and public streets.",
            is_public=True,
        )

        LegislativeRecord.objects.create(
            title="Resolution Authorizing the Procurement of Rescue Tools and Disaster Preparedness Equipment",
            category=LegislativeRecord.CATEGORY_RESOLUTION,
            document_number="Barangay Resolution No. 2026-14",
            date_approved=date(2026, 2, 28),
            summary="Authorizing the allocation of 5% Barangay Disaster Risk Reduction and Management Fund (BDRRMF) for the purchase of chainsaws, life vests, and mobile emergency generators.",
            is_public=True,
        )

        LegislativeRecord.objects.create(
            title="Executive Order Reconstituting the Barangay Peace and Order Council (BPOC)",
            category=LegislativeRecord.CATEGORY_EXECUTIVE_ORDER,
            document_number="Executive Order No. 2026-02",
            date_approved=date(2026, 3, 5),
            summary="Reorganizing the composition, roles, and operational directives of the Barangay Peace and Order Council in partnership with the PNP local precinct.",
            is_public=True,
        )
        print("Created sample Legislative records for Transparency Portal.")

    # 13. Asset & Property Inventory
    if not AssetInventory.objects.exists():
        AssetInventory.objects.create(
            item_name="Barangay Patrol Rescue Vehicle (Toyota Hilux 4x4)",
            category=AssetInventory.CATEGORY_VEHICLE,
            quantity=1,
            condition=AssetInventory.CONDITION_GOOD,
            date_acquired=date(2024, 3, 15),
            serial_number="SAB-4182 / Property #2024-001",
            remarks="Assigned to Barangay Tanod Quick Response Unit.",
        )
        AssetInventory.objects.create(
            item_name="Portable Heavy-Duty Honda Inverter Generator (7.5 kW)",
            category=AssetInventory.CATEGORY_EQUIPMENT,
            quantity=2,
            condition=AssetInventory.CONDITION_GOOD,
            date_acquired=date(2024, 6, 10),
            serial_number="GEN-HND-9921",
            remarks="Stored in Emergency Operations Center.",
        )
        AssetInventory.objects.create(
            item_name="Stihl MS 382 Heavy Duty Rescue Chainsaw",
            category=AssetInventory.CATEGORY_EMERGENCY,
            quantity=3,
            condition=AssetInventory.CONDITION_MAINTENANCE,
            date_acquired=date(2023, 11, 20),
            serial_number="CS-STL-402",
            remarks="Under scheduled blade replacement and carb cleaning.",
        )
        AssetInventory.objects.create(
            item_name="Foldable Disaster Relief Aluminum Tents (10x10)",
            category=AssetInventory.CATEGORY_EMERGENCY,
            quantity=15,
            condition=AssetInventory.CONDITION_GOOD,
            date_acquired=date(2024, 1, 12),
            serial_number="TNT-EVAC-01-15",
            remarks="Available at Multi-Purpose Covered Court storage.",
        )
        AssetInventory.objects.create(
            item_name="Conference Hall Stackable Heavy Duty Chairs",
            category=AssetInventory.CATEGORY_FURNITURE,
            quantity=80,
            condition=AssetInventory.CONDITION_GOOD,
            date_acquired=date(2023, 8, 5),
            remarks="Barangay Session Hall assembly.",
        )
        print("Created sample Asset Inventory records.")

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
