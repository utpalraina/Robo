// Strategy Manager JavaScript

let strategies = {};
let currentStrategyId = null;
let isNewStrategy = false;

// DOM Elements
const strategyList = document.getElementById('strategy-list');
const editorTitle = document.getElementById('editor-title');
const editorContent = document.getElementById('editor-content');
const strategyForm = document.getElementById('strategy-form');
const saveBtn = document.getElementById('save-btn');
const deleteBtn = document.getElementById('delete-btn');
const testBtn = document.getElementById('test-btn');
const newStrategyBtn = document.getElementById('new-strategy-btn');
const testModal = document.getElementById('test-modal');
const closeModalBtn = document.getElementById('close-modal');
const runTestBtn = document.getElementById('run-test-btn');

// Form fields
const strategyIdInput = document.getElementById('strategy-id');
const strategyNameInput = document.getElementById('strategy-name');
const strategyDirectionSelect = document.getElementById('strategy-direction');
const strategyDescriptionInput = document.getElementById('strategy-description');
const strategyRulesTextarea = document.getElementById('strategy-rules');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    loadStrategies();
    setupEventListeners();
});

function setupEventListeners() {
    newStrategyBtn.addEventListener('click', createNewStrategy);
    saveBtn.addEventListener('click', saveStrategy);
    deleteBtn.addEventListener('click', deleteStrategy);
    testBtn.addEventListener('click', openTestModal);
    closeModalBtn.addEventListener('click', closeTestModal);
    runTestBtn.addEventListener('click', runQuickTest);

    // Close modal on outside click
    testModal.addEventListener('click', (e) => {
        if (e.target === testModal) closeTestModal();
    });

    // Enable save button on form change
    strategyForm.addEventListener('input', () => {
        saveBtn.disabled = false;
    });
}

async function loadStrategies() {
    try {
        const response = await fetch('/api/strategies');
        const data = await response.json();
        strategies = data.strategies || {};
        renderStrategyList();
    } catch (error) {
        console.error('Failed to load strategies:', error);
        showNotification('Failed to load strategies', 'error');
    }
}

function renderStrategyList() {
    strategyList.innerHTML = '';

    Object.entries(strategies).forEach(([id, strategy]) => {
        const item = document.createElement('div');
        item.className = `strategy-item ${currentStrategyId === id ? 'active' : ''}`;
        item.onclick = () => selectStrategy(id);

        const direction = (strategy.direction || 'BOTH').toLowerCase();

        item.innerHTML = `
            <div class="strategy-item-name">${strategy.name || id}</div>
            <div class="strategy-item-desc">${strategy.description || 'No description'}</div>
            <span class="strategy-item-direction ${direction}">${strategy.direction || 'BOTH'}</span>
        `;

        strategyList.appendChild(item);
    });
}

function selectStrategy(id) {
    currentStrategyId = id;
    isNewStrategy = false;

    const strategy = strategies[id];
    if (!strategy) return;

    // Update UI
    editorTitle.textContent = strategy.name || id;
    showForm();

    // Populate form
    strategyIdInput.value = id;
    strategyIdInput.disabled = true; // Can't change ID of existing strategy
    strategyNameInput.value = strategy.name || '';
    strategyDirectionSelect.value = strategy.direction || 'BOTH';
    strategyDescriptionInput.value = strategy.description || '';
    strategyRulesTextarea.value = strategy.rules || '';

    // Enable buttons
    saveBtn.disabled = true; // No changes yet
    deleteBtn.disabled = false;
    testBtn.disabled = false;

    // Update list selection
    renderStrategyList();
}

function createNewStrategy() {
    currentStrategyId = null;
    isNewStrategy = true;

    editorTitle.textContent = 'New Strategy';
    showForm();

    // Clear form
    strategyIdInput.value = '';
    strategyIdInput.disabled = false;
    strategyNameInput.value = '';
    strategyDirectionSelect.value = 'BOTH';
    strategyDescriptionInput.value = '';
    strategyRulesTextarea.value = '';

    // Update buttons
    saveBtn.disabled = false;
    deleteBtn.disabled = true;
    testBtn.disabled = true;

    // Clear selection
    renderStrategyList();
    strategyIdInput.focus();
}

function showForm() {
    editorContent.querySelector('.empty-state')?.remove();
    strategyForm.style.display = 'flex';
    editorContent.appendChild(strategyForm);
}

