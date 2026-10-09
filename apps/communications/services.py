import calendar
import datetime
import os
import zoneinfo
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.models import User, Purok, StaffAssignment
from apps.accounts.permissions import check_user_perm
from apps.communications.models import Announcement
from apps.history.utils import log_activity
from apps.chat.models import Notification


def validate_post_image(image_file):
    """
    Validates image file size (max 5MB), extension, and verifies image content using Pillow.
    """
    if not image_file:
        return
    max_size = 5 * 1024 * 1024
    if image_file.size > max_size:
        raise ValueError("Image file size cannot exceed 5MB.")

    valid_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']
    ext = os.path.splitext(image_file.name)[1].lower()
    if ext not in valid_extensions:
        raise ValueError("Invalid image file format. Supported formats: JPG, PNG, WEBP, GIF.")

    try:
        from PIL import Image
        image_file.seek(0)
        img = Image.open(image_file)
        img.verify()
        image_file.seek(0)
    except Exception:
        raise ValueError("Invalid or corrupted image content. The uploaded file is not a valid image.")


def get_manila_month_end(dt=None):
    """
    Returns 23:59:59 on the last day of the current month in Asia/Manila timezone.
    """
    manila_tz = zoneinfo.ZoneInfo("Asia/Manila")
    if dt is None:
        dt = timezone.now()
    dt_manila = dt.astimezone(manila_tz)
    _, last_day = calendar.monthrange(dt_manila.year, dt_manila.month)
    return dt_manila.replace(day=last_day, hour=23, minute=59, second=59, microsecond=0)


def check_can_post_category(user, category):
    """
    Checks per-category posting permission for a given user.
    Residents are strictly denied (False).
    Admin and superusers are unconditionally allowed.
    Staff users are verified against their assigned permission rules.
    """
    if not user.is_authenticated or user.role == User.ROLE_RESIDENT:
        return False
    if user.role == User.ROLE_ADMIN or user.is_superuser:
        return True

    from apps.communications.models import PostCategory
    cat_obj = PostCategory.objects.filter(
        Q(slug__iexact=category) | Q(name__iexact=category)
    ).first()
    if cat_obj:
        slug = cat_obj.slug or cat_obj.name.lower().replace(' ', '_')
        if check_user_perm(user, 'communications', f"post_{slug}"):
            return True

    action_map = {
        Announcement.CATEGORY_ANNOUNCEMENT: 'post_announcement',
        Announcement.CATEGORY_HEALTH: 'post_health',
        Announcement.CATEGORY_EMERGENCY: 'post_emergency',
        Announcement.CATEGORY_EDUCATION: 'post_education',
        Announcement.CATEGORY_EVENT: 'post_event',
        Announcement.CATEGORY_CONCERN: 'post_concern',
        'general': 'post_announcement',
        'scholarship': 'post_education',
        'donation': 'post_announcement',
        'legislative': 'post_announcement',
        'ordinance': 'post_announcement',
    }
    action = action_map.get(category, 'post_announcement')
    return check_user_perm(user, 'communications', action)


