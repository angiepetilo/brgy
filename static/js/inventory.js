/*
 * Inventory Management Controller
 * Multi-Location & Department Warehouse Isolation
 * Strictly CSP-compliant (external JS, no inline scripts/events)
 */
document.addEventListener('DOMContentLoaded', function () {
    // 1. Modals setup
    var whModal = document.getElementById('createWarehouseModal');
    var itemModal = document.getElementById('createItemModal');
    var stockModal = document.getElementById('stockMovementModal');

    var btnOpenWh = document.getElementById('btn-open-create-wh');
    var btnOpenItem = document.getElementById('btn-open-create-item');
    var btnOpenStock = document.getElementById('btn-open-stock-movement');

    var closeWhBtn = document.getElementById('btn-close-create-wh');
    var closeWhFooterBtn = document.getElementById('btn-close-create-wh-footer');

    var closeItemBtn = document.getElementById('btn-close-create-item');
    var closeItemFooterBtn = document.getElementById('btn-close-create-item-footer');

    var closeStockBtn = document.getElementById('btn-close-stock-movement');
    var closeStockFooterBtn = document.getElementById('btn-close-stock-movement-footer');

    function openModal(el) {
        if (el) el.style.display = 'flex';
    }

    function closeModal(el) {
        if (el) el.style.display = 'none';
    }

    if (btnOpenWh) btnOpenWh.addEventListener('click', function () { openModal(whModal); });
    if (btnOpenItem) btnOpenItem.addEventListener('click', function () { openModal(itemModal); });
    if (btnOpenStock) btnOpenStock.addEventListener('click', function () { openModal(stockModal); });

    if (closeWhBtn) closeWhBtn.addEventListener('click', function () { closeModal(whModal); });
    if (closeWhFooterBtn) closeWhFooterBtn.addEventListener('click', function () { closeModal(whModal); });

    if (closeItemBtn) closeItemBtn.addEventListener('click', function () { closeModal(itemModal); });
    if (closeItemFooterBtn) closeItemFooterBtn.addEventListener('click', function () { closeModal(itemModal); });

    if (closeStockBtn) closeStockBtn.addEventListener('click', function () { closeModal(stockModal); });
    if (closeStockFooterBtn) closeStockFooterBtn.addEventListener('click', function () { closeModal(stockModal); });

    [whModal, itemModal, stockModal].forEach(function (m) {
        if (m) {
            m.addEventListener('click', function (e) {
                if (e.target === m) closeModal(m);
            });
        }
    });

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            closeModal(whModal);
            closeModal(itemModal);
            closeModal(stockModal);
        }
    });

    // 2. Warehouse dropdown filter
    var whFilterDropdown = document.getElementById('inv-warehouse-filter');
    if (whFilterDropdown) {
        whFilterDropdown.addEventListener('change', function () {
            var selectedVal = this.value;
            var url = new URL(window.location.href);
            if (selectedVal && selectedVal !== 'all') {
                url.searchParams.set('warehouse', selectedVal);
            } else {
                url.searchParams.delete('warehouse');
            }
            url.searchParams.delete('tab');
            window.location.href = url.toString();
        });
    }

    // 3. Quick Stock Movement button on table rows
    var rowStockBtns = document.querySelectorAll('.btn-row-stock-move');
    rowStockBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var itemId = this.dataset.itemId;
            var itemSelect = document.getElementById('stock-movement-item-select');
            var itemInfoBadge = document.getElementById('stock-movement-item-info');

            if (itemSelect && itemId) {
                itemSelect.value = itemId;
            }
            if (itemInfoBadge) {
                itemInfoBadge.textContent = 'Target: ' + (this.dataset.itemName || '') + ' (' + (this.dataset.itemQty || '0') + ' ' + (this.dataset.itemUnit || '') + ' in ' + (this.dataset.whName || '') + ')';
            }
            openModal(stockModal);
        });
    });

    // 4. Update item info badge when select changes in stock movement modal
    var itemSelectInput = document.getElementById('stock-movement-item-select');
    if (itemSelectInput) {
        itemSelectInput.addEventListener('change', function () {
            var selectedOption = this.options[this.selectedIndex];
            var itemInfoBadge = document.getElementById('stock-movement-item-info');
            if (itemInfoBadge && selectedOption) {
                itemInfoBadge.textContent = 'Selected: ' + selectedOption.text;
            }
        });
    }
});
