from decimal import Decimal
from django.conf import settings
from django.db import models
from django.utils import timezone


class FinancialAccount(models.Model):
    ACCOUNT_TYPE_GF = 'general_fund'
    ACCOUNT_TYPE_SK = 'sk_fund'
    ACCOUNT_TYPE_CALAMITY = 'calamity_fund'
    ACCOUNT_TYPE_DEV = 'development_fund'
    ACCOUNT_TYPE_COLLECTIONS = 'barangay_collections'
    ACCOUNT_TYPE_OTHER = 'other'

    ACCOUNT_TYPE_CHOICES = [
        (ACCOUNT_TYPE_GF, 'General Fund (GF)'),
        (ACCOUNT_TYPE_SK, 'SK Fund (10%)'),
        (ACCOUNT_TYPE_CALAMITY, 'Calamity Fund (BDRRMF 5%)'),
        (ACCOUNT_TYPE_DEV, 'Development Fund (20% BDF)'),
        (ACCOUNT_TYPE_COLLECTIONS, 'Barangay Collections'),
        (ACCOUNT_TYPE_OTHER, 'Special Account'),
    ]

    name = models.CharField(max_length=150)
    code = models.CharField(max_length=30, unique=True)
    account_type = models.CharField(max_length=50, choices=ACCOUNT_TYPE_CHOICES, default=ACCOUNT_TYPE_GF)
    description = models.TextField(blank=True)
    initial_allocation = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    current_balance = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    accountable_officer = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financial_accounts'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"

    def recalculate_balance(self):
        incomes = self.transactions.filter(transaction_type='income', status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        expenses = self.transactions.filter(transaction_type='expense', status='completed').aggregate(
            total=models.Sum('amount')
        )['total'] or Decimal('0.00')
        self.current_balance = self.initial_allocation + incomes - expenses
        self.save(update_fields=['current_balance', 'updated_at'])
        return self.current_balance


class FinancialTransaction(models.Model):
    TYPE_INCOME = 'income'
    TYPE_EXPENSE = 'expense'
    TRANSACTION_TYPE_CHOICES = [
        (TYPE_INCOME, 'Income'),
        (TYPE_EXPENSE, 'Disbursement'),
    ]

    STATUS_COMPLETED = 'completed'
    STATUS_PENDING = 'pending'
    STATUS_CANCELLED = 'cancelled'
    STATUS_CHOICES = [
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_PENDING, 'Pending Review'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    account = models.ForeignKey(FinancialAccount, on_delete=models.CASCADE, related_name='transactions')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    reference_no = models.CharField(max_length=60, blank=True)
    title = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date = models.DateField(default=timezone.now)
    payee_or_source = models.CharField(max_length=255, blank=True)
    uacs_code = models.CharField(max_length=60, blank=True)
    particulars = models.TextField(blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_financial_transactions'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financial_transactions'
        ordering = ['-date', '-created_at']

    def __str__(self):
        return f"[{self.account.code}] {self.get_transaction_type_display()} - {self.reference_no or self.title}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.account.recalculate_balance()

    def delete(self, *args, **kwargs):
        account = self.account
        super().delete(*args, **kwargs)
        account.recalculate_balance()


class CashAdvance(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_LIQUIDATED = 'liquidated'
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Liquidation'),
        (STATUS_LIQUIDATED, 'Fully Liquidated'),
    ]

    account = models.ForeignKey(FinancialAccount, on_delete=models.CASCADE, related_name='cash_advances')
    ref_no = models.CharField(max_length=60, unique=True)
    officer = models.CharField(max_length=150)
    role = models.CharField(max_length=150, blank=True)
    purpose = models.TextField()
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    date_granted = models.DateField(default=timezone.now)
    liquidation_deadline = models.CharField(max_length=100, blank=True)
    liquidation_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default=STATUS_PENDING)
    actual_spent = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    refund_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0.00'))
    or_number = models.CharField(max_length=60, blank=True)
    remarks = models.TextField(blank=True)
    liquidated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='liquidated_cash_advances'
    )
    liquidated_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financial_cash_advances'
        ordering = ['-date_granted', '-created_at']

    def __str__(self):
        return f"[{self.ref_no}] {self.officer} - ₱{self.amount}"


class Supplier(models.Model):
    name = models.CharField(max_length=200)
    tin = models.CharField(max_length=50, blank=True)
    category = models.CharField(max_length=150, blank=True)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    address = models.CharField(max_length=255, blank=True)
    terms = models.CharField(max_length=100, default='Net 30 Days')
    status = models.CharField(max_length=50, default='Accredited Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'financial_suppliers'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.category or 'Supplier'})"

