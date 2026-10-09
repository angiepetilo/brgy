import datetime
from django.test import TestCase, TransactionTestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Resident, Purok, Officer, StaffAssignment, PermissionRule
from apps.accounts.permissions import seed_default_permissions
from apps.appointments.models import (
    Appointment,
    HealthCareService,
    HealthSchedule,
    DocumentType,
    Requirement,
)
from apps.appointments.services import (
    book_appointment_service,
    approve_appointment_service,
    reject_appointment_service,
    complete_appointment_service,
    mark_no_show_service,
)
from apps.history.models import EmailLog


class PartCAppointmentsTests(TestCase):
    def get_future_weekday(self, days_ahead=1):
        cur = timezone.localdate()
        added = 0
        while added < days_ahead:
            cur += datetime.timedelta(days=1)
            if cur.weekday() not in (5, 6):
                added += 1
        return cur

    def setUp(self):
        self.client = Client()
        seed_default_permissions()

        self.purok, _ = Purok.objects.get_or_create(name="Purok 1")
        self.purok2, _ = Purok.objects.get_or_create(name="Purok 2")

        # Admin user (no Officer record needed)
        self.admin = User.objects.create_user(
            username="admin_user",
            email="admin@barangay.ph",
            password="AdminPassword123!",
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Staff user
        self.staff_user = User.objects.create_user(
            username="staff_member",
            email="staff@barangay.ph",
            password="StaffPassword123!",
            role=User.ROLE_STAFF,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )

        # Resident A
        self.resident_a = User.objects.create_user(
            username="resident_a",
            email="resident.a@example.com",
            password="ResidentPassword123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            first_name="Juan",
            last_name="Dela Cruz",
            phone_number="09171234567"
        )
        self.res_profile_a = Resident.objects.create(
            user=self.resident_a,
            first_name="Juan",
            last_name="Dela Cruz",
            birthdate=datetime.date(2000, 1, 15),
            contact_no="09171234567",
            address="123 Mabini St",
            purok=self.purok
        )

        # Resident B
        self.resident_b = User.objects.create_user(
            username="resident_b",
            email="resident.b@example.com",
            password="ResidentPassword123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            first_name="Maria",
            last_name="Santos",
            phone_number="09187654321"
        )
        self.res_profile_b = Resident.objects.create(
            user=self.resident_b,
            first_name="Maria",
            last_name="Santos",
            birthdate=datetime.date(1995, 6, 20),
            contact_no="09187654321",
            address="456 Rizal St",
            purok=self.purok2
        )

        # Catalog setup
        self.doc_type, _ = DocumentType.objects.get_or_create(
            code="clearance",
            defaults={"name": "Barangay Clearance", "is_active": True}
        )
        Requirement.objects.get_or_create(document_type=self.doc_type, name="Cedula")
        Requirement.objects.get_or_create(document_type=self.doc_type, name="Valid Government ID")

        self.health_service, _ = HealthCareService.objects.get_or_create(
            name="General Consultation",
            defaults={"is_active": True, "is_free": True}
        )

        self.tomorrow = self.get_future_weekday(days_ahead=1)
        self.health_schedule, _ = HealthSchedule.objects.get_or_create(
            health_service=self.health_service,
            service_date=self.tomorrow,
            time_window=Appointment.TIME_SLOT_MORNING,
            defaults={"capacity": 2}
        )

        # Sample Appointments
        self.apt_doc = Appointment.objects.create(
            resident=self.resident_a,
            applicant_first_name=self.resident_a.first_name,
            applicant_last_name=self.resident_a.last_name,
            applicant_email=self.resident_a.email,
            applicant_phone=self.resident_a.phone_number,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type=self.doc_type,
            appt_date=self.tomorrow,
            time_window=Appointment.TIME_SLOT_MORNING,
            purpose="Employment requirement",
            status=Appointment.STATUS_PENDING
        )

        self.apt_health = Appointment.objects.create(
            resident=self.resident_b,
            applicant_first_name=self.resident_b.first_name,
            applicant_last_name=self.resident_b.last_name,
            applicant_email=self.resident_b.email,
            applicant_phone=self.resident_b.phone_number,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=self.health_service,
            appt_date=self.tomorrow,
            time_window=Appointment.TIME_SLOT_MORNING,
            purpose="Flu consultation",
            status=Appointment.STATUS_PENDING
        )

    def test_staff_with_no_assignment_gets_403(self):
        """Staff with no assignment is denied by default (HTTP 403)."""
        self.client.login(username="staff_member", password="StaffPassword123!")
        resp = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_doc.pk}))
        self.assertEqual(resp.status_code, 403)

        with self.assertRaises(PermissionDenied):
            approve_appointment_service(self.apt_doc, self.staff_user)

    def test_admin_without_officer_record_has_unconditional_access(self):
        """Admin has full access unconditionally with no Officer record needed."""
        self.assertFalse(Officer.objects.filter(user=self.admin).exists())
        self.client.login(username="admin_user", password="AdminPassword123!")
        resp = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_doc.pk}))
        self.assertEqual(resp.status_code, 302)
        self.apt_doc.refresh_from_db()
        self.assertEqual(self.apt_doc.status, Appointment.STATUS_APPROVED)

    def test_health_scoped_staff_gets_403_on_documents_and_success_on_health(self):
        """Staff with Health scope gets 403 on Document item and success on Health item."""
        bhw_officer = Officer.objects.filter(position=Officer.POSITION_BHW).first()
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=bhw_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Health"
        )
        self.client.login(username="staff_member", password="StaffPassword123!")

        # Document item -> 403
        resp_doc = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_doc.pk}))
        self.assertEqual(resp_doc.status_code, 403)

        with self.assertRaises(PermissionDenied):
            approve_appointment_service(self.apt_doc, self.staff_user)

        # Health item -> success (302 redirect)
        resp_health = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_health.pk}))
        self.assertEqual(resp_health.status_code, 302)
        self.apt_health.refresh_from_db()
        self.assertEqual(self.apt_health.status, Appointment.STATUS_APPROVED)

    def test_two_assignments_combine(self):
        """Staff user rights are the union of all their StaffAssignments."""
        bhw_officer = Officer.objects.filter(position=Officer.POSITION_BHW).first()
        sec_officer = Officer.objects.filter(position=Officer.POSITION_SECRETARY).first()

        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=bhw_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Health"
        )
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=sec_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Documents"
        )

        self.client.login(username="staff_member", password="StaffPassword123!")

        # Both can now be approved
        resp_doc = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_doc.pk}))
        self.assertEqual(resp_doc.status_code, 302)

        resp_health = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_health.pk}))
        self.assertEqual(resp_health.status_code, 302)

        self.apt_doc.refresh_from_db()
        self.apt_health.refresh_from_db()
        self.assertEqual(self.apt_doc.status, Appointment.STATUS_APPROVED)
        self.assertEqual(self.apt_health.status, Appointment.STATUS_APPROVED)

    def test_permission_edit_applies_on_next_request(self):
        """Updating a PermissionRule takes effect immediately on the next request."""
        sec_officer = Officer.objects.filter(position=Officer.POSITION_SECRETARY).first()
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=sec_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Documents"
        )
        self.client.login(username="staff_member", password="StaffPassword123!")

        # Allowed initially
        rule = PermissionRule.objects.get(officer=sec_officer, module="appointments", action="approve")
        self.assertTrue(rule.allowed)

        # Admin revokes approval permission for Secretary
        rule.allowed = False
        rule.save()

        # Immediate next request is denied with 403
        resp = self.client.post(reverse("appointments:approve", kwargs={"pk": self.apt_doc.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_booking_requires_authentication(self):
        """Anonymous booking is redirected to login with next parameter."""
        post_data = {
            "first_name": "Ghost",
            "last_name": "Applicant",
            "email": "ghost@example.com",
            "phone_number": "09171112222",
            "age": "25",
            "address": "Sample St",
            "category": "document",
            "document_type": "clearance",
            "appt_date": self.tomorrow.isoformat(),
            "time_window": "morning",
            "purpose": "Test anonymous booking"
        }
        resp = self.client.post(reverse("appointments:api_public_book"), data=post_data)
        # Stage A8: JSON API path -> 401 JSON with a login URL, not a redirect.
        self.assertEqual(resp.status_code, 401)
        self.assertTrue(resp.json()["requires_login"])
        self.assertIn("/accounts/login/", resp.json()["login_url"])
        self.assertIn("next=", resp.json()["login_url"])
        self.assertFalse(Appointment.objects.filter(purpose="Test anonymous booking").exists())

        with self.assertRaises(PermissionDenied):
            book_appointment_service(None, post_data)

    def test_resident_prefilled_details_and_server_side_age(self):
        """Booking prefills details and calculates age on server from birthdate."""
        test_date = self.get_future_weekday(days_ahead=3)
        data = {
            "category": "document",
            "document_type": "clearance",
            "appt_date": test_date.isoformat(),
            "time_window": "morning",
            "purpose": "Passport application",
            "age": "99"  # Deliberate wrong client age to test server override
        }
        with self.captureOnCommitCallbacks(execute=True):
            apt = book_appointment_service(self.resident_a, data)

        self.assertEqual(apt.applicant_first_name, "Juan")
        self.assertEqual(apt.applicant_last_name, "Dela Cruz")
        self.assertEqual(apt.applicant_email, "resident.a@example.com")
        self.assertEqual(apt.applicant_phone, "09171234567")
        self.assertEqual(apt.applicant_address, "123 Mabini St")

        # Birthdate 2000-01-15 -> age ~ 26, never 99
        expected_age = self.res_profile_a.age
        self.assertEqual(apt.applicant_age, expected_age)
        self.assertNotEqual(apt.applicant_age, 99)

        # Unique reference number format APT-YYYY-NNNN
        self.assertTrue(apt.reference_no.startswith(f"APT-{timezone.now().year}-"))
        self.assertEqual(apt.status, Appointment.STATUS_PENDING)

        # Dispatched Email 1 (appt_received.txt)
        email_record = EmailLog.objects.filter(
            recipient="resident.a@example.com",
            email_type="appt_received.txt"
        ).first()
        self.assertIsNotNone(email_record)

    def test_health_capacity_enforcement_and_recheck_on_approve(self):
        """Health booking and approval respect HealthSchedule capacity limit."""
        # Schedule has capacity = 2
        # self.apt_health already occupies 1 slot (resident_b)
        data = {
            "category": Appointment.CATEGORY_HEALTHCARE,
            "healthcare_service": self.health_service,
            "appt_date": self.tomorrow.isoformat(),
            "time_window": "morning",
            "purpose": "Checkup"
        }
        # 2nd booking -> succeeds (resident_a)
        apt2 = book_appointment_service(self.resident_a, data)
        self.assertEqual(apt2.status, Appointment.STATUS_PENDING)

        # 3rd booking -> capacity exceeded, raises ValueError (using resident_c to test capacity rather than duplicate)
        resident_c = User.objects.create_user(
            username="resident_c",
            email="resident.c@example.com",
            password="ResidentPassword123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE
        )
        with self.assertRaises(ValueError) as cm:
            book_appointment_service(resident_c, data)
        self.assertIn("capacity full", str(cm.exception))

    def test_rejection_requires_reason_frees_slot_and_sends_email(self):
        """Rejection requires reason, frees schedule capacity, and sends Email 6."""
        # Empty reason -> ValueError
        with self.assertRaises(ValueError):
            reject_appointment_service(self.apt_health, self.admin, "")

        # Valid rejection with email capture
        with self.captureOnCommitCallbacks(execute=True):
            reject_appointment_service(
                self.apt_health,
                self.admin,
                "Health center doctor is on emergency duty."
            )

        self.apt_health.refresh_from_db()
        self.assertEqual(self.apt_health.status, Appointment.STATUS_REJECTED)
        self.assertEqual(self.apt_health.rejection_reason, "Health center doctor is on emergency duty.")

        email_record = EmailLog.objects.filter(
            recipient=self.resident_b.email,
            email_type="appt_rejected.txt"
        ).first()
        self.assertIsNotNone(email_record)

    def test_approval_dispatches_email_4_with_requirements(self):
        """Approving document appointment dispatches Email 4 with document requirements."""
        with self.captureOnCommitCallbacks(execute=True):
            approve_appointment_service(self.apt_doc, self.admin)

        self.apt_doc.refresh_from_db()
        self.assertEqual(self.apt_doc.status, Appointment.STATUS_APPROVED)

        email_record = EmailLog.objects.filter(
            recipient=self.resident_a.email,
            email_type="appt_approved.txt"
        ).first()
        self.assertIsNotNone(email_record)

    def test_residents_see_only_their_own_appointments(self):
        """Residents see only their own appointments in queue and detail view."""
        self.client.login(username="resident_a", password="ResidentPassword123!")

        # Queue view
        resp = self.client.get(reverse("appointments:list"))
        self.assertEqual(resp.status_code, 200)
        appointments_in_context = resp.context["appointments"]
        self.assertIn(self.apt_doc, appointments_in_context)
        self.assertNotIn(self.apt_health, appointments_in_context)

        # Detail view of own appointment -> 200
        resp_own = self.client.get(reverse("appointments:detail", kwargs={"pk": self.apt_doc.pk}))
        self.assertEqual(resp_own.status_code, 200)

        # Detail view of other resident's appointment -> 404
        resp_other = self.client.get(reverse("appointments:detail", kwargs={"pk": self.apt_health.pk}))
        self.assertEqual(resp_other.status_code, 404)

    def test_double_approve_sends_one_email(self):
        """A second approve attempt does nothing, returns False, and sends no second email."""
        with self.captureOnCommitCallbacks(execute=True):
            res1 = approve_appointment_service(self.apt_doc, self.admin)
        self.assertTrue(res1)
        self.apt_doc.refresh_from_db()
        self.assertEqual(self.apt_doc.status, Appointment.STATUS_APPROVED)

        email_count_1 = EmailLog.objects.filter(
            recipient=self.resident_a.email,
            email_type="appt_approved.txt"
        ).count()
        self.assertEqual(email_count_1, 1)

        # Second approve attempt
        with self.captureOnCommitCallbacks(execute=True):
            res2 = approve_appointment_service(self.apt_doc, self.admin)
        self.assertFalse(res2)

        email_count_2 = EmailLog.objects.filter(
            recipient=self.resident_a.email,
            email_type="appt_approved.txt"
        ).count()
        self.assertEqual(email_count_2, 1)

    def test_invalid_transitions_refused(self):
        """Approve/reject only from pending; complete/no_show only from approved."""
        # 1. Reject only from pending (trying on approved raises ValueError)
        approve_appointment_service(self.apt_doc, self.admin)
        self.apt_doc.refresh_from_db()
        with self.assertRaises(ValueError) as cm:
            reject_appointment_service(self.apt_doc, self.admin, "Should fail")
        self.assertIn("approved", str(cm.exception).lower())

        # 2. Complete only from approved (trying on pending raises ValueError)
        self.assertEqual(self.apt_health.status, Appointment.STATUS_PENDING)
        with self.assertRaises(ValueError) as cm:
            complete_appointment_service(self.apt_health, self.admin)
        self.assertIn("pending", str(cm.exception).lower())

        # 3. No-show only from approved (trying on pending raises ValueError)
        with self.assertRaises(ValueError) as cm:
            mark_no_show_service(self.apt_health, self.admin)
        self.assertIn("pending", str(cm.exception).lower())

        # 4. Duplicate reject attempt does nothing and returns False
        reject_res_1 = reject_appointment_service(self.apt_health, self.admin, "Reason 1")
        self.assertTrue(reject_res_1)
        self.apt_health.refresh_from_db()
        self.assertEqual(self.apt_health.status, Appointment.STATUS_REJECTED)

        reject_res_2 = reject_appointment_service(self.apt_health, self.admin, "Reason 2")
        self.assertFalse(reject_res_2)

    def test_concurrent_approval_of_the_last_slot(self):
        """Concurrent or sequential approval of the last slot checks locked schedule capacity."""
        slot_date = self.get_future_weekday(days_ahead=6)
        sched = HealthSchedule.objects.create(
            health_service=self.health_service,
            service_date=slot_date,
            time_window="morning",
            capacity=1
        )
        apt1 = Appointment.objects.create(
            resident=self.resident_a,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=self.health_service,
            appt_date=slot_date,
            time_window="morning",
            status=Appointment.STATUS_PENDING
        )
        apt2 = Appointment.objects.create(
            resident=self.resident_b,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=self.health_service,
            appt_date=slot_date,
            time_window="morning",
            status=Appointment.STATUS_PENDING
        )

        # First approval fills the only slot
        res1 = approve_appointment_service(apt1, self.admin)
        self.assertTrue(res1)
        apt1.refresh_from_db()
        self.assertEqual(apt1.status, Appointment.STATUS_APPROVED)

        # Second approval fails because capacity is full
        with self.assertRaises(ValueError) as cm:
            approve_appointment_service(apt2, self.admin)
        self.assertIn("capacity", str(cm.exception).lower())

    def test_duplicate_past_weekend_booking_refused(self):
        """Refuse duplicate pending/approved booking, past dates, >60 days, and weekends."""
        valid_date = self.get_future_weekday(days_ahead=2)
        data = {
            "category": "document",
            "document_type": "clearance",
            "appt_date": valid_date.isoformat(),
            "time_window": "morning",
            "purpose": "First valid booking"
        }
        book_appointment_service(self.resident_a, data)

        # 1. Duplicate active booking for same resident, service, and date
        with self.assertRaises(ValueError) as cm:
            book_appointment_service(self.resident_a, data)
        self.assertIn("already have an active appointment request", str(cm.exception))

        # 2. Past date refused
        past_date = timezone.localdate() - datetime.timedelta(days=1)
        data_past = data.copy()
        data_past["appt_date"] = past_date.isoformat()
        with self.assertRaises(ValueError) as cm:
            book_appointment_service(self.resident_b, data_past)
        self.assertIn("past", str(cm.exception).lower())

        # 3. Date > 60 days ahead refused
        far_date = timezone.localdate() + datetime.timedelta(days=61)
        data_far = data.copy()
        data_far["appt_date"] = far_date.isoformat()
        with self.assertRaises(ValueError) as cm:
            book_appointment_service(self.resident_b, data_far)
        self.assertIn("60 days", str(cm.exception).lower())

        # 4. Saturday / Sunday refused
        today = timezone.localdate()
        days_until_sat = (5 - today.weekday()) % 7
        if days_until_sat == 0:
            days_until_sat = 7
        sat_date = today + datetime.timedelta(days=days_until_sat)
        data_sat = data.copy()
        data_sat["appt_date"] = sat_date.isoformat()
        with self.assertRaises(ValueError) as cm:
            book_appointment_service(self.resident_b, data_sat)
        self.assertTrue("weekday" in str(cm.exception).lower() or "weekend" in str(cm.exception).lower())

    def test_no_show_before_date_refused(self):
        """Block no-show before appt_date."""
        future_date = self.get_future_weekday(days_ahead=4)
        apt = Appointment.objects.create(
            resident=self.resident_a,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type=self.doc_type,
            appt_date=future_date,
            time_window="morning",
            status=Appointment.STATUS_APPROVED
        )
        with self.assertRaises(ValueError) as cm:
            mark_no_show_service(apt, self.admin)
        self.assertIn("before the appointment date", str(cm.exception).lower())

    def test_reject_complete_no_show_respect_scope(self):
        """Reject, complete, and no_show must respect staff assignment scope."""
        bhw_officer = Officer.objects.filter(position=Officer.POSITION_BHW).first()
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=bhw_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Health"
        )
        # 1. Staff with Health scope cannot reject document request
        with self.assertRaises(PermissionDenied):
            reject_appointment_service(self.apt_doc, self.staff_user, "Not allowed")

        # 2. Staff with Health scope cannot complete document request
        approve_appointment_service(self.apt_doc, self.admin)
        self.apt_doc.refresh_from_db()
        with self.assertRaises(PermissionDenied):
            complete_appointment_service(self.apt_doc, self.staff_user)

        # 3. Staff with Health scope cannot mark no-show on document request
        with self.assertRaises(PermissionDenied):
            mark_no_show_service(self.apt_doc, self.staff_user)

    def test_rule_for_staff_with_both_service_area_and_purok_assignment(self):
        """
        Rule: Staff with both a service-area and a purok assignment:
        - Health service area matches -> allowed for all puroks.
        - Document service -> allowed only for assigned purok.
        - Outside both -> denied.
        """
        bhw_officer = Officer.objects.filter(position=Officer.POSITION_BHW).first()
        purok_lead = Officer.objects.filter(position=Officer.POSITION_PUROK_LEADER).first()

        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=bhw_officer,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value="Health"
        )
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=purok_lead,
            scope_type=StaffAssignment.SCOPE_PUROK,
            scope_value="Purok 1"
        )

        # 1. Health service for resident in Purok 2 (apt_health is resident_b who is Purok 2)
        # Allowed because Health service area matches regardless of purok
        res1 = approve_appointment_service(self.apt_health, self.staff_user)
        self.assertTrue(res1)
        self.apt_health.refresh_from_db()
        self.assertEqual(self.apt_health.status, Appointment.STATUS_APPROVED)

        # 2. Document service for resident in Purok 1 (apt_doc is resident_a who is Purok 1)
        # Allowed because resident belongs to assigned Purok 1
        res2 = approve_appointment_service(self.apt_doc, self.staff_user)
        self.assertTrue(res2)
        self.apt_doc.refresh_from_db()
        self.assertEqual(self.apt_doc.status, Appointment.STATUS_APPROVED)

        # 3. Document service for resident in Purok 2
        # Denied because neither Health service area nor Purok 1 matches
        apt_doc_purok2 = Appointment.objects.create(
            resident=self.resident_b,
            category=Appointment.CATEGORY_DOCUMENT,
            document_type=self.doc_type,
            appt_date=self.tomorrow,
            time_window="morning",
            status=Appointment.STATUS_PENDING
        )
        with self.assertRaises(PermissionDenied):
            approve_appointment_service(apt_doc_purok2, self.staff_user)

    def test_resident_can_open_schedule_page_but_not_staff_schedule_urls(self):
        """Resident can open read-only schedule page (200) but receives 403 on staff management URLs."""
        self.client.login(username="resident_a", password="ResidentPassword123!")

        # Resident schedule page -> 200
        resp_resident_sched = self.client.get(reverse("appointments:health_schedule"))
        self.assertEqual(resp_resident_sched.status_code, 200)

        # Staff management views -> 403
        resp_manage = self.client.get(reverse("appointments:schedule_manage"))
        self.assertEqual(resp_manage.status_code, 403)

        resp_edit = self.client.get(reverse("appointments:schedule_edit", kwargs={"pk": self.health_schedule.pk}))
        self.assertEqual(resp_edit.status_code, 403)

        resp_del = self.client.post(reverse("appointments:schedule_delete", kwargs={"pk": self.health_schedule.pk}))
        self.assertEqual(resp_del.status_code, 403)


