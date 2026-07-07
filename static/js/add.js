/* ===========================
   Add Transaction Page Logic
   =========================== */

function initAddForm() {
    const form = document.getElementById('add-form');
    const successState = document.getElementById('success-state');
    const dateInput = document.getElementById('add-date');

    // Default date to today
    const today = new Date();
    dateInput.value = today.toISOString().split('T')[0];

    // Form submission
    form.addEventListener('submit', async (e) => {
        e.preventDefault();

        const dateIso = dateInput.value;
        const amount = parseFloat(document.getElementById('add-amount').value);
        const category = document.getElementById('add-category').value;
        const description = document.getElementById('add-description').value.trim();

        // Validation
        if (!dateIso) {
            showToast('Please select a date', 'error');
            dateInput.focus();
            return;
        }

        if (!amount || amount <= 0) {
            showToast('Please enter a valid amount', 'error');
            document.getElementById('add-amount').focus();
            return;
        }

        if (!category) {
            showToast('Please select a category', 'error');
            document.getElementById('add-category').focus();
            return;
        }

        // Convert date from YYYY-MM-DD to DD-MM-YYYY
        const parts = dateIso.split('-');
        const dateDdMmYyyy = `${parts[2]}-${parts[1]}-${parts[0]}`;

        const submitBtn = document.getElementById('submit-btn');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Adding...';

        try {
            await apiFetch('/transactions', {
                method: 'POST',
                body: JSON.stringify({
                    date: dateDdMmYyyy,
                    amount,
                    category,
                    description,
                }),
            });

            // Show success state
            form.style.display = 'none';
            successState.style.display = 'block';
            document.getElementById('success-details').textContent =
                `${category} of ${formatCurrency(amount)} on ${new Date(dateIso).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}`;

            showToast('Transaction added successfully!', 'success');
        } catch (err) {
            showToast(`Failed to add transaction: ${err.message}`, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = '➕ Add Transaction';
        }
    });

    // Reset button
    document.getElementById('reset-btn').addEventListener('click', () => {
        form.reset();
        dateInput.value = today.toISOString().split('T')[0];
    });

    // Add another button
    document.getElementById('add-another-btn').addEventListener('click', () => {
        form.style.display = 'block';
        successState.style.display = 'none';
        form.reset();
        dateInput.value = today.toISOString().split('T')[0];
    });
}

document.addEventListener('DOMContentLoaded', initAddForm);
