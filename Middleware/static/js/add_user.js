document.addEventListener('DOMContentLoaded', function() {

    // 1. Handle Adding New App Rows
    const addAppRowBtn = document.getElementById('addAppRowBtn');
    if (addAppRowBtn) {
        addAppRowBtn.addEventListener('click', function() {
            const container = document.getElementById('appRowsContainer');
            const firstRow = container.querySelector('.app-row');
            const newRow = firstRow.cloneNode(true);
            
            // Reset values for the new row
            newRow.querySelectorAll('select').forEach(select => select.value = '');
            
            // Enable the delete button for the newly cloned row
            const deleteBtn = newRow.querySelector('.remove-app-row-btn');
            if (deleteBtn) {
                deleteBtn.disabled = false;
            }
            
            container.appendChild(newRow);
            updateDeleteButtons();
        });
    }

    // 2. Handle Removing App Rows via Event Delegation
    document.addEventListener('click', function(e) {
        const removeBtn = e.target.closest('.remove-app-row-btn');
        if (removeBtn) {
            const container = document.getElementById('appRowsContainer');
            if (container.children.length > 1) {
                removeBtn.closest('.app-row').remove();
            }
            updateDeleteButtons();
        }
    });

    // 3. Helper to correctly toggle disabled state on the trash buttons
    function updateDeleteButtons() {
        const rows = document.querySelectorAll('.app-row');
        if (rows.length > 0) {
            const firstRowBtn = rows[0].querySelector('.remove-app-row-btn');
            // Disable delete button if there's only one row left
            if (firstRowBtn) {
                firstRowBtn.disabled = (rows.length === 1);
            }
        }
    }

});