def create_post_service(author, data, image_file=None, request=None):
    """
    Creates a new post/announcement:
    - Enforces category check and per-category permission check.
    - Residents are blocked with PermissionDenied (HTTP 403).
    - Image validation: size <= 5MB, format check, Pillow content verification.
    - Purok-scoped staff member may only choose their assigned purok as audience.
    - Audience filtering: everyone or specific purok.
    - Health posts default valid_until to 23:59:59 on last day of month in Asia/Manila.
    - Emergency posts do not expire by schedule (valid_until=None) and notify residents on commit.
    - Sets state='active'.
    - Records ActivityLog.
    """
    if not author.is_authenticated or author.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents are not permitted to publish public feed posts.")

    title = data.get('title', '').strip()
    if not title:
        content_preview = (data.get('content') or '').strip().split('\n')[0][:50].strip()
        title = content_preview or 'Barangay Announcement'

    content = data.get('content', '').strip()
    if not content:
        raise ValueError("Post content is required.")

    category = data.get('category', Announcement.CATEGORY_ANNOUNCEMENT).strip().lower()
    if not check_can_post_category(author, category):
        raise PermissionDenied(f"You do not have permission to publish '{category}' posts.")

    if image_file:
        validate_post_image(image_file)

    audience_type = data.get('audience_type', Announcement.AUDIENCE_EVERYONE)
    if audience_type not in [Announcement.AUDIENCE_EVERYONE, Announcement.AUDIENCE_PUROK]:
        audience_type = Announcement.AUDIENCE_EVERYONE

    purok_obj = None
    if audience_type == Announcement.AUDIENCE_PUROK:
        purok_val = data.get('purok')
        if isinstance(purok_val, Purok):
            purok_obj = purok_val
        elif purok_val and str(purok_val).isdigit():
            purok_obj = Purok.objects.filter(id=int(purok_val)).first()
        elif purok_val:
            purok_obj = Purok.objects.filter(name=str(purok_val)).first()

    # Rule 2: A purok-scoped staff member may ONLY choose their own purok as the audience (not "everyone" and not another purok)
    if author.role != User.ROLE_ADMIN and not author.is_superuser:
        purok_assignments = author.staff_assignments.filter(scope_type=StaffAssignment.SCOPE_PUROK)
        service_assignments = author.staff_assignments.filter(scope_type=StaffAssignment.SCOPE_SERVICE_AREA)
        if purok_assignments.exists() and not service_assignments.exists():
            assigned_purok_names = [a.scope_value.strip().lower() for a in purok_assignments]
            if audience_type != Announcement.AUDIENCE_PUROK or not purok_obj:
                raise PermissionDenied("Purok-scoped staff members may only publish posts to their assigned Purok (not 'Everyone').")
            if purok_obj.name.strip().lower() not in assigned_purok_names:
                raise PermissionDenied("Purok-scoped staff members may only publish posts to their assigned Purok.")

    valid_from = data.get('valid_from') or timezone.now()
    if isinstance(valid_from, str):
        try:
            valid_from = datetime.datetime.fromisoformat(valid_from.strip())
            if timezone.is_naive(valid_from):
                valid_from = timezone.make_aware(valid_from, zoneinfo.ZoneInfo("Asia/Manila"))
        except ValueError:
            valid_from = timezone.now()

    valid_until = data.get('valid_until')

    # Date handling per category settings
    from apps.communications.models import PostCategory
    cat_setting = PostCategory.objects.filter(
        Q(slug__iexact=category) | Q(name__iexact=category)
    ).first()

    if cat_setting:
        if not cat_setting.expires:
            valid_until = None
        elif cat_setting.default_end == 'end_of_month' and not valid_until:
            valid_until = get_manila_month_end(valid_from)
        elif not valid_until and cat_setting.slug == 'health':
            valid_until = get_manila_month_end(valid_from)
    elif category == Announcement.CATEGORY_HEALTH and not valid_until:
        valid_until = get_manila_month_end(valid_from)
    elif category == Announcement.CATEGORY_EMERGENCY:
        valid_until = None

    if valid_until and isinstance(valid_until, str):
        try:
            valid_until = datetime.datetime.fromisoformat(valid_until.strip())
            if timezone.is_naive(valid_until):
                valid_until = timezone.make_aware(valid_until, zoneinfo.ZoneInfo("Asia/Manila"))
        except ValueError:
            valid_until = None

    is_pinned = bool(data.get('is_pinned', False))

    with transaction.atomic():
        post = Announcement.objects.create(
            title=title,
            content=content,
            category=category,
            audience_type=audience_type,
            purok=purok_obj,
            valid_from=valid_from,
            valid_until=valid_until,
            state=Announcement.STATE_ACTIVE,
            is_pinned=is_pinned,
            image=image_file,
            author=author
        )

        log_activity(
            actor=author,
            action='create',
            action_type='Post',
            target_id=str(post.id),
            target_name=post.title,
            details=f"Published {post.get_category_display()} post: '{post.title}' (Audience: {post.get_audience_type_display()})"
        )

        should_notify = bool(
            (cat_setting and cat_setting.notify_on_post) or
            (category == Announcement.CATEGORY_EMERGENCY)
        )

        if should_notify:
            post_id = post.id
            post_title = post.title
            post_content = post.content[:150]
            author_id = author.id
            aud_type = post.audience_type
            purok_id_val = post.purok_id if post.purok else None

            def dispatch_emergency_notifications():
                author_user = User.objects.filter(id=author_id).first()
                active_residents = User.objects.filter(role=User.ROLE_RESIDENT, status=User.STATUS_ACTIVE)
                if aud_type == Announcement.AUDIENCE_PUROK and purok_id_val:
                    active_residents = active_residents.filter(
                        Q(purok_id=purok_id_val) | Q(resident_profile__purok_id=purok_id_val)
                    )

                notifs = [
                    Notification(
                        recipient=res,
                        sender=author_user,
                        title=f"EMERGENCY ALERT: {post_title}",
                        message=post_content,
                        notification_type=Notification.TYPE_ANNOUNCEMENT,
                        link_url=f"/home/emergency/#post-{post_id}"
                    )
                    for res in active_residents
                ]
                if notifs:
                    Notification.objects.bulk_create(notifs, ignore_conflicts=True)

                try:
                    channel_layer = get_channel_layer()
                    if channel_layer:
                        async_to_sync(channel_layer.group_send)(
                            "barangay_broadcast",
                            {
                                "type": "announcement_broadcast",
                                "title": post_title,
                                "category": "EMERGENCY ALERT",
                                "created_at": timezone.now().strftime("%b %d, %Y"),
                                "announcement_id": post_id,
                            }
                        )
                except Exception:
                    pass

            transaction.on_commit(dispatch_emergency_notifications)

    return post


