import datetime
import calendar
import zoneinfo
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from django.core.management import call_command
from django.core.exceptions import PermissionDenied

from apps.accounts.models import User, Purok, Resident, StaffAssignment, PermissionRule
from apps.communications.models import Announcement
from apps.communications.services import (
    create_post_service,
    extend_post_service,
    mark_post_done_service,
    expire_posts_service,
    get_active_posts_queryset,
    get_manila_month_end,
)
from apps.history.models import ActivityLog


class PartDCommunicationsTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.manila_tz = zoneinfo.ZoneInfo("Asia/Manila")

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_user',
            email='admin@barangay.ph',
            password='password123',
            role=User.ROLE_ADMIN,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE
        )

        # Puroks
        self.purok_1, _ = Purok.objects.get_or_create(name='Purok 1')
        self.purok_2, _ = Purok.objects.get_or_create(name='Purok 2')

        # Resident in Purok 1
        self.resident_p1 = User.objects.create_user(
            username='resident_p1',
            email='resident1@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE
        )
        self.resident_profile_p1 = Resident.objects.create(
            user=self.resident_p1,
            first_name='Juan',
            last_name='PurokOne',
            birthdate=datetime.date(1995, 5, 20),
            contact_no='0917-000-1111',
            purok=self.purok_1
        )

        # Resident in Purok 2
        self.resident_p2 = User.objects.create_user(
            username='resident_p2',
            email='resident2@barangay.ph',
            password='password123',
            role=User.ROLE_RESIDENT,
            is_approved=True,
            status=User.STATUS_ACTIVE
        )
        self.resident_profile_p2 = Resident.objects.create(
            user=self.resident_p2,
            first_name='Maria',
            last_name='PurokTwo',
            birthdate=datetime.date(1998, 8, 15),
            contact_no='0917-000-2222',
            purok=self.purok_2
        )

        # Health Officer (Staff with only post_health permission)
        self.health_staff = User.objects.create_user(
            username='health_officer',
            email='health@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE
        )
        from apps.accounts.models import Officer
        self.health_officer_record = Officer.objects.create(
            position='Health Worker',
            committee='Health'
        )
        self.rule_health = PermissionRule.objects.create(
            officer=self.health_officer_record,
            module='communications',
            action='post_health',
            allowed=True
        )
        StaffAssignment.objects.create(
            user=self.health_staff,
            officer=self.health_officer_record,
            scope_type=StaffAssignment.SCOPE_SERVICE_AREA,
            scope_value='Health'
        )

        # Base active announcement
        self.sample_announcement = Announcement.objects.create(
            title='General Assembly Notice',
            content='Everyone is invited to attend the quarterly barangay assembly.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            audience_type=Announcement.AUDIENCE_EVERYONE,
            state=Announcement.STATE_ACTIVE,
            author=self.admin
        )

    # 1. Resident 403 on all post URLs
    def test_resident_403_on_all_post_urls(self):
        self.client.login(username='resident_p1', password='password123')

        # Create URLs
        res = self.client.get(reverse('communications:create_announcement'))
        self.assertEqual(res.status_code, 403)

        res = self.client.get(reverse('communications:create_announcement_alias'))
        self.assertEqual(res.status_code, 403)

        res = self.client.post(reverse('communications:create_announcement'), {
            'title': 'Resident Post Attempt',
            'content': 'Attempting to create',
            'category': Announcement.CATEGORY_ANNOUNCEMENT,
        })
        self.assertEqual(res.status_code, 403)

        # Feed post attempt
        res = self.client.post(reverse('communications:feed'), {
            'create_post': '1',
            'title': 'Feed Post Attempt',
            'content': 'Attempting to post on feed',
        })
        self.assertEqual(res.status_code, 403)

        # Announcements list post attempt
        res = self.client.post(reverse('communications:announcements_list'), {
            'create_post': '1',
            'title': 'Announcements List Attempt',
            'content': 'Attempting to post',
        })
        self.assertEqual(res.status_code, 403)

        # Emergency list post attempt
        res = self.client.post(reverse('communications:emergency_list'), {
            'create_post': '1',
            'title': 'Emergency Alert Attempt',
            'content': 'Attempting emergency post',
        })
        self.assertEqual(res.status_code, 403)

        # Edit post attempt
        res = self.client.get(reverse('communications:edit_announcement', args=[self.sample_announcement.id]))
        self.assertEqual(res.status_code, 403)

        res = self.client.post(reverse('communications:edit_announcement', args=[self.sample_announcement.id]), {
            'title': 'Hacked Title',
            'content': 'Hacked content',
        })
        self.assertEqual(res.status_code, 403)

        # Delete post attempt
        res = self.client.post(reverse('communications:delete_announcement', args=[self.sample_announcement.id]))
        self.assertEqual(res.status_code, 403)

        # Extend post attempt
        res = self.client.get(reverse('communications:extend_announcement', args=[self.sample_announcement.id]))
        self.assertEqual(res.status_code, 403)

        res = self.client.post(reverse('communications:extend_announcement', args=[self.sample_announcement.id]), {
            'new_valid_until': (timezone.now() + datetime.timedelta(days=10)).isoformat()
        })
        self.assertEqual(res.status_code, 403)

        # Mark done post attempt
        res = self.client.get(reverse('communications:mark_done_announcement', args=[self.sample_announcement.id]))
        self.assertEqual(res.status_code, 403)

        res = self.client.post(reverse('communications:mark_done_announcement', args=[self.sample_announcement.id]))
        self.assertEqual(res.status_code, 403)

        # Resident does not see Post New button in feed
        res = self.client.get(reverse('communications:feed'))
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.context['can_publish'])
        self.assertNotContains(res, 'id="createPostModal"')

    # 2. Health officer can post health but not emergency
    def test_health_officer_can_post_health_but_not_emergency(self):
        # Service level: Health officer can post health
        health_post = create_post_service(
            author=self.health_staff,
            data={
                'title': 'Measles Vaccination Drive',
                'content': 'Free immunization this coming Saturday at Health Center.',
                'category': Announcement.CATEGORY_HEALTH,
            }
        )
        self.assertIsNotNone(health_post)
        self.assertEqual(health_post.category, Announcement.CATEGORY_HEALTH)

        # Service level: Health officer cannot post emergency
        with self.assertRaises(PermissionDenied):
            create_post_service(
                author=self.health_staff,
                data={
                    'title': 'Typhoon Warning Alert',
                    'content': 'Typhoon approaching barangay.',
                    'category': Announcement.CATEGORY_EMERGENCY,
                }
            )

        # View level: Health officer posting health
        self.client.login(username='health_officer', password='password123')
        res_health = self.client.post(reverse('communications:create_announcement'), {
            'title': 'Dengue Prevention Fogging',
            'content': 'Fogging scheduled for Purok 1 and Purok 2.',
            'category': Announcement.CATEGORY_HEALTH,
        }, follow=True)
        self.assertEqual(res_health.status_code, 200)
        self.assertTrue(Announcement.objects.filter(title='Dengue Prevention Fogging').exists())

        # View level: Health officer posting emergency gets 403
        res_emergency = self.client.post(reverse('communications:create_announcement'), {
            'title': 'Emergency Flashflood Alert',
            'content': 'Severe flooding in low-lying zones.',
            'category': Announcement.CATEGORY_EMERGENCY,
        })
        self.assertEqual(res_emergency.status_code, 403)

    # 3. Audience filtering: residents see everyone-posts plus their own purok's
    def test_audience_filtering(self):
        post_everyone = Announcement.objects.create(
            title='Barangay-Wide Announcement',
            content='Open to all residents.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            audience_type=Announcement.AUDIENCE_EVERYONE,
            state=Announcement.STATE_ACTIVE,
            author=self.admin
        )
        post_purok1 = Announcement.objects.create(
            title='Purok 1 Water Interruption',
            content='Maintenance on Purok 1 water lines.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            audience_type=Announcement.AUDIENCE_PUROK,
            purok=self.purok_1,
            state=Announcement.STATE_ACTIVE,
            author=self.admin
        )
        post_purok2 = Announcement.objects.create(
            title='Purok 2 Road Clearing',
            content='Clearing operations along Purok 2 main road.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            audience_type=Announcement.AUDIENCE_PUROK,
            purok=self.purok_2,
            state=Announcement.STATE_ACTIVE,
            author=self.admin
        )

        # Resident in Purok 1
        p1_feed = list(get_active_posts_queryset(self.resident_p1))
        self.assertIn(post_everyone, p1_feed)
        self.assertIn(post_purok1, p1_feed)
        self.assertNotIn(post_purok2, p1_feed)

        # Resident in Purok 2
        p2_feed = list(get_active_posts_queryset(self.resident_p2))
        self.assertIn(post_everyone, p2_feed)
        self.assertIn(post_purok2, p2_feed)
        self.assertNotIn(post_purok1, p2_feed)

        # Admin sees all
        admin_feed = list(get_active_posts_queryset(self.admin))
        self.assertIn(post_everyone, admin_feed)
        self.assertIn(post_purok1, admin_feed)
        self.assertIn(post_purok2, admin_feed)

    # 4. Health posts default valid_until to 23:59:59 on the last day of the month in Asia/Manila
    def test_health_post_month_end_default_in_manila_time(self):
        now_utc = timezone.now()
        now_manila = now_utc.astimezone(self.manila_tz)
        _, last_day = calendar.monthrange(now_manila.year, now_manila.month)

        health_post = create_post_service(
            author=self.admin,
            data={
                'title': 'Monthly Child Wellness Check',
                'content': 'Free checkups for children under 5.',
                'category': Announcement.CATEGORY_HEALTH,
            }
        )

        self.assertIsNotNone(health_post.valid_until)
        manila_valid_until = health_post.valid_until.astimezone(self.manila_tz)
        self.assertEqual(manila_valid_until.year, now_manila.year)
        self.assertEqual(manila_valid_until.month, now_manila.month)
        self.assertEqual(manila_valid_until.day, last_day)
        self.assertEqual(manila_valid_until.hour, 23)
        self.assertEqual(manila_valid_until.minute, 59)
        self.assertEqual(manila_valid_until.second, 59)

    # 5. Expired post hidden without the command (query-time filtering)
    def test_expired_post_hidden_without_command(self):
        past_date = timezone.now() - datetime.timedelta(days=2)
        expired_post = Announcement.objects.create(
            title='Expired Community Drive',
            content='This was held 2 days ago.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            audience_type=Announcement.AUDIENCE_EVERYONE,
            state=Announcement.STATE_ACTIVE, # state still marked active
            valid_until=past_date,
            author=self.admin
        )

        active_posts = get_active_posts_queryset(self.admin)
        self.assertNotIn(expired_post, active_posts)

    # 6. Command safe to run twice (idempotent)
    def test_expire_command_safe_to_run_twice(self):
        past_date = timezone.now() - datetime.timedelta(hours=5)
        post_to_expire = Announcement.objects.create(
            title='Old Alert',
            content='Finished advisory.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            state=Announcement.STATE_ACTIVE,
            valid_until=past_date,
            author=self.admin
        )

        # Run 1: Should mark 1 post as expired
        count1 = expire_posts_service()
        self.assertEqual(count1, 1)
        post_to_expire.refresh_from_db()
        self.assertEqual(post_to_expire.state, Announcement.STATE_EXPIRED)

        # Run 2: Should find 0 posts to expire and exit cleanly
        count2 = expire_posts_service()
        self.assertEqual(count2, 0)

        # Also test via management command
        call_command('expire_posts')
        post_to_expire.refresh_from_db()
        self.assertEqual(post_to_expire.state, Announcement.STATE_EXPIRED)

    # 7. Extend with a past/earlier date refused
    def test_extend_with_past_or_earlier_date_refused(self):
        current_valid_until = timezone.now() + datetime.timedelta(days=3)
        post = Announcement.objects.create(
            title='Post to Extend',
            content='Extensible announcement.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            state=Announcement.STATE_ACTIVE,
            valid_until=current_valid_until,
            author=self.admin
        )

        # Attempt to extend with past date -> refused
        past_date = timezone.now() - datetime.timedelta(days=1)
        with self.assertRaises(ValueError):
            extend_post_service(post, self.admin, past_date)

        # Attempt to extend with earlier date than current_valid_until -> refused
        earlier_date = current_valid_until - datetime.timedelta(days=1)
        with self.assertRaises(ValueError):
            extend_post_service(post, self.admin, earlier_date)

        # Attempt to extend with equal date -> refused
        with self.assertRaises(ValueError):
            extend_post_service(post, self.admin, current_valid_until)

        # Valid extension later than current date -> succeeds and writes ActivityLog
        new_valid = current_valid_until + datetime.timedelta(days=7)
        extended_post = extend_post_service(post, self.admin, new_valid)
        self.assertEqual(extended_post.valid_until, new_valid)
        self.assertTrue(ActivityLog.objects.filter(target_id=str(post.id), details__icontains='Extended').exists())

        # Test mark_done service
        marked_post = mark_post_done_service(extended_post, self.admin)
        self.assertEqual(marked_post.state, Announcement.STATE_DONE)
        self.assertTrue(ActivityLog.objects.filter(target_id=str(post.id), details__icontains='done').exists())

    # 8. Existing posts backfilled are still shown on feed
    def test_existing_backfilled_posts_still_shown(self):
        backfilled_post = Announcement.objects.create(
            title='Legacy Migrated Announcement',
            content='Originally created before Part D migrations.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            audience_type=Announcement.AUDIENCE_EVERYONE,
            purok=None,
            state=Announcement.STATE_ACTIVE,
            valid_until=None, # no expiration
            author=self.admin
        )

        # Must appear in active posts for both residents and admins
        feed_resident = list(get_active_posts_queryset(self.resident_p1))
        self.assertIn(backfilled_post, feed_resident)

        feed_admin = list(get_active_posts_queryset(self.admin))
        self.assertIn(backfilled_post, feed_admin)

    # 9. Purok-scoped staff member may only choose their own purok
    def test_purok_scoped_staff_audience_restriction(self):
        from apps.accounts.models import Officer
        purok_staff = User.objects.create_user(
            username='leader_p1',
            email='leader1@barangay.ph',
            password='password123',
            role=User.ROLE_STAFF,
            is_staff=True,
            is_approved=True,
            status=User.STATUS_ACTIVE
        )
        leader_officer = Officer.objects.create(position='Purok Leader', committee='')
        PermissionRule.objects.create(
            officer=leader_officer,
            module='communications',
            action='post_announcement',
            allowed=True
        )
        StaffAssignment.objects.create(
            user=purok_staff,
            officer=leader_officer,
            scope_type=StaffAssignment.SCOPE_PUROK,
            scope_value='Purok 1'
        )

        # Choosing "everyone" is refused
        with self.assertRaises(PermissionDenied):
            create_post_service(
                author=purok_staff,
                data={
                    'title': 'General Notice',
                    'content': 'Attempt to post to everyone',
                    'category': Announcement.CATEGORY_ANNOUNCEMENT,
                    'audience_type': Announcement.AUDIENCE_EVERYONE,
                }
            )

        # Choosing another purok (Purok 2) is refused
        with self.assertRaises(PermissionDenied):
            create_post_service(
                author=purok_staff,
                data={
                    'title': 'Purok 2 Notice',
                    'content': 'Attempt to post to Purok 2',
                    'category': Announcement.CATEGORY_ANNOUNCEMENT,
                    'audience_type': Announcement.AUDIENCE_PUROK,
                    'purok': self.purok_2,
                }
            )

        # Choosing assigned purok (Purok 1) succeeds
        post = create_post_service(
            author=purok_staff,
            data={
                'title': 'Purok 1 Assembly',
                'content': 'Assembly for Purok 1 residents only',
                'category': Announcement.CATEGORY_ANNOUNCEMENT,
                'audience_type': Announcement.AUDIENCE_PUROK,
                'purok': self.purok_1,
            }
        )
        self.assertIsNotNone(post)
        self.assertEqual(post.purok, self.purok_1)

    # 10. Soft archive replaces hard delete and hides from active feed
    def test_soft_archive_replaces_delete(self):
        post = Announcement.objects.create(
            title='Post to Delete',
            content='Content to be deleted.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            state=Announcement.STATE_ACTIVE,
            author=self.admin
        )
        self.client.login(username='admin_user', password='password123')
        res = self.client.post(reverse('communications:delete_announcement', args=[post.id]))
        self.assertEqual(res.status_code, 302)

        # Verify record still exists in DB but state is 'archived'
        post.refresh_from_db()
        self.assertEqual(post.state, Announcement.STATE_ARCHIVED)
        self.assertNotIn(post, get_active_posts_queryset(self.admin))

    # 11. Extend on a done post is refused, but reopen succeeds
    def test_extend_on_done_post_refused_and_reopen_works(self):
        post = Announcement.objects.create(
            title='Done Post',
            content='Finished post.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            state=Announcement.STATE_DONE,
            valid_until=timezone.now() + datetime.timedelta(days=2),
            author=self.admin
        )

        # Extend on done post must raise ValueError
        with self.assertRaises(ValueError):
            extend_post_service(post, self.admin, timezone.now() + datetime.timedelta(days=5))

        # Reopen service
        from apps.communications.services import reopen_post_service
        reopened = reopen_post_service(post, self.admin)
        self.assertEqual(reopened.state, Announcement.STATE_ACTIVE)
        self.assertIn(reopened, get_active_posts_queryset(self.admin))

    # 12. Feed respects valid_from (hidden until start date)
    def test_feed_respects_valid_from_in_future(self):
        future_post = Announcement.objects.create(
            title='Future Post',
            content='This starts next week.',
            category=Announcement.CATEGORY_ANNOUNCEMENT,
            state=Announcement.STATE_ACTIVE,
            valid_from=timezone.now() + datetime.timedelta(days=7),
            author=self.admin
        )
        active_feed = get_active_posts_queryset(self.admin)
        self.assertNotIn(future_post, active_feed)

    # 13. Manage history view accessible by staff/admin and 403 for resident
    def test_manage_history_view_access(self):
        self.client.login(username='resident_p1', password='password123')
        res_res = self.client.get(reverse('communications:manage_history'))
        self.assertEqual(res_res.status_code, 403)

        self.client.login(username='admin_user', password='password123')
        res_admin = self.client.get(reverse('communications:manage_history'))
        self.assertEqual(res_admin.status_code, 200)

