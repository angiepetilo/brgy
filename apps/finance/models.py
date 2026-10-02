from django.db import models
from django.conf import settings


class AssetInventory(models.Model):
    """
    Barangay asset and property inventory record.

    Normal-Form compliance:
    1NF FIX – the old `remarks` TextField stored composite information
          (location + custodian + maintenance notes) in a single free-text
          column, violating 1NF atomicity.  Replaced with three separate,
          atomic columns: location, custodian, and maintenance_notes.
    2NF – all non-key attributes depend fully on the single PK (id).
    3NF – category and condition are controlled-vocabulary CharField values;
          no transitive dependencies exist (each attribute describes the asset
          directly, not via another non-key attribute).
    """

    CATEGORY_VEHICLE = 'Vehicle'
    CATEGORY_EQUIPMENT = 'Equipment'
    CATEGORY_EMERGENCY = 'Emergency Tool'
    CATEGORY_FURNITURE = 'Furniture'

    CATEGORY_CHOICES = [
        (CATEGORY_VEHICLE, 'Vehicle'),
        (CATEGORY_EQUIPMENT, 'Equipment'),
        (CATEGORY_EMERGENCY, 'Emergency Tool'),
        (CATEGORY_FURNITURE, 'Furniture'),
    ]

    CONDITION_GOOD = 'Good'
    CONDITION_MAINTENANCE = 'Maintenance'
    CONDITION_DISPOSED = 'Disposed'

    CONDITION_CHOICES = [
        (CONDITION_GOOD, 'Good'),
        (CONDITION_MAINTENANCE, 'Maintenance'),
        (CONDITION_DISPOSED, 'Disposed'),
    ]

    item_name = models.CharField(
        max_length=200,
        help_text="e.g. Barangay Patrol Vehicle, Portable Honda Generator, Rescue Chainsaw"
    )
    category = models.CharField(
        max_length=50,
        choices=CATEGORY_CHOICES,
        default=CATEGORY_EQUIPMENT
    )
    quantity = models.PositiveIntegerField(default=1)
    condition = models.CharField(
        max_length=50,
        choices=CONDITION_CHOICES,
        default=CONDITION_GOOD
    )
    date_acquired = models.DateField(
        help_text="Acquisition or delivery date"
    )
    serial_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Property tag or Serial number if applicable"
    )

    # 1NF FIX: replaced the composite `remarks` TextField with three atomic
    # columns so each fact is stored in exactly one, well-defined column.
    location = models.CharField(
        max_length=255,
        blank=True,
        help_text="Current storage/deployment location (e.g. Barangay Hall Storage Room)"
    )
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='custodian_assets',
        help_text="Staff member responsible for this asset"
    )
    maintenance_notes = models.TextField(
        blank=True,
        help_text="Maintenance history, repair notes, or general remarks about this asset"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['category', 'item_name']
        verbose_name = 'Barangay Asset & Property'
        verbose_name_plural = 'Barangay Asset Inventory'

    def __str__(self):
        return f"{self.item_name} ({self.category}) - Qty: {self.quantity} [{self.condition}]"

    @property
    def condition_badge(self):
        mapping = {
            self.CONDITION_GOOD: 'badge-success',
            self.CONDITION_MAINTENANCE: 'badge-warning',
            self.CONDITION_DISPOSED: 'badge-danger',
        }
        return mapping.get(self.condition, 'badge-secondary')
