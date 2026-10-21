import datetime
import re
from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q, Sum
from apps.accounts.permissions import resident_forbidden
from apps.finance.models import FinancialAccount, FinancialTransaction, CashAdvance, Supplier
from apps.finance.services import (
    ensure_default_financial_data,
    record_financial_transaction,
    liquidate_cash_advance,
)

MAX_PESO_AMOUNT = Decimal('999999999999.99')


def parse_peso_amount(raw_value, allow_zero=True):
    """
    Validates and parses a Philippine Peso currency string.
    Rules:
    - Strips '₱', 'PHP', spaces, and thousands-separator commas.
    - Rejects strings/letters, multiple decimals, negative numbers, or invalid inputs.
    - Limits value to <= ₱999,999,999,999.99 (matches DecimalField(max_digits=14, decimal_places=2)).
    Returns (Decimal, None) on success or (None, error_message_str) on failure.
    """
    if raw_value is None:
        return (Decimal('0.00'), None) if allow_zero else (None, 'Amount is required.')

    cleaned = str(raw_value).strip().replace('₱', '').replace('PHP', '').replace('php', '').replace(',', '').strip()
    if not cleaned:
        return (Decimal('0.00'), None) if allow_zero else (None, 'Amount is required.')

    # Do not allow letters, negative values, or invalid formats; must be standard numeric decimal
    if not re.match(r'^\d+(\.\d{1,2})?$', cleaned):
        return None, 'Amount must be a valid number following the Philippine Peso standard (e.g. 500,000.00). Letters and special characters are not allowed.'

    try:
        val = Decimal(cleaned)
    except (InvalidOperation, TypeError):
        return None, 'Invalid numeric value.'

    if not allow_zero and val <= Decimal('0.00'):
        return None, 'Amount must be greater than zero.'

    if val < Decimal('0.00'):
        return None, 'Amount cannot be negative.'

    if val > MAX_PESO_AMOUNT:
        return None, f'Amount exceeds the maximum allowable budget of ₱{MAX_PESO_AMOUNT:,.2f}.'

    return val, None


