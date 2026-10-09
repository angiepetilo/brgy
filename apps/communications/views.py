from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from django import forms
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.models import User
from apps.accounts.selectors import get_contact_number
from apps.communications.models import Announcement, PostReaction, PostComment, PostCategory, Post
from apps.communications.forms import AnnouncementForm
from apps.communications.selectors import feed_context
from apps.communications.services import (
    create_post_service,
    mark_post_done_service,
    extend_post_service,
    get_active_posts_queryset,
    check_can_post_category,
)


def landing_view(request):
    """
    Public Landing Page & Community Portal.
    Features services overview, announcements, upcoming community events, and registration.
    """
    from apps.appointments.models import DocumentType, HealthCareService
    raw_services = HealthCareService.objects.filter(is_active=True, is_free=True).order_by('name')
    healthcare_services = []
    seen = set()
    for s in raw_services:
        if s.name.strip().lower() not in seen:
            seen.add(s.name.strip().lower())
            healthcare_services.append(s)

    announcements = Announcement.objects.filter(
        category__in=[
            Announcement.CATEGORY_ANNOUNCEMENT,
            Announcement.CATEGORY_GENERAL,
            Announcement.CATEGORY_HEALTH,
            Announcement.CATEGORY_ORDINANCE,
            Announcement.CATEGORY_EMERGENCY
        ]
    ).order_by('-is_pinned', '-created_at')[:3]

    upcoming_events = Announcement.objects.filter(
        category=Announcement.CATEGORY_EVENT
    ).order_by('-created_at')[:3]

    admin_phone = get_contact_number()
    emergency_posts = list(
        get_active_posts_queryset(request.user, category=Announcement.CATEGORY_EMERGENCY)[:3]
    )

    return render(request, 'landing.html', {
        'emergency_posts': emergency_posts,
        'healthcare_services': healthcare_services,
        'document_types': DocumentType.objects.filter(is_active=True).order_by('order', 'name'),
        'announcements': announcements,
        'upcoming_events': upcoming_events,
        'admin_phone': admin_phone,
    })


def is_leadership_or_admin(user):
    if not user.is_authenticated or user.role == User.ROLE_RESIDENT:
        return False
    return (user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or user.is_staff or user.is_superuser)


def is_admin(user):
    return user.is_authenticated and (user.role == User.ROLE_ADMIN or user.is_staff or user.is_superuser)


