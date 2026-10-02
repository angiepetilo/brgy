from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from apps.accounts.models import User
from apps.blotter.models import BlotterRecord, KPCase
from apps.blotter.forms import BlotterRecordForm, KPCaseForm


def is_admin_or_kapitan(user):
    return user.is_authenticated and (user.role in [User.ROLE_ADMIN, User.ROLE_KAPITAN] or user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_admin_or_kapitan)
def blotter_dashboard_view(request):
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('q', '').strip()

    records = BlotterRecord.objects.select_related('created_by', 'kp_case').all()

    if status_filter:
        records = records.filter(status=status_filter)
    if search_query:
        records = records.filter(
            Q(case_number__icontains=search_query) |
            Q(complainant_name__icontains=search_query) |
            Q(respondent_name__icontains=search_query) |
            Q(incident_type__icontains=search_query) |
            Q(incident_location__icontains=search_query)
        )

    # Statistics
    total_cases = BlotterRecord.objects.count()
    open_cases = BlotterRecord.objects.filter(status=BlotterRecord.STATUS_OPEN).count()
    settled_cases = BlotterRecord.objects.filter(status=BlotterRecord.STATUS_SETTLED).count()
    referred_cases = BlotterRecord.objects.filter(status=BlotterRecord.STATUS_REFERRED).count()

    # Upcoming KP hearings
    upcoming_hearings = KPCase.objects.filter(
        hearing_date__gte=timezone.now(),
        blotter__status=BlotterRecord.STATUS_OPEN
    ).select_related('blotter').order_by('hearing_date')[:5]

    context = {
        'records': records,
        'status_filter': status_filter,
        'search_query': search_query,
        'status_choices': BlotterRecord.STATUS_CHOICES,
        'total_cases': total_cases,
        'open_cases': open_cases,
        'settled_cases': settled_cases,
        'referred_cases': referred_cases,
        'upcoming_hearings': upcoming_hearings,
    }
    return render(request, 'blotter/dashboard.html', context)


@login_required
@user_passes_test(is_admin_or_kapitan)
def blotter_create_view(request):
    if request.method == 'POST':
        form = BlotterRecordForm(request.POST)
        if form.is_valid():
            record = form.save(commit=False)
            record.created_by = request.user
            record.save()
            messages.success(request, f"Blotter incident case #{record.case_number} logged successfully.")
            return redirect('blotter:detail', pk=record.id)
    else:
        # Suggest unique case number
        year = timezone.now().year
        next_count = BlotterRecord.objects.filter(created_at__year=year).count() + 1
        suggested_num = f"BLOT-{year}-{next_count:04d}"
        form = BlotterRecordForm(initial={'case_number': suggested_num, 'incident_date': timezone.now().strftime('%Y-%m-%dT%H:%M')})

    return render(request, 'blotter/blotter_form.html', {'form': form, 'title': 'Log New Blotter Incident'})


@login_required
@user_passes_test(is_admin_or_kapitan)
def blotter_detail_view(request, pk):
    record = get_object_or_404(BlotterRecord.objects.select_related('created_by'), pk=pk)
    kp_case, created = KPCase.objects.get_or_create(blotter=record)

    if request.method == 'POST':
        if 'update_blotter' in request.POST:
            blotter_form = BlotterRecordForm(request.POST, instance=record)
            if blotter_form.is_valid():
                blotter_form.save()
                messages.success(request, "Blotter record updated successfully.")
                return redirect('blotter:detail', pk=record.id)
        elif 'update_kp' in request.POST:
            kp_form = KPCaseForm(request.POST, request.FILES, instance=kp_case)
            if kp_form.is_valid():
                kp_form.save()
                # If CFA issued, auto-suggest referred status
                if kp_form.cleaned_data.get('certificate_to_file_action'):
                    record.status = BlotterRecord.STATUS_REFERRED
                    record.save()
                messages.success(request, "Katarungang Pambarangay mediation details updated.")
                return redirect('blotter:detail', pk=record.id)
    else:
        blotter_form = BlotterRecordForm(instance=record)
        kp_form = KPCaseForm(instance=kp_case)

    context = {
        'record': record,
        'kp_case': kp_case,
        'blotter_form': blotter_form,
        'kp_form': kp_form,
    }
    return render(request, 'blotter/blotter_detail.html', context)


