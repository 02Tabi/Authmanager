document.addEventListener('DOMContentLoaded', function() {
    
    // Safely parse JSON data injected from Django json_script tags
    const getJsonData = (elementId) => {
        const el = document.getElementById(elementId);
        if (!el) return [];
        try {
            return JSON.parse(el.textContent);
        } catch (e) {
            console.error('Error parsing JSON for ' + elementId, e);
            return [];
        }
    };

    const months = getJsonData('monthsData');
    const loginsData = getJsonData('loginsData');
    const activeUsersData = getJsonData('activeUsersData');
    const newUsersData = getJsonData('newUsersData');

    // ── Main activity chart ──
    const mainCtx = document.getElementById('mainChart');
    if (mainCtx) {
        new Chart(mainCtx, {
            type: 'line',
            data: {
                labels: months.length ? months : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
                datasets: [
                    {
                        label: 'Logins',
                        backgroundColor: 'rgba(50, 168, 204, 0.15)',
                        borderColor: 'rgba(50, 168, 204, 0.8)',
                        pointHoverBackgroundColor: '#fff',
                        borderWidth: 2,
                        data: loginsData.length ? loginsData : [0,0,0,0,0,0,0.9],
                        fill: true,
                    },
                    {
                        label: 'Active Users',
                        backgroundColor: 'transparent',
                        borderColor: 'rgba(42, 194, 131, 0.8)',
                        pointHoverBackgroundColor: '#fff',
                        borderWidth: 2,
                        data: activeUsersData.length ? activeUsersData : [0,0,0,0,0,0,1.9],
                        fill: false,
                    },
                    {
                        label: 'New Users',
                        backgroundColor: 'transparent',
                        borderColor: 'rgba(229, 83, 83, 0.8)',
                        pointHoverBackgroundColor: '#fff',
                        borderWidth: 2,
                        borderDash: [8, 5],
                        data: newUsersData.length ? newUsersData : [0,0,0,0,0,0,0],
                        fill: false,
                    }
                ]
            },
            options: {
                maintainAspectRatio: false,
                responsive: true,
                plugins: { 
                    legend: { 
                        display: true,
                        position: 'bottom',
                        labels: { padding: 20, usePointStyle: true }
                    } 
                },
                scales: {
                    x: { grid: { display: false } },
                    y: { min: 0, beginAtZero: true }
                },
                elements: {
                    line: { tension: 0.4 },
                    point: { radius: 0, hitRadius: 10, hoverRadius: 4 }
                }
            }
        });
    }

    // ── Sparkline cards ──
    const sparkData = [
        { id: 'cardChart1', data: loginsData },
        { id: 'cardChart2', data: activeUsersData },
        { id: 'cardChart3', data: newUsersData },
        { id: 'cardChart4', data: loginsData }
    ];

    sparkData.forEach(function(cfg) {
        const canvasEl = document.getElementById(cfg.id);
        if (canvasEl) {
            new Chart(canvasEl, {
                type: 'line',
                data: {
                    labels: months.length ? months : ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul'],
                    datasets: [{
                        backgroundColor: 'rgba(255,255,255,0.2)',
                        borderColor: 'rgba(255,255,255,0.6)',
                        data: cfg.data.length ? cfg.data : [0,0,0,0,0,0,40],
                        fill: true,
                    }]
                },
                options: {
                    maintainAspectRatio: false,
                    responsive: true,
                    plugins: { legend: { display: false } },
                    scales: { x: { display: false }, y: { display: false } },
                    elements: {
                        line: { tension: 0.4, borderWidth: 2 },
                        point: { radius: 0 }
                    }
                }
            });
        }
    });

    // ── Secure Progress Bar Width Injector ──
    const progressBars = document.querySelectorAll('.progress-bar[data-progress]');
    progressBars.forEach(function(bar) {
        const progressValue = bar.getAttribute('data-progress');
        if (progressValue) {
            const numericVal = Math.min(parseFloat(progressValue) || 0, 100);
            bar.style.width = numericVal + '%';
        }
    });

    // ── Secure Refresh Button Handler ──
    const refreshBtn = document.getElementById('refreshDashboardBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', function() {
            window.location.reload();
        });
    }
});