@login_required
def feed_view(request):
    user = request.user
    category = request.GET.get('cat', '')

    # Dynamic categories for quick filtering
    dynamic_categories = PostCategory.objects.filter(is_active=True).order_by('name')
    if not dynamic_categories.exists():
        default_seed = [
            ('Announcement', 'Official general announcements and barangay updates'),
            ('Emergency Alert', 'Urgent disaster, weather, and safety alerts'),
            ('Upcoming Event', 'Community activities, assemblies, and sports fests'),
            ('Scholarship', 'Educational assistance and youth grants'),
            ('Donation', 'Relief drives, charity initiatives, and donations'),
            ('Legislative', 'Barangay ordinances and executive orders'),
            ('General Advisory', 'Public service guidelines and barangay reminders'),
        ]
        PostCategory.objects.bulk_create([
            PostCategory(name=name, description=desc, is_active=True)
            for name, desc in default_seed
        ], ignore_conflicts=True)
        dynamic_categories = PostCategory.objects.filter(is_active=True).order_by('name')

    can_publish = is_leadership_or_admin(user)

    # Handle post creation from feed
    if request.method == 'POST' and ('create_post' in request.POST or request.POST.get('title')):
        if user.role == User.ROLE_RESIDENT:
            raise PermissionDenied("Residents are not permitted to publish public feed posts.")

        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            clean_data = form.cleaned_data.copy()
            if not clean_data.get('title') and clean_data.get('content'):
                clean_data['title'] = clean_data['content'][:50].strip() or 'Barangay Announcement'
            if 'is_pinned' in request.POST:
                clean_data['is_pinned'] = True

            # Resolve dynamic category if selected
            raw_cat = request.POST.get('category', '').strip()
            cat_obj = PostCategory.objects.filter(name__iexact=raw_cat).first() or PostCategory.objects.filter(name__icontains=raw_cat).first()
            if cat_obj:
                clean_name = cat_obj.name.lower()
                if 'emergency' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_EMERGENCY
                elif 'event' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_EVENT
                elif 'scholarship' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_SCHOLARSHIP
                elif 'donation' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_DONATION
                elif 'legislative' in clean_name or 'ordinance' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_LEGISLATIVE
                elif 'health' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_HEALTH
                else:
                    clean_data['category'] = Announcement.CATEGORY_ANNOUNCEMENT
            elif raw_cat:
                clean_data['category'] = raw_cat.lower()

            target_cat = clean_data.get('category') or Announcement.CATEGORY_ANNOUNCEMENT
            if not check_can_post_category(user, target_cat):
                raise PermissionDenied(f"You do not have permission to publish '{target_cat}' posts.")

            try:
                announcement = create_post_service(
                    author=user,
                    data=clean_data,
                    image_file=request.FILES.get('image'),
                    request=request
                )
                if cat_obj:
                    announcement.category_ref = cat_obj
                    announcement.save(update_fields=['category_ref'])

                messages.success(request, f"Published new {announcement.get_category_display()}: '{announcement.title}'")
                return redirect('communications:feed')
            except (ValueError, forms.ValidationError) as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = AnnouncementForm()

    # Active posts with audience filtering
    queryset = list(get_active_posts_queryset(user, category=category if category else None))

    # Reaction lookups consolidated into a single query
    user_reactions = list(PostReaction.objects.filter(user=user).values_list('post_id', 'reaction_type'))
    user_liked_post_ids = {p_id for p_id, r_type in user_reactions if r_type == 'like'}
    user_supported_post_ids = {p_id for p_id, r_type in user_reactions if r_type == 'support'}
    user_important_post_ids = {p_id for p_id, r_type in user_reactions if r_type == 'important'}

    # Real-Time Stat Cards
    from apps.appointments.models import Appointment
    from django.db.models import Q

    stat_pending_docs_count = User.objects.filter(
        appointments__status=Appointment.STATUS_PENDING
    ).distinct().count()
    stat_pending_residents_count = User.objects.filter(is_approved=False).distinct().count()
    stat_total_residents_count = User.objects.filter(
        is_approved=True, role=User.ROLE_RESIDENT
    ).distinct().count()
    stat_handled_requests_count = User.objects.filter(
        appointments__status=Appointment.STATUS_COMPLETED
    ).distinct().count()
    duty_officers_roster = User.objects.filter(
        Q(role__in=[User.ROLE_ADMIN, User.ROLE_KAPITAN]) | Q(is_staff=True)
    ).distinct().order_by('role', 'last_name')

    context = {
        'announcements': queryset,
        'selected_category': category,
        'categories': Announcement.CATEGORY_CHOICES,
        'dynamic_categories': dynamic_categories,
        'creation_form': form,
        'can_publish': can_publish,
        'user_liked_post_ids': user_liked_post_ids,
        'user_supported_post_ids': user_supported_post_ids,
        'user_important_post_ids': user_important_post_ids,
        'stat_pending_docs_count': stat_pending_docs_count,
        'stat_pending_residents_count': stat_pending_residents_count,
        'stat_total_residents_count': stat_total_residents_count,
        'stat_handled_requests_count': stat_handled_requests_count,
        'duty_officers_roster': duty_officers_roster,
        'staff_members': duty_officers_roster,
        # Civic stacks; reuse the evaluated list unless a category filter narrowed it.
        **feed_context(user, visible_posts=None if category else queryset),
    }
    return render(request, 'communications/home.html', context)


@login_required
def announcements_list_view(request):
    """
    Announcement Module: Displays official announcements with audience filtering.
    Admin & Staff with permission can post, edit, and delete.
    Residents get 403 on post creation and view only their audience posts.
    """
    user = request.user
    can_publish = is_leadership_or_admin(user)

    if request.method == 'POST' and ('create_post' in request.POST or request.POST.get('title')):
        if user.role == User.ROLE_RESIDENT:
            raise PermissionDenied("Residents cannot publish announcements.")
        if not check_can_post_category(user, Announcement.CATEGORY_ANNOUNCEMENT):
            raise PermissionDenied("You do not have permission to publish announcements.")

        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            clean_data = form.cleaned_data.copy()
            clean_data['category'] = Announcement.CATEGORY_ANNOUNCEMENT
            try:
                announcement = create_post_service(
                    author=user,
                    data=clean_data,
                    image_file=request.FILES.get('image'),
                    request=request
                )
                messages.success(request, f"Published new announcement: '{announcement.title}'")
                return redirect('communications:announcements_list')
            except (ValueError, forms.ValidationError) as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = AnnouncementForm(initial={'category': Announcement.CATEGORY_ANNOUNCEMENT})

    tab = request.GET.get('tab', '')
    target_category = Announcement.CATEGORY_EVENT if tab == 'events' else Announcement.CATEGORY_ANNOUNCEMENT
    announcements = get_active_posts_queryset(user, category=target_category)
    unique_count = announcements.count()

    user_liked_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='like').values_list('post_id', flat=True)
    )
    user_supported_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='support').values_list('post_id', flat=True)
    )
    user_important_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='important').values_list('post_id', flat=True)
    )

    context = {
        'announcements': announcements,
        'unique_count': unique_count,
        'creation_form': form,
        'can_publish': can_publish,
        'current_tab': tab,
        'user_liked_post_ids': user_liked_post_ids,
        'user_supported_post_ids': user_supported_post_ids,
        'user_important_post_ids': user_important_post_ids,
    }
    return render(request, 'communications/announcements_list.html', context)


