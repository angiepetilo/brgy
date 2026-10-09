import datetime
import io
from PIL import Image
from django.test import TestCase, Client
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Officer, StaffAssignment, PermissionRule
from apps.chat.models import ChatThread, Message, Notification
from apps.chat.services import (
    create_concern_thread_service,
    create_direct_thread_service,
    update_concern_status_service,
    send_thread_message_service,
    reassign_staff_open_concerns,
)


def create_dummy_image(name='test_img.png'):
    file_io = io.BytesIO()
    image = Image.new('RGB', (100, 100), color=(73, 109, 137))
    image.save(file_io, format='PNG')
    file_io.seek(0)
    return SimpleUploadedFile(name, file_io.read(), content_type='image/png')


class PartEChatAndConcernsTests(TestCase):
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

        # Residents
        self.resident_1 = User.objects.create_user(
            username='resident_one',
            email='resident1@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Juan',
            last_name='Dela Cruz'
        )

        self.resident_2 = User.objects.create_user(
            username='resident_two',
            email='resident2@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Maria',
            last_name='Santos'
        )

        self.resident_3 = User.objects.create_user(
            username='resident_three',
            email='resident3@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Pedro',
            last_name='Penduko'
        )

        # Health Staff
        self.health_staff = User.objects.create_user(
            username='health_officer',
            email='health@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Doc',
            last_name='Reyes'
        )
        self.health_officer_role = Officer.objects.create(
            position='Health Worker',
            committee='Health'
        )
        StaffAssignment.objects.create(
            user=self.health_staff,
            officer=self.health_officer_role,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='Health'
        )

        # Peace & Order Staff
        self.peace_staff = User.objects.create_user(
            username='peace_officer',
            email='peace@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE,
            first_name='Tanod',
            last_name='Bautista'
        )
        self.peace_officer_role = Officer.objects.create(
            position='Barangay Tanod',
            committee='Peace and Order'
        )
        StaffAssignment.objects.create(
            user=self.peace_staff,
            officer=self.peace_officer_role,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='Peace and Order'
        )

    # 1. No cross-resident access (including guessed IDs)
    def test_no_cross_resident_access(self):
        # Resident 1 submits a concern
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={
                'category': 'health',
                'title': 'Cough and Fever Consultation',
                'content': 'Need medical assistance at home.'
            }
        )

        # Resident 2 tries to view Resident 1's concern
        self.client.login(username='resident_two', password='password123')
        res = self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        self.assertEqual(res.status_code, 403)

        # Resident 2 tries to reply to Resident 1's concern
        res = self.client.post(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}), {
            'message': 'Sneaking into this thread'
        })
        self.assertEqual(res.status_code, 403)

        # Resident 2 tries to update status of Resident 1's concern
        res = self.client.post(reverse('chat:update_concern_status', kwargs={'concern_id': thread.id}), {
            'status': 'resolved'
        })
        self.assertEqual(res.status_code, 403)

        # Resident 2 guesses a non-existent ID
        res = self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': 99999}))
        self.assertEqual(res.status_code, 404)

    # 2. Staff out of scope refused, admin allowed
    def test_staff_out_of_scope_refused_admin_allowed(self):
        # Health concern created
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={
                'category': 'health',
                'title': 'Vaccination inquiry',
                'content': 'When is the next immunization schedule?'
            }
        )
        self.assertEqual(thread.assigned_handler, self.health_staff)

        # Peace staff tries to view health concern -> 403
        self.client.login(username='peace_officer', password='password123')
        res = self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        self.assertEqual(res.status_code, 403)

        # Health staff views health concern -> 200
        self.client.login(username='health_officer', password='password123')
        res = self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        self.assertEqual(res.status_code, 200)

        # Admin views health concern -> 200
        self.client.login(username='admin_user', password='password123')
        res = self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        self.assertEqual(res.status_code, 200)

    # 3. Direct messages private (only the 2 participants; third parties & admin refused)
    def test_direct_messages_private(self):
        img = create_dummy_image('private_doc.png')
        msg = create_direct_thread_service(
            sender=self.resident_1,
            recipient=self.health_staff,
            raw_content='Private personal message between resident and officer',
            attachment_file=img
        )
        thread = msg.thread
        self.assertEqual(thread.thread_type, ChatThread.THREAD_DIRECT)

        # Resident 3 attempts to access attachment -> 403
        self.client.login(username='resident_three', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': msg.id}))
        self.assertEqual(res.status_code, 403)

        # Admin attempts to access direct message attachment -> 403 (direct messages strictly 2 participants)
        self.client.login(username='admin_user', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': msg.id}))
        self.assertEqual(res.status_code, 403)

        # Participant Resident 1 accesses attachment -> 200
        self.client.login(username='resident_one', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': msg.id}))
        self.assertEqual(res.status_code, 200)

        # Participant Health Staff accesses attachment -> 200
        self.client.login(username='health_officer', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': msg.id}))
        self.assertEqual(res.status_code, 200)

    # 4. Routing and fallback
    def test_routing_and_fallback(self):
        # Health category -> routes to health staff
        health_thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Need BP check.'}
        )
        self.assertEqual(health_thread.assigned_handler, self.health_staff)

        # Peace and order category -> routes to peace staff
        peace_thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'peace_and_order', 'content': 'Noise complaint next door.'}
        )
        self.assertEqual(peace_thread.assigned_handler, self.peace_staff)

        # Unmatched category (e.g. environment) with no assigned officer -> falls back to admin
        other_thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'environment', 'content': 'Uncollected garbage on street.'}
        )
        self.assertEqual(other_thread.assigned_handler, self.admin)

    # 5. Auto "seen"
    def test_auto_seen(self):
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Inquiry about prenatal checkups.'}
        )
        self.assertEqual(thread.status, ChatThread.STATUS_SUBMITTED)

        # Initiator views concern -> stays submitted
        self.client.login(username='resident_one', password='password123')
        self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.STATUS_SUBMITTED)

        # Assigned handler views concern -> automatically transitions to 'seen'
        self.client.login(username='health_officer', password='password123')
        self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.STATUS_SEEN)

    # 6. Invalid status jumps refused
    def test_invalid_status_jumps_refused(self):
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Medicine request.'}
        )
        self.assertEqual(thread.status, ChatThread.STATUS_SUBMITTED)

        # Resident attempts to change status -> PermissionDenied / 403
        with self.assertRaises(PermissionDenied):
            update_concern_status_service(thread, self.resident_1, ChatThread.STATUS_RESOLVED)

        # Handler attempts invalid jump from submitted directly to resolved -> ValueError
        with self.assertRaises(ValueError):
            update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_RESOLVED)

        # Valid step 1: submitted -> in_progress (or seen -> in_progress)
        update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_IN_PROGRESS)
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.STATUS_IN_PROGRESS)

        # Invalid jump: from in_progress back to submitted -> ValueError
        with self.assertRaises(ValueError):
            update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_SUBMITTED)

        # Valid step 2: in_progress -> resolved
        update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_RESOLVED)
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.STATUS_RESOLVED)

        # Valid step 3: reopen resolved -> in_progress
        update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_IN_PROGRESS)
        thread.refresh_from_db()
        self.assertEqual(thread.status, ChatThread.STATUS_IN_PROGRESS)

    # 7. Attachment URL refused for non-participants
    def test_attachment_url_refused_for_non_participants(self):
        img = create_dummy_image('concern_doc.png')
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Prescription attached'},
            attachment_file=img
        )
        first_msg = thread.messages.first()
        self.assertIsNotNone(first_msg.attachment)

        # Initiator has access -> 200
        self.client.login(username='resident_one', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': first_msg.id}))
        self.assertEqual(res.status_code, 200)

        # Assigned handler has access -> 200
        self.client.login(username='health_officer', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': first_msg.id}))
        self.assertEqual(res.status_code, 200)

        # Admin has access -> 200
        self.client.login(username='admin_user', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': first_msg.id}))
        self.assertEqual(res.status_code, 200)

        # Unrelated resident refused -> 403
        self.client.login(username='resident_two', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': first_msg.id}))
        self.assertEqual(res.status_code, 403)

        # Out-of-scope staff refused -> 403
        self.client.login(username='peace_officer', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': first_msg.id}))
        self.assertEqual(res.status_code, 403)

    # 8. Rate limit on new concerns per resident per hour
    def test_rate_limit(self):
        # 3 concerns within an hour are allowed
        for i in range(1, 4):
            create_concern_thread_service(
                resident=self.resident_1,
                data={'category': 'health', 'content': f'Concern #{i}'}
            )

        self.assertEqual(
            ChatThread.objects.filter(initiator=self.resident_1, thread_type=ChatThread.THREAD_CONCERN).count(),
            3
        )

        # 4th concern in the same hour is refused
        with self.assertRaises(PermissionDenied):
            create_concern_thread_service(
                resident=self.resident_1,
                data={'category': 'health', 'content': 'Concern #4 - should be rate limited'}
            )

        # Via HTTP POST in view: user is redirected with an error message, count remains 3
        self.client.login(username='resident_one', password='password123')
        res = self.client.post(reverse('chat:submit_concern'), {
            'category': 'health',
            'content': 'Attempt 4 via view'
        })
        self.assertRedirects(res, reverse('chat:inbox'))
        self.assertEqual(
            ChatThread.objects.filter(initiator=self.resident_1, thread_type=ChatThread.THREAD_CONCERN).count(),
            3
        )

    # 9. Reassignment on disable
    def test_reassignment_on_disable(self):
        # Health staff has 2 open concerns and 1 resolved concern
        open_c1 = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Open concern 1'}
        )
        open_c2 = create_concern_thread_service(
            resident=self.resident_2,
            data={'category': 'health', 'content': 'Open concern 2'}
        )
        resolved_c = create_concern_thread_service(
            resident=self.resident_3,
            data={'category': 'health', 'content': 'Resolved concern'}
        )
        update_concern_status_service(resolved_c, self.health_staff, ChatThread.STATUS_IN_PROGRESS)
        update_concern_status_service(resolved_c, self.health_staff, ChatThread.STATUS_RESOLVED)

        self.assertEqual(open_c1.assigned_handler, self.health_staff)
        self.assertEqual(open_c2.assigned_handler, self.health_staff)
        self.assertEqual(resolved_c.assigned_handler, self.health_staff)

        # Disable health staff user
        self.health_staff.status = User.STATUS_DISABLED
        self.health_staff.save()

        # Check that open concerns were reassigned to admin
        open_c1.refresh_from_db()
        open_c2.refresh_from_db()
        resolved_c.refresh_from_db()

        self.assertEqual(open_c1.assigned_handler, self.admin)
        self.assertEqual(open_c2.assigned_handler, self.admin)
        # Resolved concern was not reassigned
        self.assertEqual(resolved_c.assigned_handler, self.health_staff)

    # 10. Message length cap and HTML escaping
    def test_message_length_and_escaping(self):
        # Length cap: > 2000 chars refused
        long_text = 'A' * 2001
        with self.assertRaises(ValueError):
            create_concern_thread_service(
                resident=self.resident_1,
                data={'category': 'health', 'content': long_text}
            )

        # Raw text storage (no escaping before save, template auto-escapes)
        xss_text = '<script>alert("XSS Attack!")</script><b>Hello</b>'
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': xss_text}
        )
        first_msg = thread.messages.first()
        self.assertEqual(first_msg.content, xss_text)

        # Template renders it escaped
        self.client.login(username='resident_one', password='password123')
        res = self.client.get(reverse('chat:concern_detail', kwargs={'concern_id': thread.id}))
        self.assertContains(res, '&lt;script&gt;')
        self.assertNotContains(res, '<script>alert(')

    # 11. "Message an officer" list shows active officers with name and position only
    def test_message_an_officer_list(self):
        # Create a pending staff and disabled officer to ensure they are excluded
        User.objects.create_user(
            username='disabled_officer',
            email='disabled@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_DISABLED
        )

        self.client.login(username='resident_one', password='password123')
        res = self.client.get(reverse('chat:inbox'))
        self.assertEqual(res.status_code, 200)

        officers = res.context['officers']
        officer_names = [o['name'] for o in officers]
        officer_positions = [o['position'] for o in officers]

        # Active officers are present
        self.assertIn('Admin Barangay', officer_names)
        self.assertIn('Doc Reyes', officer_names)
        self.assertIn('Tanod Bautista', officer_names)

        # Disabled officer is NOT present
        self.assertNotIn('disabled_officer', [o.get('username') for o in officers])

        # Positions are properly populated
        self.assertIn('Health Worker', officer_positions)
        self.assertIn('Barangay Tanod', officer_positions)

    # 12. Chat attachments security (allowlist, real content type, attachment headers, no SVG/HTML)
    def test_attachment_allowlist_and_headers(self):
        # Disallowed extension (e.g. .txt or .docx)
        txt_file = SimpleUploadedFile("notes.txt", b"plain text", content_type="text/plain")
        with self.assertRaises(ValueError):
            create_concern_thread_service(
                resident=self.resident_1,
                data={'category': 'health', 'content': 'Has txt'},
                attachment_file=txt_file
            )

        # Disallowed SVG content disguised as PNG
        svg_file = SimpleUploadedFile("fake.png", b"<svg xmlns='http://www.w3.org/2000/svg'><circle/></svg>", content_type="image/png")
        with self.assertRaises(ValueError):
            create_concern_thread_service(
                resident=self.resident_1,
                data={'category': 'health', 'content': 'Has svg'},
                attachment_file=svg_file
            )

        # Disallowed HTML content
        html_file = SimpleUploadedFile("attack.pdf", b"<html><body>evil</body></html>", content_type="application/pdf")
        with self.assertRaises(ValueError):
            create_concern_thread_service(
                resident=self.resident_1,
                data={'category': 'health', 'content': 'Has html'},
                attachment_file=html_file
            )

        # Valid PDF file
        pdf_file = SimpleUploadedFile("document.pdf", b"%PDF-1.4 valid test pdf content", content_type="application/pdf")
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Valid pdf'},
            attachment_file=pdf_file
        )
        msg = thread.messages.first()

        # Check headers when served
        self.client.login(username='resident_one', password='password123')
        res = self.client.get(reverse('chat:serve_attachment', kwargs={'message_id': msg.id}))
        self.assertEqual(res.status_code, 200)
        self.assertIn('attachment;', res['Content-Disposition'])
        self.assertEqual(res['X-Content-Type-Options'], 'nosniff')

    # 13. Messaging rules: resident only messages active officers; staff messages in-scope residents
    def test_messaging_scoping_rules(self):
        from apps.accounts.models import Purok, Resident
        p1, _ = Purok.objects.get_or_create(name='Purok 1')
        p2, _ = Purok.objects.get_or_create(name='Purok 2')

        Resident.objects.create(
            user=self.resident_1,
            first_name='Juan',
            last_name='One',
            birthdate=datetime.date(1990, 1, 1),
            contact_no='0917-111-1111',
            purok=p1
        )
        Resident.objects.create(
            user=self.resident_2,
            first_name='Maria',
            last_name='Two',
            birthdate=datetime.date(1992, 2, 2),
            contact_no='0917-222-2222',
            purok=p2
        )

        # Resident messaging another resident is refused
        with self.assertRaises(PermissionDenied):
            create_direct_thread_service(
                sender=self.resident_1,
                recipient=self.resident_2,
                raw_content="Hey neighbor"
            )

        # Resident messaging disabled officer is refused
        disabled_officer = User.objects.create_user(
            username='disabled_staff',
            email='disabled_staff@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            status=User.STATUS_DISABLED
        )
        with self.assertRaises(PermissionDenied):
            create_direct_thread_service(
                sender=self.resident_1,
                recipient=disabled_officer,
                raw_content="Hello"
            )

        # Staff with Purok 1 scope may only message Purok 1 resident
        purok_staff = User.objects.create_user(
            username='purok1_leader',
            email='purok1@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            status=User.STATUS_ACTIVE
        )
        StaffAssignment.objects.create(
            user=purok_staff,
            officer=self.health_officer_role,
            scope_type=StaffAssignment.SCOPE_PUROK,
            scope_value='Purok 1'
        )

        # Messaging Resident 1 in Purok 1 -> Success
        msg = create_direct_thread_service(
            sender=purok_staff,
            recipient=self.resident_1,
            raw_content="Notice for Purok 1"
        )
        self.assertIsNotNone(msg)

        # Messaging Resident 2 in Purok 2 -> Refused
        with self.assertRaises(PermissionDenied):
            create_direct_thread_service(
                sender=purok_staff,
                recipient=self.resident_2,
                raw_content="Notice for Purok 2"
            )

    # 14. Concern reassignment action & staff assignment removal signal
    def test_reassignment_actions_and_removal_signal(self):
        from apps.chat.services import reassign_concern_service, resident_request_reassignment_service

        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Consultation'}
        )
        self.assertEqual(thread.assigned_handler, self.health_staff)

        # Current handler reassigns to peace staff
        reassign_concern_service(thread, self.health_staff, self.peace_staff)
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_handler, self.peace_staff)

        # Admin reassigns back to health staff
        reassign_concern_service(thread, self.admin, self.health_staff)
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_handler, self.health_staff)

        # Unauthorized user (resident 2) cannot reassign
        with self.assertRaises(PermissionDenied):
            reassign_concern_service(thread, self.resident_2, self.peace_staff)

        # Resident initiator requests reassignment to admin
        resident_request_reassignment_service(thread, self.resident_1)
        thread.refresh_from_db()
        self.assertEqual(thread.assigned_handler, self.admin)

        # Staff assignment removed -> concerns move to admin queue
        c2 = create_concern_thread_service(
            resident=self.resident_2,
            data={'category': 'health', 'content': 'Checkup'}
        )
        self.assertEqual(c2.assigned_handler, self.health_staff)
        # Delete health_staff's assignment
        StaffAssignment.objects.filter(user=self.health_staff).delete()
        c2.refresh_from_db()
        self.assertEqual(c2.assigned_handler, self.admin)

    # 15. Resident message on resolved concern reopens it and notifies handler
    def test_resident_reply_reopens_resolved_concern(self):
        thread = create_concern_thread_service(
            resident=self.resident_1,
            data={'category': 'health', 'content': 'Flu symptoms'}
        )
        update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_IN_PROGRESS)
        update_concern_status_service(thread, self.health_staff, ChatThread.STATUS_RESOLVED)
        self.assertEqual(thread.status, ChatThread.STATUS_RESOLVED)

        # Resident sends reply
        send_thread_message_service(thread, self.resident_1, "Still having symptoms, please help.")
        thread.refresh_from_db()

        # Automatically reopened to in_progress
        self.assertEqual(thread.status, ChatThread.STATUS_IN_PROGRESS)
        # Notification created for handler
        notif = Notification.objects.filter(recipient=self.health_staff, notification_type=Notification.TYPE_CHAT).latest('created_at')
        self.assertIn("Reopened", notif.title)

    # 16. Admin-editable concern categories
    def test_concern_categories_model(self):
        from apps.chat.models import ConcernCategory
        cat = ConcernCategory.objects.create(
            name='Waste Management',
            slug='waste_management',
            description='Garbage collection issues'
        )
        self.assertEqual(cat.slug, 'waste_management')
        self.assertTrue(cat.is_active)

