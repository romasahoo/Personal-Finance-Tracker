/* ===========================================
   Shared Utilities — Sidebar, Navigation, API
   =========================================== */

const API_BASE = '/api';

// --- API Helper ---
async function apiFetch(endpoint, options = {}) {
    const url = `${API_BASE}${endpoint}`;
    const defaults = {
        headers: { 'Content-Type': 'application/json' },
    };
    const config = { ...defaults, ...options };

    try {
        const response = await fetch(url, config);
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(error.detail || `HTTP ${response.status}`);
        }
        return response.json();
    } catch (err) {
        console.error(`API Error [${endpoint}]:`, err);
        throw err;
    }
}

// --- Toast Notifications ---
function showToast(message, type = 'success') {
    let container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const icons = { success: '✓', error: '✕', info: 'ℹ' };
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.classList.add('fade-out');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// --- Format Currency ---
function formatCurrency(amount) {
    return new Intl.NumberFormat('en-IE', { // Using en-IE for standard € formatting with period decimals
        style: 'currency',
        currency: 'EUR',
        minimumFractionDigits: 2,
    }).format(amount);
}

// --- Format Date for Display ---
function formatDateDisplay(dateStr) {
    // Input: DD-MM-YYYY, Output: human-friendly
    const parts = dateStr.split('-');
    if (parts.length !== 3) return dateStr;
    const [dd, mm, yyyy] = parts;
    const date = new Date(`${yyyy}-${mm}-${dd}`);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
}

// --- Sidebar Active State ---
function initSidebar() {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => {
        const href = item.getAttribute('href');
        if (href === currentPath || (href === '/' && currentPath === '/')) {
            item.classList.add('active');
        }
    });

    // Mobile toggle
    const toggle = document.querySelector('.mobile-toggle');
    const sidebar = document.querySelector('.sidebar');
    if (toggle && sidebar) {
        toggle.addEventListener('click', () => {
            sidebar.classList.toggle('open');
        });

        // Close sidebar on clicking outside (mobile)
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('open') && !sidebar.contains(e.target) && !toggle.contains(e.target)) {
                sidebar.classList.remove('open');
            }
        });
    }
}

// --- Animated Counter ---
function animateCounter(element, target, prefix = '€', duration = 800) {
    const start = 0;
    const startTime = performance.now();

    function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        // Ease out quad
        const eased = 1 - (1 - progress) * (1 - progress);
        const current = start + (target - start) * eased;

        if (prefix === '€' || prefix === '$') {
            element.textContent = formatCurrency(current);
        } else {
            element.textContent = prefix + Math.round(current).toLocaleString();
        }

        if (progress < 1) {
            requestAnimationFrame(update);
        }
    }

    requestAnimationFrame(update);
}

// --- Initialize on DOM Ready ---
document.addEventListener('DOMContentLoaded', initSidebar);