@login_required
def emergency_list_view(request):
    """
    Emergency Module: Displays emergency alerts with audience filtering.
    Emergency posts do not expire by schedule; they stay until marked done.
    """
    user = request.user
    can_publish = is_leadership_or_admin(user)

    if request.method == 'POST' and ('create_post' in request.POST or request.POST.get('title')):
        if user.role == User.ROLE_RESIDENT:
            raise PermissionDenied("Residents cannot broadcast emergency alerts.")
        if not check_can_post_category(user, Announcement.CATEGORY_EMERGENCY):
            raise PermissionDenied("You do not have permission to broadcast emergency alerts.")

        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            clean_data = form.cleaned_data.copy()
            clean_data['category'] = Announcement.CATEGORY_EMERGENCY
            try:
                announcement = create_post_service(
                    author=user,
                    data=clean_data,
                    image_file=request.FILES.get('image'),
                    request=request
                )
                messages.success(request, f"Emergency alert broadcasted: '{announcement.title}'")
                return redirect('communications:emergency_list')
            except (ValueError, forms.ValidationError) as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = AnnouncementForm(initial={'category': Announcement.CATEGORY_EMERGENCY})

    emergencies = get_active_posts_queryset(user, category=Announcement.CATEGORY_EMERGENCY)
    unique_count = emergencies.count()

    user_liked_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='like').values_list('post_id', flat=True)
    )
    user_supported_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='support').values_list('post_id', flat=True)
    )
    user_important_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='important').values_list('post_id', flat=True)
    )

    context = {
        'emergencies': emergencies,
        'unique_count': unique_count,
        'creation_form': form,
        'can_publish': can_publish,
        'user_liked_post_ids': user_liked_post_ids,
        'user_supported_post_ids': user_supported_post_ids,
        'user_important_post_ids': user_important_post_ids,
    }
    return render(request, 'communications/emergency_list.html', context)


@login_required
def react_post_view(request, post_id):
    post = get_object_or_404(Announcement, pk=post_id)
    reaction_type = request.POST.get('reaction_type') or request.GET.get('reaction_type', 'like')
    if reaction_type not in ['like', 'support', 'important']:
        reaction_type = 'like'

    existing = PostReaction.objects.filter(post=post, user=request.user, reaction_type=reaction_type).first()
    if existing:
        existing.delete()
        user_has_reacted = False
    else:
        PostReaction.objects.filter(post=post, user=request.user).delete()
        PostReaction.objects.create(post=post, user=request.user, reaction_type=reaction_type)
        user_has_reacted = True

    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('format') == 'json':
        return JsonResponse({
            'status': 'ok',
            'likes_count': post.likes_count,
            'supports_count': post.supports_count,
            'importants_count': post.importants_count,
            'reaction_type': reaction_type,
            'user_has_reacted': user_has_reacted,
        })

    return redirect(f"/home/#post-{post.id}")


@login_required
def comment_post_view(request, post_id):
    post = get_object_or_404(Announcement, pk=post_id)
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        if content:
            comment = PostComment.objects.create(
                post=post,
                author=request.user,
                content=content
            )
            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'ok',
                    'author': comment.author.get_full_name() or comment.author.username,
                    'initials': comment.author.initials,
                    'content': comment.content,
                    'created_at': comment.created_at.strftime("%b %d, %I:%M %p"),
                })
            messages.success(request, "Comment posted.")
    return redirect(f"/home/#post-{post.id}")


@login_required
def announcement_detail_view(request, pk):
    announcement = get_object_or_404(Announcement.objects.select_related('author'), pk=pk)
    recent_others = Announcement.objects.exclude(id=pk).order_by('-created_at')[:4]
    return render(request, 'communications/announcement_detail.html', {
        'announcement': announcement,
        'recent_others': recent_others,
    })


