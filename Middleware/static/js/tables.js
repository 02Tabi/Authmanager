document.addEventListener('DOMContentLoaded', function() {
    

    document.addEventListener('click', function(e) {
        if (e.target.closest('.toast-close-btn')) {
            const toastItem = e.target.closest('.toast-item');
            if (toastItem) toastItem.remove();
        }
    });


    const colorMap = { danger: '#e55353', success: '#2eb85c', warning: '#f9b115', info: '#39f' };
    let _pendingAction = null;
    
    const modalEl = document.getElementById('confirmModal');
    const titleEl = document.getElementById('confirmModalTitle');
    const msgEl = document.getElementById('confirmModalMessage');
    const okBtn = document.getElementById('confirmOkBtn');
    const cancelBtn = document.getElementById('confirmCancelBtn');
    const closeBtn = document.getElementById('confirmModalClose');

    function openConfirmModal(title, message, label, color, action) {
        if (!modalEl) return;
        titleEl.textContent = title;
        msgEl.textContent = message;
        okBtn.textContent = label || 'Confirm';
        okBtn.style.background = colorMap[color] || colorMap.danger;
        
        if (color === 'warning') {
            okBtn.classList.remove('text-white');
            okBtn.classList.add('text-dark');
        } else {
            okBtn.classList.add('text-white');
            okBtn.classList.remove('text-dark');
        }
        
        _pendingAction = action;
        new coreui.Modal(modalEl).show();
    }

        function postToUrl(url) {
        const csrfInput = document.querySelector('input[name=csrfmiddlewaretoken]');
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = url;
        form.style.display = 'none';

        const csrfClone = document.createElement('input');
        csrfClone.type = 'hidden';
        csrfClone.name = 'csrfmiddlewaretoken';
        csrfClone.value = csrfInput.value;
        form.appendChild(csrfClone);

        document.body.appendChild(form);
        form.submit();
    }

    function dismissConfirmModal() {
        const instance = coreui.Modal.getInstance(modalEl);
        if (instance) instance.hide();
    }

    if (okBtn) okBtn.addEventListener('click', function() {
        dismissConfirmModal();
        if (typeof _pendingAction === 'function') _pendingAction();
        _pendingAction = null;
    });
    
    if (cancelBtn) cancelBtn.addEventListener('click', dismissConfirmModal);
    if (closeBtn) closeBtn.addEventListener('click', dismissConfirmModal);

    // Stop Propagation for nested table buttons
    document.querySelectorAll('.action-cell').forEach(cell => {
    cell.addEventListener('click', e => {
        if (!e.target.closest('.confirm-nav-link')) {
            e.stopPropagation();
        }
    });
});
 
    // Handle Confirm Navigation Links
    document.addEventListener('click', function(e) {
        const navLink = e.target.closest('.confirm-nav-link');
        if (navLink) {
            e.preventDefault();
            const url = navLink.href;
            openConfirmModal(
                navLink.dataset.title,
                navLink.dataset.message,
                navLink.dataset.label,
                navLink.dataset.color,
                function() { postToUrl(url); }
            );
        }
    }); true;

    // Handle Confirm Actions inside forms/modals
    document.addEventListener('click', function(e) {
        const modalLink = e.target.closest('.confirm-modal-link');
        if (modalLink) {
            e.preventDefault();
            const formElement = document.getElementById('editUserForm');
            if (validateAccessRows(formElement, true)) {
                const url = modalLink.href;
                openConfirmModal(
                    modalLink.dataset.title,
                    modalLink.dataset.message,
                    modalLink.dataset.label,
                    modalLink.dataset.color,
                    function() { postToUrl(url); }
                );
            }
        }
    });

    const searchInput = document.getElementById('userSearch');
    const tableBody = document.getElementById('usersTableBody');
    const noResults = document.getElementById('noResults');
    const prevBtn = document.getElementById('prevBtn');
    const nextBtn = document.getElementById('nextBtn');
    const paginationInfo = document.getElementById('paginationInfo');

    const rowsPerPage = 20;
    let currentPage = 1;
    let allRows = [];
    let filteredRows = [];

    if (tableBody) {
        Array.from(tableBody.querySelectorAll('.main-row')).forEach(row => {
            row.setAttribute('data-search-content', row.innerText.toLowerCase());
            allRows.push(row);
        });
        filteredRows = [...allRows];
        renderTable();
    }

    function renderTable() {
        allRows.forEach(row => row.style.display = 'none');
        const totalPages = Math.ceil(filteredRows.length / rowsPerPage) || 1;
        if (currentPage > totalPages) currentPage = totalPages;
        if (currentPage < 1) currentPage = 1;

        const start = (currentPage - 1) * rowsPerPage;
        const end = Math.min(start + rowsPerPage, filteredRows.length);

        filteredRows.slice(start, end).forEach(row => {
            row.style.display = '';
        });

        if (paginationInfo) {
            paginationInfo.textContent = filteredRows.length === 0 
                ? 'Showing 0 entries' 
                : `Showing ${start + 1} to ${end} of ${filteredRows.length} entries`;
        }

        if (prevBtn) prevBtn.disabled = (currentPage === 1);
        if (nextBtn) nextBtn.disabled = (currentPage === totalPages);
    }

    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentPage > 1) { currentPage--; renderTable(); }
        });
    }
    
    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            const totalPages = Math.ceil(filteredRows.length / rowsPerPage);
            if (currentPage < totalPages) { currentPage++; renderTable(); }
        });
    }

    if (searchInput && tableBody) {
        searchInput.addEventListener('input', function() {
            const query = this.value.toLowerCase();
            filteredRows = allRows.filter(row => row.getAttribute('data-search-content').includes(query));
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
            if (emptyStateRow) emptyStateRow.style.display = 'none';
        });
    }


    function createAccessRow(role, appId, permType, containerId, permId, approvalStatus) {
        containerId = containerId || 'accessRowsContainer';
        const hasPermId = permId && permId !== '';
        const isEditModal = containerId === 'accessRowsContainer';
        const appTemplateHtml = document.getElementById('appOptionsTemplate').innerHTML;

        const row = document.createElement('div');
        row.className = 'row g-2 mb-2 access-row align-items-center';
        if (hasPermId) row.dataset.permId = permId;

        const checkboxHtml = isEditModal
            ? `<div class="col-auto d-flex align-items-center bulk-action-ui d-none pt-22px w-28px">
                 <input type="checkbox" class="perm-row-check" data-perm-id="${permId || ''}">
               </div>`
            : `<div class="col-auto bulk-action-ui d-none w-28px"></div>`;

        let statusBadge = '';
        if (approvalStatus === 'approved') statusBadge = '<span class="badge bg-success fs-10px">Approved</span>';
        else if (approvalStatus === 'rejected') statusBadge = '<span class="badge bg-danger fs-10px">Rejected</span>';
        else if (approvalStatus === 'pending') statusBadge = '<span class="badge bg-warning text-dark fs-10px">Pending</span>';
        else statusBadge = '<span class="badge bg-secondary fs-10px">New</span>';

        row.innerHTML = checkboxHtml + `
            <div class="col-md-2">
                <label class="modal-field-label">Role</label>
                <select class="form-select modal-editable clear-error-on-change" name="user_role[]" disabled required>
                    <option value="" ${!role ? 'selected' : ''} disabled>-- Select --</option>
                    <option value="admin"   ${role === 'admin' ? 'selected' : ''}>Admin</option>
                    <option value="staff"   ${role === 'staff' ? 'selected' : ''}>Staff</option>
                    <option value="manager" ${role === 'manager' ? 'selected' : ''}>Manager</option>
                    <option value="user"    ${role === 'user' ? 'selected' : ''}>User</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="modal-field-label">Application</label>
                <select class="form-select modal-editable clear-error-on-change" name="app_id[]" disabled required>
                    <option value="" ${!appId ? 'selected' : ''} disabled>-- Select App --</option>
                    ${appTemplateHtml}
                </select>
            </div>
            <div class="col-md-3">
                <label class="modal-field-label">Permission</label>
                <select class="form-select modal-editable clear-error-on-change" name="permission_type[]" disabled required>
                    <option value=""             ${!permType ? 'selected' : ''} disabled>-- Select --</option>
                    <option value="admin"        ${permType === 'admin' ? 'selected' : ''}>Admin</option>
                    <option value="maker"        ${permType === 'maker' ? 'selected' : ''}>Maker</option>
                    <option value="checker"      ${permType === 'checker' ? 'selected' : ''}>Checker</option>
                    <option value="user"         ${permType === 'user' ? 'selected' : ''}>User</option>
                </select>
            </div>
            <div class="col-md-2">
                <label class="modal-field-label">Status</label>
                <div class="pt-2">${statusBadge}</div>
            </div>
            <div class="col-auto pt-22px">
                <button type="button" class="btn btn-danger text-white btn-sm remove-access-btn d-none modal-editable" style="height:35px; white-space:nowrap;">
                    Remove
                </button>
            </div>
        `;

        if (appId) {
            const selectApp = row.querySelector('[name="app_id[]"]');
            if (selectApp) selectApp.value = appId;
        }
        
        document.getElementById(containerId).appendChild(row);
    }

    function addNewAccessRow(containerId) {
        containerId = containerId || 'accessRowsContainer';
        createAccessRow('', '', '', containerId, '', 'new');
        const newRow = document.getElementById(containerId).lastElementChild;
        newRow.querySelectorAll('select, button.remove-access-btn').forEach(f => f.disabled = false);
        newRow.querySelectorAll('select').forEach(s => { s.selectedIndex = 0; });
        newRow.querySelector('.remove-access-btn').classList.remove('d-none');
        
        if (containerId === 'accessRowsContainer' && document.getElementById('editToggleBtn').classList.contains('d-none')) {
            newRow.querySelector('.bulk-action-ui').classList.remove('d-none');
        }
    }

    // Bind Add Row Buttons
    const addRowBtnCreate = document.getElementById('addAccessRowBtnCreate');
    if (addRowBtnCreate) addRowBtnCreate.addEventListener('click', () => addNewAccessRow('addAccessRowsContainer'));

    const addRowBtnEdit = document.getElementById('addAccessRowBtnEdit');
    if (addRowBtnEdit) addRowBtnEdit.addEventListener('click', () => addNewAccessRow('accessRowsContainer'));

    // Delegate dynamically added select/remove events
    document.addEventListener('change', function(e) {
        if (e.target.classList.contains('clear-error-on-change')) {
            e.target.classList.remove('select-error');
        }
        if (e.target.classList.contains('perm-row-check')) {
            onPermCheckChange();
        }
    });

    document.addEventListener('click', function(e) {
        const removeBtn = e.target.closest('.remove-access-btn');
        if (removeBtn) {
            openConfirmModal('Remove Access', 'Remove this access row?', 'Remove', 'danger', function() {
                removeBtn.closest('.access-row').remove();
            });
        }
    });

    function validateAccessRows(formElement, isSaveAction) {
        let isValid = true;
        let hasDuplicates = false;
        let seenApps = new Set();
        let rowsToRemove = [];
        
        formElement.querySelectorAll('.access-row select').forEach(s => s.classList.remove('select-error'));

        const rows = formElement.querySelectorAll('.access-row');
        rows.forEach(row => {
            const role = row.querySelector('[name="user_role[]"]');
            const app = row.querySelector('[name="app_id[]"]');
            const perm = row.querySelector('[name="permission_type[]"]');
            const cb = row.querySelector('.perm-row-check');

            if (role && app && perm) {
                const isRelevant = isSaveAction ? true : (cb && cb.checked);
                if (!isRelevant) return; 

                const isCompletelyEmpty = !role.value && !app.value && !perm.value;
                const isComplete = role.value && app.value && perm.value;
                const isPartiallyFilled = (!isComplete && !isCompletelyEmpty);

                if (isSaveAction && isCompletelyEmpty) {
                    rowsToRemove.push(row);
                } else if (isPartiallyFilled) {
                    isValid = false;
                    if (!role.value) role.classList.add('select-error');
                    if (!app.value) app.classList.add('select-error');
                    if (!perm.value) perm.classList.add('select-error');
                } else if (isComplete) {
                    if (seenApps.has(app.value)) {
                        isValid = false;
                        hasDuplicates = true;
                        app.classList.add('select-error'); 
                    } else {
                        seenApps.add(app.value);
                    }
                }
            }
        });

        if (hasDuplicates) {
            if (typeof showToast === 'function') showToast("You cannot assign the same application multiple times to one user.", "error");
        } else if (!isValid) {
            if (typeof showToast === 'function') showToast("Please fill in all empty fields for the highlighted rows.", "error");
        } else if (isSaveAction) {
            rowsToRemove.forEach(r => r.remove());
        }

        return isValid;
    }

    const addUserForm = document.getElementById('addUserForm');
    if (addUserForm) {
        addUserForm.addEventListener('submit', function(e) {
            if (!validateAccessRows(this, true)) { e.preventDefault(); }
        });
    }

    // ----------------------------------------------------------------------
    // 5. Bulk Permissions Logic
    // ----------------------------------------------------------------------
    function onPermCheckChange() {
        const checked = document.querySelectorAll('#accessRowsContainer .perm-row-check:checked');
        const total   = document.querySelectorAll('#accessRowsContainer .perm-row-check');

        document.querySelectorAll('#accessRowsContainer .access-row').forEach(row => {
            const cb = row.querySelector('.perm-row-check');
            if (cb) {
                if (cb.checked) row.classList.add('selected');
                else row.classList.remove('selected');
            }
        });

        const selectAll = document.getElementById('selectAllPerms');
        if (selectAll) {
            selectAll.checked = (total.length > 0 && checked.length === total.length);
            selectAll.indeterminate = false; 
        }

        const bulkApprove = document.getElementById('bulkApproveBtn');
        const bulkReject  = document.getElementById('bulkRejectBtn');
        if (bulkApprove) {
            if (checked.length === 0) bulkApprove.classList.add('d-none');
            else bulkApprove.classList.remove('d-none');
        }
        if (bulkReject) {
            if (checked.length === 0) bulkReject.classList.add('d-none');
            else bulkReject.classList.remove('d-none');
        }
    }

    const selectAllEl = document.getElementById('selectAllPerms');
    if (selectAllEl) {
        selectAllEl.addEventListener('change', function() {
            const isChecked = this.checked;
            document.querySelectorAll('#accessRowsContainer .perm-row-check').forEach(cb => {
                cb.checked = isChecked;
            });
            onPermCheckChange();
        });
    }

    function submitBulkAction(action) {
        const editForm = document.getElementById('editUserForm');
        if (!validateAccessRows(editForm, false)) return; 

        const checkedCheckboxes = Array.from(document.querySelectorAll('#accessRowsContainer .perm-row-check:checked'));
        if (checkedCheckboxes.length === 0) return;

        const label   = action === 'approve' ? 'Approve Selected' : 'Reject Selected';
        const color   = action === 'approve' ? 'success' : 'danger';
        const count   = checkedCheckboxes.length;
        const message = `Are you sure you want to ${action} ${count} selected permission${count > 1 ? 's' : ''}?`;

        openConfirmModal(label, message, label, color, function() {
            const form = document.getElementById('bulkActionForm');
            const inputs = document.getElementById('bulkPermInputs');
            const actionType = document.getElementById('bulkActionType');
            
            inputs.innerHTML = '';
            actionType.value = action;

            checkedCheckboxes.forEach(cb => {
                if (cb.dataset.permId) { 
                    const inp = document.createElement('input');
                    inp.type  = 'hidden';
                    inp.name  = 'perm_ids[]';
                    inp.value = cb.dataset.permId;
                    inputs.appendChild(inp);
                }
            });
            form.submit();
        });
    }

    const btnApprove = document.getElementById('bulkApproveBtn');
    if (btnApprove) btnApprove.addEventListener('click', () => submitBulkAction('approve'));
    
    const btnReject = document.getElementById('bulkRejectBtn');
    if (btnReject) btnReject.addEventListener('click', () => submitBulkAction('reject'));

    // ----------------------------------------------------------------------
    // 6. View & Edit User Modals
    // ----------------------------------------------------------------------
    const addUserModalEl = document.getElementById('addUserModal');
    if (addUserModalEl) {
        addUserModalEl.addEventListener('show.coreui.modal', function() {
            document.getElementById('addUserForm').reset();
            document.getElementById('addAccessRowsContainer').innerHTML = '';
            addNewAccessRow('addAccessRowsContainer');
        });
    }

    document.querySelectorAll('.view-btn').forEach(btn => {
        btn.addEventListener('click', function() {
            const row = this.closest('.main-row');
            const username = row.dataset.username;

            document.getElementById('modalUsername').textContent = '@' + username;
            document.getElementById('modalUsernameField').value  = username;
            document.getElementById('modalFirstname').value      = row.dataset.firstname;
            document.getElementById('modalLastname').value       = row.dataset.lastname;
            document.getElementById('modalEmail').value          = row.dataset.email;
            document.getElementById('modalPhone').value          = row.dataset.phone;
            document.getElementById('modalFailedAttempts').value = row.dataset.failedAttempts;
            document.getElementById('modalProfileId').value      = row.dataset.profileId;
            document.getElementById('editUserForm').action       = '/portal/users/edit/' + row.dataset.profileId + '/';

            document.getElementById('accessRowsContainer').innerHTML = '';
            document.querySelectorAll('.perm-data-row[data-username="' + username + '"]').forEach(uRow => {
                createAccessRow(uRow.dataset.role, uRow.dataset.appId, uRow.dataset.permission, 'accessRowsContainer', uRow.dataset.permId, uRow.dataset.approvalStatus);
            });

            const selectAll = document.getElementById('selectAllPerms');
            if (selectAll) {
                selectAll.checked = false;
                selectAll.indeterminate = false;
            }
            onPermCheckChange(); 

            document.getElementById('activeStatusContainer').innerHTML = row.dataset.isActive === 'true'
                ? '<span class="badge bg-success fs-10px">Active</span>'
                : '<span class="badge bg-danger fs-10px">Inactive</span>';

            const activateBtn = document.getElementById('modalActivateBtn');
            if(activateBtn) activateBtn.href = row.dataset.activateUrl;
            
            const deactivateBtn = document.getElementById('modalDeactivateBtn');
            if(deactivateBtn) deactivateBtn.href = row.dataset.deactivateUrl;
            
            const resetBtn = document.getElementById('modalResetBtn');
            if(resetBtn) resetBtn.href = row.dataset.resetUrl;

            setViewMode();
            new coreui.Modal(document.getElementById('userModal')).show();
        });
    });

    function setViewMode() {
        document.querySelectorAll('#editUserForm .modal-editable').forEach(f => f.disabled = true);
        document.querySelectorAll('#editUserForm .remove-access-btn').forEach(btn => btn.classList.add('d-none'));
        
        const addRowBtn = document.getElementById('addAccessRowBtnEdit');
        if(addRowBtn) addRowBtn.classList.add('d-none');
        
        const editToggle = document.getElementById('editToggleBtn');
        if(editToggle) editToggle.classList.remove('d-none');
        
        const saveBtn = document.getElementById('saveBtn');
        if(saveBtn) saveBtn.classList.add('d-none');
        
        const cancelBtn = document.getElementById('cancelEditBtn');
        if(cancelBtn) cancelBtn.classList.add('d-none');
        
        document.querySelectorAll('.bulk-action-ui').forEach(el => el.classList.add('d-none'));
        
        const selectAll = document.getElementById('selectAllPerms');
        if (selectAll) {
            selectAll.checked = false;
            selectAll.indeterminate = false;
        }
        
        document.querySelectorAll('#editUserForm select').forEach(s => s.classList.remove('select-error'));
        document.querySelectorAll('#accessRowsContainer .perm-row-check').forEach(cb => cb.checked = false);
        onPermCheckChange(); 
    }
    
    function setEditMode() {
        document.querySelectorAll('#editUserForm .modal-editable').forEach(f => f.disabled = false);
        document.querySelectorAll('#editUserForm .remove-access-btn').forEach(btn => btn.classList.remove('d-none'));
        
        const addRowBtn = document.getElementById('addAccessRowBtnEdit');
        if(addRowBtn) addRowBtn.classList.remove('d-none');
        
        const editToggle = document.getElementById('editToggleBtn');
        if(editToggle) editToggle.classList.add('d-none');
        
        const saveBtn = document.getElementById('saveBtn');
        if(saveBtn) saveBtn.classList.remove('d-none');
        
        const cancelBtn = document.getElementById('cancelEditBtn');
        if(cancelBtn) cancelBtn.classList.remove('d-none');
        
        document.querySelectorAll('.bulk-action-ui').forEach(el => el.classList.remove('d-none'));
    }
    
    const editToggleBtn = document.getElementById('editToggleBtn');
    if (editToggleBtn) editToggleBtn.addEventListener('click', setEditMode);
    
    const cancelEditBtn = document.getElementById('cancelEditBtn');
    if (cancelEditBtn) cancelEditBtn.addEventListener('click', setViewMode);
    
    const saveBtn = document.getElementById('saveBtn');
    if (saveBtn) {
        saveBtn.addEventListener('click', function() { 
            const form = document.getElementById('editUserForm');
            if (form.checkValidity()) {
                if (validateAccessRows(form, true)) form.submit();
            } else {
                form.reportValidity(); 
            }
        });
    }

    // Modal cleanup fix
    document.querySelectorAll('.modal').forEach(m => {
        m.addEventListener('hidden.coreui.modal', function() {
            if (document.querySelectorAll('.modal.show').length === 0) {
                document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
                document.body.classList.remove('modal-open');
                document.body.style.overflow = ''; 
                document.body.style.paddingRight = '';
            }
        });
    });

});