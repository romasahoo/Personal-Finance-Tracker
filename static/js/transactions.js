/* ===========================
   Transactions Page Logic
   =========================== */

let allTransactions = [];

// --- Sort State ---
let currentSortColumn = null;   // 'date' | 'description' | 'category' | 'amount' | null
let currentSortDirection = null; // 'asc' | 'desc' | null

async function loadTransactions(filters = {}) {
    try {
        const params = new URLSearchParams();
        if (filters.start_date) params.set('start_date', filters.start_date);
        if (filters.end_date) params.set('end_date', filters.end_date);
        if (filters.category && filters.category !== 'all') params.set('category', filters.category);

        const queryStr = params.toString() ? `?${params.toString()}` : '';
        allTransactions = await apiFetch(`/transactions${queryStr}`);

        // Client-side search filter
        if (filters.search) {
            const search = filters.search.toLowerCase();
            allTransactions = allTransactions.filter(tx =>
                (tx.description || '').toLowerCase().includes(search)
            );
        }

        applySortAndRender();
    } catch (err) {
        showToast('Failed to load transactions', 'error');
    }
}

function renderTransactions(transactions) {
    const tbody = document.getElementById('tx-tbody');
    const badge = document.getElementById('tx-total-badge');
    badge.textContent = `(${transactions.length} records)`;

    if (!transactions.length) {
        tbody.innerHTML = `
            <tr><td colspan="5">
                <div class="empty-state">
                    <div class="icon">📭</div>
                    <p>No transactions found</p>
                    <a href="/add" class="btn btn-primary">Add Transaction</a>
                </div>
            </td></tr>`;
        return;
    }

    tbody.innerHTML = transactions.map(tx => `
        <tr data-id="${tx.id}">
            <td>${formatDateDisplay(tx.date)}</td>
            <td>${tx.description || '—'}</td>
            <td><span class="badge ${tx.category.toLowerCase()}">${tx.category}</span></td>
            <td class="amount-${tx.category.toLowerCase()}">${tx.category === 'Income' ? '+' : '-'}${formatCurrency(tx.amount)}</td>
            <td>
                <div class="action-btns">
                    <button class="btn-icon edit" onclick="openEditModal(${tx.id})" title="Edit" aria-label="Edit transaction">✏️</button>
                    <button class="btn-icon delete" onclick="openDeleteModal(${tx.id})" title="Delete" aria-label="Delete transaction">🗑️</button>
                </div>
            </td>
        </tr>
    `).join('');
}

// --- Sorting ---
function applySortAndRender() {
    if (!currentSortColumn || !currentSortDirection) {
        renderTransactions(allTransactions);
        return;
    }

    const sorted = [...allTransactions];
    const dir = currentSortDirection === 'asc' ? 1 : -1;
    const col = currentSortColumn;

    sorted.sort((a, b) => {
        let valA, valB;

        switch (col) {
            case 'date':
                // DD-MM-YYYY → comparable YYYYMMDD
                valA = a.date.split('-').reverse().join('');
                valB = b.date.split('-').reverse().join('');
                return valA < valB ? -1 * dir : valA > valB ? 1 * dir : 0;
            case 'description':
                valA = (a.description || '').toLowerCase();
                valB = (b.description || '').toLowerCase();
                return valA < valB ? -1 * dir : valA > valB ? 1 * dir : 0;
            case 'category':
                valA = a.category.toLowerCase();
                valB = b.category.toLowerCase();
                return valA < valB ? -1 * dir : valA > valB ? 1 * dir : 0;
            case 'amount':
                return (a.amount - b.amount) * dir;
            default:
                return 0;
        }
    });

    renderTransactions(sorted);
}

function handleSortClick(column) {
    if (currentSortColumn === column) {
        // Cycle: asc → desc → none
        if (currentSortDirection === 'asc') {
            currentSortDirection = 'desc';
        } else if (currentSortDirection === 'desc') {
            currentSortColumn = null;
            currentSortDirection = null;
        }
    } else {
        currentSortColumn = column;
        currentSortDirection = 'asc';
    }

    updateSortIndicators();
    applySortAndRender();
}

function updateSortIndicators() {
    document.querySelectorAll('.data-table thead th.sortable').forEach(th => {
        const col = th.dataset.sort;
        const arrow = th.querySelector('.sort-arrow');

        th.classList.remove('sort-asc', 'sort-desc');

        if (col === currentSortColumn && currentSortDirection) {
            th.classList.add(currentSortDirection === 'asc' ? 'sort-asc' : 'sort-desc');
            arrow.textContent = currentSortDirection === 'asc' ? '▲' : '▼';
        } else {
            arrow.textContent = '▲';
        }
    });
}

function resetSort() {
    currentSortColumn = null;
    currentSortDirection = null;
    updateSortIndicators();
}

