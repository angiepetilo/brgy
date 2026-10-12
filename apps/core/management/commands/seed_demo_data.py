from django.core.management.base import BaseCommand
from apps.finance.services import ensure_default_financial_data
from apps.inventory.services import ensure_default_inventory_data


class Command(BaseCommand):
    help = 'Seeds standard baseline demo financial accounts, transactions, warehouses, and inventory items.'

    def handle(self, *args, **options):
        self.stdout.write('Seeding default financial data...')
        ensure_default_financial_data()
        self.stdout.write(self.style.SUCCESS('Financial data seeded successfully.'))

        self.stdout.write('Seeding default inventory data...')
        ensure_default_inventory_data()
        self.stdout.write(self.style.SUCCESS('Inventory data seeded successfully.'))
