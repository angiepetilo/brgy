// Moved from templates/communications/announcement_form.html (inline scripts are blocked by the CSP).
function handleStandaloneImage(fileInput) {
    const previewWrapper = document.getElementById('standaloneImagePreviewWrapper');
    const previewImg = document.getElementById('standaloneImagePreviewElement');
    if (fileInput && fileInput.files && fileInput.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            if (previewImg && previewWrapper) {
                previewImg.src = e.target.result;
                previewWrapper.style.display = 'block';
            }
        };
        reader.readAsDataURL(fileInput.files[0]);
    }
}

function clearStandaloneImage() {
    const fileInput = document.getElementById('standaloneImageFileInput');
    const previewWrapper = document.getElementById('standaloneImagePreviewWrapper');
    const previewImg = document.getElementById('standaloneImagePreviewElement');
    const clearFlag = document.getElementById('standaloneClearImageFlag');
    if (fileInput) fileInput.value = '';
    if (previewImg) previewImg.src = '';
    if (previewWrapper) previewWrapper.style.display = 'none';
    if (clearFlag) clearFlag.value = '1';
}

document.addEventListener('click', function (event) {
    if (event.target.closest('[data-form-action="clear-image"]')) {
        clearStandaloneImage();
    }
});

document.addEventListener('change', function (event) {
    var el = event.target;
    if (el.id === 'standaloneImageFileInput') {
        handleStandaloneImage(el);
    } else if (el.hasAttribute('data-pin-toggle') && el.parentElement) {
        el.parentElement.style.opacity = el.checked ? '1' : '0.5';
    }
});
