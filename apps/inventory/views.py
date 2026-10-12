from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.db.models import Q, Sum
from django.shortcuts import render, redirect, get_object_or_404
from apps.accounts.permissions import resident_forbidden
from apps.inventory.models import (
    InventoryWarehouse,
    InventoryItem,
    StockMovement,
)
from apps.inventory.services import (
    ensure_default_inventory_data,
    process_stock_movement,
)


@resident_forbidden
def inventory_view(request):
    """
    Inventory and Asset Tracking:
    Features Multi-Category and Multi-Location tracking across departments:
    - Barangay Hall Assets (Fixed capital assets)
    - Disaster & Relief Goods (BDRRMC perishable packs, consumables, rescue gear)
    - Barangay Health Station (BHS medicines, vaccines, trauma kits, wheelchairs)
    - Peace & Order (Tanod gear, flashlights, batons, vests, radios)
    - Custom user-created Inventories / Warehouses with isolated stock-in and stock-out tracking.
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_warehouse':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            department = request.POST.get('department', '').strip()
            location_address = request.POST.get('location_address', '').strip()
            custodian_name = request.POST.get('custodian_name', '').strip()
            description = request.POST.get('description', '').strip()

            if not name or not code:
                messages.error(request, 'Warehouse name and unique code are required.')
            elif InventoryWarehouse.objects.filter(code=code).exists():
                messages.error(request, f'An inventory warehouse with code "{code}" already exists.')
            else:
                wh = InventoryWarehouse.objects.create(
                    name=name,
                    code=code,
                    department=department,
                    location_address=location_address,
                    custodian_name=custodian_name,
                    description=description,
                )
                messages.success(request, f'New inventory warehouse "{wh.name}" ({wh.code}) created successfully.')
                return redirect(f"{request.path}?warehouse={wh.id}")

        elif action == 'create_item':
            warehouse_id = request.POST.get('warehouse_id')
            name = request.POST.get('name', '').strip()
            item_code = request.POST.get('item_code', '').strip().upper()
            item_type = request.POST.get('item_type', InventoryItem.TYPE_FIXED_ASSET)
            tag_no = request.POST.get('tag_no', '').strip()
            unit = request.POST.get('unit', 'Units').strip()
            condition = request.POST.get('condition', InventoryItem.CONDITION_OPERATIONAL)
            storage_bay = request.POST.get('storage_bay', '').strip()
            custodian = request.POST.get('custodian', '').strip()
            notes = request.POST.get('notes', '').strip()

            try:
                quantity = max(0, int(request.POST.get('quantity', 0)))
            except (ValueError, TypeError):
                quantity = 0

            try:
                estimated_value = Decimal(request.POST.get('estimated_value', '0').replace(',', ''))
            except (InvalidOperation, TypeError):
                estimated_value = Decimal('0.00')

            warehouse = get_object_or_404(InventoryWarehouse, id=warehouse_id)
            item = InventoryItem.objects.create(
                warehouse=warehouse,
                name=name,
                item_code=item_code,
                item_type=item_type,
                tag_no=tag_no,
                quantity=quantity,
                unit=unit,
                condition=condition,
                estimated_value=estimated_value,
                storage_bay=storage_bay,
                custodian=custodian,
                notes=notes,
            )
            messages.success(request, f'Item "{item.name}" added to {warehouse.name}.')
            return redirect(f"{request.path}?warehouse={warehouse.id}")

        elif action == 'stock_movement':
            item_id = request.POST.get('item_id')
            movement_type = request.POST.get('movement_type', StockMovement.MOVEMENT_IN)
            purpose = request.POST.get('purpose', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()

            try:
                quantity = max(1, int(request.POST.get('quantity', 1)))
            except (ValueError, TypeError):
                quantity = 1

            item = get_object_or_404(InventoryItem, id=item_id)
            if movement_type == StockMovement.MOVEMENT_OUT and quantity > item.quantity:
                messages.error(request, f'Cannot stock out {quantity} {item.unit}. Only {item.quantity} {item.unit} available in {item.warehouse.name}.')
            else:
                movement = process_stock_movement(
                    item=item,
                    movement_type=movement_type,
                    quantity=quantity,
                    purpose=purpose,
                    reference_no=reference_no,
                    handled_by=request.user,
                )
                action_word = 'Stock-in' if movement_type == 'stock_in' else ('Stock-out' if movement_type == 'stock_out' else 'Stock adjustment')
                messages.success(
                    request,
                    f'{action_word} of {quantity} {item.unit} processed for "{item.name}" in {item.warehouse.name}. New balance: {item.quantity} {item.unit}.'
                )
            return redirect(f"{request.path}?warehouse={item.warehouse_id}")

    # GET Filter logic
    selected_warehouse_param = request.GET.get('warehouse')
    legacy_tab = request.GET.get('tab', '')
    q = request.GET.get('q', '').strip().lower()

    warehouses = InventoryWarehouse.objects.filter(is_active=True).order_by('code')

    # Map legacy tabs if warehouse parameter not provided
    tab_to_code = {
        'physical_properties': 'WH-HALL',
        'relief_goods': 'WH-BDRRMC',
        'medical_kits': 'WH-BHS',
        'event_supplies': 'WH-TANOD',
    }
    active_warehouse_id = None
    if selected_warehouse_param:
        if selected_warehouse_param != 'all':
            try:
                active_warehouse_id = int(selected_warehouse_param)
            except ValueError:
                wh_match = warehouses.filter(code=selected_warehouse_param).first()
                if wh_match:
                    active_warehouse_id = wh_match.id
    elif legacy_tab and legacy_tab in tab_to_code:
        wh_match = warehouses.filter(code=tab_to_code[legacy_tab]).first()
        if wh_match:
            active_warehouse_id = wh_match.id

    items_qs = InventoryItem.objects.select_related('warehouse')
    if active_warehouse_id:
        items_qs = items_qs.filter(warehouse_id=active_warehouse_id)

    if q:
        items_qs = items_qs.filter(
            Q(name__icontains=q)
            | Q(item_code__icontains=q)
            | Q(tag_no__icontains=q)
            | Q(custodian__icontains=q)
            | Q(storage_bay__icontains=q)
            | Q(warehouse__name__icontains=q)
        )

    # Sorting
    sort_by = request.GET.get('sort', '').strip().lower()
    sort_dir = request.GET.get('dir', '').strip().lower()
    if sort_dir not in ['asc', 'desc']:
        sort_dir = 'asc' if sort_by in ['name', 'code', 'status', 'location'] else 'desc'
    desc = (sort_dir == 'desc')

    if sort_by == 'name':
        items_qs = items_qs.order_by('-name' if desc else 'name')
    elif sort_by == 'code':
        items_qs = items_qs.order_by('-item_code' if desc else 'item_code')
    elif sort_by == 'quantity':
        items_qs = items_qs.order_by('-quantity' if desc else 'quantity')
    elif sort_by == 'status':
        items_qs = items_qs.order_by('-condition' if desc else 'condition')
    elif sort_by == 'location':
        items_qs = items_qs.order_by('-warehouse__name' if desc else 'warehouse__name')
    else:
        items_qs = items_qs.order_by('name')

    items = list(items_qs)

    # Department and Category counts
    all_items_qs = InventoryItem.objects.all()
    hall_count = all_items_qs.filter(Q(warehouse__code='WH-HALL') | Q(item_type=InventoryItem.TYPE_FIXED_ASSET)).count()
    bdrrmc_count = all_items_qs.filter(Q(warehouse__code='WH-BDRRMC') | Q(item_type=InventoryItem.TYPE_RELIEF_GOOD)).count()
    bhs_count = all_items_qs.filter(Q(warehouse__code='WH-BHS') | Q(item_type=InventoryItem.TYPE_MEDICAL)).count()
    tanod_count = all_items_qs.filter(Q(warehouse__code='WH-TANOD') | Q(item_type=InventoryItem.TYPE_PEACE_ORDER)).count()

    total_value = all_items_qs.aggregate(total=Sum('estimated_value'))['total'] or Decimal('0.00')
    total_qty = all_items_qs.aggregate(total=Sum('quantity'))['total'] or 0

    recent_movements = StockMovement.objects.select_related('item', 'item__warehouse', 'handled_by').order_by('-date')[:15]

    context = {
        'items': items,
        'warehouses': warehouses,
        'active_warehouse_id': active_warehouse_id,
        'selected_warehouse_param': selected_warehouse_param or (str(active_warehouse_id) if active_warehouse_id else 'all'),
        'search_query': q,
        'current_sort': sort_by,
        'current_dir': sort_dir,
        'total_items_count': len(items),
        'hall_count': hall_count,
        'bdrrmc_count': bdrrmc_count,
        'bhs_count': bhs_count,
        'tanod_count': tanod_count,
        'total_value': total_value,
        'total_qty': total_qty,
        'recent_movements': recent_movements,
        'item_type_choices': InventoryItem.ITEM_TYPE_CHOICES,
        'condition_choices': InventoryItem.CONDITION_CHOICES,
    }
    return render(request, 'inventory/inventory.html', context)
