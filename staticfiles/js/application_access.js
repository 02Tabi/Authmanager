document.addEventListener('DOMContentLoaded', function() {
    
    // ==========================================
    // 1. APPLICATION SEARCH FILTER
    // ==========================================
    const searchInput = document.getElementById('appSearch');
    const tableBody = document.getElementById('appTableBody');
    const noResults = document.getElementById('noResults');

    if (searchInput && tableBody && noResults) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase().trim();
            const rows = tableBody.querySelectorAll('.app-row');
            let visibleCount = 0;
            
            rows.forEach(function (row) {
                const text = row.getAttribute('data-search-content') || row.innerText.toLowerCase();
                if (text.toLowerCase().includes(query)) {
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

    // ==========================================
    // 2. COREUI MODAL POPULATION EVENT
    // ==========================================
    const viewAppModal = document.getElementById('viewAppModal');
    const editAppForm = document.getElementById('editAppForm');
    const editToggleBtn = document.getElementById('editToggleBtn');
    const saveBtn = document.getElementById('saveBtn');
    const cancelEditBtn = document.getElementById('cancelEditBtn');
    const editableInputs = document.querySelectorAll('.modal-editable, .checker-editable');

    if (viewAppModal) {
        viewAppModal.addEventListener('show.coreui.modal', function (event) {
            const button = event.relatedTarget; // The button that was clicked
            if (!button) return;

            // Extract attributes from the clicked button
            const actionUrl = button.getAttribute('data-action-url');
            const appName = button.getAttribute('data-name') || '';
            const appCode = button.getAttribute('data-appid') || '';
            const appType = button.getAttribute('data-type') || '';
            const appStatus = button.getAttribute('data-status') || '';
            const appDesc = button.getAttribute('data-desc') || '';
            const appLoginUrl = button.getAttribute('data-login-url') || '';

            // Set the form submission action URL dynamically
            if (editAppForm && actionUrl) {
                editAppForm.action = actionUrl;
            }

            // Populate the input fields
            document.getElementById('modalAppName').value = appName;
            document.getElementById('modalAppId').value = appCode;
            document.getElementById('modalAppType').value = appType;
            document.getElementById('modalStatus').value = appStatus;
            document.getElementById('modalDesc').value = appDesc;
            const loginUrlField = document.getElementById('modalLoginUrl');
            if (loginUrlField) loginUrlField.value = appLoginUrl;

            // Reset modal state to read-only
            editableInputs.forEach(input => input.disabled = true);
            if (editToggleBtn) editToggleBtn.classList.remove('d-none');
            if (saveBtn) saveBtn.classList.add('d-none');
            if (cancelEditBtn) cancelEditBtn.classList.add('d-none');
        });
    }

    // ==========================================
    // 3. EDIT & CANCEL BUTTON TOGGLE LOGIC
    // ==========================================
    if (editToggleBtn && cancelEditBtn) {
        editToggleBtn.addEventListener('click', function() {
            const isCheckerData = document.getElementById('canApproveData');
            let isChecker = isCheckerData ? JSON.parse(isCheckerData.textContent) : false;

            editableInputs.forEach(input => {
                if (input.id === 'modalStatus' && !isChecker) {
                    input.disabled = true; // Lock status if not a checker
                } else {
                    input.disabled = false; // Unlock everything else
                }
            });

            editToggleBtn.classList.add('d-none');
            if (saveBtn) saveBtn.classList.remove('d-none');
            cancelEditBtn.classList.remove('d-none');
        });

        cancelEditBtn.addEventListener('click', function() {
            editableInputs.forEach(input => input.disabled = true);
            
            editToggleBtn.classList.remove('d-none');
            if (saveBtn) saveBtn.classList.add('d-none');
            cancelEditBtn.classList.add('d-none');
        });
    }

});