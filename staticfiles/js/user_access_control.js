document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Secure Search Filter Logic
    const searchInput = document.getElementById('accessSearch');
    const tableBody = document.getElementById('accessTableBody');
    const noResults = document.getElementById('noResults');

    if (searchInput && tableBody && noResults) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            const rows = tableBody.querySelectorAll('.access-row');
            let visibleCount = 0;
            
            rows.forEach(function (row) {
                const text = row.innerText.toLowerCase();
                if (text.includes(query)) {
                    // Use d-none class for secure display toggling
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

        // 2. Secure Event Delegation for Confirmation Buttons
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

    document.addEventListener('click', function(e) {
        const actionBtn = e.target.closest('.confirm-action-btn');
        if (actionBtn) {
            e.preventDefault(); // Always stop the default GET navigation
            const message = actionBtn.getAttribute('data-confirm-msg') || 'Are you sure?';
            if (confirm(message)) {
                postToUrl(actionBtn.href);
            }
        }
    });