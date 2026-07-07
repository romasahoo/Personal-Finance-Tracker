/* ===========================
   Dashboard Page Logic
   =========================== */

let lineChart = null;
let doughnutChart = null;

// Chart.js global defaults for dark theme
Chart.defaults.color = '#9d9db8';
Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.05)';
Chart.defaults.font.family = "'Inter', sans-serif";

async function loadDashboard() {
    try {
        const [summary, chartData, transactions] = await Promise.all([
            apiFetch('/summary'),
            apiFetch('/chart-data'),
            apiFetch('/transactions'),
        ]);

        renderSummaryCards(summary);
        renderLineChart(chartData.line_chart);
        renderDoughnutChart(chartData.doughnut_chart);
        renderRecentTransactions(transactions.slice(0, 5));
    } catch (err) {
        showToast('Failed to load dashboard data', 'error');
    }
}

function renderSummaryCards(summary) {
    animateCounter(document.getElementById('total-income'), summary.total_income, '$');
    animateCounter(document.getElementById('total-expense'), summary.total_expense, '$');
    animateCounter(document.getElementById('net-savings'), summary.net_savings, '$');
    animateCounter(document.getElementById('tx-count'), summary.transaction_count, '');
}

function renderLineChart(data) {
    const ctx = document.getElementById('lineChart').getContext('2d');

    if (lineChart) lineChart.destroy();

    const displayLabels = data.labels.map(d => {
        const parts = d.split('-');
        if (parts.length === 3) {
            return `${parts[0]}/${parts[1]}`;
        }
        return d;
    });

    lineChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: displayLabels,
            datasets: [
                {
                    label: 'Income',
                    data: data.income,
                    borderColor: '#06d6a0',
                    backgroundColor: 'rgba(6, 214, 160, 0.1)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#06d6a0',
                    pointBorderColor: '#06d6a0',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                },
                {
                    label: 'Expense',
                    data: data.expense,
                    borderColor: '#ef476f',
                    backgroundColor: 'rgba(239, 71, 111, 0.1)',
                    borderWidth: 2.5,
                    fill: true,
                    tension: 0.4,
                    pointBackgroundColor: '#ef476f',
                    pointBorderColor: '#ef476f',
                    pointRadius: 4,
                    pointHoverRadius: 6,
                },
            ],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
                mode: 'index',
                intersect: false,
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: {
                        usePointStyle: true,
                        padding: 20,
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 46, 0.9)',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    titleFont: { weight: '600' },
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${formatCurrency(ctx.parsed.y)}`,
                    },
                },
            },
            scales: {
                x: {
                    grid: { display: false },
                    ticks: { maxTicksLimit: 12 },
                },
                y: {
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    ticks: {
                        callback: (val) => '$' + val,
                    },
                },
            },
        },
    });
}

function renderDoughnutChart(data) {
    const ctx = document.getElementById('doughnutChart').getContext('2d');

    if (doughnutChart) doughnutChart.destroy();

    if (!data.labels.length) {
        ctx.canvas.parentElement.innerHTML = '<div class="empty-state"><div class="icon">🍩</div><p>No expense data yet</p></div>';
        return;
    }

    const colors = [
        '#ef476f', '#ffd166', '#06d6a0', '#118ab2', '#7c3aed',
        '#a78bfa', '#f472b6', '#fb923c', '#34d399', '#60a5fa',
    ];

    doughnutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.data,
                backgroundColor: colors.slice(0, data.labels.length),
                borderColor: '#0a0a1a',
                borderWidth: 3,
                hoverBorderColor: '#0a0a1a',
                hoverOffset: 8,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '65%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 14,
                        font: { size: 11 },
                    },
                },
                tooltip: {
                    backgroundColor: 'rgba(15, 15, 46, 0.9)',
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 1,
                    padding: 12,
                    callbacks: {
                        label: (ctx) => {
                            const total = ctx.dataset.data.reduce((a, b) => a + b, 0);
                            const pct = ((ctx.parsed / total) * 100).toFixed(1);
                            return `${ctx.label}: ${formatCurrency(ctx.parsed)} (${pct}%)`;
                        },
                    },
                },
            },
        },
    });
}

function renderRecentTransactions(transactions) {
    const tbody = document.getElementById('recent-tbody');

    if (!transactions.length) {
        tbody.innerHTML = `
            <tr><td colspan="4">
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <p>No transactions yet. <a href="/add" style="color: var(--accent-purple-light)">Add your first one!</a></p>
                </div>
            </td></tr>`;
        return;
    }

    tbody.innerHTML = transactions.map(tx => `
        <tr>
            <td>${formatDateDisplay(tx.date)}</td>
            <td>${tx.description || '—'}</td>
            <td><span class="badge ${tx.category.toLowerCase()}">${tx.category}</span></td>
            <td class="amount-${tx.category.toLowerCase()}">${tx.category === 'Income' ? '+' : '-'}${formatCurrency(tx.amount)}</td>
        </tr>
    `).join('');
}

// Initialize
document.addEventListener('DOMContentLoaded', loadDashboard);
