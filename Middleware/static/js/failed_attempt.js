$(document).ready(function() {
    
    /* ── Initialize DataTables (Pagination Automatically Included) ── */
    var table = $('#failedLoginsTable').DataTable({
        "pageLength": 10,
        "ordering": false,
        "lengthChange": false,
        "info": true,
        "autoWidth": false,
        // The 'p' in 'lrtip' guarantees that the Next/Previous pagination renders!
        "dom": 'lrtip' 
    });

    /* ── Link your custom Search Bar to DataTables ── */
    $('#attemptSearch').on('keyup', function () {
        table.search(this.value).draw();
    });

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