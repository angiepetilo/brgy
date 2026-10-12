import mimetypes
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, HttpResponse, Http404, HttpResponseForbidden, JsonResponse
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from apps.accounts.models import User, Resident, Household, HouseholdMember, Purok, Officer, StaffAssignment, PermissionRule
from apps.accounts.permissions import require_perm, registry, check_user_perm, has_perm
from apps.accounts.forms import (
    ResidentRegistrationForm,
    HouseholdForm,
    UserLoginForm,
    ForcePasswordChangeForm,
    ProfileUpdateForm,
)
from apps.core.ratelimit import ratelimit
from apps.accounts.services import (
    clean_demographics,
    update_resident_demographics_service,
    update_resident_account_service,
    register_resident_service,
    approve_resident_service,
    reject_resident_service,
    resend_temporary_password_service,
    change_password_service,
    disable_account_service,
)


@ratelimit(key='ip', rate='signup')
def signup_view(request):
    if request.user.is_authenticated and request.user.status == User.STATUS_ACTIVE:
        return redirect('home')

    if request.method == 'POST':
        form = ResidentRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user, resident = register_resident_service(
                    form.cleaned_data,
                    request.FILES.get('id_photo')
                )
                return render(request, 'accounts/signup.html', {
                    'form': ResidentRegistrationForm(),
                    'registration_submitted': True,
                    'registered_user': user,
                })
            except ValueError as err:
                form.add_error(None, str(err))
    else:
        form = ResidentRegistrationForm()

    return render(request, 'accounts/signup.html', {
        'form': form,
        'registration_submitted': False,
    })


def login_view(request):
    if request.user.is_authenticated:
        if request.user.status == User.STATUS_ACTIVE:
            if request.user.must_change_password:
                return redirect('accounts:change_password')
            return redirect('home')
        else:
            logout(request)

    if request.method == 'POST':
        form = UserLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            if user.must_change_password:
                return redirect('accounts:change_password')
            return redirect('home')
    else:
        form = UserLoginForm(request)

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been safely signed out.")
    return redirect('accounts:login')


@login_required
def change_password_view(request):
    user = request.user
    if not user.must_change_password:
        return redirect('home')

    if request.method == 'POST':
        form = ForcePasswordChangeForm(request.POST, user=user)
        if form.is_valid():
            new_pw = form.cleaned_data['new_password']
            change_password_service(user, new_pw)
            # Rotate the current session key so the old session is invalidated
            update_session_auth_hash(request, user)
            messages.success(request, "Your password has been successfully updated. Welcome to the portal!")
            return redirect('home')
    else:
        form = ForcePasswordChangeForm(user=user)

    return render(request, 'accounts/change_password.html', {'form': form})


@login_required
def pending_approval_view(request):
    return render(request, 'accounts/pending_approval.html', {'user': request.user})


@login_required
def serve_id_photo_view(request, resident_id):
    """
    Secure endpoint serving resident identification documents only to:
    - Admin or authorized staff
    - The resident owner themself
    Direct unauthenticated or unauthorized access returns 403.
    """
    resident = get_object_or_404(Resident, id=resident_id)

    is_owner = (resident.user_id == request.user.id)
    is_staff_or_admin = (
        request.user.role in [User.ROLE_ADMIN, User.ROLE_STAFF, User.ROLE_KAPITAN]
        or request.user.is_staff
        or request.user.is_superuser
    )

    if not (is_owner or is_staff_or_admin):
        raise PermissionDenied("You do not have permission to view this identification document.")

    if not resident.id_photo:
        raise Http404("No ID photo found for this resident.")

    try:
        handle = resident.id_photo.open('rb')
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("ID photo file not found on server.")
    content_type = mimetypes.guess_type(resident.id_photo.name)[0] or 'application/octet-stream'
    response = FileResponse(handle, content_type=content_type, as_attachment=False)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


@require_perm('accounts', 'approve')
def approve_resident_view(request, user_id):
    if request.method == 'POST':
        user_to_approve = get_object_or_404(User, id=user_id)
        link_resident_id = request.POST.get('link_resident_id')
        res = approve_resident_service(user_to_approve, request.user, link_resident_id=link_resident_id, request=request)
        linked_str = ""
        if res.get('linked_resident'):
            linked_str = f" Linked to existing record #{res['linked_resident'].id} ({res['linked_resident'].get_full_name()})."
        if not res.get('email_sent', True):
            messages.warning(
                request,
                f"Account for {user_to_approve.get_full_name() or user_to_approve.username} approved! "
                f"Warning: Failed to deliver temporary password: {res.get('email_error')}. Please use 'Resend temporary password'.{linked_str}"
            )
        else:
            messages.success(
                request,
                f"Account for {user_to_approve.get_full_name() or user_to_approve.username} approved! "
                f"Temporary credentials were sent to {user_to_approve.email}.{linked_str}"
            )
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


