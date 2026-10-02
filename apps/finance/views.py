from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from apps.accounts.models import User
from apps.appointments.models import Appointment, IssuedDocumentLog
from apps.finance.models import AssetInventory
from apps.finance.forms import AssetInventoryForm


def is_admin(user):
    return user.is_authenticated and (user.role == User.ROLE_ADMIN or user.is_staff or user.is_superuser)


@login_required
@user_passes_test(is_admin)
def finance_overview_view(request):
    """
    Finance & Assets Overview: Displays official document issuing throughput,
    clearance registry, and property/asset inventory.
    """
    # 1. Document Issuing Activity
    total_issued = IssuedDocumentLog.objects.count()
    recent_logs = IssuedDocumentLog.objects.select_related(
        'appointment', 'issued_to', 'issued_by'
    ).order_by('-issued_at')[:12]

    clearance_count = IssuedDocumentLog.objects.filter(appointment__document_type=Appointment.DOC_CLEARANCE).count()
    residency_count = IssuedDocumentLog.objects.filter(appointment__document_type=Appointment.DOC_RESIDENCY).count()
    indigency_count = IssuedDocumentLog.objects.filter(appointment__document_type=Appointment.DOC_INDIGENCY).count()
    noa_count = IssuedDocumentLog.objects.filter(appointment__document_type=Appointment.DOC_NOA).count()

    # 2. Asset Inventory
    category_filter = request.GET.get('cat', '')
    condition_filter = request.GET.get('condition', '')

    assets_query = AssetInventory.objects.all()
    if category_filter:
        assets_query = assets_query.filter(category=category_filter)
    if condition_filter:
        assets_query = assets_query.filter(condition=condition_filter)

    all_assets = AssetInventory.objects.all()
    total_qty = sum(a.quantity for a in all_assets)
    good_qty = sum(a.quantity for a in all_assets if a.condition == AssetInventory.CONDITION_GOOD)
    maintenance_qty = sum(a.quantity for a in all_assets if a.condition == AssetInventory.CONDITION_MAINTENANCE)
    disposed_qty = sum(a.quantity for a in all_assets if a.condition == AssetInventory.CONDITION_DISPOSED)

    context = {
        'total_issued': total_issued,
        'recent_logs': recent_logs,
        'clearance_count': clearance_count,
        'residency_count': residency_count,
        'indigency_count': indigency_count,
        'noa_count': noa_count,
        'assets': assets_query,
        'total_qty': total_qty,
        'good_qty': good_qty,
        'maintenance_qty': maintenance_qty,
        'disposed_qty': disposed_qty,
        'category_filter': category_filter,
        'condition_filter': condition_filter,
        'category_choices': AssetInventory.CATEGORY_CHOICES,
        'condition_choices': AssetInventory.CONDITION_CHOICES,
    }
    return render(request, 'finance/overview.html', context)


@login_required
@user_passes_test(is_admin)
def asset_create_view(request):
    if request.method == 'POST':
        form = AssetInventoryForm(request.POST)
        if form.is_valid():
            asset = form.save()
            messages.success(request, f"Asset '{asset.item_name}' successfully added to inventory.")
            return redirect('finance:overview')
    else:
        form = AssetInventoryForm()

    return render(request, 'finance/asset_form.html', {'form': form, 'title': 'Register New Barangay Asset'})


@login_required
@user_passes_test(is_admin)
def asset_edit_view(request, pk):
    asset = get_object_or_404(AssetInventory, pk=pk)
    if request.method == 'POST':
        form = AssetInventoryForm(request.POST, instance=asset)
        if form.is_valid():
            form.save()
            messages.success(request, f"Asset '{asset.item_name}' updated successfully.")
            return redirect('finance:overview')
    else:
        form = AssetInventoryForm(instance=asset)

    return render(request, 'finance/asset_form.html', {'form': form, 'title': 'Edit Asset Item', 'is_edit': True})
