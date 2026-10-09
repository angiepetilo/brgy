/**
 * Resident Signup ID Verification File Preview & Modal Viewer
 * Adheres strictly to CSP (no inline handlers).
 */
document.addEventListener('DOMContentLoaded', function () {
    var frontInput = document.getElementById('id_id_photo') || document.querySelector('input[name="id_photo"]');
    var backInput = document.getElementById('id_photo_back_input') || document.querySelector('input[name="id_photo_back"]');

    var frontPreview = document.getElementById('front_id_preview_card');
    var backPreview = document.getElementById('back_id_preview_card');

    var viewerModal = document.getElementById('fileViewerModal');
    var viewerImage = document.getElementById('viewerModalImage');
    var viewerPdf = document.getElementById('viewerModalPdf');
    var viewerFilename = document.getElementById('viewerModalFilename');
    var viewerCloseBtn = document.getElementById('viewerModalCloseBtn');
    var viewerDismissBtn = document.getElementById('viewerModalDismissBtn');

    var frontFileBlob = null;
    var backFileBlob = null;
    var frontFileName = '';
    var backFileName = '';

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 Bytes';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function setupFileInput(inputEl, previewEl, isFront) {
        if (!inputEl || !previewEl) return;

        inputEl.addEventListener('change', function (e) {
            var file = this.files && this.files[0];
            var promptEl = isFront ? document.getElementById('front_id_prompt_box') : document.getElementById('back_id_prompt_box');
            var cardBox = isFront ? document.getElementById('front_id_card_box') : document.getElementById('back_id_card_box');

            if (!file) {
                previewEl.style.display = 'none';
                if (promptEl) promptEl.style.display = 'block';
                if (cardBox) cardBox.style.padding = '1.5rem 1rem';
                return;
            }

            var objectUrl = URL.createObjectURL(file);
            var isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

            if (isFront) {
                frontFileBlob = objectUrl;
                frontFileName = file.name;
            } else {
                backFileBlob = objectUrl;
                backFileName = file.name;
            }

            // Fill preview elements
            var imgThumb = previewEl.querySelector('.preview-thumb-img');
            var pdfIcon = previewEl.querySelector('.preview-thumb-pdf');
            var nameEl = previewEl.querySelector('.preview-file-name');
            var sizeEl = previewEl.querySelector('.preview-file-size');

            if (nameEl) nameEl.textContent = file.name;
            if (sizeEl) sizeEl.textContent = formatBytes(file.size);

            if (isPdf) {
                if (imgThumb) imgThumb.style.display = 'none';
                if (pdfIcon) pdfIcon.style.display = 'flex';
            } else {
                if (pdfIcon) pdfIcon.style.display = 'none';
                if (imgThumb) {
                    imgThumb.src = objectUrl;
                    imgThumb.style.display = 'block';
                }
            }

            if (promptEl) promptEl.style.display = 'none';
            if (cardBox) cardBox.style.padding = '0';
            previewEl.style.display = 'block';
        });

        // View button inside preview card
        var viewBtn = previewEl.querySelector('.btn-view-uploaded');
        if (viewBtn) {
            viewBtn.addEventListener('click', function () {
                var url = isFront ? frontFileBlob : backFileBlob;
                var fname = isFront ? frontFileName : backFileName;
                openViewer(url, fname);
            });
        }

        // Remove button inside preview card
        var removeBtn = previewEl.querySelector('.btn-remove-uploaded');
        if (removeBtn) {
            removeBtn.addEventListener('click', function () {
                inputEl.value = '';
                previewEl.style.display = 'none';
                var promptEl = isFront ? document.getElementById('front_id_prompt_box') : document.getElementById('back_id_prompt_box');
                var cardBox = isFront ? document.getElementById('front_id_card_box') : document.getElementById('back_id_card_box');
                if (promptEl) promptEl.style.display = 'block';
                if (cardBox) cardBox.style.padding = '1.5rem 1rem';

                if (isFront) {
                    frontFileBlob = null;
                    frontFileName = '';
                } else {
                    backFileBlob = null;
                    backFileName = '';
                }
            });
        }
    }

    function openViewer(fileUrl, fileName) {
        if (!viewerModal || !fileUrl) return;

        var isPdf = (fileName || '').toLowerCase().endsWith('.pdf');
        if (viewerFilename) {
            viewerFilename.textContent = fileName || 'Uploaded Document';
        }

        if (isPdf) {
            if (viewerImage) viewerImage.style.display = 'none';
            if (viewerPdf) {
                viewerPdf.src = fileUrl;
                viewerPdf.style.display = 'block';
            }
        } else {
            if (viewerPdf) viewerPdf.style.display = 'none';
            if (viewerImage) {
                viewerImage.src = fileUrl;
                viewerImage.style.display = 'block';
            }
        }

        viewerModal.style.display = 'flex';
    }

    function closeViewer() {
        if (!viewerModal) return;
        viewerModal.style.display = 'none';
        if (viewerImage) viewerImage.src = '';
        if (viewerPdf) viewerPdf.src = '';
    }

    if (viewerCloseBtn) viewerCloseBtn.addEventListener('click', closeViewer);
    if (viewerDismissBtn) viewerDismissBtn.addEventListener('click', closeViewer);

    if (viewerModal) {
        viewerModal.addEventListener('click', function (e) {
            if (e.target === viewerModal) closeViewer();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && viewerModal && viewerModal.style.display === 'flex') {
            closeViewer();
        }
    });

    setupFileInput(frontInput, frontPreview, true);
    setupFileInput(backInput, backPreview, false);

    // Privacy Notice Modal handlers
    var privacyLink = document.getElementById('openPrivacyNoticeLink');
    var privacyModal = document.getElementById('privacyNoticeModal');
    var closePrivacyBtn = document.getElementById('closePrivacyNoticeModalBtn');
    var dismissPrivacyBtn = document.getElementById('dismissPrivacyNoticeModalBtn');

    function openPrivacyModal() {
        if (privacyModal) privacyModal.style.display = 'flex';
    }
    function closePrivacyModal() {
        if (privacyModal) privacyModal.style.display = 'none';
    }

    if (privacyLink) privacyLink.addEventListener('click', openPrivacyModal);
    if (closePrivacyBtn) closePrivacyBtn.addEventListener('click', closePrivacyModal);
    if (dismissPrivacyBtn) dismissPrivacyBtn.addEventListener('click', closePrivacyModal);

    if (privacyModal) {
        privacyModal.addEventListener('click', function (e) {
            if (e.target === privacyModal) closePrivacyModal();
        });
    }

    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && privacyModal && privacyModal.style.display === 'flex') {
            closePrivacyModal();
        }
    });

    // 4-digit year enforcement for birthdate
    var birthdateInput = document.querySelector('input[name="birthdate"]');
    if (birthdateInput) {
        birthdateInput.setAttribute('min', '1900-01-01');
        birthdateInput.setAttribute('max', '9999-12-31');
        birthdateInput.addEventListener('input', function () {
            if (this.value) {
                var parts = this.value.split('-');
                if (parts[0] && parts[0].length > 4) {
                    parts[0] = parts[0].slice(0, 4);
                    this.value = parts.join('-');
                }
            }
        });
    }
});