def records_hub_view(request):
    """
    Records Management Module (/records/)
    Tri-Tab Interface:
    PEACE & ORDER - Incident blotters, KP mediation case schedules, and settlement files.
    FINANCE & ASSETS - Certificate revenue logs and barangay property inventory tracking.
    RBI DIRECTORY - Demographic breakdowns by Purok, Senior Citizens, PWDs, and Households.
    """
    from apps.finance.models import AssetInventory
    from apps.appointments.models import Appointment, IssuedDocumentLog
    from apps.accounts.models import Household, User

    active_tab = request.GET.get('tab', 'peace_order')
    if active_tab not in ['peace_order', 'finance_assets', 'rbi']:
        active_tab = 'peace_order'

    search_query = request.GET.get('q', '').strip()

    # 1. Peace & Order
    blotters = BlotterRecord.objects.select_related('created_by', 'kp_case').all()
    if search_query and active_tab == 'peace_order':
        blotters = blotters.filter(
            Q(case_number__icontains=search_query) |
            Q(complainant_name__icontains=search_query) |
            Q(respondent_name__icontains=search_query) |
            Q(incident_type__icontains=search_query)
        )
    total_blotters = BlotterRecord.objects.count()
    open_blotters = BlotterRecord.objects.filter(status=BlotterRecord.STATUS_OPEN).count()
    settled_blotters = BlotterRecord.objects.filter(status=BlotterRecord.STATUS_SETTLED).count()
    referred_blotters = BlotterRecord.objects.filter(status=BlotterRecord.STATUS_REFERRED).count()
    kp_cases = KPCase.objects.select_related('blotter').order_by('-hearing_date')[:10]

    # 2. Finance & Assets
    issued_logs = IssuedDocumentLog.objects.select_related('appointment', 'issued_to', 'issued_by').all()
    if search_query and active_tab == 'finance_assets':
        issued_logs = issued_logs.filter(
            Q(control_number__icontains=search_query) |
            Q(issued_to__first_name__icontains=search_query) |
            Q(issued_to__last_name__icontains=search_query) |
            Q(appointment__document_type__icontains=search_query)
        )
    total_issued = IssuedDocumentLog.objects.count()
    assets = AssetInventory.objects.all()
    total_assets_qty = sum(a.quantity for a in assets)
    good_assets_qty = sum(a.quantity for a in assets if a.condition == AssetInventory.CONDITION_GOOD)
    maintenance_assets_qty = sum(a.quantity for a in assets if a.condition == AssetInventory.CONDITION_MAINTENANCE)

    # 3. RBI Directory
    rbi_residents = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True).select_related('household').order_by('last_name', 'first_name')
    if search_query and active_tab == 'rbi':
        rbi_residents = rbi_residents.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(username__icontains=search_query) |
            Q(address__icontains=search_query)
        )
    purok_breakdown = []
    for p_code, p_label in User.PUROK_CHOICES:
        count = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True, purok__name=p_code).count()
        purok_breakdown.append({'code': p_code, 'label': p_label, 'count': count})

    total_verified_residents = User.objects.filter(role=User.ROLE_RESIDENT, is_approved=True).count()
    total_seniors = User.objects.filter(role=User.ROLE_RESIDENT, is_senior=True).count()
    total_pwd = User.objects.filter(role=User.ROLE_RESIDENT, is_pwd=True).count()
    total_4ps = User.objects.filter(role=User.ROLE_RESIDENT, is_4ps=True).count()
    total_households = Household.objects.count()

    context = {
        'active_tab': active_tab,
        'search_query': search_query,
        # Peace & Order
        'blotters': blotters[:20],
        'total_blotters': total_blotters,
        'open_blotters': open_blotters,
        'settled_blotters': settled_blotters,
        'referred_blotters': referred_blotters,
        'kp_cases': kp_cases,
        # Finance & Assets
        'issued_logs': issued_logs[:20],
        'total_issued': total_issued,
        'assets': assets,
        'total_assets_qty': total_assets_qty,
        'good_assets_qty': good_assets_qty,
        'maintenance_assets_qty': maintenance_assets_qty,
        # RBI Directory
        'rbi_residents': rbi_residents[:30],
        'purok_breakdown': purok_breakdown,
        'total_verified_residents': total_verified_residents,
        'total_seniors': total_seniors,
        'total_pwd': total_pwd,
        'total_4ps': total_4ps,
        'total_households': total_households,
    }
    return render(request, 'records/records_hub.html', context)
