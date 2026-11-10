document.addEventListener('DOMContentLoaded', function() {
    
    // Pagination & Search Logic
    const searchInput = document.getElementById('auditSearch');
    const tableBody = document.getElementById('auditTableBody');
    const noResults = document.getElementById('noResults');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const paginationInfo = document.getElementById('paginationInfo');

    const rowsPerPage = 25; // Limit set to exactly 25
    let currentPage = 1;
    let allRows = [];
    let filteredRows = [];

    if (tableBody) {
        // Initialize the rows and cache their search content
        Array.from(tableBody.querySelectorAll('.audit-row')).forEach(row => {
            row.setAttribute('data-search-content', row.innerText.toLowerCase());
            allRows.push(row);
        });
        
        filteredRows = [...allRows];
        renderTable();
    }

    function renderTable() {
        // Hide all rows safely via CSS class
        allRows.forEach(row => row.classList.add('d-none'));
        
        const totalPages = Math.ceil(filteredRows.length / rowsPerPage) || 1;
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        const start = (currentPage - 1) * rowsPerPage;
        const end = Math.min(start + rowsPerPage, filteredRows.length);

        // Show only the rows for the current page
        filteredRows.slice(start, end).forEach(row => {
            row.classList.remove('d-none');
        });

        // Update Pagination Info Text
        if (paginationInfo) {
            if (filteredRows.length === 0) {
                paginationInfo.textContent = 'Showing 0 entries';
            } else {
                paginationInfo.textContent = `Showing ${start + 1} to ${end} of ${filteredRows.length} entries`;
            }
        }

        // Disable Next/Prev buttons if we are at the beginning/end
        if (prevBtn) prevBtn.disabled = (currentPage === 1);
        if (nextBtn) nextBtn.disabled = (currentPage === totalPages);
    }

    // Previous Page Action
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) { 
                currentPage--; 
                renderTable(); 
            }
        });
    }
    
    // Next Page Action
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
            if (currentPage < totalPages) { 
                currentPage++; 
                renderTable(); 
            }
        });
    }

    // Table Real-time Filter Search
    if (searchInput && tableBody) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            
            // Filter based on the hidden data attribute
            filteredRows = allRows.filter(row => {
                return row.getAttribute('data-search-content').includes(query);
            });
            
            currentPage = 1; // Reset to page 1 whenever they type
            renderTable();
            
            if (noResults) {
                if (filteredRows.length === 0) {
                    noResults.classList.remove('d-none');
                } else {
                    noResults.classList.add('d-none');
                }
            }
            
            const emptyStateRow = document.getElementById('emptyStateRow');
            if (emptyStateRow) {
                emptyStateRow.classList.add('d-none');
            }
        });
    }
});