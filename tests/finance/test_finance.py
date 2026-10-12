from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.finance.models import FinancialAccount, FinancialTransaction
from apps.finance.services import ensure_default_financial_data


class FinanceManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin_test',
            email='admin@barangay.ph',
            password='testpassword123'
        )
        self.client = Client()
        self.client.force_login(self.user)
        ensure_default_financial_data()

    def test_default_accounts_seeded(self):
        self.assertTrue(FinancialAccount.objects.filter(code='GF-101').exists())
        self.assertTrue(FinancialAccount.objects.filter(code='SK-201').exists())
        self.assertTrue(FinancialAccount.objects.filter(code='BDRRMF-301').exists())
        self.assertTrue(FinancialAccount.objects.filter(code='BDF-401').exists())
        self.assertTrue(FinancialAccount.objects.filter(code='COLL-501').exists())

    def test_financial_transaction_requires_source_account(self):
        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'create_transaction',
            'transaction_type': 'expense',
            'amount': '5000',
            'title': 'Test Disbursement',
        })
        self.assertEqual(response.status_code, 200)

        gf_acc = FinancialAccount.objects.get(code='GF-101')
        initial_balance = gf_acc.current_balance

        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'create_transaction',
            'account_id': gf_acc.id,
            'transaction_type': 'expense',
            'amount': '5000.00',
            'title': 'Procurement of Clearances Paper',
            'reference_no': 'DV-TEST-001',
        })
        self.assertEqual(response.status_code, 302)
        gf_acc.refresh_from_db()
        self.assertEqual(gf_acc.current_balance, initial_balance - Decimal('5000.00'))

    def test_create_custom_financial_account(self):
        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'create_account',
            'name': 'Senior Citizens Special Assistance Fund',
            'code': 'SC-601',
            'account_type': FinancialAccount.ACCOUNT_TYPE_OTHER,
            'initial_allocation': '250000.00',
            'accountable_officer': 'OSCA Focal Officer',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(FinancialAccount.objects.filter(code='SC-601').exists())

    def test_default_cash_advances_seeded(self):
        from apps.finance.models import CashAdvance
        self.assertTrue(CashAdvance.objects.filter(ref_no='CA-2026-008', status=CashAdvance.STATUS_LIQUIDATED).exists())
        self.assertTrue(CashAdvance.objects.filter(ref_no='CA-2026-009', status=CashAdvance.STATUS_LIQUIDATED).exists())
        self.assertTrue(CashAdvance.objects.filter(ref_no='CA-2026-010', status=CashAdvance.STATUS_PENDING).exists())

    def test_liquidate_pending_cash_advance_with_refund(self):
        from apps.finance.models import CashAdvance
        ca = CashAdvance.objects.get(ref_no='CA-2026-010')
        self.assertEqual(ca.status, CashAdvance.STATUS_PENDING)

        account = ca.account
        starting_balance = account.current_balance

        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'liquidate_cash_advance',
            'ca_id': ca.id,
            'actual_spent': '15500.00',
            'refund_amount': '2500.00',
            'or_number': 'LR-2026-010',
            'remarks': 'Drill logistics verified; excess food allowance refunded.',
        })
        self.assertEqual(response.status_code, 302)

        ca.refresh_from_db()
        self.assertEqual(ca.status, CashAdvance.STATUS_LIQUIDATED)
        self.assertEqual(ca.actual_spent, Decimal('15500.00'))
        self.assertEqual(ca.refund_amount, Decimal('2500.00'))
        self.assertEqual(ca.or_number, 'LR-2026-010')

        # Verify excess cash refund is credited back to source fund
        account.refresh_from_db()
        self.assertEqual(account.current_balance, starting_balance + Decimal('2500.00'))
        self.assertTrue(
            FinancialTransaction.objects.filter(
                account=account,
                transaction_type=FinancialTransaction.TYPE_INCOME,
                amount=Decimal('2500.00'),
                reference_no='LR-2026-010'
            ).exists()
        )

    def test_liquidate_validation_rejects_overspend_exceeding_granted(self):
        from apps.finance.models import CashAdvance
        ca = CashAdvance.objects.get(ref_no='CA-2026-010')
        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'liquidate_cash_advance',
            'ca_id': ca.id,
            'actual_spent': '20000.00',
            'refund_amount': '0.00',
        })
        self.assertEqual(response.status_code, 200)
        ca.refresh_from_db()
        self.assertEqual(ca.status, CashAdvance.STATUS_PENDING)

    def test_create_cash_advance_with_disbursement(self):
        from apps.finance.models import CashAdvance, FinancialAccount
        gf_acc = FinancialAccount.objects.get(code='GF-101')
        start_bal = gf_acc.current_balance

        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'create_cash_advance',
            'account_id': gf_acc.id,
            'officer': 'Federeck Morales',
            'role': 'Disaster Officer',
            'purpose': 'Medical Supply Outreach Logistics',
            'amount': '1000.00',
            'ref_no': 'CA-2026-099',
            'post_disbursement': 'on',
        })
        self.assertEqual(response.status_code, 302)

        ca = CashAdvance.objects.get(ref_no='CA-2026-099')
        self.assertEqual(ca.officer, 'Federeck Morales')
        self.assertEqual(ca.amount, Decimal('1000.00'))
        self.assertEqual(ca.status, CashAdvance.STATUS_PENDING)

        gf_acc.refresh_from_db()
        self.assertEqual(gf_acc.current_balance, start_bal - Decimal('1000.00'))

    def test_create_supplier(self):
        from apps.finance.models import Supplier
        response = self.client.post(reverse('finance:financial_management'), {
            'action': 'create_supplier',
            'name': 'VitalHealth Medical Supplies',
            'tin': '998-112-334-000',
            'category': 'Medical & First Aid',
            'contact_person': 'Elena Torres',
            'phone': '0917-888-9999',
            'address': 'Quezon City',
            'terms': 'Net 30 Days',
            'status': 'Accredited Active',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Supplier.objects.filter(name='VitalHealth Medical Supplies').exists())

