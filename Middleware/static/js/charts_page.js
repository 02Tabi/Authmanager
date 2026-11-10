document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Line Chart Initialization
    const lineCtx = document.getElementById('chartsPageLine');
    if (lineCtx) {
        new Chart(lineCtx, {
            type: 'line',
            data: {
                labels: ['January', 'February', 'March', 'April', 'May', 'June', 'July'],
                datasets: [{
                    label: 'Successful Logins',
                    backgroundColor: 'rgba(46, 184, 92, 0.2)',
                    borderColor: '#2eb85c',
                    pointBackgroundColor: '#2eb85c',
                    data: [45, 65, 80, 120, 150, 190, 240],
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: true } }
            }
        });
    }

    // 2. Bar Chart Initialization
    const barCtx = document.getElementById('chartsPageBar');
    if (barCtx) {
        new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: ['Core Banking', 'Loan Portal', 'ATM Network', 'Mobile App', 'USSD Gateway'],
                datasets: [{
                    label: 'Requests',
                    backgroundColor: '#321fdb',
                    data: [300, 200, 150, 450, 280]
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { display: false } }
            }
        });
    }

    // 3. Doughnut Chart Initialization
    const doughnutCtx = document.getElementById('chartsPageDoughnut');
    if (doughnutCtx) {
        new Chart(doughnutCtx, {
            type: 'doughnut',
            data: {
                labels: ['Staff', 'Manager', 'Admin'],
                datasets: [{
                    backgroundColor: ['#39f', '#f9b115', '#2eb85c', '#e55353'],
                    data: [60, 20, 15, 5]
                }]
            },
            options: {
                maintainAspectRatio: false,
                plugins: { legend: { position: 'bottom' } }
            }
        });
    }

});