import datetime
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.finance.models import FinancialAccount, FinancialTransaction, CashAdvance


def ensure_default_financial_data():
    """
    Ensures standard baseline Barangay accounts and transactions
    are seeded if tables are empty.
    """
    if not FinancialAccount.objects.exists():
        accounts_data = [
            {
                'name': 'Barangay General Fund (GF)',
                'code': 'GF-101',
                'account_type': FinancialAccount.ACCOUNT_TYPE_GF,
                'description': 'Core operating budget, National Tax Allotment (NTA/IRA), and statutory maintenance allotments.',
                'initial_allocation': Decimal('12500000.00'),
                'accountable_officer': 'Ma. Teresa Ramos (Barangay Treasurer)',
            },
            {
                'name': 'Sangguniang Kabataan (SK) Fund (10%)',
                'code': 'SK-201',
                'account_type': FinancialAccount.ACCOUNT_TYPE_SK,
                'description': 'Mandated 10% youth development programs, scholarship assistance, and leadership seminars.',
                'initial_allocation': Decimal('1250000.00'),
                'accountable_officer': 'Mark Anthony Santos (SK Treasurer)',
            },
            {
                'name': 'Barangay Disaster Risk Reduction & Management Fund (BDRRMF - 5%)',
                'code': 'BDRRMF-301',
                'account_type': FinancialAccount.ACCOUNT_TYPE_CALAMITY,
                'description': 'Mandated 5% disaster preparedness, quick response reserves, and relief stockpile replenishment.',
                'initial_allocation': Decimal('625000.00'),
                'accountable_officer': 'Ernesto Valenzuela (BDRRMC Head)',
            },
            {
                'name': '20% Barangay Development Fund (BDF)',
                'code': 'BDF-401',
                'account_type': FinancialAccount.ACCOUNT_TYPE_DEV,
                'description': 'Dedicated 20% statutory allocation for community infrastructure, streetlighting, and health post upgrades.',
                'initial_allocation': Decimal('2500000.00'),
                'accountable_officer': 'Engr. Danilo Cruz (Infrastructure Kagawad)',
            },
            {
                'name': 'Barangay Collections & Local Revenue',
                'code': 'COLL-501',
                'account_type': FinancialAccount.ACCOUNT_TYPE_COLLECTIONS,
                'description': 'Local internally-generated revenues from clearance fees, CTC cedula shares, permits, and stalls.',
                'initial_allocation': Decimal('450000.00'),
                'accountable_officer': 'Ma. Teresa Ramos (Barangay Treasurer)',
            },
        ]

        created_accounts = {}
        for d in accounts_data:
            acc = FinancialAccount.objects.create(
                name=d['name'],
                code=d['code'],
                account_type=d['account_type'],
                description=d['description'],
                initial_allocation=d['initial_allocation'],
                current_balance=d['initial_allocation'],
                accountable_officer=d['accountable_officer'],
            )
            created_accounts[acc.code] = acc

        transactions_data = [
            {
                'account': created_accounts['GF-101'],
                'transaction_type': FinancialTransaction.TYPE_EXPENSE,
                'reference_no': 'DV-2026-0042',
                'title': 'Office Supplies & Clearance Security Paper',
                'amount': Decimal('34500.00'),
                'payee_or_source': 'Manila Paper & Supply Co.',
                'uacs_code': '5-02-03-010',
                'particulars': 'Stationery, official document security paper, and printer toner cartridges',
            },
            {
                'account': created_accounts['BDRRMF-301'],
                'transaction_type': FinancialTransaction.TYPE_EXPENSE,
                'reference_no': 'DV-2026-0041',
                'title': 'Emergency Medical Kits & Trauma Packs',
                'amount': Decimal('78200.00'),
                'payee_or_source': 'PhilPharma Medical Distributors',
                'uacs_code': '5-02-03-080',
                'particulars': 'Replenishment of emergency response kits, bandages, and oxygen cylinder refills',
            },
            {
                'account': created_accounts['BDF-401'],
                'transaction_type': FinancialTransaction.TYPE_EXPENSE,
                'reference_no': 'DV-2026-0040',
                'title': 'Purok Drainage De-clogging & Pathway Repair Supplies',
                'amount': Decimal('45000.00'),
                'payee_or_source': 'BuildCraft Hardware & Const. Supplies',
                'uacs_code': '5-02-13-040',
                'particulars': 'Cement covers, pipes, gravel, and construction materials for drainage rehabilitation',
            },
            {
                'account': created_accounts['BDF-401'],
                'transaction_type': FinancialTransaction.TYPE_EXPENSE,
                'reference_no': 'DV-2026-0039',
                'title': 'Solar Street Lighting Units (8 sets installed)',
                'amount': Decimal('120000.00'),
                'payee_or_source': 'SolTech Energy Solutions Inc.',
                'uacs_code': '1-06-05-990',
                'particulars': 'Turnkey installation of heavy duty solar lighting across vulnerable Purok alleys',
            },
            {
                'account': created_accounts['GF-101'],
                'transaction_type': FinancialTransaction.TYPE_EXPENSE,
                'reference_no': 'DV-2026-0038',
                'title': 'Tanod Brigade Night Patrol Honoraria',
                'amount': Decimal('180000.00'),
                'payee_or_source': 'Barangay Tanod Brigade Officers',
                'uacs_code': '5-01-02-990',
                'particulars': 'Monthly night duty honoraria and emergency peace-and-order hazard compensation',
            },
            {
                'account': created_accounts['COLL-501'],
                'transaction_type': FinancialTransaction.TYPE_INCOME,
                'reference_no': 'OR-2026-1052',
                'title': 'Barangay Clearance & Business Permit Collections (Oct 1-7)',
                'amount': Decimal('84500.00'),
                'payee_or_source': 'Barangay Cashier Counter',
                'uacs_code': '4-01-01-010',
                'particulars': 'Statutory revenue remittances from resident clearances, residency certificates, and stalls',
            },
            {
                'account': created_accounts['SK-201'],
                'transaction_type': FinancialTransaction.TYPE_EXPENSE,
                'reference_no': 'DV-2026-SK05',
                'title': 'Youth Inter-Purok Basketball League & Sports Equipment',
                'amount': Decimal('65000.00'),
                'payee_or_source': 'ActiveSports Outfitters',
                'uacs_code': '5-02-99-990',
                'particulars': 'Sports jerseys, balls, whistles, trophies, and tournament officiating kits',
            },
        ]

        for tx in transactions_data:
            FinancialTransaction.objects.create(
                account=tx['account'],
                transaction_type=tx['transaction_type'],
                reference_no=tx['reference_no'],
                title=tx['title'],
                amount=tx['amount'],
                payee_or_source=tx['payee_or_source'],
                uacs_code=tx['uacs_code'],
                particulars=tx['particulars'],
            )

    # Seed baseline Cash Advance records if table is empty
    if not CashAdvance.objects.exists():
        gf_acc = FinancialAccount.objects.filter(code='GF-101').first() or FinancialAccount.objects.first()
        bdrrmf_acc = FinancialAccount.objects.filter(code='BDRRMF-301').first() or gf_acc

        if gf_acc and bdrrmf_acc:
            CashAdvance.objects.create(
                account=gf_acc,
                ref_no='CA-2026-008',
                officer='Dr. Remedios Santos, MD',
                role='Municipal Health Physician',
                purpose='Community Medical Outreach & Free Vaccination Caravan',
                amount=Decimal('25000.00'),
                date_granted=datetime.date(2026, 9, 10),
                liquidation_deadline='Sep 25, 2026',
                liquidation_date=datetime.date(2026, 9, 25),
                status=CashAdvance.STATUS_LIQUIDATED,
                actual_spent=Decimal('25000.00'),
                refund_amount=Decimal('0.00'),
                or_number='LR-2026-008',
                remarks='Approved by Barangay Treasurer & Punong Barangay',
            )
            CashAdvance.objects.create(
                account=gf_acc,
                ref_no='CA-2026-009',
                officer='Hon. Ernesto Valenzuela',
                role='Punong Barangay',
                purpose='Barangay Clean-Up Drive & Drainage Debris Disposal Meals',
                amount=Decimal('15000.00'),
                date_granted=datetime.date(2026, 9, 18),
                liquidation_deadline='Oct 02, 2026',
                liquidation_date=datetime.date(2026, 10, 2),
                status=CashAdvance.STATUS_LIQUIDATED,
                actual_spent=Decimal('15000.00'),
                refund_amount=Decimal('0.00'),
                or_number='LR-2026-009',
                remarks='Official receipts and attendance verified',
            )
            CashAdvance.objects.create(
                account=bdrrmf_acc,
                ref_no='CA-2026-010',
                officer='Sgt. Fernando Morales',
                role='Disaster Risk Reduction Officer',
                purpose='Disaster Drill Simulation & Rescue Trainee Logistics',
                amount=Decimal('18000.00'),
                date_granted=datetime.date(2026, 10, 4),
                liquidation_deadline='Oct 25, 2026 (Upcoming)',
                status=CashAdvance.STATUS_PENDING,
                remarks='Within 30-day statutory liquidation window',
            )