def edit_post_service(post, actor, data, image_file=None, request=None):
    """
    Edits an existing post/announcement:
    - Permission checked against post's EXISTING category.
    - Edit must not allow changing to a category the user cannot post.
    - Image validation: Pillow content verification.
    - Records ActivityLog.
    """
    if not actor.is_authenticated or actor.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot edit posts.")

    # Check permission on EXISTING category
    if not (actor.role == User.ROLE_ADMIN or actor.is_superuser or check_can_post_category(actor, post.category)):
        raise PermissionDenied(f"You do not have permission to edit '{post.category}' posts.")

    # If category is changing, check permission on NEW category
    new_cat = data.get('category')
    if new_cat:
        new_cat = new_cat.strip().lower()
        if new_cat != post.category:
            if not (actor.role == User.ROLE_ADMIN or actor.is_superuser or check_can_post_category(actor, new_cat)):
                raise PermissionDenied(f"You do not have permission to change category to '{new_cat}'.")
            post.category = new_cat

    if image_file:
        validate_post_image(image_file)
        post.image = image_file
    elif data.get('clear_image') == '1' or data.get('clear_image') is True or (request and request.POST.get('clear_image') == '1'):
        post.image = None

    if 'title' in data and data['title'] and data['title'].strip():
        post.title = data['title'].strip()
    elif 'content' in data and data['content'] and data['content'].strip():
        post.title = data['content'].strip()[:50].strip() or 'Barangay Announcement'
    if 'content' in data and data['content'] and data['content'].strip():
        post.content = data['content'].strip()

    if 'is_pinned' in data:
        post.is_pinned = bool(data['is_pinned'])

    audience_type = data.get('audience_type')
    if audience_type in [Announcement.AUDIENCE_EVERYONE, Announcement.AUDIENCE_PUROK]:
        post.audience_type = audience_type

    if 'purok' in data:
        purok_val = data.get('purok')
        if isinstance(purok_val, Purok):
            post.purok = purok_val
        elif purok_val and str(purok_val).isdigit():
            post.purok = Purok.objects.filter(id=int(purok_val)).first()
        elif not purok_val:
            post.purok = None

    valid_until = data.get('valid_until')
    if valid_until and isinstance(valid_until, str):
        try:
            valid_until = datetime.datetime.fromisoformat(valid_until.strip())
            if timezone.is_naive(valid_until):
                valid_until = timezone.make_aware(valid_until, zoneinfo.ZoneInfo("Asia/Manila"))
            post.valid_until = valid_until
        except ValueError:
            pass
    elif valid_until and isinstance(valid_until, datetime.datetime):
        post.valid_until = valid_until

    with transaction.atomic():
        post.save()
        log_activity(
            actor=actor,
            action='update',
            action_type='Post',
            target_id=str(post.id),
            target_name=post.title,
            details=f"Updated {post.get_category_display()} post '{post.title}'"
        )
    return post


