/*
 * Resident Accounts Management & Modals (CSP-compliant, external script).
 */
document.addEventListener('DOMContentLoaded', function() {
    var detailModal = document.getElementById('accountDetailModal');
    var rejectModal = document.getElementById('rejectAccountModal');

    // Close buttons
    var closeDetBtn = document.getElementById('btn-close-account-detail');
    var cancelDetBtn = document.getElementById('btn-cancel-account-detail');
    if (closeDetBtn) closeDetBtn.addEventListener('click', function() { if (detailModal) detailModal.style.display = 'none'; });
    if (cancelDetBtn) cancelDetBtn.addEventListener('click', function() { if (detailModal) detailModal.style.display = 'none'; });

    var cancelRejBtn = document.getElementById('btn-cancel-reject-account');
    if (cancelRejBtn) cancelRejBtn.addEventListener('click', function() { if (rejectModal) rejectModal.style.display = 'none'; });

    window.addEventListener('click', function(e) {
        if (detailModal && e.target === detailModal) detailModal.style.display = 'none';
        if (rejectModal && e.target === rejectModal) rejectModal.style.display = 'none';
    });

    var setElText = function(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text || '';
    };

    // View account profile detail
    document.querySelectorAll('.btn-view-resident-account').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var d = btn.dataset;
            setElText('det-name', d.name);
            setElText('det-username', '@' + (d.username || ''));
            setElText('det-email', d.email);
            setElText('det-phone', d.phone);
            setElText('det-purok', d.purok);
            setElText('det-birthdate', (d.birthdate || 'N/A') + (d.age ? ' (' + d.age + ')' : ''));
            setElText('det-address', d.address);

            var img = document.getElementById('det-doc-img');
            var noDoc = document.getElementById('det-no-doc');
            var link = document.getElementById('det-doc-link');

            if (d.docUrl) {
                if (img) {
                    img.src = d.docUrl;
                    img.style.display = 'block';
                }
                if (noDoc) noDoc.style.display = 'none';
                if (link) {
                    link.href = d.docUrl;
                    link.style.display = 'inline-flex';
                }
            } else {
                if (img) img.style.display = 'none';
                if (noDoc) noDoc.style.display = 'block';
                if (link) link.style.display = 'none';
            }

            var approveForm = document.getElementById('det-approve-form');
            var rejectBtn = document.getElementById('det-reject-btn');

            if (d.status === 'pending') {
                // Show Approve button inside modal
                if (approveForm) {
                    approveForm.action = d.approveUrl || ('/accounts/residents/' + d.id + '/approve/');
                    approveForm.style.display = 'inline-block';
                }
                // Show Reject button inside modal
                if (rejectBtn) {
                    rejectBtn.style.display = 'inline-flex';
                    rejectBtn.onclick = function() {
                        // Close detail modal, open reject modal
                        if (detailModal) detailModal.style.display = 'none';
                        setElText('reject-applicant-name', d.name);
                        var rejForm = document.getElementById('rejectAccountForm');
                        if (rejForm) rejForm.action = d.rejectUrl || ('/accounts/residents/' + d.id + '/reject/');
                        if (rejectModal) rejectModal.style.display = 'flex';
                    };
                }
            } else {
                if (approveForm) approveForm.style.display = 'none';
                if (rejectBtn) rejectBtn.style.display = 'none';
            }

            if (detailModal) detailModal.style.display = 'flex';
        });
    });

    // Preview ID file directly (from "View ID File" button in the table)
    document.querySelectorAll('.btn-preview-id').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var url = btn.dataset.url;
            var name = btn.dataset.name;
            setElText('det-name', name);
            setElText('det-username', 'Identity Document Verification');
            var img = document.getElementById('det-doc-img');
            var noDoc = document.getElementById('det-no-doc');
            var link = document.getElementById('det-doc-link');
            if (img) {
                img.src = url;
                img.style.display = 'block';
            }
            if (noDoc) noDoc.style.display = 'none';
            if (link) {
                link.href = url;
                link.style.display = 'inline-flex';
            }
            var approveForm = document.getElementById('det-approve-form');
            var rejectBtn = document.getElementById('det-reject-btn');
            if (approveForm) approveForm.style.display = 'none';
            if (rejectBtn) rejectBtn.style.display = 'none';
            if (detailModal) detailModal.style.display = 'flex';
        });
    });

    // Reject account (standalone row button — kept for backward compatibility)
    document.querySelectorAll('.btn-reject-account').forEach(function(btn) {
        btn.addEventListener('click', function() {
            var id = btn.dataset.id;
            var name = btn.dataset.name;
            setElText('reject-applicant-name', name);
            var rejForm = document.getElementById('rejectAccountForm');
            if (rejForm) rejForm.action = '/accounts/residents/' + id + '/reject/';
            if (rejectModal) rejectModal.style.display = 'flex';
        });
    });
});