@resident_forbidden
def financial_management_view(request):
    """
    Budget and Financial Management (Multi-Account Ledger Architecture):
    Features separate financial pipeline profiles for:
    - General Fund (GF): Core operating budget & NTA/IRA allotment
    - SK Fund (Sangguniang Kabataan): Mandated 10% youth allocation
    - Calamity Fund (BDRRMF): Mandated 5% disaster response & relief fund
    - Development Fund: 20% allocation dedicated to local development projects
    - Barangay Collections: Local internally-generated clearance and permit revenues
    Every transaction (Income or Expense) requires the user to select the Source Account
    from a dropdown list to prevent mixing of funds.
    """
    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'create_account':
            name = request.POST.get('name', '').strip()
            code = request.POST.get('code', '').strip().upper()
            account_type = request.POST.get('account_type', FinancialAccount.ACCOUNT_TYPE_GF)
            accountable_officer = request.POST.get('accountable_officer', '').strip()
            description = request.POST.get('description', '').strip()

            initial_allocation, err = parse_peso_amount(
                request.POST.get('initial_allocation', '0'),
                allow_zero=True
            )
            if err:
                messages.error(request, err)
                return redirect(f"{request.path}?tab=accounts")

            if not name or not code:
                messages.error(request, 'Account name and unique code are required.')
            elif FinancialAccount.objects.filter(code=code).exists():
                messages.error(request, f'An account with code "{code}" already exists.')
            else:
                acc = FinancialAccount.objects.create(
                    name=name,
                    code=code,
                    account_type=account_type,
                    initial_allocation=initial_allocation,
                    current_balance=initial_allocation,
                    accountable_officer=accountable_officer,
                    description=description,
                )
                messages.success(request, f'New financial account "{acc.name}" ({acc.code}) created successfully.')
                return redirect(f"{request.path}?tab=accounts")

        elif action == 'create_transaction':
            account_id = request.POST.get('account_id')
            transaction_type = request.POST.get('transaction_type', FinancialTransaction.TYPE_EXPENSE)
            title = request.POST.get('title', '').strip()
            reference_no = request.POST.get('reference_no', '').strip()
            payee_or_source = request.POST.get('payee_or_source', '').strip()
            uacs_code = request.POST.get('uacs_code', '').strip()
            particulars = request.POST.get('particulars', '').strip()

            amount, err = parse_peso_amount(request.POST.get('amount'), allow_zero=False)
            if err:
                messages.error(request, err)
                return redirect(f"{request.path}?tab=transactions")

            if not account_id:
                messages.error(request, 'Selection of Source Account from dropdown is required to prevent mixing of funds.')
            elif not title:
                messages.error(request, 'Transaction title or payee is required.')
            else:
                account = get_object_or_404(FinancialAccount, id=account_id)
                tx = record_financial_transaction(
                    account=account,
                    transaction_type=transaction_type,
                    title=title,
                    amount=amount,
                    reference_no=reference_no,
                    payee_or_source=payee_or_source,
                    uacs_code=uacs_code,
                    particulars=particulars,
                    recorded_by=request.user,
                )
                type_label = 'Income' if transaction_type == 'income' else 'Disbursement'
                messages.success(
                    request,
                    f'{type_label} of ₱{amount:,.2f} recorded under {account.name}. Updated balance: ₱{account.current_balance:,.2f}.'
                )
                return redirect(f"{request.path}?tab=transactions&account={account.id}")

        elif action == 'liquidate_cash_advance':
            ca_id = request.POST.get('ca_id')
            ca = get_object_or_404(CashAdvance, id=ca_id)

            actual_spent, err_spent = parse_peso_amount(request.POST.get('actual_spent', '0'), allow_zero=True)
            if err_spent:
                messages.error(request, f'Actual spent: {err_spent}')
                return redirect(f"{request.path}?tab=liquidations")

            refund_amount, err_refund = parse_peso_amount(request.POST.get('refund_amount', '0'), allow_zero=True)
            if err_refund:
                messages.error(request, f'Refund amount: {err_refund}')
                return redirect(f"{request.path}?tab=liquidations")

            or_number = request.POST.get('or_number', '').strip()
            remarks = request.POST.get('remarks', '').strip()

            if actual_spent + refund_amount > ca.amount:
                messages.error(
                    request,
                    f'Total accounted amount (₱{actual_spent + refund_amount:,.2f}) cannot exceed granted advance of ₱{ca.amount:,.2f}.'
                )
            else:
                liquidate_cash_advance(
                    cash_advance=ca,
                    actual_spent=actual_spent,
                    refund_amount=refund_amount,
                    or_number=or_number,
                    remarks=remarks,
                    liquidated_by=request.user,
                )
                msg = f'Cash Advance {ca.ref_no} for {ca.officer} is now Fully Liquidated.'
                if refund_amount > Decimal('0.00'):
                    msg += f' Excess refund of ₱{refund_amount:,.2f} credited back to {ca.account.name}.'
                messages.success(request, msg)
                return redirect(f"{request.path}?tab=liquidations")

        elif action == 'create_cash_advance':
            account_id = request.POST.get('account_id')
            officer = request.POST.get('officer', '').strip()
            role = request.POST.get('role', '').strip()
            purpose = request.POST.get('purpose', '').strip()
            ref_no = request.POST.get('ref_no', '').strip().upper()
            liquidation_deadline = request.POST.get('liquidation_deadline', '').strip()
            post_disbursement = request.POST.get('post_disbursement') == 'on'

            amount, err = parse_peso_amount(request.POST.get('amount'), allow_zero=False)
            if err:
                messages.error(request, err)
                return redirect(f"{request.path}?tab=liquidations")

            account = get_object_or_404(FinancialAccount, id=account_id) if account_id else None

            if not account:
                messages.error(request, 'Please select a source fund account for the cash advance.')
            elif not officer or not purpose:
                messages.error(request, 'Accountable officer and purpose are required.')
            else:
                if not ref_no:
                    curr_year = datetime.date.today().year
                    count = CashAdvance.objects.filter(ref_no__startswith=f'CA-{curr_year}').count() + 1
                    ref_no = f"CA-{curr_year}-{count:03d}"

                if CashAdvance.objects.filter(ref_no=ref_no).exists():
                    messages.error(request, f'Cash Advance reference "{ref_no}" already exists.')
                else:
                    ca = CashAdvance.objects.create(
                        account=account,
                        ref_no=ref_no,
                        officer=officer,
                        role=role,
                        purpose=purpose,
                        amount=amount,
                        liquidation_deadline=liquidation_deadline or f"{(datetime.date.today() + datetime.timedelta(days=30)).strftime('%b %d, %Y')}",
                        status=CashAdvance.STATUS_PENDING,
                    )

                    if post_disbursement:
                        record_financial_transaction(
                            account=account,
                            transaction_type=FinancialTransaction.TYPE_EXPENSE,
                            title=f"Cash Advance - {officer}",
                            amount=amount,
                            reference_no=ref_no,
                            payee_or_source=officer,
                            uacs_code='5-02-99-990',
                            particulars=f"Cash advance granted for: {purpose}".strip(),
                            recorded_by=request.user,
                        )

                    messages.success(request, f'Cash Advance {ca.ref_no} of ₱{ca.amount:,.2f} granted to {ca.officer}.')
                    return redirect(f"{request.path}?tab=liquidations")

        elif action == 'create_supplier':
            name = request.POST.get('name', '').strip()
            tin = request.POST.get('tin', '').strip()
            category = request.POST.get('category', '').strip()
            contact_person = request.POST.get('contact_person', '').strip()
            phone = request.POST.get('phone', '').strip()
            address = request.POST.get('address', '').strip()
            terms = request.POST.get('terms', 'Net 30 Days').strip()
            status = request.POST.get('status', 'Accredited Active').strip()

            if not name:
                messages.error(request, 'Supplier name is required.')
            else:
                Supplier.objects.create(
                    name=name,
                    tin=tin,
                    category=category,
                    contact_person=contact_person,
                    phone=phone,
                    address=address,
                    terms=terms or 'Net 30 Days',
                    status=status or 'Accredited Active',
                )
                messages.success(request, f'Supplier "{name}" added successfully.')
                return redirect(f"{request.path}?tab=suppliers")

    tab = request.GET.get('tab', 'accounts')
    account_filter = request.GET.get('account', '')
    q = request.GET.get('q', '').strip().lower()

    accounts = FinancialAccount.objects.filter(is_active=True).order_by('code')

    # Transactions query
    transactions_qs = FinancialTransaction.objects.select_related('account', 'recorded_by').order_by('-date', '-created_at')
    if account_filter and account_filter != 'all':
        try:
            acc_id = int(account_filter)
            transactions_qs = transactions_qs.filter(account_id=acc_id)
        except ValueError:
            acc_match = accounts.filter(code=account_filter).first()
            if acc_match:
                transactions_qs = transactions_qs.filter(account=acc_match)

    if q:
        transactions_qs = transactions_qs.filter(
            Q(title__icontains=q)
            | Q(reference_no__icontains=q)
            | Q(payee_or_source__icontains=q)
            | Q(uacs_code__icontains=q)
            | Q(particulars__icontains=q)
            | Q(account__name__icontains=q)
            | Q(account__code__icontains=q)
        )

    transactions = list(transactions_qs)

    # Compute Aggregate Balances
    total_budget = accounts.aggregate(total=Sum('initial_allocation'))['total'] or Decimal('0.00')
    total_balance = accounts.aggregate(total=Sum('current_balance'))['total'] or Decimal('0.00')
    total_disbursed = FinancialTransaction.objects.filter(
        transaction_type=FinancialTransaction.TYPE_EXPENSE,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    total_income = FinancialTransaction.objects.filter(
        transaction_type=FinancialTransaction.TYPE_INCOME,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    utilization_rate = round(float((total_disbursed / total_budget) * 100), 1) if total_budget > 0 else 0.0

    # UACS Line Items for reference
    uacs_items = []

    # Supplier Records from database
    suppliers_qs = Supplier.objects.all().order_by('name')
    if q and tab == 'suppliers':
        suppliers_qs = suppliers_qs.filter(
            Q(name__icontains=q)
            | Q(tin__icontains=q)
            | Q(category__icontains=q)
            | Q(contact_person__icontains=q)
            | Q(address__icontains=q)
        )
    suppliers = list(suppliers_qs)

    # Cash Advances from persistent model
    ca_queryset = CashAdvance.objects.select_related('account', 'liquidated_by').order_by('-date_granted', '-created_at')
    if q and tab == 'liquidations':
        ca_queryset = ca_queryset.filter(
            Q(officer__icontains=q)
            | Q(ref_no__icontains=q)
            | Q(purpose__icontains=q)
            | Q(role__icontains=q)
            | Q(account__name__icontains=q)
        )
    cash_advances = []
    for ca in ca_queryset:
        if ca.liquidation_date:
            liq_str = ca.liquidation_date.strftime('%b %d, %Y')
            target_type = 'Liq'
            target_str = liq_str
        else:
            liq_str = ca.liquidation_deadline or 'Pending Settle'
            target_type = 'Due'
            target_str = ca.liquidation_deadline.replace(' (Upcoming)', '') if ca.liquidation_deadline else 'Oct 25, 2026'

        status_label = 'Liquidated' if ca.status == CashAdvance.STATUS_LIQUIDATED else 'Pending'
        status_class = 'badge-success' if ca.status == CashAdvance.STATUS_LIQUIDATED else 'badge-warning'
        short_ref = f"#{ca.ref_no.split('-')[-1]}" if '-' in ca.ref_no else f"#{ca.ref_no}"

        cash_advances.append({
            'id': ca.id,
            'ref_no': ca.ref_no,
            'short_ref': short_ref,
            'officer': ca.officer,
            'role': ca.role,
            'purpose': ca.purpose,
            'amount': f'₱{ca.amount:,.2f}',
            'raw_amount': float(ca.amount),
            'date_granted': ca.date_granted.strftime('%b %d, %Y'),
            'liquidation_date': liq_str,
            'granted_date_str': ca.date_granted.strftime('%b %d, %Y'),
            'target_date_type': target_type,
            'target_date_str': target_str,
            'status': status_label,
            'is_pending': ca.status == CashAdvance.STATUS_PENDING,
            'status_class': status_class,
            'remarks': ca.remarks,
            'actual_spent': f'₱{ca.actual_spent:,.2f}' if ca.actual_spent is not None else None,
            'refund_amount': f'₱{ca.refund_amount:,.2f}' if ca.refund_amount else None,
            'or_number': ca.or_number,
            'account_name': ca.account.name,
            'account_code': ca.account.code,
        })

    context = {
        'active_tab': tab,
        'account_filter': account_filter,
        'search_query': q,
        'accounts': accounts,
        'transactions': transactions,
        'uacs_items': uacs_items,
        'suppliers': suppliers,
        'cash_advances': cash_advances,
        'total_budget': f'₱{total_budget:,.2f}',
        'total_disbursed': f'₱{total_disbursed:,.2f}',
        'total_balance': f'₱{total_balance:,.2f}',
        'total_income': f'₱{total_income:,.2f}',
        'utilization_rate': utilization_rate,
        'account_type_choices': FinancialAccount.ACCOUNT_TYPE_CHOICES,
    }
    return render(request, 'finance/financial_management.html', context)