def archive_post_service(post, actor, request=None):
    """
    Soft-archives a post instead of hard delete:
    - Permission checked against post's EXISTING category.
    - Sets post.state = 'archived'.
    - Records ActivityLog.
    """
    if not actor.is_authenticated or actor.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot archive posts.")

    if not (actor.role == User.ROLE_ADMIN or actor.is_superuser or check_can_post_category(actor, post.category)):
        raise PermissionDenied(f"You do not have permission to archive '{post.category}' posts.")

    with transaction.atomic():
        post.state = Announcement.STATE_ARCHIVED
        post.save(update_fields=['state'])

        log_activity(
            actor=actor,
            action='delete',
            action_type='Post',
            target_id=str(post.id),
            target_name=post.title,
            details=f"Archived {post.get_category_display()} post '{post.title}'"
        )
    return post


def mark_post_done_service(post, actor, request=None):
    """
    Marks an active post as done:
    - Permission checked against post's EXISTING category.
    - Updates post.state='done'.
    - Records ActivityLog.
    """
    if not actor.is_authenticated or actor.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot mark posts as done.")

    if not (actor.role == User.ROLE_ADMIN or actor.is_superuser or check_can_post_category(actor, post.category)):
        raise PermissionDenied(f"You do not have permission to manage '{post.category}' posts.")

    with transaction.atomic():
        post.state = Announcement.STATE_DONE
        post.save(update_fields=['state'])

        log_activity(
            actor=actor,
            action='complete',
            action_type='Post',
            target_id=str(post.id),
            target_name=post.title,
            details=f"Marked post '{post.title}' as done"
        )
    return post


def extend_post_service(post, actor, new_valid_until, request=None):
    """
    Extends an announcement's expiration date:
    - Permission checked against post's EXISTING category.
    - Extend on a done post is REFUSED (must be reopened first).
    - new_valid_until must be in the future.
    - new_valid_until must be later than the current valid_until (if set).
    - If post was expired, resets state to 'active'.
    - Records ActivityLog.
    """
    if not actor.is_authenticated or actor.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot extend posts.")

    if not (actor.role == User.ROLE_ADMIN or actor.is_superuser or check_can_post_category(actor, post.category)):
        raise PermissionDenied(f"You do not have permission to manage '{post.category}' posts.")

    if post.state == Announcement.STATE_DONE:
        raise ValueError("Cannot extend a post that has been marked as done. Please reopen it first.")

    if isinstance(new_valid_until, str):
        try:
            new_valid_until = datetime.datetime.fromisoformat(new_valid_until.strip())
        except ValueError:
            raise ValueError("Invalid date format for extension.")

    if timezone.is_naive(new_valid_until):
        new_valid_until = timezone.make_aware(new_valid_until, zoneinfo.ZoneInfo("Asia/Manila"))

    now = timezone.now()
    if new_valid_until <= now:
        raise ValueError("New expiration date must be in the future.")

    if post.valid_until and new_valid_until <= post.valid_until:
        raise ValueError("New expiration date must be later than the current expiration date.")

    with transaction.atomic():
        post.valid_until = new_valid_until
        if post.state == Announcement.STATE_EXPIRED:
            post.state = Announcement.STATE_ACTIVE
        post.save(update_fields=['valid_until', 'state'])

        log_activity(
            actor=actor,
            action='update',
            action_type='Post',
            target_id=str(post.id),
            target_name=post.title,
            details=f"Extended expiration date for post '{post.title}' to {new_valid_until.strftime('%B %d, %Y %H:%M')}"
        )
    return post


