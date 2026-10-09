from django.test import TestCase, Client
from django.urls import reverse
from datetime import date
from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.communications.models import Announcement, PostReaction, PostComment
from tests.base import get_clearance_type, get_document_type


class Facebook3ColumnLayoutAndStatsTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Admin
        self.admin = User.objects.create_user(
            username='admin_officer',
            password='adminpassword123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_approved=True,
            first_name='Maria',
            last_name='Santos',
            duty_status='on_duty'
        )

        # Create Kapitan on leave
        self.kapitan = User.objects.create_user(
            username='capt_delacruz',
            password='captpassword123',
            role=User.ROLE_KAPITAN,
            is_approved=True,
            first_name='Juan',
            last_name='Dela Cruz',
            duty_status='on_leave',
            duty_leave_reason='Attending Provincial Liga Summit',
            duty_return_date=date(2026, 10, 15)
        )

        # Create Resident 1: Approved, has active document request
        self.resident1 = User.objects.create_user(
            username='resident_juan',
            password='residentpassword123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            first_name='Juan',
            last_name='Reyes'
        )
        self.appointment1 = Appointment.objects.create(
            resident=self.resident1,
            document_type=get_clearance_type(),
            status=Appointment.STATUS_PENDING,
            appt_date=date.today(),
            purpose='Employment Requirement'
        )
        # Add second active request for same user to test distinct counting
        self.appointment1_b = Appointment.objects.create(
            resident=self.resident1,
            document_type=get_document_type("indigency", "Certificate of Indigency"),
            status=Appointment.STATUS_PENDING,
            appt_date=date.today(),
            purpose='Medical Assistance'
        )

        # Create Resident 2: Approved, has completed document request
        self.resident2 = User.objects.create_user(
            username='resident_maria',
            password='residentpassword123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            first_name='Maria',
            last_name='Clara'
        )
        self.appointment2 = Appointment.objects.create(
            resident=self.resident2,
            document_type=get_document_type("residency", "Certificate of Residency"),
            status=Appointment.STATUS_COMPLETED,
            appt_date=date.today(),
            purpose='Bank Account Opening'
        )

        # Create Resident 3: Unapproved (Pending resident approval)
        self.resident3 = User.objects.create_user(
            username='pending_resident',
            password='residentpassword123',
            role=User.ROLE_RESIDENT,
            is_approved=False,
            first_name='Pedro',
            last_name='Penduko'
        )

        # Create Feed Announcement
        self.announcement = Announcement.objects.create(
            title='Barangay Clean-up Drive 2026',
            content='Join our monthly cleanup along Purok 1 to Purok 7.',
            category=Announcement.CATEGORY_EVENT,
            author=self.admin
        )

    def test_four_unique_resident_metrics_calculation(self):
        """
        Verify distinct resident counting logic for the 4 stat cards:
        1. PENDING DOCUMENT REQUESTS (Distinct User.id count)
        2. PENDING RESIDENTS APPROVAL (Distinct User.id count where is_approved=False)
        3. TOTAL RESIDENTS (Distinct verified User.id where is_approved=True, role='resident')
        4. TOTAL REQUESTS HANDLED (Distinct User.id count where status='completed')
        """
        # 1. Distinct users with active requests: resident1 has 2 active requests, so count must be 1 (distinct)
        pending_docs_distinct = User.objects.filter(
            appointments__status=Appointment.STATUS_PENDING
        ).distinct().count()
        self.assertEqual(pending_docs_distinct, 1)

        # 2. Distinct users where is_approved=False
        pending_residents_distinct = User.objects.filter(is_approved=False).distinct().count()
        self.assertEqual(pending_residents_distinct, 1)

        # 3. Distinct verified residents (resident1, resident2)
        total_residents_distinct = User.objects.filter(
            is_approved=True, role=User.ROLE_RESIDENT
        ).distinct().count()
        self.assertEqual(total_residents_distinct, 2)

        # 4. Distinct users with completed requests (resident2)
        handled_requests_distinct = User.objects.filter(
            appointments__status=Appointment.STATUS_COMPLETED
        ).distinct().count()
        self.assertEqual(handled_requests_distinct, 1)

    def test_feed_view_context_and_layout_render(self):
        """
        Test that the feed renders with Facebook 3-column layout elements,
        stat cards metrics, staff duty roster, and pure flat design tokens.
        """
        self.client.login(username='admin_officer', password='adminpassword123')
        response = self.client.get(reverse('communications:feed'))
        self.assertEqual(response.status_code, 200)

        # Context metrics
        self.assertEqual(response.context['stat_pending_docs_count'], 1)
        self.assertEqual(response.context['stat_pending_residents_count'], 1)
        self.assertEqual(response.context['stat_total_residents_count'], 2)
        self.assertEqual(response.context['stat_handled_requests_count'], 1)

        content = response.content.decode('utf-8')

        # Top Bar Navigation Center Tabs & Icons
        self.assertIn('#lucide-house', content)
        self.assertIn('Home', content)
        self.assertIn('#lucide-megaphone', content)
        self.assertIn('Announcements', content)
        self.assertIn('#lucide-triangle-alert', content)
        self.assertIn('Emergency', content)

        # Top Bar Right Action Group & Icons
        self.assertIn('#lucide-message-square', content)
        self.assertIn('Messages', content)
        self.assertIn('#lucide-bell', content)
        self.assertIn('Notifications', content)
        self.assertIn('#lucide-user', content)

        # Collapsible Left Sidebar Elements & Icons
        self.assertIn('fb-left-sidebar', content)
        self.assertIn('#lucide-chevron-left', content)
        self.assertIn('#lucide-chevron-right', content)
        self.assertIn('Collapse', content)
        self.assertIn('Expand', content)
        self.assertIn('#lucide-calendar-check', content)
        lowered = content.lower()
        self.assertIn('appointments', lowered)
        self.assertIn('#lucide-users', content)
        self.assertIn('residents', lowered)
        self.assertIn('#lucide-folder-open', content)
        self.assertIn('records', lowered)

        # Center Feed Post Card and Interaction Bar with 3-Dots Menu
        self.assertIn('[BARANGAY ADMINISTRATOR]', content)
        self.assertIn('#lucide-ellipsis', content)
        self.assertIn('post-card-menu-container', content)
        self.assertNotIn('Like (', content)
        self.assertNotIn('Support (', content)
        self.assertIn('Comments (', content)


        # Right Sidebar Panel Stat Cards & Plain Header
        self.assertIn('KEY BARANGAY METRICS', content)
        self.assertNotIn('fa-', content)
        self.assertIn('PENDING DOCUMENT REQUESTS', content)
        self.assertIn('PENDING RESIDENTS APPROVAL', content)
        self.assertIn('TOTAL RESIDENTS', content)
        self.assertIn('TOTAL REQUESTS HANDLED', content)

        # Staff Duty Roster & Icons
        self.assertIn('STAFF DUTY ROSTER', content)
        self.assertIn('#lucide-user-round', content)
        self.assertIn('ON-DUTY', content)
        self.assertIn('ON-LEAVE', content)
        self.assertIn('MESSAGE', content)
        self.assertIn('Attending Provincial Liga Summit', content)

    def test_live_reaction_ajax(self):
        """Test AJAX reaction toggle on feed post."""
        self.client.login(username='resident_juan', password='residentpassword123')
        url = reverse('communications:react_post', args=[self.announcement.id])

        # Like the post
        response = self.client.post(
            url,
            {'reaction_type': 'like'},
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['likes_count'], 1)
        self.assertTrue(data['user_has_reacted'])

        # Unlike the post
        response = self.client.post(
            url,
            {'reaction_type': 'like'},
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['likes_count'], 0)
        self.assertFalse(data['user_has_reacted'])

    def test_live_comment_ajax(self):
        """Test AJAX comment posting on feed post."""
        self.client.login(username='resident_juan', password='residentpassword123')
        url = reverse('communications:comment_post', args=[self.announcement.id])

        response = self.client.post(
            url,
            {'content': 'Looking forward to participating in the clean-up!'},
            headers={'x-requested-with': 'XMLHttpRequest'}
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['content'], 'Looking forward to participating in the clean-up!')
        self.assertEqual(data['author'], 'Juan Reyes')
        self.assertEqual(data['initials'], 'JR')
        self.assertEqual(self.announcement.comments.count(), 1)


class HomeAnnouncementEmergencyModulesTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_user',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_approved=True,
            first_name='Admin',
            last_name='Barangay'
        )
        self.staff = User.objects.create_user(
            username='staff_user',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_approved=True,
            first_name='Staff',
            last_name='Member'
        )
        self.resident = User.objects.create_user(
            username='resident_user',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            first_name='Resident',
            last_name='Citizen'
        )

        # Create sample posts across categories
        self.announcement1 = Announcement.objects.create(
            title='Barangay General Assembly',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            content='Annual general meeting.',
            author=self.admin
        )
        self.announcement2 = Announcement.objects.create(
            title='Clean and Green Drive',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            content='Tree planting and road cleanup.',
            author=self.staff
        )
        self.emergency1 = Announcement.objects.create(
            title='Typhoon Signal No. 2 Advisory',
            category=Announcement.CATEGORY_EMERGENCY,
            content='Heavy rainfall and strong winds expected.',
            author=self.admin
        )
        self.event1 = Announcement.objects.create(
            title='Youth Basketball League',
            category=Announcement.CATEGORY_EVENT,
            content='Summer sports fest opening.',
            author=self.admin
        )
        self.scholarship1 = Announcement.objects.create(
            title='Barangay College Educational Assistance',
            category=Announcement.CATEGORY_SCHOLARSHIP,
            content='Scholarship applications open.',
            author=self.admin
        )
        self.donation1 = Announcement.objects.create(
            title='Disaster Relief Donation Drive',
            category=Announcement.CATEGORY_DONATION,
            content='Canned goods and clothing accepted.',
            author=self.admin
        )

    def test_home_feed_admin_and_staff_can_post_edit_delete(self):
        # Login as Staff
        self.client.login(username='staff_user', password='password123')
        
        # Can post without photo
        response = self.client.post(reverse('communications:feed'), {
            'create_post': '1',
            'title': 'Senior Citizens Pension Distribution',
            'category': Announcement.CATEGORY_ANNOUNCEMENT,
            'content': 'Quarterly pension will be released this Friday.',
        }, follow=True)
        self.assertEqual(response.status_code, 200)
        new_post = Announcement.objects.filter(title='Senior Citizens Pension Distribution').first()
        self.assertIsNotNone(new_post)
        self.assertEqual(new_post.category, Announcement.CATEGORY_ANNOUNCEMENT)

        # Staff can edit post
        edit_response = self.client.post(reverse('communications:edit_announcement', args=[new_post.id]), {
            'title': 'Senior Citizens Pension Distribution (Rescheduled)',
            'category': Announcement.CATEGORY_ANNOUNCEMENT,
            'content': 'Updated schedule.',
        }, follow=True)
        self.assertEqual(edit_response.status_code, 200)
        new_post.refresh_from_db()
        self.assertEqual(new_post.title, 'Senior Citizens Pension Distribution (Rescheduled)')

        # Staff can delete (archive) post
        del_response = self.client.post(reverse('communications:delete_announcement', args=[new_post.id]), follow=True)
        self.assertEqual(del_response.status_code, 200)
        new_post.refresh_from_db()
        self.assertEqual(new_post.state, Announcement.STATE_ARCHIVED)
        self.assertFalse(Announcement.objects.filter(id=new_post.id, state=Announcement.STATE_ACTIVE).exists())

    def test_resident_can_only_view_home_feed(self):
        self.client.login(username='resident_user', password='password123')
        response = self.client.get(reverse('communications:feed'))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['can_publish'])
        self.assertNotContains(response, 'CREATE NEW POST')
        self.assertNotContains(response, 'title="Edit Post"')
        self.assertNotContains(response, 'title="Delete Post"')

        # Resident is blocked with 403 if attempting to access edit/delete directly
        edit_attempt = self.client.get(reverse('communications:edit_announcement', args=[self.announcement1.id]))
        self.assertEqual(edit_attempt.status_code, 403)
        delete_attempt = self.client.post(reverse('communications:delete_announcement', args=[self.announcement1.id]))
        self.assertEqual(delete_attempt.status_code, 403)

    def test_announcement_module_displays_unique_announcements_and_counts(self):
        self.client.login(username='resident_user', password='password123')
        response = self.client.get(reverse('communications:announcements_list'))
        self.assertEqual(response.status_code, 200)
        # Unique announcements count should be 2
        self.assertEqual(response.context['unique_count'], 2)
        self.assertContains(response, 'Official Announcements')
        self.assertContains(response, 'Barangay General Assembly')
        self.assertContains(response, 'Clean and Green Drive')
        # Emergency alerts should NOT be in this module
        self.assertNotContains(response, 'Typhoon Signal No. 2 Advisory')

    def test_emergency_module_displays_all_emergencies_and_counts(self):
        self.client.login(username='resident_user', password='password123')
        response = self.client.get(reverse('communications:emergency_list'))
        self.assertEqual(response.status_code, 200)
        # Emergency alerts count should be 1
        self.assertEqual(response.context['unique_count'], 1)
        self.assertContains(response, 'Emergency Alerts')
        self.assertContains(response, 'Typhoon Signal No. 2 Advisory')
        # Standard announcements should NOT be in this module
        self.assertNotContains(response, 'Clean and Green Drive')


class FacebookPostModalAndCategoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin = User.objects.create_user(
            username='admin_fb',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            first_name='Admin',
            last_name='User'
        )
        self.resident = User.objects.create_user(
            username='res_fb',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            first_name='Resident',
            last_name='User'
        )

    def test_trigger_bar_and_modal_present_for_admin_and_hidden_for_resident(self):
        from apps.communications.models import PostCategory

        # Admin view has trigger bar and modal
        self.client.login(username='admin_fb', password='password123')
        res_admin = self.client.get(reverse('communications:feed'))
        self.assertEqual(res_admin.status_code, 200)
        self.assertContains(res_admin, 'post-trigger-card')
        self.assertContains(res_admin, 'Post an announcement for residents')
        self.assertContains(res_admin, 'id="createPostModal"')
        self.assertContains(res_admin, 'id="postCategorySelect"')

        # Resident view has neither trigger bar nor modal
        self.client.login(username='res_fb', password='password123')
        res_user = self.client.get(reverse('communications:feed'))
        self.assertEqual(res_user.status_code, 200)
        self.assertNotContains(res_user, 'post-trigger-card')
        self.assertNotContains(res_user, 'id="createPostModal"')

    def test_post_creation_from_modal_with_dynamic_category(self):
        from apps.communications.models import PostCategory, Post, Announcement

        self.client.login(username='admin_fb', password='password123')
        # Create a custom category dynamically
        cat = PostCategory.objects.create(name='Senior Citizens Assistance', description='Aid for seniors')

        # Post via Facebook modal with custom category
        post_data = {
            'create_post': '1',
            'title': 'Senior Citizen Monthly Pension Distribution',
            'category': 'Senior Citizens Assistance',
            'content': 'Please proceed to the Barangay Hall on Monday for distribution.',
        }
        resp = self.client.post(reverse('communications:feed'), data=post_data, follow=True)
        self.assertEqual(resp.status_code, 200)

        # Verify Announcement created with category_ref
        announcement = Announcement.objects.filter(title='Senior Citizen Monthly Pension Distribution').first()
        self.assertIsNotNone(announcement)
        self.assertEqual(announcement.category_ref, cat)
        self.assertEqual(announcement.author, self.admin)

        # Verify Post created
        post_obj = Post.objects.filter(category_ref=cat).first()
        self.assertIsNotNone(post_obj)
        self.assertEqual(post_obj.author, self.admin)
        self.assertIn('distribution', post_obj.content)

        # Verify dynamic category rendered in modal dropdown
        res = self.client.get(reverse('communications:feed'))
        self.assertContains(res, 'Senior Citizens Assistance')

    def test_three_dots_action_menu_and_removed_reactions_and_consistent_edit(self):
        from apps.communications.models import Announcement

        post = Announcement.objects.create(
            title='Barangay Tree Planting Project',
            content='Everyone is invited to join on Saturday.',
            category=Announcement.CATEGORY_EVENT,
            author=self.admin
        )

        self.client.login(username='admin_fb', password='password123')
        res = self.client.get(reverse('communications:feed'))
        self.assertEqual(res.status_code, 200)

        # 3-dots floating menu is rendered
        self.assertContains(res, 'post-card-menu-container')
        self.assertContains(res, 'post-menu-trigger')
        self.assertContains(res, 'post-dropdown-menu')
        self.assertContains(res, 'Edit Post')
        self.assertContains(res, 'Delete Post')

        # Reaction buttons (like, support, important) are removed
        self.assertNotContains(res, 'btn-primary reaction-btn')
        self.assertNotContains(res, 'name="reaction_type"')

        # Edit post modal is present on the page
        self.assertContains(res, 'id="editPostModal"')
        self.assertContains(res, 'id="editPostCategorySelect"')

        # Standalone edit view has consistent Facebook-style card design
        edit_page = self.client.get(reverse('communications:edit_announcement', args=[post.id]))
        self.assertEqual(edit_page.status_code, 200)
        self.assertContains(edit_page, 'post-standalone-card-container')
        self.assertContains(edit_page, 'category-select-pill')
        self.assertContains(edit_page, 'post-modal-content')

    def test_create_post_with_and_without_photo_and_title_fallback(self):
        from apps.communications.models import Announcement
        from django.core.files.uploadedfile import SimpleUploadedFile
        from tests.base import PNG_BYTES

        self.client.login(username='admin_fb', password='password123')

        # 1. Post without photo and without title (title fallback)
        post_data_no_photo = {
            'create_post': '1',
            'content': 'Notice: Power interruption scheduled tomorrow from 8 AM to 5 PM.',
            'category': 'announcement',
        }
        resp = self.client.post(reverse('communications:feed'), data=post_data_no_photo, follow=True)
        self.assertEqual(resp.status_code, 200)
        p1 = Announcement.objects.filter(content__startswith='Notice: Power interruption').first()
        self.assertIsNotNone(p1)
        self.assertTrue(len(p1.title) > 0)
        self.assertFalse(bool(p1.image))

        # 2. Post with photo
        from io import BytesIO
        from PIL import Image
        img = Image.new('RGB', (64, 64), color='#1E3A8A')
        buf = BytesIO()
        img.save(buf, format='PNG')
        buf.seek(0)
        photo = SimpleUploadedFile('poster.png', buf.getvalue(), content_type='image/png')
        post_data_with_photo = {
            'create_post': '1',
            'title': 'Barangay Sports Festival 2026',
            'content': 'Registration is now open at the gymnasium.',
            'category': 'event',
            'image': photo,
        }
        resp2 = self.client.post(reverse('communications:feed'), data=post_data_with_photo, follow=True)
        self.assertEqual(resp2.status_code, 200)
        p2 = Announcement.objects.filter(title='Barangay Sports Festival 2026').first()
        self.assertIsNotNone(p2)
        self.assertTrue(bool(p2.image))

    def test_post_pin_and_unpin_action(self):
        from apps.communications.models import Announcement

        post = Announcement.objects.create(
            title='Purok Meeting Notice',
            content='General meeting for Purok 4.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            author=self.admin,
            is_pinned=False
        )

        self.client.login(username='admin_fb', password='password123')

        # Pin post
        resp = self.client.post(reverse('communications:toggle_pin_announcement', args=[post.id]), follow=True)
        self.assertEqual(resp.status_code, 200)
        post.refresh_from_db()
        self.assertTrue(post.is_pinned)

        # Unpin post
        resp2 = self.client.post(reverse('communications:toggle_pin_announcement', args=[post.id]), follow=True)
        self.assertEqual(resp2.status_code, 200)
        post.refresh_from_db()
        self.assertFalse(post.is_pinned)

    def test_edit_and_delete_post_actions(self):
        from apps.communications.models import Announcement

        post = Announcement.objects.create(
            title='Old Title',
            content='Old content details',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            author=self.admin
        )

        self.client.login(username='admin_fb', password='password123')

        # Edit post
        edit_data = {
            'title': 'Updated Title',
            'content': 'Updated content details for residents',
            'category': Announcement.CATEGORY_EVENT,
        }
        resp = self.client.post(reverse('communications:edit_announcement', args=[post.id]), data=edit_data, follow=True)
        self.assertEqual(resp.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.title, 'Updated Title')
        self.assertEqual(post.content, 'Updated content details for residents')

        # Delete post (soft-archive)
        del_resp = self.client.post(reverse('communications:delete_announcement', args=[post.id]), follow=True)
        self.assertEqual(del_resp.status_code, 200)
        post.refresh_from_db()
        self.assertEqual(post.state, Announcement.STATE_ARCHIVED)

    def test_login_redirects_to_home(self):
        resp = self.client.post(reverse('accounts:login'), {
            'username': 'admin_fb',
            'password': 'password123',
        })
        self.assertRedirects(resp, reverse('home'))