// --- Date format conversion helpers ---
function ddmmyyyyToIso(dateStr) {
    // DD-MM-YYYY -> YYYY-MM-DD for <input type="date">
    const parts = dateStr.split('-');
    if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`;
    return dateStr;
}

function isoToDdmmyyyy(isoStr) {
    // YYYY-MM-DD -> DD-MM-YYYY for API
    const parts = isoStr.split('-');
    if (parts.length === 3) return `${parts[2]}-${parts[1]}-${parts[0]}`;
    return isoStr;
}

// --- Edit Modal ---
function openEditModal(id) {
    const tx = allTransactions.find(t => t.id === id);
    if (!tx) return;

    document.getElementById('edit-id').value = tx.id;
    document.getElementById('edit-date').value = ddmmyyyyToIso(tx.date);
    document.getElementById('edit-amount').value = tx.amount;
    document.getElementById('edit-category').value = tx.category;
    document.getElementById('edit-description').value = tx.description || '';

    document.getElementById('edit-modal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('edit-modal').classList.remove('active');
}

async function saveEdit() {
    const id = document.getElementById('edit-id').value;
    const dateIso = document.getElementById('edit-date').value;
    const amount = parseFloat(document.getElementById('edit-amount').value);
    const category = document.getElementById('edit-category').value;
    const description = document.getElementById('edit-description').value;

    if (!dateIso || !amount || amount <= 0) {
        showToast('Please fill in all required fields', 'error');
        return;
    }

    try {
        await apiFetch(`/transactions/${id}`, {
            method: 'PUT',
            body: JSON.stringify({
                date: isoToDdmmyyyy(dateIso),
                amount,
                category,
                description,
            }),
        });
        showToast('Transaction updated successfully', 'success');
        closeEditModal();
        loadTransactions(getCurrentFilters());
    } catch (err) {
        showToast(`Update failed: ${err.message}`, 'error');
    }
}

// --- Delete Modal ---
function openDeleteModal(id) {
    const tx = allTransactions.find(t => t.id === id);
    if (!tx) return;

    document.getElementById('delete-id').value = tx.id;
    document.getElementById('delete-details').innerHTML = `
        <div style="display: grid; gap: 6px; font-size: 0.88rem;">
            <div><strong style="color: var(--text-muted);">Date:</strong> ${formatDateDisplay(tx.date)}</div>
            <div><strong style="color: var(--text-muted);">Amount:</strong> <span class="amount-${tx.category.toLowerCase()}">${formatCurrency(tx.amount)}</span></div>
            <div><strong style="color: var(--text-muted);">Category:</strong> ${tx.category}</div>
            <div><strong style="color: var(--text-muted);">Description:</strong> ${tx.description || '—'}</div>
        </div>
    `;
    document.getElementById('delete-modal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('delete-modal').classList.remove('active');
}

async function confirmDelete() {
    const id = document.getElementById('delete-id').value;

    try {
        await apiFetch(`/transactions/${id}`, { method: 'DELETE' });
        showToast('Transaction deleted', 'success');
        closeDeleteModal();
        loadTransactions(getCurrentFilters());
    } catch (err) {
        showToast(`Delete failed: ${err.message}`, 'error');
    }
}

// --- Filters ---
function getCurrentFilters() {
    const startIso = document.getElementById('filter-start').value;
    const endIso = document.getElementById('filter-end').value;
    return {
        start_date: startIso ? isoToDdmmyyyy(startIso) : '',
        end_date: endIso ? isoToDdmmyyyy(endIso) : '',
        category: document.getElementById('filter-category').value,
        search: document.getElementById('filter-search').value,
    };
}

function clearFilters() {
    document.getElementById('filter-start').value = '';
    document.getElementById('filter-end').value = '';
    document.getElementById('filter-category').value = 'all';
    document.getElementById('filter-search').value = '';
    resetSort();
    loadTransactions();
}

// --- Event Listeners ---
document.addEventListener('DOMContentLoaded', () => {
    loadTransactions();

    document.getElementById('filter-btn').addEventListener('click', () => {
        resetSort();
        loadTransactions(getCurrentFilters());
    });

    document.getElementById('clear-btn').addEventListener('click', clearFilters);

    // Sort column click handlers
    document.querySelectorAll('.data-table thead th.sortable').forEach(th => {
        th.addEventListener('click', () => handleSortClick(th.dataset.sort));
    });

    // Edit modal
    document.getElementById('edit-cancel-btn').addEventListener('click', closeEditModal);
    document.getElementById('edit-save-btn').addEventListener('click', saveEdit);

    // Delete modal
    document.getElementById('delete-cancel-btn').addEventListener('click', closeDeleteModal);
    document.getElementById('delete-confirm-btn').addEventListener('click', confirmDelete);

    // Close modals on overlay click
    document.getElementById('edit-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeEditModal();
    });
    document.getElementById('delete-modal').addEventListener('click', (e) => {
        if (e.target === e.currentTarget) closeDeleteModal();
    });

    // Keyboard shortcut: Escape to close modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeEditModal();
            closeDeleteModal();
        }
    });
});
