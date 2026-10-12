from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class InventoryWarehouse(models.Model):
    name = models.CharField(max_length=150)
    code = models.CharField(max_length=40, unique=True)
    department = models.CharField(max_length=100, blank=True)
    location_address = models.CharField(max_length=255, blank=True)
    custodian_name = models.CharField(max_length=150, blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_warehouses'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    @property
    def total_items(self):
        return self.items.count()

    @property
    def total_stock_quantity(self):
        return self.items.aggregate(total=models.Sum('quantity'))['total'] or 0


class InventoryItem(models.Model):
    TYPE_FIXED_ASSET = 'fixed_asset'
    TYPE_RELIEF_GOOD = 'relief_good'
    TYPE_MEDICAL = 'medical_supply'
    TYPE_PEACE_ORDER = 'tanod_gear'
    TYPE_EVENT = 'event_supply'
    TYPE_CONSUMABLE = 'consumable'

    ITEM_TYPE_CHOICES = [
        (TYPE_FIXED_ASSET, 'Fixed Asset'),
        (TYPE_RELIEF_GOOD, 'Disaster Relief Goods'),
        (TYPE_MEDICAL, 'Medical Supplies'),
        (TYPE_PEACE_ORDER, 'Tanod Gear'),
        (TYPE_EVENT, 'Event Supplies'),
        (TYPE_CONSUMABLE, 'Consumables'),
    ]

    CONDITION_OPERATIONAL = 'operational'
    CONDITION_STOCK = 'in_stock'
    CONDITION_LOW = 'low_stock'
    CONDITION_REPAIR = 'for_repair'
    CONDITION_DAMAGED = 'damaged'
    CONDITION_DISPOSED = 'disposed'

    CONDITION_CHOICES = [
        (CONDITION_OPERATIONAL, 'Operational'),
        (CONDITION_STOCK, 'Stocked'),
        (CONDITION_LOW, 'Low Stock'),
        (CONDITION_REPAIR, 'For Repair'),
        (CONDITION_DAMAGED, 'Damaged'),
        (CONDITION_DISPOSED, 'Disposed'),
    ]

    warehouse = models.ForeignKey(InventoryWarehouse, on_delete=models.CASCADE, related_name='items')
    item_code = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=255)
    item_type = models.CharField(max_length=50, choices=ITEM_TYPE_CHOICES, default=TYPE_FIXED_ASSET)
    tag_no = models.CharField(max_length=60, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    unit = models.CharField(max_length=30, default='Units')
    condition = models.CharField(max_length=50, choices=CONDITION_CHOICES, default=CONDITION_OPERATIONAL)
    estimated_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    storage_bay = models.CharField(max_length=150, blank=True)
    custodian = models.CharField(max_length=150, blank=True)
    acquired_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'inventory_items'
        ordering = ['warehouse', 'item_code', 'name']

    def __str__(self):
        return f"[{self.warehouse.code}] {self.name} ({self.quantity} {self.unit})"


class StockMovement(models.Model):
    MOVEMENT_IN = 'stock_in'
    MOVEMENT_OUT = 'stock_out'
    MOVEMENT_ADJUSTMENT = 'adjustment'

    MOVEMENT_CHOICES = [
        (MOVEMENT_IN, 'Stock In'),
        (MOVEMENT_OUT, 'Stock Out'),
        (MOVEMENT_ADJUSTMENT, 'Count Adjustment'),
    ]

    item = models.ForeignKey(InventoryItem, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=30, choices=MOVEMENT_CHOICES)
    quantity = models.PositiveIntegerField()
    previous_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    reference_no = models.CharField(max_length=60, blank=True)
    purpose = models.CharField(max_length=255, blank=True)
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_stock_movements'
    )
    date = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = 'inventory_stock_movements'
        ordering = ['-date', '-id']

    def __str__(self):
        return f"{self.get_movement_type_display()} - {self.item.name} ({self.quantity} {self.item.unit})"
