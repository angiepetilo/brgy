import datetime
from django.test import TestCase, Client
from django.urls import reverse
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Purok, Resident, Household, Officer, StaffAssignment, PermissionRule
from apps.accounts.services import (
    register_resident_service,
    staff_register_resident_service,
    update_resident_needs_service,
    approve_resident_service,
    assign_resident_officer_service,
    assign_purok_residents_officer_service,
    get_dashboard_metrics,
)
from apps.chat.models import ChatThread, Message
from apps.chat.services import create_concern_thread_service, send_thread_message_service, update_concern_status_service
from apps.history.models import ActivityLog


class PartFAccountsAndResidentsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@barangay.ph',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Admin',
            last_name='Barangay'
        )

        # Puroks
        self.purok_1, _ = Purok.objects.get_or_create(name='Purok 1')
        self.purok_2, _ = Purok.objects.get_or_create(name='Purok 2')

        # Staff with resident create & view_needs
        self.staff_user = User.objects.create_user(
            username='staff_user',
            email='staff@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Staff',
            last_name='Member'
        )
        self.officer_role = Officer.objects.create(
            position='Kagawad',
            committee='Health'
        )
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=self.officer_role,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='all'
        )
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='view', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='create', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='view_needs', allowed=True)
        PermissionRule.objects.create(officer=self.officer_role, module='residents', action='edit_needs', allowed=True)

        # Staff without view_needs
        self.restricted_staff = User.objects.create_user(
            username='restricted_staff',
            email='restricted@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Restricted',
            last_name='Staff'
        )
        self.tanod_role = Officer.objects.create(
            position='Tanod',
            committee='Peace and Order'
        )
        StaffAssignment.objects.create(
            user=self.restricted_staff,
            officer=self.tanod_role,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='security'
        )
        PermissionRule.objects.create(officer=self.tanod_role, module='residents', action='view', allowed=True)

        # Normal resident
        self.resident_user = User.objects.create_user(
            username='resident_user',
            email='resident@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Juan',
            last_name='Dela Cruz',
            date_of_birth=datetime.date(1990, 5, 10)
        )
        self.resident_profile = Resident.objects.create(
            user=self.resident_user,
            first_name='Juan',
            last_name='Dela Cruz',
            birthdate=datetime.date(1990, 5, 10),
            purok=self.purok_1,
            needs_attention=True,
            needs_category='pwd',
            needs_notes='Requires wheelchair access ramp.'
        )

    # 1. Needs data hidden everywhere without permission
    def test_needs_data_hidden_without_permission(self):
        # Normal resident cannot view needs
        self.client.login(username='resident_user', password='password123')
        res = self.client.get(reverse('accounts:residents_tabbed'))
        # Should be forbidden for residents
        self.assertEqual(res.status_code, 403)

        # Restricted staff without view_needs visits residents page
        self.client.login(username='restricted_staff', password='password123')
        res = self.client.get(reverse('accounts:residents_tabbed'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['can_view_needs'])

        # Staff with view_needs visits residents page
        self.client.login(username='staff_user', password='password123')
        res = self.client.get(reverse('accounts:residents_tabbed'))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['can_view_needs'])

        # Admin visits residents page
        self.client.login(username='admin_user', password='password123')
        res = self.client.get(reverse('accounts:residents_tabbed'))
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.context['can_view_needs'])

        # Restricted staff attempting to edit needs raises PermissionDenied
        with self.assertRaises(PermissionDenied):
            update_resident_needs_service(
                resident=self.resident_profile,
                actor=self.restricted_staff,
                data={'needs_attention': True, 'needs_category': 'senior'}
            )

    # 2. Staff can register a minor but minor cannot self-sign-up
    def test_staff_registers_minor_vs_self_signup(self):
        minor_dob = datetime.date(2012, 6, 15)  # 14 years old

        # 1. Self-signup by minor fails (18+ required)
        with self.assertRaises(ValueError) as ctx:
            register_resident_service({
                'email': 'minor@barangay.ph',
                'first_name': 'Young',
                'last_name': 'Resident',
                'birthdate': minor_dob,
                'contact_no': '09171234567',
                'address': 'House 123',
                'purok': self.purok_1,
            })
        self.assertIn("18 and above", str(ctx.exception))

        # 2. Staff registration for minor succeeds (no user, minimal fields)
        minor_res = staff_register_resident_service(
            staff_user=self.staff_user,
            data={
                'first_name': 'Young',
                'last_name': 'Resident',
                'birthdate': minor_dob,
                'purok': self.purok_1,
            }
        )
        self.assertIsNotNone(minor_res.id)
        self.assertIsNone(minor_res.user)
        self.assertEqual(minor_res.birthdate, minor_dob)
        self.assertLess(minor_res.age, 18)

    # 3. Link-on-approval
    def test_link_on_approval(self):
        # Staff previously registered Maria Clara offline (no User)
        dob = datetime.date(1995, 3, 20)
        existing_res = staff_register_resident_service(
            staff_user=self.staff_user,
            data={
                'first_name': 'Maria',
                'last_name': 'Clara',
                'birthdate': dob,
                'purok': self.purok_1,
                'address': 'Calle Real',
                'contact_no': '09175555555'
            }
        )
        self.assertIsNone(existing_res.user)

        # Later, Maria Clara registers online for portal account
        user_signup, _ = register_resident_service({
            'email': 'maria.clara@barangay.ph',
            'first_name': 'Maria',
            'last_name': 'Clara',
            'birthdate': dob,
            'contact_no': '09175555555',
            'address': 'Calle Real',
            'purok': self.purok_1,
        })
        self.assertEqual(user_signup.status, User.STATUS_PENDING)

        # Admin approves WITHOUT confirming a link -> must NOT auto-merge
        res = approve_resident_service(user_signup, self.admin)
        self.assertIsNone(res['linked_resident'])
        existing_res.refresh_from_db()
        self.assertIsNone(existing_res.user)
        self.assertEqual(Resident.objects.filter(first_name='Maria', last_name='Clara').count(), 2)

        # A second signup confirmed explicitly by admin links to the existing record
        user_b, _ = register_resident_service({
            'email': 'maria.clara2@barangay.ph',
            'first_name': 'Maria',
            'last_name': 'Clara',
            'birthdate': dob,
            'contact_no': '09175555555',
            'address': 'Calle Real',
            'purok': self.purok_1,
        })
        res_b = approve_resident_service(user_b, self.admin, link_resident_id=existing_res.id)
        self.assertEqual(res_b['linked_resident'].id, existing_res.id)
        existing_res.refresh_from_db()
        self.assertEqual(existing_res.user, user_b)

    # 4. Dashboard counts with mixed-status fixtures
    def test_dashboard_counts_with_mixed_status_fixtures(self):
        # Create fixtures:
        # Active resident
        res_active = Resident.objects.create(
            first_name='Active', last_name='One', birthdate=datetime.date(1990, 1, 1),
            purok=self.purok_1, is_archived=False, needs_attention=True
        )
        # Archived resident (must be excluded from counts)
        res_archived = Resident.objects.create(
            first_name='Archived', last_name='Two', birthdate=datetime.date(1980, 1, 1),
            purok=self.purok_1, is_archived=True, needs_attention=True
        )

        # Portal Users:
        # Pending user
        User.objects.create_user(
            username='pending_user', email='pending@barangay.ph', password='pw',
            role=User.ROLE_RESIDENT, status=User.STATUS_PENDING, purok=self.purok_1
        )
        # Rejected user (excluded from portal counts)
        User.objects.create_user(
            username='rejected_user', email='rejected@barangay.ph', password='pw',
            role=User.ROLE_RESIDENT, status=User.STATUS_REJECTED, purok=self.purok_1
        )
        # Disabled user (excluded from portal counts)
        User.objects.create_user(
            username='disabled_user', email='disabled@barangay.ph', password='pw',
            role=User.ROLE_RESIDENT, status=User.STATUS_DISABLED, purok=self.purok_1
        )

        metrics = get_dashboard_metrics(self.admin)

        # Registered residents excludes archived: self.resident_profile + res_active = 2
        self.assertEqual(metrics['registered_residents_count'], 2)

        # Portal accounts excludes rejected, disabled, pending: self.resident_user = 1
        self.assertEqual(metrics['portal_accounts_count'], 1)

        # Needs attention excludes archived: self.resident_profile + res_active = 2
        self.assertEqual(metrics['needs_attention_count'], 2)

        # Pending registrations = 1
        self.assertEqual(metrics['pending_registrations_count'], 1)

    # 5. Per-leader counts and empty state
    def test_per_leader_counts_and_empty_state(self):
        # Assign self.staff_user as Purok 1 Leader
        StaffAssignment.objects.create(
            user=self.staff_user,
            officer=self.officer_role,
            scope_type=StaffAssignment.SCOPE_PUROK,
            scope_value='Purok 1'
        )

        metrics = get_dashboard_metrics(self.admin)
        leaders = metrics['residents_per_purok_leader']

        p1_data = next((x for x in leaders if x['purok_name'] == 'Purok 1'), None)
        p2_data = next((x for x in leaders if x['purok_name'] == 'Purok 2'), None)

        self.assertIsNotNone(p1_data)
        self.assertIsNotNone(p2_data)

        # Purok 1 has leader assigned
        self.assertEqual(p1_data['leader_name'], self.staff_user.get_full_name())

        # Purok 2 has no leader assigned -> shows 'no leader assigned'
        self.assertEqual(p2_data['leader_name'], 'no leader assigned')

    # 6. Audit entry on needs changes
    def test_audit_entry_on_needs_changes(self):
        update_resident_needs_service(
            resident=self.resident_profile,
            actor=self.staff_user,
            data={
                'needs_attention': True,
                'needs_category': 'senior',
                'needs_notes': 'Requires monthly medication delivery.',
                'consent_recorded': True
            }
        )

        # Verify ActivityLog entry created
        log = ActivityLog.objects.filter(
            action_type='ResidentNeeds',
            target_id=str(self.resident_profile.id)
        ).latest('created_at')

        self.assertEqual(log.actor, self.staff_user)
        self.assertEqual(log.action, 'update')
        self.assertIn("senior", log.details)

    # 7. Resident reply reopens a resolved concern
    def test_resident_reply_reopens_concern(self):
        thread = create_concern_thread_service(
            resident=self.resident_user,
            data={'category': 'health', 'content': 'Medical request'}
        )
        update_concern_status_service(thread, self.admin, ChatThread.STATUS_IN_PROGRESS)
        update_concern_status_service(thread, self.admin, ChatThread.STATUS_RESOLVED)
        self.assertEqual(thread.status, ChatThread.STATUS_RESOLVED)

        # Resident sends message -> auto reopens
        send_thread_message_service(thread, self.resident_user, "Follow-up question on medication.")
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.STATUS_IN_PROGRESS)

    # 8. Message text stored raw
    def test_message_text_stored_raw(self):
        raw_msg = "Hello <b>World</b> & 'friends' <script>alert(1)</script>"
        thread = create_concern_thread_service(
            resident=self.resident_user,
            data={'category': 'general', 'content': raw_msg}
        )
        msg = thread.messages.first()
        # Verifies stored text is raw, not HTML-escaped before save
        self.assertEqual(msg.content, raw_msg)
