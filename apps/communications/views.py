from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from apps.accounts.models import User
from apps.communications.models import KapitanStatus, Announcement, PostReaction, PostComment, PostCategory, Post
from apps.communications.forms import KapitanStatusUpdateForm, AnnouncementForm


def landing_view(request):
    """
    Public Landing Page & Community Portal.
    Features services overview, announcements, upcoming community events, and registration.
    """
    from apps.appointments.models import HealthCareService, Appointment
    healthcare_services = HealthCareService.objects.filter(is_active=True)
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

    admin_user = User.objects.filter(role=User.ROLE_ADMIN).first() or User.objects.filter(is_superuser=True).first()
    admin_phone = admin_user.phone_number if (admin_user and admin_user.phone_number) else '0917-111-2222'

    return render(request, 'landing.html', {
        'healthcare_services': healthcare_services,
        'document_choices': Appointment.DOCUMENT_CHOICES,
        'announcements': announcements,
        'upcoming_events': upcoming_events,
        'admin_phone': admin_phone,
    })


def is_leadership_or_admin(user):
    return user.is_authenticated and (user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or user.is_staff or user.is_superuser)


def is_admin(user):
    return user.is_authenticated and (user.role == User.ROLE_ADMIN or user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_leadership_or_admin)
def kapitan_tracker_view(request):
    current_status = KapitanStatus.objects.order_by('-updated_at').first()
    history = KapitanStatus.objects.select_related('updated_by').order_by('-updated_at')[:15]

    if request.method == 'POST':
        form = KapitanStatusUpdateForm(request.POST)
        if form.is_valid():
            new_status = form.save(commit=False)
            new_status.updated_by = request.user
            # Clear leave reason/date if on duty
            if new_status.status == KapitanStatus.STATUS_ON_DUTY:
                new_status.leave_reason = ''
                new_status.return_date = None
            new_status.save()

            # Broadcast real-time status update to all connected users
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                "barangay_broadcast",
                {
                    "type": "kapitan_status_update",
                    "status": new_status.status,
                    "status_display": new_status.get_status_display(),
                    "leave_reason": new_status.leave_reason,
                    "return_date": new_status.return_date.strftime("%B %d, %Y") if new_status.return_date else "",
                    "updated_at": new_status.updated_at.strftime("%I:%M %p"),
                }
            )

            messages.success(request, f"Barangay Kapitan status broadcasted as '{new_status.get_status_display()}' to all residents.")
            return redirect('communications:kapitan_tracker')
    else:
        initial = {}
        if current_status:
            initial = {
                'status': current_status.status,
                'leave_reason': current_status.leave_reason,
                'return_date': current_status.return_date,
            }
        form = KapitanStatusUpdateForm(initial=initial)

    context = {
        'current_status': current_status,
        'history': history,
        'form': form,
    }
    return render(request, 'communications/kapitan_tracker.html', context)


@login_required
def feed_view(request):
    user = request.user
    category = request.GET.get('cat', '')
    
    # Ensure default dynamic categories exist if table is empty
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
        for name, desc in default_seed:
            PostCategory.objects.get_or_create(name=name, defaults={'description': desc, 'is_active': True})
        dynamic_categories = PostCategory.objects.filter(is_active=True).order_by('name')

    # Handle instant post publishing from Facebook-style modal or feed form
    if request.method == 'POST' and 'create_post' in request.POST:
        if is_leadership_or_admin(user):
            form = AnnouncementForm(request.POST, request.FILES)
            if form.is_valid():
                announcement = form.save(commit=False)
                announcement.author = user

                # Resolve dynamic category
                raw_cat = request.POST.get('category', '').strip()
                cat_obj = PostCategory.objects.filter(name__iexact=raw_cat).first()
                if not cat_obj:
                    cat_obj = PostCategory.objects.filter(name__icontains=raw_cat).first()

                if cat_obj:
                    announcement.category_ref = cat_obj
                    clean_name = cat_obj.name.lower()
                    if 'emergency' in clean_name:
                        announcement.category = Announcement.CATEGORY_EMERGENCY
                    elif 'event' in clean_name:
                        announcement.category = Announcement.CATEGORY_EVENT
                    elif 'scholarship' in clean_name:
                        announcement.category = Announcement.CATEGORY_SCHOLARSHIP
                    elif 'donation' in clean_name:
                        announcement.category = Announcement.CATEGORY_DONATION
                    elif 'legislative' in clean_name or 'ordinance' in clean_name:
                        announcement.category = Announcement.CATEGORY_LEGISLATIVE
                    elif 'health' in clean_name:
                        announcement.category = Announcement.CATEGORY_HEALTH
                    else:
                        announcement.category = Announcement.CATEGORY_ANNOUNCEMENT

                announcement.save()

                # Also create Post entry
                try:
                    Post.objects.create(
                        author=user,
                        category=cat_obj,
                        content=announcement.content,
                        image=announcement.image
                    )
                except Exception:
                    pass

                # Broadcast live announcement notification
                try:
                    channel_layer = get_channel_layer()
                    async_to_sync(channel_layer.group_send)(
                        "barangay_broadcast",
                        {
                            "type": "announcement_broadcast",
                            "title": announcement.title,
                            "category": announcement.get_category_display(),
                            "created_at": announcement.created_at.strftime("%b %d, %Y"),
                            "announcement_id": announcement.id,
                        }
                    )
                except Exception:
                    pass

                messages.success(request, f"Published new {announcement.get_category_display()}: '{announcement.title}'")
                return redirect('communications:feed')
        else:
            messages.error(request, "Only Barangay Officials and Staff can publish official feed posts.")
            return redirect('communications:feed')
    else:
        form = AnnouncementForm()


    queryset = Announcement.objects.select_related('author').prefetch_related('comments__author', 'reactions').all()
    if category:
        queryset = queryset.filter(category=category)

    # Build user reaction sets for simple in-template lookups
    user_liked_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='like').values_list('post_id', flat=True)
    )
    user_supported_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='support').values_list('post_id', flat=True)
    )
    user_important_post_ids = set(
        PostReaction.objects.filter(user=user, reaction_type='important').values_list('post_id', flat=True)
    )

    # 4 Unique Real-Time Stat Cards (User.id level aggregations)
    from apps.appointments.models import Appointment
    from django.db.models import Q

    stat_pending_docs_count = User.objects.filter(
        appointments__status__in=[Appointment.STATUS_SUBMITTED, Appointment.STATUS_UNDER_REVIEW]
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
        'can_publish': is_leadership_or_admin(user),
        'user_liked_post_ids': user_liked_post_ids,
        'user_supported_post_ids': user_supported_post_ids,
        'user_important_post_ids': user_important_post_ids,
        'stat_pending_docs_count': stat_pending_docs_count,
        'stat_pending_residents_count': stat_pending_residents_count,
        'stat_total_residents_count': stat_total_residents_count,
        'stat_handled_requests_count': stat_handled_requests_count,
        'duty_officers_roster': duty_officers_roster,
        'staff_members': duty_officers_roster,
    }
    return render(request, 'communications/feed.html', context)


