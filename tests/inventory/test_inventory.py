from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.inventory.models import InventoryWarehouse, InventoryItem, StockMovement
from apps.inventory.services import ensure_default_inventory_data


class InventoryManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_test',
            email='admin@barangay.ph',
            password='testpassword123'
        )
        self.client = Client()
        self.client.force_login(self.user)
        ensure_default_inventory_data()

    def test_default_warehouses_seeded(self):
        self.assertTrue(InventoryWarehouse.objects.filter(code='WH-HALL').exists())
        self.assertTrue(InventoryWarehouse.objects.filter(code='WH-BDRRMC').exists())
        self.assertTrue(InventoryWarehouse.objects.filter(code='WH-BHS').exists())
        self.assertTrue(InventoryWarehouse.objects.filter(code='WH-TANOD').exists())

    def test_create_custom_warehouse_and_item(self):
        response = self.client.post(reverse('inventory:inventory'), {
            'action': 'create_warehouse',
            'name': 'Barangay Agriculture & Seed Depot',
            'code': 'WH-AGRI',
            'department': 'Agriculture & Livelihood',
            'location_address': 'Barangay Nursery compound',
            'custodian_name': 'Kagawad on Agriculture',
        })
        self.assertEqual(response.status_code, 302)
        wh = InventoryWarehouse.objects.get(code='WH-AGRI')

        response = self.client.post(reverse('inventory:inventory'), {
            'action': 'create_item',
            'warehouse_id': wh.id,
            'name': 'High-Yield Vegetable Seed Packs (Hybrid Tomato & Eggplant)',
            'item_code': 'AST-AGRI-001',
            'quantity': 150,
            'unit': 'Packs',
            'estimated_value': '7500.00',
        })
        self.assertEqual(response.status_code, 302)
        item = InventoryItem.objects.get(item_code='AST-AGRI-001')
        self.assertEqual(item.warehouse, wh)
        self.assertEqual(item.quantity, 150)

    def test_isolated_stock_movement(self):
        bhs_wh = InventoryWarehouse.objects.get(code='WH-BHS')
        bhs_item = InventoryItem.objects.filter(warehouse=bhs_wh).first()
        bhs_initial_qty = bhs_item.quantity

        relief_wh = InventoryWarehouse.objects.get(code='WH-BDRRMC')
        relief_item = InventoryItem.objects.filter(warehouse=relief_wh).first()
        relief_initial_qty = relief_item.quantity

        response = self.client.post(reverse('inventory:inventory'), {
            'action': 'stock_movement',
            'item_id': bhs_item.id,
            'movement_type': StockMovement.MOVEMENT_OUT,
            'quantity': 1,
            'purpose': 'Consultation clinic use',
        })
        self.assertEqual(response.status_code, 302)

        bhs_item.refresh_from_db()
        relief_item.refresh_from_db()

        self.assertEqual(bhs_item.quantity, bhs_initial_qty - 1)
        self.assertEqual(relief_item.quantity, relief_initial_qty)

    def test_inventory_sorting(self):
        response = self.client.get(reverse('inventory:inventory'), {'sort': 'quantity', 'dir': 'desc'})
        self.assertEqual(response.status_code, 200)
        items = list(response.context['items'])
        for i in range(len(items) - 1):
            self.assertGreaterEqual(items[i].quantity, items[i + 1].quantity)

        response = self.client.get(reverse('inventory:inventory'), {'sort': 'name', 'dir': 'asc'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_sort'], 'name')
        self.assertEqual(response.context['current_dir'], 'asc')

