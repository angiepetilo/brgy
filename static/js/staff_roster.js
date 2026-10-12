/*
 * Staff Directory duty roster behaviors (CSP-compliant, external script).
 */
document.addEventListener('DOMContentLoaded', function () {
    const directoryCard = document.getElementById('staff-directory-card');
    if (!directoryCard) return;

    const dutyUrl = directoryCard.dataset.dutyUrl || '/accounts/staff/toggle-duty/';

    // Search toggle in Staff Directory
    const searchBtn = document.getElementById('search-staff-toggle-btn');
    const searchContainer = document.getElementById('staff-search-container');
    const searchInput = document.getElementById('staff-search-input');
    if (searchBtn && searchContainer && searchInput) {
        searchBtn.addEventListener('click', function () {
            const isHidden = searchContainer.style.display === 'none';
            searchContainer.style.display = isHidden ? 'block' : 'none';
            if (isHidden) searchInput.focus();
        });
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            document.querySelectorAll('#staff-roster-list .roster-row-item').forEach(function (row) {
                const name = row.dataset.name || '';
                const role = row.dataset.role || '';
                row.style.display = (name.includes(query) || role.includes(query)) ? 'flex' : 'none';
            });
        });
    }

    // CSRF token lookup
    function getCsrfToken() {
        const tokenInput = document.querySelector('[name=csrfmiddlewaretoken]');
        if (tokenInput) return tokenInput.value;
        const cookie = document.cookie.split('; ').find(function (row) { return row.startsWith('csrftoken='); });
        return cookie ? cookie.split('=')[1] : '';
    }

    // Duty Status AJAX Toggle
    document.querySelectorAll('.duty-toggle-input').forEach(function (toggle) {
        toggle.addEventListener('change', function () {
            const userId = this.dataset.userId;
            const isChecked = this.checked;
            const isSelf = this.dataset.isSelf === 'true';
            const newStatus = isChecked ? 'on_duty' : 'off_duty';

            // Optimistic UI updates
            updateUI(userId, newStatus, isSelf);

            const formData = new FormData();
            formData.append('user_id', userId);
            formData.append('status', newStatus);

            fetch(dutyUrl, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': getCsrfToken(),
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json'
                },
                body: formData
            })
            .then(function (res) { return res.json(); })
            .then(function (data) {
                if (data.status === 'ok') {
                    updateUI(userId, data.duty_status, isSelf);
                } else {
                    revertUI(toggle, !isChecked);
                }
            })
            .catch(function (err) {
                console.error("Failed to toggle duty status:", err);
                revertUI(toggle, !isChecked);
            });
        });
    });

    function updateUI(userId, status, isSelf) {
        const isOn = status === 'on_duty';
        const color = isOn ? '#10B981' : '#9CA3AF';
        const text = isOn ? 'ON' : 'OFF';
        const fullText = isOn ? 'ON-DUTY' : 'OFF-DUTY';
        const textColor = isOn ? '#059669' : '#64748B';
        const trackColor = isOn ? '#10B981' : '#CBD5E1';
        const thumbLeft = isOn ? '16px' : '2px';

        // Update dot
        const dot = document.getElementById('officer-dot-' + userId);
        if (dot) dot.style.background = color;

        // Update text
        const label = document.getElementById('officer-text-' + userId);
        if (label) {
            label.textContent = text;
            label.style.color = textColor;
        }

        // Update slider track and thumb
        const track = document.getElementById('slider-track-' + userId);
        if (track) track.style.backgroundColor = trackColor;
        const thumb = document.getElementById('slider-thumb-' + userId);
        if (thumb) thumb.style.left = thumbLeft;

        // If self banner exists
        if (isSelf) {
            const myDot = document.getElementById('my-duty-dot');
            if (myDot) myDot.style.background = color;
            const myLabel = document.getElementById('my-duty-label');
            if (myLabel) {
                myLabel.textContent = fullText;
                myLabel.style.color = textColor;
            }
        }
    }

    function revertUI(toggle, previousChecked) {
        toggle.checked = previousChecked;
        alert("Unable to update duty status. Please try again.");
    }
});
