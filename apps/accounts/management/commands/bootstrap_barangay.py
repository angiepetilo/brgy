import getpass
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from django.utils.text import slugify

from apps.accounts.models import User, BarangayInfo, Purok
from apps.accounts.permissions import seed_default_permissions
from apps.communications.models import PostCategory
from apps.chat.models import ConcernCategory
from apps.appointments.models import DocumentType, Requirement, HealthCareService


class Command(BaseCommand):
    help = "Idempotent bootstrap command to set up default Barangay configuration, categories, documents, and admin."

    def add_arguments(self, parser):
        parser.add_argument(
            '--no-input',
            action='store_true',
            help='Do not prompt for admin creation if no superuser exists.'
        )
        parser.add_argument(
            '--admin-username',
            type=str,
            default='admin',
            help='Default admin username when using --no-input.'
        )
        parser.add_argument(
            '--admin-email',
            type=str,
            default='admin@barangay.ph',
            help='Default admin email when using --no-input.'
        )
        parser.add_argument(
            '--admin-password',
            type=str,
            default='',
            help='Admin password for scripted setup.'
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("=== Bootstrapping Barangay System ==="))

        with transaction.atomic():
            # 1. BarangayInfo Defaults
            info = BarangayInfo.get_solo()
            if not info.name or info.name == 'Barangay Poblacion':
                info.name = getattr(settings, 'BARANGAY_NAME', 'Barangay Poblacion')
            info.venue = getattr(settings, 'BARANGAY_VENUE', 'Barangay Hall Multi-Purpose Center')
            info.contact_no = getattr(settings, 'BARANGAY_CONTACT', '') or info.contact_no
            info.address = 'Barangay Hall, Center Street, Metro Manila'
            info.office_hours = 'Monday - Friday, 8:00 AM - 5:00 PM'
            info.save()
            self.stdout.write(self.style.SUCCESS(f"[1/6] BarangayInfo verified: {info.name}"))

            # 2. Purok Defaults
            default_puroks = ['Purok 1', 'Purok 2', 'Purok 3', 'Purok 4', 'Purok 5', 'Purok 6', 'Purok 7']
            for p_name in default_puroks:
                Purok.objects.get_or_create(name=p_name, defaults={'description': f'Jurisdiction {p_name}'})
            self.stdout.write(self.style.SUCCESS(f"[2/6] Default puroks verified: {len(default_puroks)} puroks."))

            # 3. Default Post Categories (Health and Emergency as system categories)
            post_cats = [
                {'name': 'Health', 'slug': 'health', 'is_system': True, 'expires': True, 'default_end': 'none', 'notify_on_post': False, 'order': 10},
                {'name': 'Emergency Alert', 'slug': 'emergency', 'is_system': True, 'expires': False, 'default_end': 'none', 'notify_on_post': True, 'order': 20},
                {'name': 'Announcement', 'slug': 'announcement', 'is_system': False, 'expires': True, 'default_end': 'none', 'notify_on_post': False, 'order': 30},
                {'name': 'General Advisory', 'slug': 'general', 'is_system': False, 'expires': True, 'default_end': 'none', 'notify_on_post': False, 'order': 40},
                {'name': 'Upcoming Event', 'slug': 'event', 'is_system': False, 'expires': True, 'default_end': 'none', 'notify_on_post': False, 'order': 50},
                {'name': 'Education', 'slug': 'education', 'is_system': False, 'expires': True, 'default_end': 'none', 'notify_on_post': False, 'order': 60},
            ]
            for cat_data in post_cats:
                cat_obj = PostCategory.objects.filter(slug=cat_data['slug']).first() or \
                          PostCategory.objects.filter(name__iexact=cat_data['name']).first()
                if cat_obj:
                    for k, v in cat_data.items():
                        setattr(cat_obj, k, v)
                    cat_obj.save()
                else:
                    PostCategory.objects.create(**cat_data)
            self.stdout.write(self.style.SUCCESS(f"[3/6] Post categories verified (Health & Emergency marked system)."))

            # 4. Concern Categories
            concern_cats = [
                {'name': 'Peace & Order', 'slug': 'peace_order', 'routing_target_type': 'committee', 'routing_target_value': 'Peace and Order'},
                {'name': 'Infrastructure & Public Works', 'slug': 'infrastructure_works', 'routing_target_type': 'committee', 'routing_target_value': 'Infrastructure'},
                {'name': 'Waste Management & Sanitation', 'slug': 'sanitation_waste', 'routing_target_type': 'committee', 'routing_target_value': 'Health'},
                {'name': 'Health Center Inquiries', 'slug': 'health_inquiries', 'routing_target_type': 'service_area', 'routing_target_value': 'Health'},
                {'name': 'Document Requests & Verification', 'slug': 'document_inquiries', 'routing_target_type': 'service_area', 'routing_target_value': 'Documents'},
                {'name': 'General Resident Concern', 'slug': 'general_concern', 'routing_target_type': 'service_area', 'routing_target_value': 'Administration'},
            ]
            for c_data in concern_cats:
                c_obj = ConcernCategory.objects.filter(slug=c_data['slug']).first() or \
                        ConcernCategory.objects.filter(name__iexact=c_data['name']).first()
                if c_obj:
                    for k, v in c_data.items():
                        setattr(c_obj, k, v)
                    c_obj.save()
                else:
                    ConcernCategory.objects.create(**c_data)
            self.stdout.write(self.style.SUCCESS(f"[4/6] Concern categories verified."))

            # 5. Three Document Types with sample requirements
            doc_types = [
                {
                    'name': 'Barangay Clearance and Business Permits',
                    'code': 'clearance_permit',
                    'description': 'Official clearance for employment, residency verification, and local business operations.',
                    'fee': Decimal('50.00'),
                    'order': 1,
                    'requirements': [
                        'Valid Government-issued ID',
                        'Community Tax Certificate (Cedula)',
                        'Proof of Billing or Purok Endorsement',
                    ]
                },
                {
                    'name': 'Certificate of Indigency / Residency',
                    'code': 'indigency_residency',
                    'description': 'Certification for financial assistance, scholarship, medical aid, or residency verification.',
                    'fee': Decimal('0.00'),
                    'order': 2,
                    'requirements': [
                        'Valid ID or School/Voter ID',
                        'Endorsement from Purok Leader / Certification of Low Income',
                    ]
                },
                {
                    'name': 'Barangay ID Issuance',
                    'code': 'barangay_id',
                    'description': 'Official Barangay Resident Identification Card.',
                    'fee': Decimal('100.00'),
                    'order': 3,
                    'requirements': [
                        '1x1 or 2x2 Recent ID Photo',
                        'Proof of Billing / Residential Address Document',
                        'Valid Primary or Secondary Government ID',
                    ]
                },
            ]
            for doc_info in doc_types:
                reqs = doc_info.pop('requirements')
                doc_obj = DocumentType.objects.filter(code=doc_info['code']).first() or \
                          DocumentType.objects.filter(name__iexact=doc_info['name']).first()
                if doc_obj:
                    for k, v in doc_info.items():
                        setattr(doc_obj, k, v)
                    doc_obj.save()
                else:
                    doc_obj = DocumentType.objects.create(**doc_info)

                for idx, r_name in enumerate(reqs, start=1):
                    Requirement.objects.get_or_create(
                        document_type=doc_obj,
                        name=r_name,
                        defaults={'order': idx}
                    )
            self.stdout.write(self.style.SUCCESS(f"[5/6] 3 Document types & sample requirements configured."))

            # 6. Default Officer Positions and Permission Rules
            seed_default_permissions()
            self.stdout.write(self.style.SUCCESS(f"[6/6] Officer positions and baseline permission rules seeded."))

        # 7. First Admin Account
        admin_exists = User.objects.filter(role=User.ROLE_ADMIN, is_superuser=True).exists()
        if admin_exists:
            existing = User.objects.filter(role=User.ROLE_ADMIN, is_superuser=True).first()
            self.stdout.write(self.style.SUCCESS(f"-> Admin superuser already exists: {existing.username} ({existing.email})"))
        else:
            no_input = options.get('no_input')
            admin_pwd = options.get('admin_password')
            if no_input or admin_pwd:
                username = options.get('admin_username') or 'admin'
                email = options.get('admin_email') or 'admin@barangay.ph'
                password = admin_pwd or 'AdminPass12345!'
                user = User.objects.create_superuser(
                    username=username,
                    email=email,
                    password=password,
                    role=User.ROLE_ADMIN,
                    status=User.STATUS_ACTIVE,
                    must_change_password=False
                )
                self.stdout.write(self.style.SUCCESS(f"-> Created first admin user: {username} ({email})"))
            else:
                self.stdout.write(self.style.WARNING("No administrator account found. Create the first admin user now:"))
                username = input("Admin username: ").strip() or "admin"
                email = input("Admin email address: ").strip() or "admin@barangay.ph"
                password = getpass.getpass("Admin password: ")
                confirm = getpass.getpass("Confirm password: ")
                if password and password == confirm:
                    User.objects.create_superuser(
                        username=username,
                        email=email,
                        password=password,
                        role=User.ROLE_ADMIN,
                        status=User.STATUS_ACTIVE,
                        must_change_password=False
                    )
                    self.stdout.write(self.style.SUCCESS(f"-> Created first admin user: {username} ({email})"))
                else:
                    self.stdout.write(self.style.ERROR("Passwords did not match or were empty. Admin account skipped."))

        self.stdout.write(self.style.SUCCESS("=== Bootstrap Completed Successfully ==="))