async function saveStrategy() {
    const id = strategyIdInput.value.trim();
    const name = strategyNameInput.value.trim();
    const direction = strategyDirectionSelect.value;
    const description = strategyDescriptionInput.value.trim();
    const rules = strategyRulesTextarea.value.trim();

    // Validation
    if (!id) {
        showNotification('Strategy ID is required', 'error');
        strategyIdInput.focus();
        return;
    }

    if (!/^[a-z0-9_]+$/.test(id)) {
        showNotification('Strategy ID must be lowercase letters, numbers, and underscores only', 'error');
        strategyIdInput.focus();
        return;
    }

    if (!name) {
        showNotification('Display name is required', 'error');
        strategyNameInput.focus();
        return;
    }

    if (!rules) {
        showNotification('Trading rules are required', 'error');
        strategyRulesTextarea.focus();
        return;
    }

    // Check for duplicate ID on new strategy
    if (isNewStrategy && strategies[id]) {
        showNotification('A strategy with this ID already exists', 'error');
        return;
    }

    const strategyData = {
        name,
        description,
        direction,
        rules
    };

    try {
        const response = await fetch(`/api/strategies/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(strategyData)
        });

        if (!response.ok) {
            throw new Error('Failed to save strategy');
        }

        // Update local data
        strategies[id] = strategyData;
        currentStrategyId = id;
        isNewStrategy = false;

        // Update UI
        strategyIdInput.disabled = true;
        saveBtn.disabled = true;
        deleteBtn.disabled = false;
        testBtn.disabled = false;
        editorTitle.textContent = name;

        renderStrategyList();
        showNotification('Strategy saved successfully', 'success');
    } catch (error) {
        console.error('Failed to save strategy:', error);
        showNotification('Failed to save strategy', 'error');
    }
}

async function deleteStrategy() {
    if (!currentStrategyId) return;

    const strategyName = strategies[currentStrategyId]?.name || currentStrategyId;

    if (!confirm(`Are you sure you want to delete "${strategyName}"?`)) {
        return;
    }

    try {
        const response = await fetch(`/api/strategies/${currentStrategyId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete strategy');
        }

        // Remove from local data
        delete strategies[currentStrategyId];
        currentStrategyId = null;

        // Reset UI
        editorTitle.textContent = 'Select a Strategy';
        strategyForm.style.display = 'none';
        editorContent.innerHTML = `
            <div class="empty-state">
                <p>Select a strategy from the list or create a new one to get started.</p>
            </div>
        `;

        saveBtn.disabled = true;
        deleteBtn.disabled = true;
        testBtn.disabled = true;

        renderStrategyList();
        showNotification('Strategy deleted', 'success');
    } catch (error) {
        console.error('Failed to delete strategy:', error);
        showNotification('Failed to delete strategy', 'error');
    }
}

function openTestModal() {
    if (!currentStrategyId) return;

    document.getElementById('test-strategy-name').textContent =
        strategies[currentStrategyId]?.name || currentStrategyId;

    // Set default date to 2 months ago
    const defaultDate = new Date();
    defaultDate.setMonth(defaultDate.getMonth() - 2);
    document.getElementById('test-start-date').value = defaultDate.toISOString().split('T')[0];

    // Reset results
    document.getElementById('test-results').style.display = 'none';
    document.getElementById('test-loading').style.display = 'none';

    testModal.style.display = 'flex';
}

function closeTestModal() {
    testModal.style.display = 'none';
}

async function runQuickTest() {
    const days = document.getElementById('test-days').value || 5;
    const startDate = document.getElementById('test-start-date').value;

    if (!startDate) {
        showNotification('Please select a start date', 'error');
        return;
    }

    // Show loading
    document.getElementById('test-results').style.display = 'none';
    document.getElementById('test-loading').style.display = 'flex';
    runTestBtn.disabled = true;

    try {
        const response = await fetch('/api/backtest', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                strategy: currentStrategyId,
                days: parseInt(days),
                start_date: startDate,
                trades_per_day: 3,
                capital: 2000,
                risk_percent: 0.5
            })
        });

        if (!response.ok) {
            throw new Error('Backtest failed');
        }

        const results = await response.json();
        displayTestResults(results);
    } catch (error) {
        console.error('Backtest failed:', error);
        showNotification('Backtest failed. Check console for details.', 'error');
    } finally {
        document.getElementById('test-loading').style.display = 'none';
        runTestBtn.disabled = false;
    }
}

function displayTestResults(results) {
    const grid = document.getElementById('results-grid');

    const totalR = results.total_r || 0;
    const roi = results.roi || 0;

    grid.innerHTML = `
        <div class="result-item">
            <div class="label">Trades</div>
            <div class="value">${results.trades || 0}</div>
        </div>
        <div class="result-item">
            <div class="label">Wins</div>
            <div class="value">${results.wins || 0}</div>
        </div>
        <div class="result-item">
            <div class="label">Losses</div>
            <div class="value">${results.losses || 0}</div>
        </div>
        <div class="result-item">
            <div class="label">Win Rate</div>
            <div class="value">${(results.win_rate || 0).toFixed(1)}%</div>
        </div>
        <div class="result-item">
            <div class="label">Total R</div>
            <div class="value ${totalR >= 0 ? 'positive' : 'negative'}">${totalR >= 0 ? '+' : ''}${totalR.toFixed(1)}R</div>
        </div>
        <div class="result-item">
            <div class="label">ROI</div>
            <div class="value ${roi >= 0 ? 'positive' : 'negative'}">${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%</div>
        </div>
    `;

    document.getElementById('test-results').style.display = 'block';
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 600;
        z-index: 2000;
        animation: slideIn 0.3s ease;
        ${type === 'error' ? 'background: #ef4444;' : 'background: #10b981;'}
    `;

    document.body.appendChild(notification);

    // Remove after 3 seconds
    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
    @keyframes slideOut {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);
