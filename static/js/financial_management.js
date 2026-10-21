/*
 * Financial Management Controller
 * Multi-Account Ledger & Dynamic Transactions
 * Strictly CSP-compliant (external JS, no inline scripts/events)
 */
document.addEventListener('DOMContentLoaded', function () {
    // 1. Modals setup
    var txModal = document.getElementById('recordTxModal');
    var accModal = document.getElementById('createAccountModal');
    var liqModal = document.getElementById('liquidateCaModal');
    var grantCaModal = document.getElementById('grantCaModal');
    var supplierModal = document.getElementById('createSupplierModal');

    var btnOpenTx = document.getElementById('btn-open-record-tx');
    var btnOpenAcc = document.getElementById('btn-open-create-acc');
    var btnOpenGrantCa = document.getElementById('btn-open-grant-ca');
    var btnOpenSupplier = document.getElementById('btn-open-create-supplier');

    var closeTxBtn = document.getElementById('btn-close-record-tx');
    var closeTxFooterBtn = document.getElementById('btn-close-record-tx-footer');

    var closeAccBtn = document.getElementById('btn-close-create-acc');
    var closeAccFooterBtn = document.getElementById('btn-close-create-acc-footer');

    var closeLiqBtn = document.getElementById('btn-close-liq-ca');
    var closeLiqFooterBtn = document.getElementById('btn-close-liq-ca-footer');

    var closeGrantCaBtn = document.getElementById('btn-close-grant-ca');
    var closeGrantCaFooterBtn = document.getElementById('btn-close-grant-ca-footer');

    var closeSupplierBtn = document.getElementById('btn-close-create-supplier');
    var closeSupplierFooterBtn = document.getElementById('btn-close-create-supplier-footer');

    function openModal(el) {
        if (el) el.style.display = 'flex';
    }

    function closeModal(el) {
        if (el) el.style.display = 'none';
    }

    // Global click delegation for all modal triggers
    document.addEventListener('click', function (e) {
        var grantTrigger = e.target.closest('[data-action="open-grant-ca"], #btn-open-grant-ca, .btn-open-grant-ca-inline');
        if (grantTrigger) {
            e.preventDefault();
            openModal(grantCaModal);
            return;
        }

        var suppTrigger = e.target.closest('[data-action="open-supplier"], #btn-open-create-supplier, .btn-open-create-supplier-inline');
        if (suppTrigger) {
            e.preventDefault();
            openModal(supplierModal);
            return;
        }

        var accTrigger = e.target.closest('[data-action="open-create-acc"], #btn-open-create-acc');
        if (accTrigger) {
            e.preventDefault();
            openModal(accModal);
            return;
        }

        var txTrigger = e.target.closest('[data-action="open-record-tx"], #btn-open-record-tx');
        if (txTrigger) {
            e.preventDefault();
            openModal(txModal);
            return;
        }
    });

    if (closeTxBtn) closeTxBtn.addEventListener('click', function () { closeModal(txModal); });
    if (closeTxFooterBtn) closeTxFooterBtn.addEventListener('click', function () { closeModal(txModal); });

    if (closeAccBtn) closeAccBtn.addEventListener('click', function () { closeModal(accModal); });
    if (closeAccFooterBtn) closeAccFooterBtn.addEventListener('click', function () { closeModal(accModal); });

    if (closeLiqBtn) closeLiqBtn.addEventListener('click', function () { closeModal(liqModal); });
    if (closeLiqFooterBtn) closeLiqFooterBtn.addEventListener('click', function () { closeModal(liqModal); });

    if (closeGrantCaBtn) closeGrantCaBtn.addEventListener('click', function () { closeModal(grantCaModal); });
    if (closeGrantCaFooterBtn) closeGrantCaFooterBtn.addEventListener('click', function () { closeModal(grantCaModal); });

    if (closeSupplierBtn) closeSupplierBtn.addEventListener('click', function () { closeModal(supplierModal); });
    if (closeSupplierFooterBtn) closeSupplierFooterBtn.addEventListener('click', function () { closeModal(supplierModal); });

    // Overlay click close
    [txModal, accModal, liqModal, grantCaModal, supplierModal].forEach(function (m) {
        if (m) {
            m.addEventListener('click', function (e) {
                if (e.target === m) closeModal(m);
            });
        }
    });

    // Escape key close
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeModal(txModal);
            closeModal(accModal);
            closeModal(liqModal);
            closeModal(grantCaModal);
            closeModal(supplierModal);
        }
    });

    // 2. Account filter dropdown
    var accountFilterDropdown = document.getElementById('fin-account-filter');
    if (accountFilterDropdown) {
        accountFilterDropdown.addEventListener('change', function () {
            var selectedVal = this.value;
            var url = new URL(window.location.href);
            url.searchParams.set('tab', 'transactions');
            if (selectedVal && selectedVal !== 'all') {
                url.searchParams.set('account', selectedVal);
            } else {
                url.searchParams.delete('account');
            }
            window.location.href = url.toString();
        });
    }

    // 3. Quick "New Transaction for this Account" buttons on Account cards
    var accountCardBtns = document.querySelectorAll('.btn-add-tx-for-acc');
    accountCardBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var accId = this.dataset.accId;
            var sourceSelect = document.getElementById('tx-source-account');
            if (sourceSelect && accId) {
                sourceSelect.value = accId;
            }
            openModal(txModal);
        });
    });

    // 3b. Dynamic label adjustment for Record Transaction modal (Received By vs Received From)
    var txTypeSelect = document.getElementById('tx-type');
    var txPayeeLabel = document.getElementById('tx-payee-label');
    var txPayeeInput = document.getElementById('tx-payee');
    var txPayeeHelp = document.getElementById('tx-payee-help');

    if (txTypeSelect && txPayeeLabel && txPayeeInput) {
        txTypeSelect.addEventListener('change', function () {
            if (this.value === 'income') {
                txPayeeLabel.textContent = 'Received From';
                txPayeeInput.placeholder = 'e.g. Resident Name, Registrant, or Remitting Office';
                if (txPayeeHelp) txPayeeHelp.textContent = 'The person or entity remitting the collection or revenue.';
            } else {
                txPayeeLabel.textContent = 'Received By';
                txPayeeInput.placeholder = 'e.g. Officer Name, Supplier, or Recipient';
                if (txPayeeHelp) txPayeeHelp.textContent = 'The person, company, or entity receiving the funds or goods.';
            }
        });
    }

    // 4. Interactive "Settle / Liquidate Cash Advance" Action
    var currentGrantedAmount = 0;
    var actualSpentInput = document.getElementById('liq-actual-spent');
    var refundInput = document.getElementById('liq-refund-amount');

    function updateRefundCalculation() {
        if (!actualSpentInput || !refundInput) return;
        var spent = parseFloat(actualSpentInput.value) || 0;
        var refund = Math.max(0, currentGrantedAmount - spent);
        refundInput.value = refund.toFixed(2);
    }

    if (actualSpentInput) {
        actualSpentInput.addEventListener('input', updateRefundCalculation);
    }

    var liquidateBtns = document.querySelectorAll('.btn-liquidate-ca');
    liquidateBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var caId = this.dataset.caId;
            var ref = this.dataset.ref;
            var officer = this.dataset.officer;
            var amount = parseFloat(this.dataset.amount) || 0;
            var formattedAmount = this.dataset.formattedAmount || ('₱' + amount.toFixed(2));
            var purpose = this.dataset.purpose || '';
            var account = this.dataset.account || '';

            currentGrantedAmount = amount;

            var idInput = document.getElementById('liq-ca-id');
            var refEl = document.getElementById('liq-ca-ref');
            var officerEl = document.getElementById('liq-ca-officer');
            var grantedEl = document.getElementById('liq-ca-granted-display');
            var purposeEl = document.getElementById('liq-ca-purpose');
            var accountEl = document.getElementById('liq-ca-account');
            var orInput = document.getElementById('liq-or-number');
            var remarksInput = document.getElementById('liq-remarks');

            if (idInput) idInput.value = caId;
            if (refEl) refEl.textContent = ref;
            if (officerEl) officerEl.textContent = officer;
            if (grantedEl) grantedEl.textContent = formattedAmount;
            if (purposeEl) purposeEl.textContent = 'Purpose: ' + purpose;
            if (accountEl) accountEl.textContent = 'Charged to Fund: ' + account;
            if (actualSpentInput) actualSpentInput.value = amount.toFixed(2);
            if (refundInput) refundInput.value = '0.00';
            if (orInput) orInput.value = 'LR-' + (ref ? ref.replace('CA-', '') : '001');
            if (remarksInput) remarksInput.value = 'Receipts inspected and verified by Barangay Treasurer.';

            openModal(liqModal);
        });
    });

    // 5. Philippine Peso Currency Standard Input Sanitization & Formatting
    // Strictly enforces: numbers only, single decimal point, max 2 decimal places, max 12 integer digits
    var pesoInputs = document.querySelectorAll('.peso-currency-input');

    function sanitizePesoInput(input) {
        var raw = input.value;
        // Strip any character that is not a digit or decimal point
        var cleaned = raw.replace(/[^0-9.]/g, '');

        // Ensure only at most one decimal point
        var firstDot = cleaned.indexOf('.');
        if (firstDot !== -1) {
            var intPart = cleaned.substring(0, firstDot);
            var decPart = cleaned.substring(firstDot + 1).replace(/\./g, '');
            // Limit integer digits to 12 (max 999,999,999,999)
            if (intPart.length > 12) intPart = intPart.substring(0, 12);
            // Limit decimal digits to 2 (centavos standard)
            if (decPart.length > 2) decPart = decPart.substring(0, 2);
            cleaned = intPart + '.' + decPart;
        } else {
            // No decimal point yet: limit integer digits to 12
            if (cleaned.length > 12) cleaned = cleaned.substring(0, 12);
        }

        if (input.value !== cleaned) {
            input.value = cleaned;
        }
    }

    pesoInputs.forEach(function (input) {
        // Block invalid characters at keypress time
        input.addEventListener('keydown', function (e) {
            // Allow control keys (Backspace, Tab, Enter, Esc, Delete, Arrow keys, Home, End)
            if ([8, 9, 13, 27, 46, 37, 38, 39, 40, 35, 36].indexOf(e.keyCode) !== -1 ||
                (e.ctrlKey || e.metaKey)) {
                return;
            }

            // Allow decimal point only if not already present
            if (e.key === '.' || e.key === 'Decimal') {
                if (this.value.indexOf('.') !== -1) {
                    e.preventDefault();
                }
                return;
            }

            // Block non-digit keys (including 'e', '+', '-', letters, symbols)
            if (e.key < '0' || e.key > '9') {
                e.preventDefault();
            }
        });

        // Intercept paste & input to clean any invalid pasted content
        input.addEventListener('input', function () {
            sanitizePesoInput(this);
            if (this.id === 'liq-actual-spent' && typeof updateRefundCalculation === 'function') {
                updateRefundCalculation();
            }
        });

        input.addEventListener('paste', function () {
            var self = this;
            setTimeout(function () {
                sanitizePesoInput(self);
                if (self.id === 'liq-actual-spent' && typeof updateRefundCalculation === 'function') {
                    updateRefundCalculation();
                }
            }, 0);
        });

        // Format to 2 decimal places on blur if user entered a number
        input.addEventListener('blur', function () {
            var val = this.value.trim();
            if (!val) return;
            if (val.endsWith('.')) {
                val = val.slice(0, -1);
            }
            var num = parseFloat(val);
            if (!isNaN(num) && isFinite(num)) {
                this.value = num.toFixed(2);
            }
            if (this.id === 'liq-actual-spent' && typeof updateRefundCalculation === 'function') {
                updateRefundCalculation();
            }
        });
    });
});
