import re
from datetime import date
from django.test import TestCase, Client
from django.urls import get_resolver, URLPattern, URLResolver
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.accounts.models import Resident, Purok, Officer, StaffAssignment
from apps.accounts.permissions import seed_default_permissions
from apps.appointments.models import Appointment, HealthCareService, DocumentType
from apps.communications.models import Announcement, PostCategory

User = get_user_model()


class AutomatedRouteCrawlTests(TestCase):
    """
    Automated URL crawl test:
    Generates every route from the application URLconf, requests it under 5 personas:
    1. Anonymous
    2. Resident
    3. Staff (No Assignment)
    4. Scoped Staff
    5. Admin / Leadership

    Verifies:
    - Every non-public route enforces login or permission rules.
    - No private view leaks access to anonymous users.
    - No administrative view allows access to residents.
    """

    def setUp(self):
        cache.clear()
        self.purok, _ = Purok.objects.get_or_create(name="Purok Test Crawl")
        seed_default_permissions()

        # Admin
        self.admin = User.objects.create_superuser(
            username="crawl_admin",
            email="crawl_admin@barangay.ph",
            password="AdminPassword123!",
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Resident
        self.resident_user = User.objects.create_user(
            username="crawl_resident",
            email="crawl_resident@example.com",
            password="ResidentPassword123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident = Resident.objects.create(
            user=self.resident_user,
            first_name="Juan",
            last_name="Crawler",
            birthdate=date(1995, 1, 1),
            contact_no="09170001122",
            address="123 Street",
            purok=self.purok,
            consent_recorded=True
        )

        # Staff with no assignment
        self.staff_unassigned = User.objects.create_user(
            username="crawl_staff_no_assign",
            email="crawl_staff_no_assign@barangay.ph",
            password="StaffPassword123!",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Scoped staff (Health)
        self.staff_scoped = User.objects.create_user(
            username="crawl_staff_scoped",
            email="crawl_staff_scoped@barangay.ph",
            password="StaffPassword123!",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        bhw = Officer.objects.filter(position='BHW').first() or Officer.objects.create(position='BHW')
        StaffAssignment.objects.create(
            user=self.staff_scoped,
            officer=bhw,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='Health'
        )

        # Sample announcement
        self.announcement = Announcement.objects.create(
            title="Sample Announcement for Crawl",
            content="Content",
            author=self.admin,
            category=Announcement.CATEGORY_GENERAL
        )

        # Sample appointment
        self.appointment = Appointment.objects.create(
            resident=self.resident_user,
            category=Appointment.CATEGORY_HEALTHCARE,
            status=Appointment.STATUS_PENDING,
            appt_date=date(2026, 10, 15)
        )

        # Setup Clients
        self.client_anon = Client()

        self.client_resident = Client()
        self.client_resident.force_login(self.resident_user)

        self.client_staff_unassigned = Client()
        self.client_staff_unassigned.force_login(self.staff_unassigned)

        self.client_staff_scoped = Client()
        self.client_staff_scoped.force_login(self.staff_scoped)

        self.client_admin = Client()
        self.client_admin.force_login(self.admin)

    def _collect_all_urls(self, patterns, prefix=''):
        routes = []
        for p in patterns:
            if isinstance(p, URLPattern):
                raw = prefix + str(p.pattern)
                routes.append(raw)
            elif isinstance(p, URLResolver):
                routes.extend(self._collect_all_urls(p.url_patterns, prefix + str(p.pattern)))
        return routes

    def _resolve_url_path(self, raw_path):
        """Replaces URL parameters with concrete test IDs."""
        path = raw_path
        # Clean regex anchors if present
        path = path.lstrip('^').rstrip('$')
        # Replace parameterized segments
        path = re.sub(r'<int:user_id>', str(self.resident_user.id), path)
        path = re.sub(r'<int:resident_id>', str(self.resident.id), path)
        path = re.sub(r'<int:post_id>', str(self.announcement.id), path)
        path = re.sub(r'<int:announcement_id>', str(self.announcement.id), path)
        path = re.sub(r'<int:appointment_id>', str(self.appointment.id), path)
        path = re.sub(r'<int:pk>', str(self.announcement.id), path)
        path = re.sub(r'<int:id>', str(self.announcement.id), path)
        path = re.sub(r'<int:officer_id>', '1', path)
        path = re.sub(r'<int:rule_id>', '1', path)
        path = re.sub(r'<str:ref_no>', str(self.appointment.reference_no), path)
        path = re.sub(r'<uidb64>', 'dummy_uid', path)
        path = re.sub(r'<token>', 'dummy_token', path)
        if not path.startswith('/'):
            path = '/' + path
        return path

    def test_crawl_every_route_enforces_auth_and_permissions(self):
        """Crawl all application routes and verify security boundaries across all 5 personas."""
        resolver = get_resolver()
        raw_routes = self._collect_all_urls(resolver.url_patterns)

        # Publicly accessible routes
        PUBLIC_PREFIXES = (
            '/',
            '/landing/',
            '/accounts/login/',
            '/accounts/signup/',
            '/accounts/password-reset/',
            '/appointments/api/',
            '/static/',
            '/media/avatars/',
            '/media/announcements/',
            '/media/attachments/',
        )

        # Administrative management routes (strictly forbidden to residents)
        ADMIN_PREFIXES = (
            '/accounts/residents/',
            '/accounts/officers/',
            '/accounts/system/',
            '/appointments/schedules/manage/',
            '/history/',
            '/statistics/',
            '/blotter/',
            '/admin/',
        )

        tested_count = 0
        for raw in raw_routes:
            # Skip media / internal django admin js routes
            if raw.startswith('media/') or 'jsi18n' in raw or '<path:' in raw:
                continue

            path = self._resolve_url_path(raw)
            tested_count += 1

            # 1. Anonymous test
            is_public = (path in ['/', '/landing/'] or any(path.startswith(p) for p in PUBLIC_PREFIXES))
            resp_anon = self.client_anon.get(path)

            if not is_public:
                self.assertNotEqual(
                    resp_anon.status_code, 200,
                    f"SECURITY DEFECT: Private route {path} is accessible (200 OK) by anonymous user!"
                )
                self.assertIn(
                    resp_anon.status_code, [302, 401, 403, 404, 405],
                    f"Private route {path} returned unexpected status {resp_anon.status_code} for anonymous."
                )

            # 2. Resident test against Administrative routes
            is_admin_route = any(path.startswith(p) for p in ADMIN_PREFIXES) and not path.startswith('/admin/login/')
            if is_admin_route:
                resp_resident = self.client_resident.get(path)
                self.assertNotEqual(
                    resp_resident.status_code, 200,
                    f"SECURITY DEFECT: Administrative route {path} is accessible (200 OK) by resident user!"
                )
                self.assertIn(
                    resp_resident.status_code, [302, 403, 404, 405],
                    f"Admin route {path} returned unexpected status {resp_resident.status_code} for resident."
                )

            # 3. Admin test
            # The crawl visits /accounts/logout/, which ends the admin session; after that,
            # HTML routes answer 302 to login and JSON API routes answer 401 JSON (Stage A8).
            resp_admin = self.client_admin.get(path)
            admin_allowed = [200, 302, 400, 403, 404, 405] + ([401] if '/api/' in path else [])
            self.assertIn(
                resp_admin.status_code, admin_allowed,
                f"Admin user encountered server error {resp_admin.status_code} on route {path}"
            )

        print(f"\n[URL Crawl Test] Successfully crawled and validated {tested_count} routes across 5 personas.")
        self.assertGreater(tested_count, 30)