@transaction.atomic
def record_financial_transaction(account, transaction_type, title, amount, reference_no='',
                                 payee_or_source='', uacs_code='', particulars='', recorded_by=None):
    """
    Creates a transaction for the designated account and updates balance.
    """
    tx = FinancialTransaction.objects.create(
        account=account,
        transaction_type=transaction_type,
        reference_no=reference_no,
        title=title,
        amount=amount,
        payee_or_source=payee_or_source,
        uacs_code=uacs_code,
        particulars=particulars,
        recorded_by=recorded_by,
    )
    return tx


@transaction.atomic
def liquidate_cash_advance(cash_advance, actual_spent, refund_amount=Decimal('0.00'),
                           or_number='', remarks='', liquidated_by=None):
    """
    Settles a pending cash advance.
    If refund_amount > 0, records an Income transaction returning excess cash to the account.
    """
    cash_advance.status = CashAdvance.STATUS_LIQUIDATED
    cash_advance.actual_spent = actual_spent
    cash_advance.refund_amount = refund_amount
    cash_advance.or_number = or_number
    cash_advance.liquidation_date = timezone.now().date()
    if remarks:
        cash_advance.remarks = remarks
    else:
        cash_advance.remarks = f"Liquidated with official receipts on {timezone.now().strftime('%b %d, %Y')}"
    cash_advance.liquidated_by = liquidated_by
    cash_advance.liquidated_at = timezone.now()
    cash_advance.save()

    # If unspent money is returned, credit the source fund as income
    if refund_amount and refund_amount > Decimal('0.00'):
        ref_label = or_number or f"REF-{cash_advance.ref_no}"
        record_financial_transaction(
            account=cash_advance.account,
            transaction_type=FinancialTransaction.TYPE_INCOME,
            title=f"Cash Advance Refund - {cash_advance.ref_no} ({cash_advance.officer})",
            amount=refund_amount,
            reference_no=ref_label,
            payee_or_source=cash_advance.officer,
            uacs_code='4-01-01-010',
            particulars=f"Unexpended cash refund returned to {cash_advance.account.name}. {remarks}".strip(),
            recorded_by=liquidated_by,
        )

    return cash_advance
