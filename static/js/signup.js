/**
 * Resident Signup Registration Wizard Controller
 * Accessible 4-Step flow designed for elderly, adult, and young users.
 * Adheres strictly to CSP (no inline scripts/handlers).
 */
document.addEventListener('DOMContentLoaded', function () {
    // --- Step Panels and Indicators ---
    var wizardRoot = document.getElementById('reg-wizard-root');
    if (!wizardRoot) return; // Not on the registration form page (e.g. already submitted)

    var form = document.getElementById('reg-wizard-form');
    var btnBack = document.getElementById('reg-btn-back');
    var btnNext = document.getElementById('reg-btn-next');
    var btnSubmit = document.getElementById('reg-btn-submit');
    var stepIndicatorText = document.getElementById('reg-progress-step-text');
    var stepSegments = document.querySelectorAll('.reg-progress-bar-seg');

    var stepPanels = [
        document.getElementById('reg-step-1'),
        document.getElementById('reg-step-2'),
        document.getElementById('reg-step-3'),
        document.getElementById('reg-step-4')
    ];

    var stepTitles = [
        'About you',
        'How to reach you',
        'Your ID verification',
        'Check and send'
    ];

    var currentStep = 1;

    // --- Font Size Toggle (100% vs 125%) ---
    var btnFontNormal = document.getElementById('btn-font-normal');
    var btnFontLarge = document.getElementById('btn-font-large');

    function setFontSize(size) {
        if (size === 'large') {
            document.body.setAttribute('data-font-size', 'large');
            if (btnFontLarge) {
                btnFontLarge.classList.add('active');
                btnFontLarge.setAttribute('aria-pressed', 'true');
            }
            if (btnFontNormal) {
                btnFontNormal.classList.remove('active');
                btnFontNormal.setAttribute('aria-pressed', 'false');
            }
            try { localStorage.setItem('reg_font_size', 'large'); } catch (e) {}
        } else {
            document.body.removeAttribute('data-font-size');
            if (btnFontNormal) {
                btnFontNormal.classList.add('active');
                btnFontNormal.setAttribute('aria-pressed', 'true');
            }
            if (btnFontLarge) {
                btnFontLarge.classList.remove('active');
                btnFontLarge.setAttribute('aria-pressed', 'false');
            }
            try { localStorage.setItem('reg_font_size', 'normal'); } catch (e) {}
        }
    }

    try {
        var savedFontSize = localStorage.getItem('reg_font_size');
        if (savedFontSize === 'large') setFontSize('large');
    } catch (e) {}

    if (btnFontNormal) {
        btnFontNormal.addEventListener('click', function () { setFontSize('normal'); });
    }
    if (btnFontLarge) {
        btnFontLarge.addEventListener('click', function () { setFontSize('large'); });
    }

    // --- Step 1: Birthdate Month/Day/Year Selects ---
    var monthSelect = document.getElementById('reg-dob-month');
    var daySelect = document.getElementById('reg-dob-day');
    var yearSelect = document.getElementById('reg-dob-year');
    var hiddenBirthdate = document.getElementById('id_birthdate');
    var errorBirthdate = document.getElementById('error-birthdate');

    // Populate Year Select down to 1920
    if (yearSelect && yearSelect.options.length <= 1) {
        var currentYear = new Date().getFullYear();
        for (var y = currentYear; y >= 1920; y--) {
            var opt = document.createElement('option');
            opt.value = y.toString();
            opt.textContent = y.toString();
            yearSelect.appendChild(opt);
        }
    }

    // Pre-populate selects if hidden input already has value (YYYY-MM-DD)
    if (hiddenBirthdate && hiddenBirthdate.value) {
        var parts = hiddenBirthdate.value.split('-');
        if (parts.length === 3) {
            if (yearSelect) yearSelect.value = parts[0];
            if (monthSelect) monthSelect.value = parts[1];
            if (daySelect) daySelect.value = parts[2];
        }
    }

    function calculateAge(birthDate) {
        var today = new Date();
        var age = today.getFullYear() - birthDate.getFullYear();
        var m = today.getMonth() - birthDate.getMonth();
        if (m < 0 || (m === 0 && today.getDate() < birthDate.getDate())) {
            age--;
        }
        return age;
    }

    function updateBirthdate() {
        if (!monthSelect || !daySelect || !yearSelect || !hiddenBirthdate) return true;
        var m = monthSelect.value;
        var d = daySelect.value;
        var y = yearSelect.value;

        if (!m && !d && !y) {
            hiddenBirthdate.value = '';
            return false;
        }

        if (!m || !d || !y) {
            hiddenBirthdate.value = '';
            if (errorBirthdate) errorBirthdate.textContent = 'Please select Month, Day, and Year.';
            return false;
        }

        var yearNum = parseInt(y, 10);
        var monthNum = parseInt(m, 10);
        var dayNum = parseInt(d, 10);

        // Check valid date for month
        var daysInMonth = new Date(yearNum, monthNum, 0).getDate();
        if (dayNum > daysInMonth) {
            if (errorBirthdate) {
                var monthName = monthSelect.options[monthSelect.selectedIndex].text;
                errorBirthdate.textContent = monthName + ' only has ' + daysInMonth + ' days.';
            }
            hiddenBirthdate.value = '';
            return false;
        }

        var dob = new Date(yearNum, monthNum - 1, dayNum);
        var today = new Date();
        today.setHours(0, 0, 0, 0);

        if (dob > today) {
            if (errorBirthdate) errorBirthdate.textContent = 'Date of birth cannot be in the future.';
            hiddenBirthdate.value = '';
            return false;
        }

        var age = calculateAge(dob);
        if (age < 18) {
            if (errorBirthdate) errorBirthdate.textContent = 'You must be at least 18 years old to register.';
            hiddenBirthdate.value = '';
            return false;
        }

        var formattedDate = y + '-' + m + '-' + d;
        hiddenBirthdate.value = formattedDate;
        if (errorBirthdate) errorBirthdate.textContent = '';
        return true;
    }

    if (monthSelect) monthSelect.addEventListener('change', updateBirthdate);
    if (daySelect) daySelect.addEventListener('change', updateBirthdate);
    if (yearSelect) yearSelect.addEventListener('change', updateBirthdate);

    // --- Choice Buttons (Gender & Civil Status) ---
    function setupChoiceGroup(containerId, hiddenInputId, errorId) {
        var container = document.getElementById(containerId);
        var hiddenInput = document.getElementById(hiddenInputId);
        var errorEl = document.getElementById(errorId);
        if (!container || !hiddenInput) return;

        var buttons = container.querySelectorAll('.reg-choice-btn');

        function selectValue(val) {
            hiddenInput.value = val;
            buttons.forEach(function (btn) {
                var isMatch = btn.getAttribute('data-value') === val;
                btn.classList.toggle('selected', isMatch);
                btn.setAttribute('aria-checked', isMatch ? 'true' : 'false');
            });
            if (errorEl) errorEl.textContent = '';
        }

        // Initialize from existing hidden value
        if (hiddenInput.value) {
            selectValue(hiddenInput.value);
        }

        buttons.forEach(function (btn) {
            btn.addEventListener('click', function () {
                var val = this.getAttribute('data-value');
                selectValue(val);
            });

            btn.addEventListener('keydown', function (e) {
                if (e.key === ' ' || e.key === 'Enter') {
                    e.preventDefault();
                    var val = this.getAttribute('data-value');
                    selectValue(val);
                }
            });
        });
    }

    setupChoiceGroup('reg-gender-group', 'id_gender', 'error-gender');
    setupChoiceGroup('reg-civil-status-group', 'id_civil_status', 'error-civil-status');

    // --- Step 2: Phone Input Live Enforcement & Formatting ---
    var contactInput = document.getElementById('reg-contact-no');
    var phoneBadge = document.getElementById('reg-phone-badge');
    var errorContact = document.getElementById('error-contact-no');

    if (contactInput) {
        contactInput.addEventListener('input', function () {
            // Keep digits only, max 11
            var cleaned = this.value.replace(/\D/g, '').slice(0, 11);
            this.value = cleaned;

            if (cleaned.length === 11 && cleaned.startsWith('09')) {
                if (phoneBadge) phoneBadge.style.display = 'inline-flex';
                if (errorContact) errorContact.textContent = '';
            } else {
                if (phoneBadge) phoneBadge.style.display = 'none';
            }
        });
    }

    // --- Step 3: File Uploads & Live Previews ---
    var frontInput = document.getElementById('id_id_photo');
    var backInput = document.getElementById('id_photo_back_input');

    var frontPreview = document.getElementById('front_id_preview_card');
    var backPreview = document.getElementById('back_id_preview_card');

    var frontBox = document.getElementById('front_id_card_box');
    var backBox = document.getElementById('back_id_card_box');

    var frontPrompt = document.getElementById('front_id_prompt_box');
    var backPrompt = document.getElementById('back_id_prompt_box');

    var frontBadge = document.getElementById('front_id_status_badge');
    var backBadge = document.getElementById('back_id_status_badge');

    var errorFront = document.getElementById('error-id-photo');
    var errorBack = document.getElementById('error-id-photo-back');

    var frontFileBlob = null;
    var backFileBlob = null;
    var frontFileName = '';
    var backFileName = '';

    var MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

    function formatBytes(bytes) {
        if (!bytes || bytes === 0) return '0 Bytes';
        var k = 1024;
        var sizes = ['Bytes', 'KB', 'MB', 'GB'];
        var i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    function setupUploadZone(inputEl, previewEl, cardBox, promptEl, badgeEl, errorEl, isFront) {
        if (!inputEl || !previewEl) return;

        inputEl.addEventListener('change', function () {
            var file = this.files && this.files[0];

            // Cleanup previous blob
            if (isFront && frontFileBlob) {
                URL.revokeObjectURL(frontFileBlob);
                frontFileBlob = null;
                frontFileName = '';
            } else if (!isFront && backFileBlob) {
                URL.revokeObjectURL(backFileBlob);
                backFileBlob = null;
                backFileName = '';
            }

            if (!file) {
                previewEl.style.display = 'none';
                if (promptEl) promptEl.style.display = 'flex';
                if (cardBox) cardBox.classList.remove('has-file');
                if (badgeEl) badgeEl.style.display = 'none';
                return;
            }

            // Size limit validation (10MB)
            if (file.size > MAX_FILE_SIZE) {
                inputEl.value = '';
                if (errorEl) errorEl.textContent = 'This photo is too big (' + formatBytes(file.size) + '). Maximum allowed is 10MB.';
                previewEl.style.display = 'none';
                if (promptEl) promptEl.style.display = 'flex';
                if (cardBox) cardBox.classList.remove('has-file');
                if (badgeEl) badgeEl.style.display = 'none';
                return;
            }

            if (errorEl) errorEl.textContent = '';

            var objectUrl = URL.createObjectURL(file);
            var isPdf = file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf');

            if (isFront) {
                frontFileBlob = objectUrl;
                frontFileName = file.name;
            } else {
                backFileBlob = objectUrl;
                backFileName = file.name;
            }

            var imgThumb = previewEl.querySelector('.preview-thumb-img');
            var pdfThumb = previewEl.querySelector('.preview-thumb-pdf');
            var pdfName = previewEl.querySelector('.preview-file-name');

            if (isPdf) {
                if (imgThumb) imgThumb.style.display = 'none';
                if (pdfThumb) pdfThumb.style.display = 'flex';
                if (pdfName) pdfName.textContent = file.name + ' (' + formatBytes(file.size) + ')';
            } else {
                if (pdfThumb) pdfThumb.style.display = 'none';
                if (imgThumb) {
                    imgThumb.src = objectUrl;
                    imgThumb.style.display = 'block';
                }
            }

            if (promptEl) promptEl.style.display = 'none';
            if (cardBox) cardBox.classList.add('has-file');
            if (badgeEl) badgeEl.style.display = 'inline-flex';
            previewEl.style.display = 'block';
        });

        // View action button
        var viewBtn = previewEl.querySelector('.btn-view-uploaded');
        if (viewBtn) {
            viewBtn.addEventListener('click', function () {
                var url = isFront ? frontFileBlob : backFileBlob;
                var fname = isFront ? frontFileName : backFileName;
                openViewer(url, fname);
            });
        }

        // Remove action button
        var removeBtn = previewEl.querySelector('.btn-remove-uploaded');
        if (removeBtn) {
            removeBtn.addEventListener('click', function () {
                inputEl.value = '';
                if (isFront && frontFileBlob) {
                    URL.revokeObjectURL(frontFileBlob);
                    frontFileBlob = null;
                    frontFileName = '';
                } else if (!isFront && backFileBlob) {
                    URL.revokeObjectURL(backFileBlob);
                    backFileBlob = null;
                    backFileName = '';
                }
                previewEl.style.display = 'none';
                if (promptEl) promptEl.style.display = 'flex';
                if (cardBox) cardBox.classList.remove('has-file');
                if (badgeEl) badgeEl.style.display = 'none';
            });
        }
    }

    setupUploadZone(frontInput, frontPreview, frontBox, frontPrompt, frontBadge, errorFront, true);
    setupUploadZone(backInput, backPreview, backBox, backPrompt, backBadge, errorBack, false);

    // --- Lightbox Modal Viewer ---
    var viewerModal = document.getElementById('fileViewerModal');
    var viewerImage = document.getElementById('viewerModalImage');
    var viewerPdf = document.getElementById('viewerModalPdf');
    var viewerFilename = document.getElementById('viewerModalFilename');
    var viewerCloseBtn = document.getElementById('viewerModalCloseBtn');
    var viewerDismissBtn = document.getElementById('viewerModalDismissBtn');

    function openViewer(fileUrl, fileName) {
        if (!viewerModal || !fileUrl) return;
        var isPdf = (fileName || '').toLowerCase().endsWith('.pdf');
        if (viewerFilename) viewerFilename.textContent = fileName || 'Uploaded Document';

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

    // --- Privacy Notice Modal ---
    var privacyLink = document.getElementById('openPrivacyNoticeLink');
    var privacyModal = document.getElementById('privacyNoticeModal');
    var closePrivacyBtn = document.getElementById('closePrivacyNoticeModalBtn');
    var dismissPrivacyBtn = document.getElementById('dismissPrivacyNoticeModalBtn');

    function openPrivacyModal(e) {
        if (e) e.preventDefault();
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
        if (e.key === 'Escape') {
            if (viewerModal && viewerModal.style.display === 'flex') closeViewer();
            if (privacyModal && privacyModal.style.display === 'flex') closePrivacyModal();
        }
    });

    // --- Validation Functions for Each Step ---
    function validateStep1() {
        var isValid = true;
        var firstInvalidEl = null;

        var firstName = document.getElementById('reg-first-name');
        var errFirst = document.getElementById('error-first-name');
        if (!firstName.value.trim()) {
            errFirst.textContent = 'Please enter your first name.';
            firstName.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = firstName;
        } else {
            errFirst.textContent = '';
            firstName.classList.remove('is-invalid');
        }

        var lastName = document.getElementById('reg-last-name');
        var errLast = document.getElementById('error-last-name');
        if (!lastName.value.trim()) {
            errLast.textContent = 'Please enter your last name.';
            lastName.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = lastName;
        } else {
            errLast.textContent = '';
            lastName.classList.remove('is-invalid');
        }

        var dobValid = updateBirthdate();
        if (!dobValid) {
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = monthSelect;
        }

        var genderInput = document.getElementById('id_gender');
        var errGender = document.getElementById('error-gender');
        if (!genderInput.value) {
            errGender.textContent = 'Please select your gender.';
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = document.getElementById('reg-gender-group');
        } else {
            errGender.textContent = '';
        }

        var civilInput = document.getElementById('id_civil_status');
        var errCivil = document.getElementById('error-civil-status');
        if (!civilInput.value) {
            errCivil.textContent = 'Please select your civil status.';
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = document.getElementById('reg-civil-status-group');
        } else {
            errCivil.textContent = '';
        }

        if (firstInvalidEl && typeof firstInvalidEl.focus === 'function') {
            firstInvalidEl.focus();
        }
        return isValid;
    }

    function validateStep2() {
        var isValid = true;
        var firstInvalidEl = null;

        var addressInput = document.getElementById('reg-address');
        var errAddress = document.getElementById('error-address');
        if (!addressInput.value.trim()) {
            errAddress.textContent = 'Please enter your home address.';
            addressInput.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = addressInput;
        } else {
            errAddress.textContent = '';
            addressInput.classList.remove('is-invalid');
        }

        var contactInput = document.getElementById('reg-contact-no');
        var errContact = document.getElementById('error-contact-no');
        var phoneVal = (contactInput.value || '').trim();
        if (!phoneVal) {
            errContact.textContent = 'Please enter your 11-digit mobile number.';
            contactInput.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = contactInput;
        } else if (phoneVal.length !== 11 || !phoneVal.startsWith('09')) {
            errContact.textContent = 'Mobile number must be exactly 11 digits starting with 09.';
            contactInput.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = contactInput;
        } else {
            errContact.textContent = '';
            contactInput.classList.remove('is-invalid');
        }

        var emailInput = document.getElementById('reg-email');
        var errEmail = document.getElementById('error-email');
        var emailVal = (emailInput.value || '').trim();
        var emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailVal) {
            errEmail.textContent = 'Please enter your email address.';
            emailInput.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = emailInput;
        } else if (!emailPattern.test(emailVal)) {
            errEmail.textContent = 'Please enter a valid email address (e.g. name@example.com).';
            emailInput.classList.add('is-invalid');
            isValid = false;
            if (!firstInvalidEl) firstInvalidEl = emailInput;
        } else {
            errEmail.textContent = '';
            emailInput.classList.remove('is-invalid');
        }

        if (firstInvalidEl && typeof firstInvalidEl.focus === 'function') {
            firstInvalidEl.focus();
        }
        return isValid;
    }

    function validateStep3() {
        var isValid = true;
        var errFront = document.getElementById('error-id-photo');
        var hasFrontFile = frontInput && frontInput.files && frontInput.files.length > 0;

        if (!hasFrontFile) {
            errFront.textContent = 'Please take or choose a photo of the front of your ID.';
            isValid = false;
            var promptBtn = document.querySelector('#front_id_prompt_box .reg-file-button');
            if (promptBtn) promptBtn.focus();
        } else {
            errFront.textContent = '';
        }
        return isValid;
    }

    // --- Step 4: Populate Review Summary ---
    function populateSummary() {
        var firstName = (document.getElementById('reg-first-name').value || '').trim();
        var middleName = (document.getElementById('reg-middle-name').value || '').trim();
        var lastName = (document.getElementById('reg-last-name').value || '').trim();
        var fullName = firstName + (middleName ? ' ' + middleName : '') + ' ' + lastName;
        var sumName = document.getElementById('summary-full-name');
        if (sumName) sumName.textContent = fullName || '—';

        var dobVal = (hiddenBirthdate ? hiddenBirthdate.value : '');
        var sumDob = document.getElementById('summary-dob');
        if (sumDob && dobVal) {
            var parts = dobVal.split('-');
            var mNum = parseInt(parts[1], 10);
            var mNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
            var mStr = mNames[mNum - 1] || parts[1];
            var age = calculateAge(new Date(parseInt(parts[0], 10), mNum - 1, parseInt(parts[2], 10)));
            sumDob.textContent = mStr + ' ' + parseInt(parts[2], 10) + ', ' + parts[0] + ' (' + age + ' years old)';
        }

        var genderVal = document.getElementById('id_gender').value;
        var civilVal = document.getElementById('id_civil_status').value;
        var sumGenderStatus = document.getElementById('summary-gender-status');
        if (sumGenderStatus) {
            var gText = genderVal ? genderVal.charAt(0).toUpperCase() + genderVal.slice(1) : '';
            var cText = civilVal ? civilVal.charAt(0).toUpperCase() + civilVal.slice(1) : '';
            sumGenderStatus.textContent = gText + (gText && cText ? ' • ' : '') + cText;
        }

        var addressVal = (document.getElementById('reg-address').value || '').trim();
        var sumAddress = document.getElementById('summary-address');
        if (sumAddress) sumAddress.textContent = addressVal || '—';

        var phoneVal = (document.getElementById('reg-contact-no').value || '').trim();
        var sumPhone = document.getElementById('summary-contact-no');
        if (sumPhone) sumPhone.textContent = phoneVal || '—';

        var emailVal = (document.getElementById('reg-email').value || '').trim();
        var sumEmail = document.getElementById('summary-email');
        if (sumEmail) sumEmail.textContent = emailVal || '—';

        var sumFront = document.getElementById('summary-id-front');
        if (sumFront) {
            sumFront.textContent = frontFileName ? ('✓ ' + frontFileName) : 'Front ID uploaded';
        }

        var sumBack = document.getElementById('summary-id-back');
        if (sumBack) {
            sumBack.innerHTML = backFileName ? ('✓ ' + backFileName) : '<span class="reg-text-muted">Not provided</span>';
        }
    }

    // --- Navigation (goToStep) ---
    function goToStep(step) {
        if (step < 1 || step > 4) return;
        currentStep = step;
        wizardRoot.setAttribute('data-current-step', step);

        // Show/hide panels
        stepPanels.forEach(function (panel, idx) {
            if (panel) {
                var isCurrent = (idx + 1) === step;
                panel.style.display = isCurrent ? 'flex' : 'none';
            }
        });

        // Update progress bar segments
        stepSegments.forEach(function (seg, idx) {
            var segStep = idx + 1;
            seg.classList.remove('active', 'done');
            if (segStep < step) {
                seg.classList.add('done');
            } else if (segStep === step) {
                seg.classList.add('active');
            }
        });

        // Update step text
        if (stepIndicatorText) {
            stepIndicatorText.textContent = 'Step ' + step + ' of 4: ' + stepTitles[step - 1];
        }

        // Update Footer Buttons
        if (btnBack) {
            btnBack.disabled = (step === 1);
        }

        if (step === 4) {
            if (btnNext) btnNext.style.display = 'none';
            if (btnSubmit) btnSubmit.style.display = 'inline-flex';
            populateSummary();
        } else {
            if (btnNext) btnNext.style.display = 'inline-flex';
            if (btnSubmit) btnSubmit.style.display = 'none';
        }

        // Scroll to top of wizard smoothly
        var modalScrollContainer = wizardRoot.closest('.reg-wizard-modal-scroll');
        if (modalScrollContainer) {
            modalScrollContainer.scrollTop = 0;
        } else if (wizardRoot.offsetParent !== null) {
            wizardRoot.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
    }

    // Next Button Click Handler
    if (btnNext) {
        btnNext.addEventListener('click', function () {
            if (currentStep === 1) {
                if (!validateStep1()) return;
                goToStep(2);
            } else if (currentStep === 2) {
                if (!validateStep2()) return;
                goToStep(3);
            } else if (currentStep === 3) {
                if (!validateStep3()) return;
                goToStep(4);
            }
        });
    }

    // Back Button Click Handler
    if (btnBack) {
        btnBack.addEventListener('click', function () {
            if (currentStep > 1) {
                goToStep(currentStep - 1);
            }
        });
    }

    // Review "Change" jump buttons
    var changeBtns = document.querySelectorAll('.reg-summary-change-btn');
    changeBtns.forEach(function (btn) {
        btn.addEventListener('click', function () {
            var jumpTo = parseInt(this.getAttribute('data-jump-to'), 10);
            if (jumpTo >= 1 && jumpTo <= 3) {
                goToStep(jumpTo);
            }
        });
    });

    // Form Submission Handler
    if (form) {
        form.addEventListener('submit', function (e) {
            // Check privacy consent
            var consentCheckbox = document.getElementById('id_privacy_consent');
            var errConsent = document.getElementById('error-privacy-consent');
            if (consentCheckbox && !consentCheckbox.checked) {
                e.preventDefault();
                if (errConsent) errConsent.textContent = 'Please agree to the privacy notice before sending your registration.';
                consentCheckbox.focus();
                return false;
            } else if (errConsent) {
                errConsent.textContent = '';
            }

            // Ensure hidden inputs are validated
            if (!validateStep1()) {
                e.preventDefault();
                goToStep(1);
                return false;
            }
            if (!validateStep2()) {
                e.preventDefault();
                goToStep(2);
                return false;
            }
            if (!validateStep3()) {
                e.preventDefault();
                goToStep(3);
                return false;
            }

            // Allow form submission
            if (btnSubmit) {
                btnSubmit.disabled = true;
                var submitMsg = btnSubmit.getAttribute('data-submitting-text') || 'Sending registration...';
                btnSubmit.textContent = submitMsg;
            }
        });
    }

    // --- Check for server-side error banner on load ---
    var errorBanner = document.getElementById('reg-server-error-banner');
    if (errorBanner) {
        var errorStep = parseInt(errorBanner.getAttribute('data-error-step'), 10) || 1;
        goToStep(errorStep);
    } else {
        goToStep(1);
    }
});