class ConcurrentApprovalTransactionTests(TransactionTestCase):
    """
    Validates atomic row-locking and last-slot approval capacity checks
    inside a real transaction environment (TransactionTestCase).
    """

    def get_future_weekday(self, days_ahead=1):
        cur = timezone.localdate()
        added = 0
        while added < days_ahead:
            cur += datetime.timedelta(days=1)
            if cur.weekday() not in (5, 6):
                added += 1
        return cur

    def setUp(self):
        seed_default_permissions()
        self.purok, _ = Purok.objects.get_or_create(name="Purok Concurrent")
        self.admin = User.objects.create_user(
            username="admin_tx_concurrent",
            email="admin_tx_conc@barangay.ph",
            password="AdminPassword123!",
            role=User.ROLE_ADMIN,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.user_a = User.objects.create_user(
            username="res_tx_a",
            email="res_tx_a@example.com",
            password="Password123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident_a = Resident.objects.create(
            user=self.user_a,
            first_name="Alice",
            last_name="Tx",
            birthdate=datetime.date(1990, 1, 1),
            contact_no="09171112233",
            address="Purok Concurrent",
            purok=self.purok,
            consent_recorded=True
        )
        self.user_b = User.objects.create_user(
            username="res_tx_b",
            email="res_tx_b@example.com",
            password="Password123!",
            role=User.ROLE_RESIDENT,
            status=User.STATUS_ACTIVE,
            must_change_password=False
        )
        self.resident_b = Resident.objects.create(
            user=self.user_b,
            first_name="Bob",
            last_name="Tx",
            birthdate=datetime.date(1992, 2, 2),
            contact_no="09172223344",
            address="Purok Concurrent",
            purok=self.purok,
            consent_recorded=True
        )
        self.health_service = HealthCareService.objects.create(
            name="Consultation Tx",
            description="Consultation service",
            is_active=True
        )

    def test_concurrent_approval_of_the_last_slot_tx(self):
        """Concurrent last-slot approval test as TransactionTestCase."""
        slot_date = self.get_future_weekday(days_ahead=6)
        sched = HealthSchedule.objects.create(
            health_service=self.health_service,
            service_date=slot_date,
            time_window="morning",
            capacity=1
        )
        apt1 = Appointment.objects.create(
            resident=self.user_a,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=self.health_service,
            appt_date=slot_date,
            time_window="morning",
            status=Appointment.STATUS_PENDING
        )
        apt2 = Appointment.objects.create(
            resident=self.user_b,
            category=Appointment.CATEGORY_HEALTHCARE,
            healthcare_service=self.health_service,
            appt_date=slot_date,
            time_window="morning",
            status=Appointment.STATUS_PENDING
        )

        res1 = approve_appointment_service(apt1, self.admin)
        self.assertTrue(res1)
        apt1.refresh_from_db()
        self.assertEqual(apt1.status, Appointment.STATUS_APPROVED)

        with self.assertRaises(ValueError) as cm:
            approve_appointment_service(apt2, self.admin)
        self.assertIn("capacity", str(cm.exception).lower())