@require_perm('accounts', 'resend_password')
def resend_temp_password_view(request, user_id):
    if request.method == 'POST':
        user_obj = get_object_or_404(User, id=user_id)
        res = resend_temporary_password_service(user_obj, request.user, request)
        if not res.get('email_sent', True):
            messages.warning(request, res.get('message', 'Failed to deliver temporary password.'))
        else:
            messages.success(request, res.get('message', 'Temporary password resent successfully.'))
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


@require_perm('accounts', 'reject')
def reject_resident_view(request, user_id):
    if request.method == 'POST':
        user_to_reject = get_object_or_404(User, id=user_id)
        reason = request.POST.get('rejection_reason', '').strip()
        if not reason:
            messages.error(request, "Rejection reason is required. Please provide a clear explanation.")
        else:
            res = reject_resident_service(user_to_reject, request.user, reason, request)
            messages.warning(
                request,
                f"Registration for {user_to_reject.get_full_name() or user_to_reject.username} was rejected. Notice sent to {user_to_reject.email}."
            )
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


def residents_tabbed_view(request):
    if not request.user.is_authenticated:
        return redirect(f"/accounts/login/?next={request.path}")
    if not (check_user_perm(request.user, 'residents', 'view') or check_user_perm(request.user, 'accounts', 'view')):
        raise PermissionDenied("You do not have permission to view residents.")
    """
    Residents Management Module (/accounts/residents/)
    Tabs:
    - PENDING: Unreviewed applicants (status=pending). Side-by-side review of ID photo and details.
    - APPROVED: Verified residents (status=active).
    - REJECTED: Declined applicants (status=rejected).
    """
    active_tab = request.GET.get('tab', 'all')
    if active_tab in ['records', 'residents_records', 'approved']:
        active_tab = 'records'
    elif active_tab not in ['all', 'pending', 'records', 'rejected']:
        active_tab = 'all'

    # Filter by user status
    all_qs = User.objects.filter(role=User.ROLE_RESIDENT).select_related('resident_profile', 'purok')
    pending_qs = User.objects.filter(status=User.STATUS_PENDING, role=User.ROLE_RESIDENT).select_related('resident_profile', 'purok').order_by('-date_joined')
    approved_qs = User.objects.filter(status=User.STATUS_ACTIVE, role=User.ROLE_RESIDENT).select_related('resident_profile', 'purok').order_by('last_name', 'first_name')
    rejected_qs = User.objects.filter(status=User.STATUS_REJECTED, role=User.ROLE_RESIDENT).select_related('resident_profile', 'purok').order_by('-reviewed_at', '-date_joined')

    # Search filter
    search_query = request.GET.get('q', '').strip()
    purok_filter = request.GET.get('purok', '')

    if search_query:
        query_filter = (
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query) |
            Q(resident_profile__contact_no__icontains=search_query) |
            Q(resident_profile__address__icontains=search_query)
        )
        all_qs = all_qs.filter(query_filter)
        pending_qs = pending_qs.filter(query_filter)
        approved_qs = approved_qs.filter(query_filter)
        rejected_qs = rejected_qs.filter(query_filter)

    if purok_filter:
        if purok_filter.isdigit():
            all_qs = all_qs.filter(purok_id=int(purok_filter))
            approved_qs = approved_qs.filter(purok_id=int(purok_filter))
        else:
            all_qs = all_qs.filter(purok__name=purok_filter)
            approved_qs = approved_qs.filter(purok__name=purok_filter)

    # Sorting
    sort_by = request.GET.get('sort', '').strip().lower()
    sort_dir = request.GET.get('dir', '').strip().lower()
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'asc' if sort_by == 'name' else 'desc'
    desc = (sort_dir == 'desc')

    if sort_by == 'name':
        order_fields = ['-first_name', '-last_name'] if desc else ['first_name', 'last_name']
        all_qs = all_qs.order_by(*order_fields)
        pending_qs = pending_qs.order_by(*order_fields)
        approved_qs = approved_qs.order_by(*order_fields)
        rejected_qs = rejected_qs.order_by(*order_fields)
    elif sort_by == 'date':
        order_field = '-date_joined' if desc else 'date_joined'
        all_qs = all_qs.order_by(order_field)
        pending_qs = pending_qs.order_by(order_field)
        approved_qs = approved_qs.order_by(order_field)
        rejected_qs = rejected_qs.order_by(order_field)
    elif sort_by == 'status':
        order_field = '-status' if desc else 'status'
        all_qs = all_qs.order_by(order_field)
        pending_qs = pending_qs.order_by(order_field)
        approved_qs = approved_qs.order_by(order_field)
        rejected_qs = rejected_qs.order_by(order_field)
    else:
        all_qs = all_qs.order_by('-date_joined')

    if active_tab in ['all', 'pending']:
        target_check = all_page_list = all_qs if active_tab == 'all' else pending_qs
        for u in target_check:
            if u.status == User.STATUS_PENDING:
                dob = u.date_of_birth
                if not dob and hasattr(u, 'resident_profile') and u.resident_profile:
                    dob = u.resident_profile.birthdate
                matches = []
                if dob and u.first_name and u.last_name:
                    candidates = Resident.objects.filter(
                        user__isnull=True,
                        first_name__iexact=u.first_name.strip(),
                        last_name__iexact=u.last_name.strip(),
                        birthdate=dob
                    )
                    matches = [c for c in candidates if c.age and c.age >= 18]
                u.possible_existing_records = matches

    pending_count = pending_qs.count()
    approved_count = approved_qs.count()
    rejected_count = rejected_qs.count()
    all_count = all_qs.count()

    page_number = request.GET.get('page')
    paginator_all = Paginator(all_qs, 15)
    all_page = paginator_all.get_page(page_number)

    paginator_approved = Paginator(approved_qs, 15)
    approved_page = paginator_approved.get_page(page_number)

    main_tab = request.GET.get('main_tab', 'residents')
    if main_tab not in ['residents', 'rbi']:
        main_tab = 'residents'

    puroks = Purok.objects.all()

    can_view_needs = (
        request.user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or
        request.user.is_superuser or
        has_perm(request.user, 'residents', 'view_needs')
    )
    can_edit_needs = (
        request.user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or
        request.user.is_superuser or
        has_perm(request.user, 'residents', 'edit_needs')
    )

    context = {
        'gender_choices': Resident.GENDER_CHOICES,
        'civil_status_choices': Resident.CIVIL_STATUS_CHOICES,
        'can_register_resident': (
            request.user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or
            request.user.is_superuser or
            has_perm(request.user, 'residents', 'create')
        ),
        'main_tab': main_tab,
        'active_tab': active_tab,
        'all_page': all_page,
        'all_count': all_count,
        'pending_residents': pending_qs,
        'approved_page': approved_page,
        'rejected_residents': rejected_qs,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'search_query': search_query,
        'purok_filter': purok_filter,
        'puroks': puroks,
        'current_sort': sort_by,
        'current_dir': sort_dir,
        'can_view_needs': can_view_needs,
        'can_edit_needs': can_edit_needs,
    }
    return render(request, 'accounts/residents_tabbed.html', context)