@login_required
def announcements_list_view(request):
    """
    Announcement Module: Displays all each unique announcement only,
    and counts each unique announcement posted.
    Admin & Staff can post with or without photo, edit, and delete.
    Residents only can view.
    """
    user = request.user
    can_publish = is_leadership_or_admin(user)

    if request.method == 'POST' and 'create_post' in request.POST:
        if can_publish:
            form = AnnouncementForm(request.POST, request.FILES)
            if form.is_valid():
                announcement = form.save(commit=False)
                announcement.author = user
                announcement.category = Announcement.CATEGORY_ANNOUNCEMENT
                announcement.save()
                messages.success(request, f"Published new announcement: '{announcement.title}'")
                return redirect('communications:announcements_list')
        else:
            messages.error(request, "Only Barangay Officials and Staff can publish announcements.")
            return redirect('communications:announcements_list')
    else:
        form = AnnouncementForm(initial={'category': Announcement.CATEGORY_ANNOUNCEMENT})

    # Unique announcements only
    announcements = Announcement.objects.filter(
        category=Announcement.CATEGORY_ANNOUNCEMENT
    ).select_related('author').prefetch_related('comments__author', 'reactions').order_by('-is_pinned', '-created_at')

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
        'user_liked_post_ids': user_liked_post_ids,
        'user_supported_post_ids': user_supported_post_ids,
        'user_important_post_ids': user_important_post_ids,
    }
    return render(request, 'communications/announcements_list.html', context)


@login_required
def emergency_list_view(request):
    """
    Emergency Module: Displays all emergency alerts only,
    and counts each unique emergency posted.
    Admin & Staff can post with or without photo, edit, and delete.
    Residents only can view.
    """
    user = request.user
    can_publish = is_leadership_or_admin(user)

    if request.method == 'POST' and 'create_post' in request.POST:
        if can_publish:
            form = AnnouncementForm(request.POST, request.FILES)
            if form.is_valid():
                announcement = form.save(commit=False)
                announcement.author = user
                announcement.category = Announcement.CATEGORY_EMERGENCY
                announcement.save()
                messages.success(request, f"Emergency alert broadcasted: '{announcement.title}'")
                return redirect('communications:emergency_list')
        else:
            messages.error(request, "Only Barangay Officials and Staff can broadcast emergency alerts.")
            return redirect('communications:emergency_list')
    else:
        form = AnnouncementForm(initial={'category': Announcement.CATEGORY_EMERGENCY})

    # Unique emergencies only
    emergencies = Announcement.objects.filter(
        category=Announcement.CATEGORY_EMERGENCY
    ).select_related('author').prefetch_related('comments__author', 'reactions').order_by('-is_pinned', '-created_at')

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
        # Clear any other reaction by this user on this post, then set new
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

    return redirect(f"/communications/#post-{post.id}")


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
    return redirect(f"/communications/#post-{post.id}")



@login_required
def announcement_detail_view(request, pk):
    announcement = get_object_or_404(Announcement.objects.select_related('author'), pk=pk)
    recent_others = Announcement.objects.exclude(id=pk).order_by('-created_at')[:4]
    return render(request, 'communications/announcement_detail.html', {
        'announcement': announcement,
        'recent_others': recent_others,
    })