@login_required
def create_announcement_view(request):
    """
    Publish new announcement or advisory.
    Residents get 403.
    Staff verified for category permission.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot create announcements.")

    next_url = request.POST.get('next') or request.GET.get('next') or 'communications:feed'
    cat = request.GET.get('cat', Announcement.CATEGORY_ANNOUNCEMENT)

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            clean_data = form.cleaned_data.copy()
            target_cat = clean_data.get('category') or cat
            if not check_can_post_category(user, target_cat):
                raise PermissionDenied(f"You do not have permission to publish '{target_cat}' posts.")

            try:
                announcement = create_post_service(
                    author=user,
                    data=clean_data,
                    image_file=request.FILES.get('image'),
                    request=request
                )
                messages.success(request, f"Published new {announcement.get_category_display()}: '{announcement.title}'")
                return redirect(next_url)
            except (ValueError, forms.ValidationError) as e:
                messages.error(request, str(e))
        else:
            messages.error(request, "Please correct the form errors.")
    else:
        form = AnnouncementForm(initial={'category': cat})

    dynamic_categories = PostCategory.objects.filter(is_active=True).order_by('name')

    return render(request, 'communications/announcement_form.html', {
        'form': form,
        'title': 'Publish New Post / Advisory',
        'next_url': next_url,
        'dynamic_categories': dynamic_categories,
    })


@login_required
def edit_announcement_view(request, pk):
    """
    Edit existing announcement.
    Residents get 403.
    Checks permission on EXISTING category and any NEW category.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot edit announcements.")

    announcement = get_object_or_404(Announcement, pk=pk)
    if not (user.role == User.ROLE_ADMIN or user.is_superuser or check_can_post_category(user, announcement.category)):
        raise PermissionDenied(f"You do not have permission to edit '{announcement.category}' posts.")

    next_url = request.POST.get('next') or request.GET.get('next') or 'communications:feed'
    dynamic_categories = PostCategory.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        if form.is_valid():
            clean_data = form.cleaned_data.copy()
            raw_cat = request.POST.get('category', '').strip()
            cat_obj = PostCategory.objects.filter(name__iexact=raw_cat).first() or PostCategory.objects.filter(name__icontains=raw_cat).first()
            if cat_obj:
                clean_name = cat_obj.name.lower()
                if 'emergency' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_EMERGENCY
                elif 'event' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_EVENT
                elif 'scholarship' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_SCHOLARSHIP
                elif 'donation' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_DONATION
                elif 'legislative' in clean_name or 'ordinance' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_LEGISLATIVE
                elif 'health' in clean_name:
                    clean_data['category'] = Announcement.CATEGORY_HEALTH
                else:
                    clean_data['category'] = Announcement.CATEGORY_ANNOUNCEMENT
            elif raw_cat:
                clean_data['category'] = raw_cat.lower()

            try:
                from apps.communications.services import edit_post_service
                edit_post_service(
                    post=announcement,
                    actor=user,
                    data=clean_data,
                    image_file=request.FILES.get('image'),
                    request=request
                )
                if cat_obj:
                    announcement.category_ref = cat_obj
                    announcement.save(update_fields=['category_ref'])
                messages.success(request, f"Post '{announcement.title}' updated successfully.")
                return redirect(next_url)
            except (ValueError, PermissionDenied) as e:
                if isinstance(e, PermissionDenied):
                    raise
                messages.error(request, str(e))
    else:
        form = AnnouncementForm(instance=announcement)

    return render(request, 'communications/announcement_form.html', {
        'form': form,
        'title': 'Edit Post / Advisory',
        'is_edit': True,
        'announcement': announcement,
        'next_url': next_url,
        'dynamic_categories': dynamic_categories,
    })


@login_required
def delete_announcement_view(request, pk):
    """
    Soft-archives announcement instead of hard deleting.
    Residents get 403.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot delete announcements.")

    announcement = get_object_or_404(Announcement, pk=pk)
    if not (user.role == User.ROLE_ADMIN or user.is_superuser or check_can_post_category(user, announcement.category)):
        raise PermissionDenied(f"You do not have permission to delete '{announcement.category}' posts.")

    if request.method == 'POST':
        from apps.communications.services import archive_post_service
        title = announcement.title
        archive_post_service(announcement, user, request=request)
        messages.success(request, f"Post '{title}' archived successfully.")
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'communications:feed'
        return redirect(next_url)
    return redirect('communications:announcement_detail', pk=pk)


@login_required
def toggle_pin_announcement_view(request, pk):
    """
    Toggle pinned status of an announcement.
    Only authorized leadership/admin users can pin/unpin.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot pin announcements.")

    announcement = get_object_or_404(Announcement, pk=pk)
    if not (user.role == User.ROLE_ADMIN or user.is_superuser or check_can_post_category(user, announcement.category)):
        raise PermissionDenied(f"You do not have permission to pin '{announcement.category}' posts.")

    if request.method == 'POST':
        announcement.is_pinned = not announcement.is_pinned
        announcement.save(update_fields=['is_pinned'])
        action_name = "pinned to top" if announcement.is_pinned else "unpinned from top"
        messages.success(request, f"Post '{announcement.title}' {action_name}.")
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'communications:feed'
        return redirect(next_url)

    return redirect('communications:feed')


