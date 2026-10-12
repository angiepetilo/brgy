// Home feed interactions (toggle comments, etc.)
function toggleComments(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        const isHidden = el.style.display === 'none' || window.getComputedStyle(el).display === 'none';
        if (isHidden) {
            el.style.display = 'block';
            const input = el.querySelector('.comment-input');
            if (input) input.focus();
        } else {
            el.style.display = 'none';
        }
    }
}

document.addEventListener('click', function (event) {
    var btn = event.target.closest('[data-toggle-comments]');
    if (btn) {
        toggleComments(btn.getAttribute('data-toggle-comments'));
    }
});