@login_required
@user_passes_test(is_leadership_or_admin)
def create_announcement_view(request):
    next_url = request.POST.get('next') or request.GET.get('next') or 'communications:feed'
    cat = request.GET.get('cat', Announcement.CATEGORY_ANNOUNCEMENT)
    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES)
        if form.is_valid():
            announcement = form.save(commit=False)
            announcement.author = request.user
            announcement.save()

            # Broadcast new announcement alert via WebSockets
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    "barangay_broadcast",
                    {
                        "type": "announcement_broadcast",
                        "title": announcement.title,
                        "category": announcement.get_category_display(),
                        "created_at": announcement.created_at.strftime("%b %d, %Y"),
                        "announcement_id": announcement.id,
                    }
                )
            except Exception:
                pass

            messages.success(request, f"Published new {announcement.get_category_display()}: '{announcement.title}'")
            return redirect(next_url)
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
@user_passes_test(is_leadership_or_admin)
def edit_announcement_view(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    next_url = request.POST.get('next') or request.GET.get('next') or 'communications:feed'
    dynamic_categories = PostCategory.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        form = AnnouncementForm(request.POST, request.FILES, instance=announcement)
        if form.is_valid():
            post_obj = form.save(commit=False)
            if request.POST.get('clear_image') == '1' and not request.FILES.get('image'):
                if post_obj.image:
                    try:
                        post_obj.image.delete(save=False)
                    except Exception:
                        pass
                post_obj.image = None

            raw_cat = request.POST.get('category', '').strip()
            cat_obj = PostCategory.objects.filter(name__iexact=raw_cat).first()
            if not cat_obj:
                cat_obj = PostCategory.objects.filter(name__icontains=raw_cat).first()
            if cat_obj:
                post_obj.category_ref = cat_obj
                clean_name = cat_obj.name.lower()
                if 'emergency' in clean_name:
                    post_obj.category = Announcement.CATEGORY_EMERGENCY
                elif 'event' in clean_name:
                    post_obj.category = Announcement.CATEGORY_EVENT
                elif 'scholarship' in clean_name:
                    post_obj.category = Announcement.CATEGORY_SCHOLARSHIP
                elif 'donation' in clean_name:
                    post_obj.category = Announcement.CATEGORY_DONATION
                elif 'legislative' in clean_name or 'ordinance' in clean_name:
                    post_obj.category = Announcement.CATEGORY_LEGISLATIVE
                elif 'health' in clean_name:
                    post_obj.category = Announcement.CATEGORY_HEALTH
                else:
                    post_obj.category = Announcement.CATEGORY_ANNOUNCEMENT

            post_obj.save()
            messages.success(request, f"Post '{announcement.title}' updated successfully.")
            return redirect(next_url)
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
@user_passes_test(is_leadership_or_admin)
def delete_announcement_view(request, pk):
    announcement = get_object_or_404(Announcement, pk=pk)
    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f"Post '{title}' deleted successfully.")
        next_url = request.POST.get('next') or request.META.get('HTTP_REFERER') or 'communications:feed'
        return redirect(next_url)
    return redirect('communications:announcement_detail', pk=pk)


@login_required
def transparency_portal_view(request):
    """
    Public Transparency Portal displaying published Barangay Ordinances,
    Resolutions, and Executive Orders with downloadable official PDF documents.
    """
    from django.db.models import Q
    from apps.communications.models import LegislativeRecord

    category = request.GET.get('cat', '')
    search_query = request.GET.get('q', '').strip()

    if request.user.is_admin_user or request.user.is_kapitan_user:
        records = LegislativeRecord.objects.all()
    else:
        records = LegislativeRecord.objects.filter(is_public=True)

    if category:
        records = records.filter(category=category)
    if search_query:
        records = records.filter(
            Q(title__icontains=search_query) |
            Q(document_number__icontains=search_query) |
            Q(summary__icontains=search_query)
        )

    # Counts
    ordinance_count = records.filter(category=LegislativeRecord.CATEGORY_ORDINANCE).count()
    resolution_count = records.filter(category=LegislativeRecord.CATEGORY_RESOLUTION).count()
    eo_count = records.filter(category=LegislativeRecord.CATEGORY_EXECUTIVE_ORDER).count()

    context = {
        'records': records,
        'selected_category': category,
        'search_query': search_query,
        'categories': LegislativeRecord.CATEGORY_CHOICES,
        'ordinance_count': ordinance_count,
        'resolution_count': resolution_count,
        'eo_count': eo_count,
    }
    return render(request, 'communications/transparency.html', context)


@login_required
@user_passes_test(is_admin)
def legislative_create_view(request):
    from apps.communications.forms import LegislativeRecordForm

    if request.method == 'POST':
        form = LegislativeRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save()
            messages.success(request, f"Legislative measure '{record.document_number}' successfully recorded.")
            return redirect('communications:transparency')
    else:
        form = LegislativeRecordForm()

    return render(request, 'communications/legislative_form.html', {'form': form, 'title': 'Publish Legislative Measure'})