@require_perm('accounts', 'approve')
def reevaluate_resident_view(request, user_id):
    user_obj = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        action = request.POST.get('action', 'approve')
        if action == 'approve':
            res = approve_resident_service(user_obj, request.user, request)
            messages.success(request, f"Resident {user_obj.get_full_name() or user_obj.username} re-evaluated and approved!")
        else:
            user_obj.status = User.STATUS_PENDING
            user_obj.rejection_reason = ''
            user_obj.save()
            messages.info(request, f"Resident {user_obj.username} returned to pending review.")
    return redirect('/accounts/residents/?tab=rejected')


@login_required
def profile_view(request):
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash

    user = request.user
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'change_password':
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect('accounts:profile')
            else:
                for field, errors in password_form.errors.items():
                    for err in errors:
                        messages.error(request, f"{field.replace('_', ' ').capitalize()}: {err}")
                return redirect('accounts:profile')
        else:
            form = ProfileUpdateForm(request.POST, request.FILES, instance=user)
            if form.is_valid():
                form.save()
                messages.success(request, "Your profile has been updated.")
                return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(instance=user)

    password_form = PasswordChangeForm(user=user)
    return render(request, 'accounts/profile.html', {
        'form': form,
        'password_form': password_form,
        'user_obj': user
    })


