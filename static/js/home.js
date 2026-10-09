// Home feed interactions (toggle comments, etc.)
function toggleComments(elementId) {
    const el = document.getElementById(elementId);
    if (el) {
        if (el.style.display === 'none') {
            el.style.display = 'block';
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