@login_required
def extend_announcement_view(request, pk):
    """
    Extends expiration date of an announcement.
    Residents get 403.
    Extend on a done post is refused.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot extend announcements.")

    announcement = get_object_or_404(Announcement, pk=pk)
    if not (user.role == User.ROLE_ADMIN or user.is_superuser or check_can_post_category(user, announcement.category)):
        raise PermissionDenied(f"You do not have permission to extend '{announcement.category}' posts.")

    if request.method == 'POST':
        new_valid_until = request.POST.get('new_valid_until') or request.POST.get('valid_until')
        if not new_valid_until:
            messages.error(request, "New expiration date is required.")
        else:
            try:
                extend_post_service(announcement, user, new_valid_until, request=request)
                messages.success(request, f"Post '{announcement.title}' extended successfully.")
            except (ValueError, PermissionDenied) as e:
                if isinstance(e, PermissionDenied):
                    raise
                messages.error(request, str(e))
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'communications:feed'
        return redirect(next_url)

    return render(request, 'communications/post_extend.html', {
        'announcement': announcement,
    })


@login_required
def mark_done_announcement_view(request, pk):
    """
    Marks an announcement as done.
    Residents get 403.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot mark announcements as done.")

    announcement = get_object_or_404(Announcement, pk=pk)
    if not (user.role == User.ROLE_ADMIN or user.is_superuser or check_can_post_category(user, announcement.category)):
        raise PermissionDenied(f"You do not have permission to mark '{announcement.category}' posts as done.")

    if request.method == 'POST':
        try:
            mark_post_done_service(announcement, user, request=request)
            messages.success(request, f"Post '{announcement.title}' marked as done.")
        except (ValueError, PermissionDenied) as e:
            if isinstance(e, PermissionDenied):
                raise
            messages.error(request, str(e))
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'communications:feed'
        return redirect(next_url)

    return render(request, 'communications/post_mark_done.html', {
        'announcement': announcement,
    })


@login_required
def reopen_announcement_view(request, pk):
    """
    Reopens a done, expired, or archived announcement.
    Residents get 403.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot reopen announcements.")

    announcement = get_object_or_404(Announcement, pk=pk)
    if not (user.role == User.ROLE_ADMIN or user.is_superuser or check_can_post_category(user, announcement.category)):
        raise PermissionDenied(f"You do not have permission to reopen '{announcement.category}' posts.")

    if request.method == 'POST':
        new_valid_until = request.POST.get('new_valid_until') or request.POST.get('valid_until')
        try:
            from apps.communications.services import reopen_post_service
            reopen_post_service(announcement, user, new_valid_until=new_valid_until, request=request)
            messages.success(request, f"Post '{announcement.title}' reopened to active feed.")
        except (ValueError, PermissionDenied) as e:
            if isinstance(e, PermissionDenied):
                raise
            messages.error(request, str(e))
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'communications:feed'
        return redirect(next_url)

    return render(request, 'communications/post_extend.html', {
        'announcement': announcement,
        'is_reopen': True,
    })


@login_required
def manage_history_posts_view(request):
    """
    Lists expired, done, and archived posts for Staff/Admin review.
    Residents get 403.
    """
    user = request.user
    if user.role == User.ROLE_RESIDENT:
        raise PermissionDenied("Residents cannot access post archives and history.")

    from apps.communications.services import get_history_posts_queryset
    current_state = request.GET.get('state', '')
    posts = get_history_posts_queryset(user, state=current_state if current_state else None)
    total_count = Announcement.objects.filter(
        state__in=[Announcement.STATE_DONE, Announcement.STATE_EXPIRED, Announcement.STATE_ARCHIVED]
    ).count()

    return render(request, 'communications/manage_history.html', {
        'posts': posts,
        'current_state': current_state,
        'total_count': total_count,
    })