def reopen_post_service(post, actor, new_valid_until=None, request=None):
    """
    Reopens a done or expired post back to active state:
    - Permission checked against post's EXISTING category.
    - If valid_until is past, new_valid_until in the future is required.
    - Sets post.state='active'.
    - Records ActivityLog.
    """
    if not actor.is_authenticated or actor.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot reopen posts.")

    if not (actor.role == User.ROLE_ADMIN or actor.is_superuser or check_can_post_category(actor, post.category)):
        raise PermissionDenied(f"You do not have permission to reopen '{post.category}' posts.")

    now = timezone.now()
    with transaction.atomic():
        if new_valid_until:
            if isinstance(new_valid_until, str):
                try:
                    new_valid_until = datetime.datetime.fromisoformat(new_valid_until.strip())
                except ValueError:
                    raise ValueError("Invalid date format for reopening.")
            if timezone.is_naive(new_valid_until):
                new_valid_until = timezone.make_aware(new_valid_until, zoneinfo.ZoneInfo("Asia/Manila"))
            if new_valid_until <= now:
                raise ValueError("New expiration date must be in the future.")
            post.valid_until = new_valid_until
        elif post.valid_until and post.valid_until < now:
            raise ValueError("This post has expired. Please specify a new valid expiration date to reopen it.")

        post.state = Announcement.STATE_ACTIVE
        post.save(update_fields=['state', 'valid_until'])

        log_activity(
            actor=actor,
            action='update',
            action_type='Post',
            target_id=str(post.id),
            target_name=post.title,
            details=f"Reopened post '{post.title}' to active feed"
        )
    return post


def expire_posts_service():
    """
    Idempotent daily maintenance routine:
    Marks any active posts past valid_until as expired.
    """
    now = timezone.now()
    qs = Announcement.objects.filter(
        state=Announcement.STATE_ACTIVE,
        valid_until__isnull=False,
        valid_until__lt=now
    )
    count = qs.update(state=Announcement.STATE_EXPIRED)
    return count


def get_active_posts_queryset(user, category=None):
    """
    Retrieves active posts:
    - Filters by state=active AND (valid_until is null OR valid_until >= now)
    - Respects valid_from (hide until it starts: valid_from <= now)
    - Audience filtering: residents see 'everyone' posts plus their own purok's.
    - Staff / Admin / Superusers see all audiences (not expired/done posts).
    """
    now = timezone.now()
    qs = Announcement.objects.filter(
        state=Announcement.STATE_ACTIVE
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=now)
    ).filter(
        Q(valid_from__isnull=True) | Q(valid_from__lte=now)
    )

    if category:
        qs = qs.filter(category=category)

    if user.is_authenticated and user.role == User.ROLE_RESIDENT:
        resident_profile = getattr(user, 'resident_profile', None)
        if resident_profile and resident_profile.purok:
            qs = qs.filter(
                Q(audience_type=Announcement.AUDIENCE_EVERYONE) |
                Q(audience_type=Announcement.AUDIENCE_PUROK, purok=resident_profile.purok)
            )
        elif getattr(user, 'purok', None):
            qs = qs.filter(
                Q(audience_type=Announcement.AUDIENCE_EVERYONE) |
                Q(audience_type=Announcement.AUDIENCE_PUROK, purok=user.purok)
            )
        else:
            qs = qs.filter(audience_type=Announcement.AUDIENCE_EVERYONE)
    elif not user.is_authenticated:
        qs = qs.filter(audience_type=Announcement.AUDIENCE_EVERYONE)

    return qs.select_related('author', 'purok', 'category_ref').prefetch_related(
        'author__officer_roles',
        'comments__author',
        'reactions'
    ).order_by('-is_pinned', '-created_at')


def get_history_posts_queryset(user, category=None, state=None):
    """
    Retrieves expired, done, and archived posts for Staff/Admin management and audit review.
    Residents cannot access this history.
    """
    if not user.is_authenticated or user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot access post archives and history.")

    qs = Announcement.objects.filter(
        state__in=[Announcement.STATE_DONE, Announcement.STATE_EXPIRED, Announcement.STATE_ARCHIVED]
    )
    if state:
        qs = qs.filter(state=state)
    if category:
        qs = qs.filter(category=category)

    return qs.select_related('author', 'purok').order_by('-created_at')
