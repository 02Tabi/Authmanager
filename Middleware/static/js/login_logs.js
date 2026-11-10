document.addEventListener('DOMContentLoaded', function() {

    /* ── Secure Search Filter Logic ── */
    const searchInput = document.getElementById('logSearch');
    const tableBody = document.getElementById('logTableBody');
    const noResults = document.getElementById('noResults');

    if (searchInput && tableBody && noResults) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            const rows = tableBody.querySelectorAll('.log-row');
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

    /* ── Secure User Agent Expand / Collapse Logic ── */
    document.addEventListener('click', function (e) {
        if (!e.target.classList.contains('ua-toggle')) return;
        
        const wrapper = e.target.closest('.ua-wrapper');
        if (!wrapper) return;
        
        const short = wrapper.querySelector('.ua-short');
        const full = wrapper.querySelector('.ua-full');
        
        if (short && full) {
            // Toggle the Bootstrap d-none class to securely hide/show content
            if (full.classList.contains('d-none')) {
                short.classList.add('d-none');
                full.classList.remove('d-none');
            } else {
                short.classList.remove('d-none');
                full.classList.add('d-none');
            }
        }
    });

});