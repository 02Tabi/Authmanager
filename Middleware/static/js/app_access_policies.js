document.addEventListener('DOMContentLoaded', function() {
    
    // ==========================================
    // POLICY TABLE SEARCH FILTER
    // ==========================================
    const searchInput = document.getElementById('policySearch');
    const tableBody = document.getElementById('policyTableBody');
    const noResults = document.getElementById('noResults');

    if (searchInput && tableBody && noResults) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            const rows = tableBody.querySelectorAll('.policy-row');
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

});