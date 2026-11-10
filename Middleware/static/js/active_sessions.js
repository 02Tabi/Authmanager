document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Secure Search Filter Logic
    const searchInput = document.getElementById('sessionSearch');
    const tableBody = document.getElementById('sessionTableBody');
    const noResults = document.getElementById('noResults');

    if (searchInput && tableBody && noResults) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            const rows = tableBody.querySelectorAll('.session-row');
            let visibleCount = 0;
            
            rows.forEach(function (row) {
                const text = row.innerText.toLowerCase();
                if (text.includes(query)) {
                    row.classList.remove('d-none');
                    visibleCount++;
                } else {
                    row.classList.add('d-none');
                }
            });
            
            if (visibleCount === 0 && rows.length > 0) {
                noResults.classList.remove('d-none');
            } else {
                noResults.classList.add('d-none');
            }
        });
    }

    // 2. Secure Event Delegation for Confirm Dialogs
    document.addEventListener('click', function(e) {
        const logoutBtn = e.target.closest('.force-logout-btn');
        if (logoutBtn) {
            // Intercept the click and run the confirm securely
            if (!confirm('Force logout this user?')) {
                e.preventDefault(); // Stop the link from opening if they click Cancel
            }
        }
    });

    // 3. Secure Auto-Refresh
    // Reloads the page every 30 seconds to keep session list fresh
    setInterval(() => {
        window.location.reload();
    }, 30000);

});