@login_required
def remove_avatar_view(request):
    user = request.user
    if request.method == 'POST':
        if user.avatar:
            user.avatar.delete(save=False)
            user.avatar = None
            user.save()
            messages.success(request, "Profile avatar removed.")
    return redirect('accounts:profile')


def _safe_back(request, fallback='accounts:residents_tabbed'):
    """Redirect to the same-site referer, else to ``fallback`` (never offsite)."""
    referer = request.META.get('HTTP_REFERER', '')
    if referer and url_has_allowed_host_and_scheme(
        referer, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(referer)
    return redirect(reverse(fallback))


@require_perm('residents', 'edit')
def resident_edit_view(request, user_id):
    resident_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        try:
            user, resident = update_resident_account_service(request.user, resident_user, request.POST)
        except ValueError as e:
            messages.error(request, str(e))
            return _safe_back(request)

        name = user.get_full_name() or user.username
        if resident is None:
            messages.warning(
                request,
                f"Account details for {name} were updated, but this user has no resident (RBI) profile, "
                "so demographics were not saved.",
            )
        else:
            messages.success(request, f"Resident profile for {name} updated.")
    return _safe_back(request)


@require_perm('residents', 'delete')
def resident_delete_view(request, user_id):
    resident_user = get_object_or_404(User, id=user_id)
    if request.method == 'POST':
        name = resident_user.get_full_name() or resident_user.username
        resident_user.delete()
        messages.success(request, f"Resident account for {name} has been removed.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


@require_perm('residents', 'create')
def staff_register_resident_view(request):
    if request.method == 'POST':
        try:
            from apps.accounts.services import staff_register_resident_service
            resident = staff_register_resident_service(request.user, request.POST, request.FILES)
            messages.success(request, f"Resident account for {resident.get_full_name()} registered successfully.")
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


@require_perm('residents', 'edit_needs')
def update_resident_needs_view(request, resident_id):
    from apps.accounts.models import Resident
    resident = get_object_or_404(Resident, id=resident_id)
    if request.method == 'POST':
        try:
            from apps.accounts.services import update_resident_needs_service
            update_resident_needs_service(resident, request.user, request.POST)
            messages.success(request, f"Needs-attention details updated for {resident.get_full_name()}.")
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


@require_perm('residents', 'assign')
def assign_resident_officer_view(request):
    if request.method == 'POST':
        officer_id = request.POST.get('officer_id')
        officer = get_object_or_404(Officer, id=officer_id) if officer_id else None
        purok_id = request.POST.get('purok_id')
        resident_id = request.POST.get('resident_id')

        try:
            from apps.accounts.services import assign_resident_officer_service, assign_purok_residents_officer_service
            from apps.accounts.models import Resident
            if purok_id:
                purok = get_object_or_404(Purok, id=purok_id)
                count = assign_purok_residents_officer_service(purok, officer, request.user)
                messages.success(request, f"Assigned {count} residents in {purok.name} to {officer.position if officer else 'None'}.")
            elif resident_id:
                resident = get_object_or_404(Resident, id=resident_id)
                assign_resident_officer_service(resident, officer, request.user)
                messages.success(request, f"Assigned {resident.get_full_name()} to {officer.position if officer else 'None'}.")
        except (ValueError, PermissionDenied) as e:
            messages.error(request, str(e))
    return redirect(request.META.get('HTTP_REFERER') or reverse('accounts:residents_tabbed'))


@login_required
def dashboard_view(request):
    """
    Barangay Dashboard view displaying separate numbers for registered residents,
    portal accounts, needs-attention count, and residents per purok leader.
    """
    from apps.accounts.services import get_dashboard_metrics
    metrics = get_dashboard_metrics(request.user)
    return render(request, 'accounts/dashboard.html', {
        'metrics': metrics,
        'residents_per_purok_leader': metrics['residents_per_purok_leader'],
    })


@require_perm('officers', 'edit')
def officers_permissions_view(request):
    """
    Admin Permission & Officer Assignment Management Page.
    Dynamically lists all registered modules and actions from code registry.
    Allows editing PermissionRule records and staff assignments.
    """
    officers = Officer.objects.select_related('user').all()
    all_modules = registry.get_modules()

    if request.method == 'POST':
        # Update permissions
        action_type = request.POST.get('action_type')
        if action_type == 'update_rules':
            officer_id = request.POST.get('officer_id')
            officer = get_object_or_404(Officer, id=officer_id)

            for mod, acts in all_modules.items():
                for act in acts:
                    field_name = f"perm_{officer.id}_{mod}_{act}"
                    allowed = field_name in request.POST
                    PermissionRule.objects.update_or_create(
                        officer=officer,
                        module=mod,
                        action=act,
                        defaults={'allowed': allowed}
                    )
            messages.success(request, f"Permissions for {officer.position} updated successfully.")
            return redirect('accounts:officers_permissions')

        elif action_type == 'assign_staff':
            officer_id = request.POST.get('officer_id')
            user_id = request.POST.get('user_id')
            scope_type = request.POST.get('scope_type')
            scope_value = request.POST.get('scope_value', '').strip()

            officer = get_object_or_404(Officer, id=officer_id)
            assigned_user = get_object_or_404(User, id=user_id)

            StaffAssignment.objects.create(
                user=assigned_user,
                officer=officer,
                scope_type=scope_type,
                scope_value=scope_value
            )
            messages.success(request, f"Assignment created for {assigned_user.get_full_name()} as {officer.position}.")
            return redirect('accounts:officers_permissions')

        elif action_type == 'create_officer':
            position = request.POST.get('position', '').strip()
            committee = request.POST.get('committee', '').strip()
            user_id = request.POST.get('user_id')
            assigned_user = User.objects.filter(id=user_id).first() if user_id else None

            if position:
                new_officer = Officer.objects.create(
                    position=position,
                    committee=committee,
                    user=assigned_user
                )
                messages.success(request, f"Officer role '{new_officer.position}' successfully created.")
            else:
                messages.error(request, "Officer position name is required.")
            return redirect('accounts:officers_permissions')

        elif action_type == 'delete_officer':
            officer_id = request.POST.get('officer_id')
            officer = get_object_or_404(Officer, id=officer_id)
            title = officer.position
            officer.delete()
            messages.success(request, f"Officer role '{title}' deleted.")
            return redirect('accounts:officers_permissions')

    # Build existing rules dictionary: (officer_id, module, action) -> bool
    rules_qs = PermissionRule.objects.all()
    rules_dict = {(r.officer_id, r.module, r.action): r.allowed for r in rules_qs}

    staff_assignments = StaffAssignment.objects.select_related('user', 'officer').all()
    staff_users = User.objects.filter(role__in=[User.ROLE_STAFF, User.ROLE_ADMIN, User.ROLE_KAPITAN])

    context = {
        'officers': officers,
        'modules': all_modules,
        'rules_dict': rules_dict,
        'staff_assignments': staff_assignments,
        'staff_users': staff_users,
    }
    return render(request, 'accounts/officers_permissions.html', context)


# -----------------------------------------------------------------------------
# Household Management Module (Screenshot 2)
# -----------------------------------------------------------------------------

@login_required
def household_list_view(request):
    if not (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff):
        raise PermissionDenied("You do not have permission to view household registry.")

    query = request.GET.get('q', '').strip()
    purok_filter = request.GET.get('purok', '').strip()
    selected_id = request.GET.get('selected', '').strip()

    households = Household.objects.select_related('purok', 'encoded_by', 'updated_by').prefetch_related('household_members').all().order_by('id')

    if query:
        filter_q = (
            Q(household_id__icontains=query) |
            Q(household_number__icontains=query) |
            Q(household_family_name__icontains=query) |
            Q(street__icontains=query) |
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(household_members__first_name__icontains=query) |
            Q(household_members__last_name__icontains=query)
        )
        if query.isdigit():
            filter_q |= Q(id=int(query))
        households = households.filter(filter_q).distinct()

    if purok_filter:
        if purok_filter.isdigit():
            households = households.filter(purok_id=int(purok_filter))
        else:
            households = households.filter(purok__name=purok_filter)

    paginator = Paginator(households, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    selected_hh = None
    if selected_id and selected_id.isdigit():
        selected_hh = Household.objects.filter(id=int(selected_id)).select_related('purok', 'encoded_by', 'updated_by').prefetch_related('household_members').first()
    if not selected_hh and page_obj.object_list:
        selected_hh = page_obj.object_list[0]

    form = HouseholdForm()
    puroks = Purok.objects.all()

    context = {
        'page_obj': page_obj,
        'households': page_obj.object_list,
        'selected_hh': selected_hh,
        'puroks': puroks,
        'search_query': query,
        'purok_filter': purok_filter,
        'form': form,
    }
    return render(request, 'accounts/household_list.html', context)


@login_required
def household_create_view(request):
    if not (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff):
        raise PermissionDenied("You do not have permission to register households.")

    if request.method == 'POST':
        form = HouseholdForm(request.POST)
        if form.is_valid():
            household = form.save(commit=False)
            household.encoded_by = request.user
            household.updated_by = request.user
            if not household.date_of_visit:
                household.date_of_visit = timezone.localdate()
            if not household.interviewed_by:
                household.interviewed_by = request.user.get_full_name() or request.user.username
            if not household.reviewed_by:
                household.reviewed_by = 'Barangay Secretary'

            # Dynamic member arrays from POST
            first_names = request.POST.getlist('member_first_name[]') or request.POST.getlist('member_first_name')
            last_names = request.POST.getlist('member_last_name[]') or request.POST.getlist('member_last_name')
            relationships = request.POST.getlist('member_relationship[]') or request.POST.getlist('member_relationship')
            birthdates = request.POST.getlist('member_birthdate[]') or request.POST.getlist('member_birthdate')
            is_pwds = request.POST.getlist('member_is_pwd[]') or request.POST.getlist('member_is_pwd')
            is_solos = request.POST.getlist('member_is_solo_parent[]') or request.POST.getlist('member_is_solo_parent')
            is_fourps = request.POST.getlist('member_is_4ps[]') or request.POST.getlist('member_is_4ps')

            members_data = []
            for idx in range(len(first_names)):
                fn = first_names[idx].strip()
                ln = last_names[idx].strip() if idx < len(last_names) else ''
                rel = relationships[idx].strip() if idx < len(relationships) else 'Head'
                bd_raw = birthdates[idx].strip() if idx < len(birthdates) else ''
                bd = None
                if bd_raw:
                    try:
                        from datetime import datetime
                        bd = datetime.strptime(bd_raw, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        bd = None
                pwd_val = is_pwds[idx].strip() if idx < len(is_pwds) else '0'
                solo_val = is_solos[idx].strip() if idx < len(is_solos) else '0'
                fourps_val = is_fourps[idx].strip() if idx < len(is_fourps) else '0'
                is_pwd = (pwd_val in ('1', 'true', 'True', 'on'))
                is_solo = (solo_val in ('1', 'true', 'True', 'on'))
                is_4p = (fourps_val in ('1', 'true', 'True', 'on'))

                if fn or ln:
                    members_data.append((fn, ln, rel, bd, is_pwd, is_solo, is_4p))

            if members_data:
                household.first_name = members_data[0][0]
                household.last_name = members_data[0][1]
                household.relationship = members_data[0][2]
                if members_data[0][3]:
                    household.birthdate = members_data[0][3]
            elif household.first_name or household.last_name:
                members_data.append((household.first_name, household.last_name, household.relationship or 'Head', household.birthdate, False, False, False))

            if not household.household_family_name:
                if household.last_name:
                    household.household_family_name = f"{household.last_name} Family"
                else:
                    household.household_family_name = "Household"

            household.save()

            for fn, ln, rel, bd, is_pwd, is_solo, is_4p in members_data:
                HouseholdMember.objects.create(
                    household=household,
                    first_name=fn,
                    last_name=ln or household.last_name,
                    relationship=rel,
                    birthdate=bd,
                    is_pwd=is_pwd,
                    is_solo_parent=is_solo,
                    is_4ps=is_4p
                )

            messages.success(request, f"Household '{household.household_family_name}' successfully registered!")
            return redirect(f"{reverse('accounts:household_list')}?selected={household.id}")
        else:
            err_msg = "; ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
            messages.error(request, f"Failed to register household: {err_msg}")
    return redirect('accounts:household_list')


@login_required
def household_edit_view(request, pk):
    if not (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff):
        raise PermissionDenied("You do not have permission to edit households.")

    household = get_object_or_404(Household, pk=pk)
    if request.method == 'POST':
        form = HouseholdForm(request.POST, instance=household)
        if form.is_valid():
            hh = form.save(commit=False)
            hh.updated_by = request.user
            hh.date_updated = timezone.now()

            # Dynamic member arrays from POST
            first_names = request.POST.getlist('member_first_name[]') or request.POST.getlist('member_first_name')
            last_names = request.POST.getlist('member_last_name[]') or request.POST.getlist('member_last_name')
            relationships = request.POST.getlist('member_relationship[]') or request.POST.getlist('member_relationship')
            birthdates = request.POST.getlist('member_birthdate[]') or request.POST.getlist('member_birthdate')
            is_pwds = request.POST.getlist('member_is_pwd[]') or request.POST.getlist('member_is_pwd')
            is_solos = request.POST.getlist('member_is_solo_parent[]') or request.POST.getlist('member_is_solo_parent')
            is_fourps = request.POST.getlist('member_is_4ps[]') or request.POST.getlist('member_is_4ps')

            members_data = []
            for idx in range(len(first_names)):
                fn = first_names[idx].strip()
                ln = last_names[idx].strip() if idx < len(last_names) else ''
                rel = relationships[idx].strip() if idx < len(relationships) else 'Head'
                bd_raw = birthdates[idx].strip() if idx < len(birthdates) else ''
                bd = None
                if bd_raw:
                    try:
                        from datetime import datetime
                        bd = datetime.strptime(bd_raw, '%Y-%m-%d').date()
                    except (ValueError, TypeError):
                        bd = None
                pwd_val = is_pwds[idx].strip() if idx < len(is_pwds) else '0'
                solo_val = is_solos[idx].strip() if idx < len(is_solos) else '0'
                fourps_val = is_fourps[idx].strip() if idx < len(is_fourps) else '0'
                is_pwd = (pwd_val in ('1', 'true', 'True', 'on'))
                is_solo = (solo_val in ('1', 'true', 'True', 'on'))
                is_4p = (fourps_val in ('1', 'true', 'True', 'on'))

                if fn or ln:
                    members_data.append((fn, ln, rel, bd, is_pwd, is_solo, is_4p))

            if members_data:
                hh.first_name = members_data[0][0]
                hh.last_name = members_data[0][1]
                hh.relationship = members_data[0][2]
                if members_data[0][3]:
                    hh.birthdate = members_data[0][3]
                hh.household_members.all().delete()
                for fn, ln, rel, bd, is_pwd, is_solo, is_4p in members_data:
                    HouseholdMember.objects.create(
                        household=hh,
                        first_name=fn,
                        last_name=ln or hh.last_name,
                        relationship=rel,
                        birthdate=bd,
                        is_pwd=is_pwd,
                        is_solo_parent=is_solo,
                        is_4ps=is_4p
                    )

            if not hh.household_family_name and hh.last_name:
                hh.household_family_name = f"{hh.last_name} Family"

            hh.save()
            messages.success(request, f"Household '{hh.household_family_name}' successfully updated!")
            return redirect(f"{reverse('accounts:household_list')}?selected={hh.id}")
        else:
            err_msg = "; ".join([f"{f}: {e[0]}" for f, e in form.errors.items()])
            messages.error(request, f"Failed to update household: {err_msg}")
    return redirect(f"{reverse('accounts:household_list')}?selected={pk}")


@login_required
def household_delete_view(request, pk):
    if not (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff):
        raise PermissionDenied("You do not have permission to delete households.")

    household = get_object_or_404(Household, pk=pk)
    if request.method == 'POST':
        hh_id = household.household_id
        hh_name = household.household_family_name
        household.delete()
        messages.success(request, f"Household '{hh_name}' [{hh_id}] was deleted successfully.")
    return redirect('accounts:household_list')


# -----------------------------------------------------------------------------
# Resident Accounts Module (Sidebar)
# -----------------------------------------------------------------------------

@login_required
def resident_accounts_list_view(request):
    if not (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff):
        raise PermissionDenied("You do not have permission to view resident accounts.")

    active_tab = request.GET.get('tab', 'pending')
    if active_tab not in ['pending', 'approved', 'rejected']:
        active_tab = 'pending'

    query = request.GET.get('q', '').strip()

    pending_qs = (
        User.objects.filter(role=User.ROLE_RESIDENT)
        .exclude(status=User.STATUS_REJECTED)
        .exclude(is_approved=True, status=User.STATUS_ACTIVE)
        .select_related('resident_profile', 'purok')
        .order_by('-date_joined')
    )
    approved_qs = (
        User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True, status=User.STATUS_ACTIVE)
        .select_related('resident_profile', 'purok')
        .order_by('-date_joined')
    )
    rejected_qs = (
        User.objects.filter(role=User.ROLE_RESIDENT, status=User.STATUS_REJECTED)
        .select_related('resident_profile', 'purok')
        .order_by('-reviewed_at', '-date_joined')
    )

    if query:
        filter_q = (
            Q(first_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(username__icontains=query) |
            Q(email__icontains=query) |
            Q(phone_number__icontains=query) |
            Q(resident_profile__contact_no__icontains=query)
        )
        pending_qs = pending_qs.filter(filter_q)
        approved_qs = approved_qs.filter(filter_q)
        rejected_qs = rejected_qs.filter(filter_q)

    pending_count = pending_qs.count()
    approved_count = approved_qs.count()
    rejected_count = rejected_qs.count()

    if active_tab == 'pending':
        target_qs = pending_qs
    elif active_tab == 'approved':
        target_qs = approved_qs
    else:
        target_qs = rejected_qs

    paginator = Paginator(target_qs, 15)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'active_tab': active_tab,
        'page_obj': page_obj,
        'accounts': page_obj.object_list,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
        'search_query': query,
    }
    return render(request, 'accounts/resident_accounts_list.html', context)


@login_required
def serve_user_id_proof_view(request, user_id):
    target_user = get_object_or_404(User, id=user_id)
    is_owner = (target_user.id == request.user.id)
    is_staff = (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff or request.user.is_superuser)

    if not (is_owner or is_staff):
        raise PermissionDenied("You do not have permission to view this document.")

    file_field = None
    if hasattr(target_user, 'resident_profile') and target_user.resident_profile and target_user.resident_profile.id_photo:
        file_field = target_user.resident_profile.id_photo
    elif target_user.id_proof:
        file_field = target_user.id_proof

    if not file_field:
        raise Http404("No uploaded ID document found.")

    try:
        handle = file_field.open('rb')
    except (FileNotFoundError, OSError, ValueError):
        raise Http404("Document file not found on server.")

    content_type = mimetypes.guess_type(file_field.name)[0] or 'application/octet-stream'
    response = FileResponse(handle, content_type=content_type, as_attachment=False)
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, no-store'
    return response


# -----------------------------------------------------------------------------
# Staff Duty Status Toggle
# -----------------------------------------------------------------------------

@login_required
def toggle_duty_status_view(request):
    if not (request.user.is_admin_user or request.user.is_kapitan_user or request.user.is_staff_user or request.user.is_staff):
        raise PermissionDenied("Only staff and administrators can set on-duty status.")

    target_user_id = request.POST.get('user_id')
    if target_user_id and request.user.is_admin_user:
        target_user = get_object_or_404(User, id=target_user_id)
    elif target_user_id and str(request.user.id) == str(target_user_id):
        target_user = request.user
    else:
        target_user = request.user

    desired_status = request.POST.get('status')
    if desired_status in ['on_duty', 'off_duty']:
        new_status = desired_status
    else:
        new_status = 'off_duty' if target_user.duty_status == 'on_duty' else 'on_duty'

    target_user.duty_status = new_status
    target_user.save(update_fields=['duty_status'])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.GET.get('format') == 'json' or 'application/json' in request.headers.get('Accept', ''):
        return JsonResponse({
            'status': 'ok',
            'duty_status': new_status,
            'duty_label': 'On-Duty' if new_status == 'on_duty' else 'Off-Duty',
            'user_id': target_user.id,
            'user_name': target_user.get_full_name() or target_user.username
        })

    messages.success(request, f"Duty status updated to {'On-Duty' if new_status == 'on_duty' else 'Off-Duty'}.")
    return redirect(request.META.get('HTTP_REFERER') or reverse('chat:inbox'))


@login_required
def departments_directory_view(request):
    """
    Public / Resident & Staff accessible Barangay Officers and Department Directory.
    Residents and staff can browse departments, barangay officers, assigned personnel,
    contact info, and initiate direct messages.
    """
    from apps.accounts.departments import get_departments_with_staff
    departments = get_departments_with_staff()
    officers = Officer.objects.select_related('user').all().order_by('position')
    tab = request.GET.get('tab', 'departments')
    return render(request, 'accounts/departments_directory.html', {
        'departments': departments,
        'officers': officers,
        'active_tab': tab,
        'page_title': 'Officers and Directory',
    })

