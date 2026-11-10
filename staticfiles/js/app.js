document.addEventListener('DOMContentLoaded', function() {
    
    // Pagination & Search Elements
    const searchInput = document.getElementById('policySearch');
    const tableBody = document.getElementById('policyTableBody');
    const noResults = document.getElementById('noResults');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const paginationInfo = document.getElementById('paginationInfo');

    const rowsPerPage = 20; 
    let currentPage = 1;
    let allRows = [];
    let filteredRows = [];

    if (tableBody) {
        // Build the search index
        Array.from(tableBody.querySelectorAll('.policy-row')).forEach(row => {
            const userCell = row.querySelector('td:first-child');
            // Store search content dynamically
            row.setAttribute('data-search-content', row.innerText.toLowerCase());
            // Use the data-uname we placed in the HTML
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

        let previousUsername = "";

        // Show rows for the current page
        filteredRows.forEach((row, index) => {
            if (index >= start && index < end) {
                row.classList.remove('d-none');
                
                // Hide duplicate names visually
                const userCell = row.querySelector('td:first-child');
                if (userCell) {
                    const currentUname = userCell.getAttribute('data-uname');
                    if (currentUname === previousUsername) {
                        userCell.innerText = ""; 
                    } else {
                        userCell.innerText = currentUname; 
                        previousUsername = currentUname;
                    }
                }
            }
        });

        // Update Pagination Info
        if (paginationInfo) {
            if (filteredRows.length === 0) {
                paginationInfo.textContent = 'Showing 0 entries';
            } else {
                paginationInfo.textContent = `Showing ${start + 1} to ${end} of ${filteredRows.length} entries`;
            }
        }

        if (prevBtn) prevBtn.disabled = (currentPage === 1);
        if (nextBtn) nextBtn.disabled = (currentPage === totalPages);
    }

    // Previous Page
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) { 
                currentPage--; 
                renderTable(); 
            }
        });
    }
    
    // Next Page
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
            if (currentPage < totalPages) { 
                currentPage++; 
                renderTable(); 
            }
        });
    }

    // Real-time Search
    if (searchInput && tableBody) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            
            filteredRows = allRows.filter(row => {
                return row.getAttribute('data-search-content').includes(query);
            });
            
            currentPage = 1; 
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

    // View Policy Modal Integration
    document.querySelectorAll('.view-btn').forEach(function(btn) {
        btn.addEventListener('click', function() {
            const username = this.dataset.username;
            const appName  = this.dataset.appName;
            const appId    = this.dataset.appId;
            const authType = this.dataset.authType;
            const permType = this.dataset.permission;
            const status   = this.dataset.status;
            const date     = this.dataset.date;

            const modalUserEl = document.getElementById('viewModalUsername');
            if (modalUserEl) modalUserEl.textContent = '@' + username;
            
            const appEl = document.getElementById('viewModalApp');
            if (appEl) appEl.textContent = appName;
            
            const appIdEl = document.getElementById('viewModalAppId');
            if (appIdEl) appIdEl.textContent = appId;
            
            const authEl = document.getElementById('viewModalAuth');
            if (authEl) authEl.textContent = authType;
            
            const permEl = document.getElementById('viewModalPerm');
            if (permEl) permEl.textContent = permType;
            
            const dateEl = document.getElementById('viewModalDate');
            if (dateEl) dateEl.textContent = date;

            const statusCell = document.getElementById('viewModalStatus');
            if (statusCell) {
                if (status === 'Active') {
                    statusCell.innerHTML = '<span class="badge bg-success">Active</span>';
                } else {
                    statusCell.innerHTML = '<span class="badge bg-danger">Inactive</span>';
                }
            }

            const modalEl = document.getElementById('viewPolicyModal');
            if (modalEl) {
                new coreui.Modal(modalEl).show();
            }
        });
    });

    // Add App Modal Reset
    const addAppModalEl = document.getElementById('addAppModal');
    if (addAppModalEl) {
        addAppModalEl.addEventListener('show.coreui.modal', function() {
            const form = document.getElementById('addAppForm');
            if (form) form.reset();
        });
    }

});