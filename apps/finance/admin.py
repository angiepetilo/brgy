from django.contrib import admin
from apps.finance.models import AssetInventory


@admin.register(AssetInventory)
class AssetInventoryAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'category', 'quantity', 'condition', 'date_acquired', 'serial_number')
    list_filter = ('category', 'condition', 'date_acquired')
    search_fields = ('item_name', 'serial_number', 'remarks')
