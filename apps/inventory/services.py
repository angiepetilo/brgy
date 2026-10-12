from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.inventory.models import (
    InventoryWarehouse,
    InventoryItem,
    StockMovement,
)


def ensure_default_inventory_data():
    """
    Ensures standard baseline Barangay warehouses and stock items are seeded if tables are empty.
    """
    if not InventoryWarehouse.objects.exists():
        warehouses_data = [
            {
                'name': 'Barangay Hall Assets',
                'code': 'WH-HALL',
                'department': 'General Administration & IT',
                'location_address': 'Barangay Hall 2nd Floor, Main Office',
                'custodian_name': 'Engr. Manuel Rivera (Property Custodian)',
                'description': 'Fixed capital assets including desktop workstations, laser printers, ergonomic chairs, conference tables, and split-type air conditioners.',
            },
            {
                'name': 'Disaster & Relief Goods (BDRRMC)',
                'code': 'WH-BDRRMC',
                'department': 'Disaster Risk Reduction & Management',
                'location_address': 'Multi-Purpose Evacuation Center, Storage Bay A & B',
                'custodian_name': 'Capt. Rodrigo Valenzuela (DRRM Officer)',
                'description': 'Perishable food packs, canned goods, bottled drinking water, rescue speedboats, heavy nylon ropes, safety hardhats, and search lights.',
            },
            {
                'name': 'Barangay Health Station (BHS)',
                'code': 'WH-BHS',
                'department': 'Health & Sanitation Services',
                'location_address': 'Barangay Health Center, Ground Floor Pharmacy Storage',
                'custodian_name': 'Head Nurse Althea Cruz',
                'description': 'Essential medicines, pediatric vaccines, trauma medical kits, automated external defibrillators (AED), digital BP monitors, and patient wheelchairs.',
            },
            {
                'name': 'Peace & Order (Tanod Gear)',
                'code': 'WH-TANOD',
                'department': 'Public Safety & Peace and Order Council',
                'location_address': 'Barangay Outpost & Tanod Armory Locker',
                'custodian_name': 'Chief Tanod Danilo Morales',
                'description': 'High-lumen tactical flashlights, defense batons, ballistic tactical vests, raincoats, handcuffs, and dual-band UHF/VHF communication radios.',
            },
        ]

        created_wh = {}
        for w in warehouses_data:
            wh = InventoryWarehouse.objects.create(
                name=w['name'],
                code=w['code'],
                department=w['department'],
                location_address=w['location_address'],
                custodian_name=w['custodian_name'],
                description=w['description'],
            )
            created_wh[wh.code] = wh

        items_data = [
            # WH-HALL
            {
                'warehouse': created_wh['WH-HALL'],
                'item_code': 'AST-IT-001',
                'name': 'HP ProDesk 400 G7 Workstation PCs with Dual Monitors',
                'item_type': InventoryItem.TYPE_FIXED_ASSET,
                'tag_no': 'IT-WRK-001-008',
                'quantity': 8,
                'unit': 'Units',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('360000.00'),
                'storage_bay': 'Admin Office & Clearance Desk',
                'custodian': 'IT Administrator',
                'notes': 'Assigned to clearance issuance and resident records management.',
            },
            {
                'warehouse': created_wh['WH-HALL'],
                'item_code': 'AST-IT-002',
                'name': 'Epson EcoTank L3210 Multi-Function Document Printers',
                'item_type': InventoryItem.TYPE_FIXED_ASSET,
                'tag_no': 'IT-PRN-001-004',
                'quantity': 4,
                'unit': 'Units',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('38000.00'),
                'storage_bay': 'Records & Secretariat Counter',
                'custodian': 'Barangay Secretary Staff',
                'notes': 'Used for high-volume clearance certificate printing.',
            },
            {
                'warehouse': created_wh['WH-HALL'],
                'item_code': 'AST-FURN-001',
                'name': 'Heavy-Duty Steel Office Desks with 3-Tier Drawers',
                'item_type': InventoryItem.TYPE_FIXED_ASSET,
                'tag_no': 'FN-DSK-010-025',
                'quantity': 15,
                'unit': 'Units',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('112500.00'),
                'storage_bay': 'Main Hall & Committee Rooms',
                'custodian': 'Property Custodian',
                'notes': 'Fixed administrative desks.',
            },
            {
                'warehouse': created_wh['WH-HALL'],
                'item_code': 'AST-HVAC-001',
                'name': 'Daikin 2.5HP Inverter Split-Type Air Conditioning Units',
                'item_type': InventoryItem.TYPE_FIXED_ASSET,
                'tag_no': 'AC-SPL-001-003',
                'quantity': 3,
                'unit': 'Units',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('145000.00'),
                'storage_bay': 'Session Hall & Admin Office',
                'custodian': 'Maintenance Supervisor',
                'notes': 'Scheduled for bi-monthly maintenance.',
            },

            # WH-BDRRMC
            {
                'warehouse': created_wh['WH-BDRRMC'],
                'item_code': 'AST-RLF-001',
                'name': 'Emergency Family Food Packs (5kg Rice, Canned Fish, Coffee)',
                'item_type': InventoryItem.TYPE_RELIEF_GOOD,
                'tag_no': 'RLF-FDP-001',
                'quantity': 500,
                'unit': 'Packs',
                'condition': InventoryItem.CONDITION_STOCK,
                'estimated_value': Decimal('275000.00'),
                'storage_bay': 'Storage Bay A (Climate Controlled)',
                'custodian': 'Relief Goods Officer',
                'notes': 'Disaster reserve buffer. Expiry inspected monthly.',
            },
            {
                'warehouse': created_wh['WH-BDRRMC'],
                'item_code': 'AST-RLF-002',
                'name': 'Hygiene & Sanitation Kits (Soaps, Toothbrushes, Towels, Alcohol)',
                'item_type': InventoryItem.TYPE_RELIEF_GOOD,
                'tag_no': 'RLF-HYG-012',
                'quantity': 300,
                'unit': 'Kits',
                'condition': InventoryItem.CONDITION_STOCK,
                'estimated_value': Decimal('120000.00'),
                'storage_bay': 'Storage Bay B',
                'custodian': 'Social Welfare Focal Person',
                'notes': 'Ready for immediate dispatch during flood evacuation.',
            },
            {
                'warehouse': created_wh['WH-BDRRMC'],
                'item_code': 'AST-DRRM-001',
                'name': 'Heavy-Duty Rescue Rubber Boat with 30HP Outboard Motor',
                'item_type': InventoryItem.TYPE_RELIEF_GOOD,
                'tag_no': 'BOT-RSC-001',
                'quantity': 2,
                'unit': 'Boats',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('380000.00'),
                'storage_bay': 'Evacuation Compound Garage',
                'custodian': 'BDRRMC Rescue Lead',
                'notes': 'Equipped with 10 adult life jackets and oars.',
            },
            {
                'warehouse': created_wh['WH-BDRRMC'],
                'item_code': 'AST-DRRM-002',
                'name': 'Static Climbing Ropes (100m, 12mm) & Tactical Hard Hats',
                'item_type': InventoryItem.TYPE_RELIEF_GOOD,
                'tag_no': 'EQ-ROP-050',
                'quantity': 25,
                'unit': 'Sets',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('62500.00'),
                'storage_bay': 'Rescue Locker 4',
                'custodian': 'BDRRMC Rescue Lead',
                'notes': 'Certified for high-angle rescue and flood crossing.',
            },

            # WH-BHS
            {
                'warehouse': created_wh['WH-BHS'],
                'item_code': 'AST-MED-001',
                'name': 'Emergency Trauma Response Medical Kits (AED, Bag-Valve-Mask, Oxygen)',
                'item_type': InventoryItem.TYPE_MEDICAL,
                'tag_no': 'MED-KIT-001-004',
                'quantity': 4,
                'unit': 'Sets',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('180000.00'),
                'storage_bay': 'Health Station Triage Room',
                'custodian': 'Barangay Health Center Nurse',
                'notes': 'Maintained with battery check logs.',
            },
            {
                'warehouse': created_wh['WH-BHS'],
                'item_code': 'AST-MED-002',
                'name': 'Essential Maintenance Medicines (Paracetamol, Amoxicillin, Amlodipine)',
                'item_type': InventoryItem.TYPE_MEDICAL,
                'tag_no': 'MED-DRG-2026',
                'quantity': 1200,
                'unit': 'Boxes',
                'condition': InventoryItem.CONDITION_STOCK,
                'estimated_value': Decimal('96000.00'),
                'storage_bay': 'Pharmacy Cabinet 1 & 2',
                'custodian': 'Barangay Pharmacist',
                'notes': 'Dispensed for free to indigent and senior residents.',
            },
            {
                'warehouse': created_wh['WH-BHS'],
                'item_code': 'AST-MED-003',
                'name': 'Foldable Steel Wheelchairs & Mobile Stretchers',
                'item_type': InventoryItem.TYPE_MEDICAL,
                'tag_no': 'MED-WCH-001-006',
                'quantity': 6,
                'unit': 'Units',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('48000.00'),
                'storage_bay': 'Health Station Emergency Ward',
                'custodian': 'BHW Supervisor',
                'notes': 'Cleaned and sanitized after each patient transport.',
            },

            # WH-TANOD
            {
                'warehouse': created_wh['WH-TANOD'],
                'item_code': 'AST-TND-001',
                'name': 'Rechargeable Ultra-Bright Tactical LED Flashlights (10000 Lumens)',
                'item_type': InventoryItem.TYPE_PEACE_ORDER,
                'tag_no': 'TND-FLS-001-030',
                'quantity': 30,
                'unit': 'Units',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('45000.00'),
                'storage_bay': 'Tanod Station Charger Rack',
                'custodian': 'Tanod Desk Officer',
                'notes': 'Issued nightly to roving curfew patrols.',
            },
            {
                'warehouse': created_wh['WH-TANOD'],
                'item_code': 'AST-TND-002',
                'name': 'Dual-Band Handheld Two-Way Walkie-Talkies (UHF/VHF)',
                'item_type': InventoryItem.TYPE_PEACE_ORDER,
                'tag_no': 'TND-RAD-001-020',
                'quantity': 20,
                'unit': 'Radios',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('70000.00'),
                'storage_bay': 'Communications Command Desk',
                'custodian': 'Radio Communications Officer',
                'notes': 'Frequency programmed to Barangay Emergency Channel 1 & 2.',
            },
            {
                'warehouse': created_wh['WH-TANOD'],
                'item_code': 'AST-TND-003',
                'name': 'High-Visibility Reflective Patrol Vests & Defense Batons',
                'item_type': InventoryItem.TYPE_PEACE_ORDER,
                'tag_no': 'TND-VST-001-050',
                'quantity': 50,
                'unit': 'Sets',
                'condition': InventoryItem.CONDITION_OPERATIONAL,
                'estimated_value': Decimal('55000.00'),
                'storage_bay': 'Armory Locker B',
                'custodian': 'Chief Tanod Danilo Morales',
                'notes': 'Standard issue gear for peace and order personnel.',
            },
        ]

        for item in items_data:
            InventoryItem.objects.create(
                warehouse=item['warehouse'],
                item_code=item['item_code'],
                name=item['name'],
                item_type=item['item_type'],
                tag_no=item['tag_no'],
                quantity=item['quantity'],
                unit=item['unit'],
                condition=item['condition'],
                estimated_value=item['estimated_value'],
                storage_bay=item['storage_bay'],
                custodian=item['custodian'],
                notes=item['notes'],
            )


@transaction.atomic
def process_stock_movement(item, movement_type, quantity, purpose='', reference_no='', handled_by=None):
    """
    Performs an isolated stock-in, stock-out, or adjustment on an inventory item.
    Guarantees that a stock movement in one warehouse never touches other warehouses.
    """
    prev_qty = item.quantity
    if movement_type == StockMovement.MOVEMENT_IN:
        new_qty = prev_qty + quantity
    elif movement_type == StockMovement.MOVEMENT_OUT:
        new_qty = max(0, prev_qty - quantity)
    else:  # adjustment
        new_qty = quantity

    item.quantity = new_qty
    item.save(update_fields=['quantity', 'updated_at'])

    movement = StockMovement.objects.create(
        item=item,
        movement_type=movement_type,
        quantity=quantity,
        previous_quantity=prev_qty,
        new_quantity=new_qty,
        reference_no=reference_no,
        purpose=purpose,
        handled_by=handled_by,
    )
    return movement
