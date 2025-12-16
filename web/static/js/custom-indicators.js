/**
 * Custom Indicators with Pine Script Support
 * Handles Pine Script editor, custom indicator management, and chart integration
 */

// Default Pine Script template
const DEFAULT_PINE_TEMPLATE = `//@version=5
indicator("My Indicator", overlay=true)

// Input parameters
length = input.int(14, "Length", minval=1)

// Calculate indicator
smaValue = ta.sma(close, length)

// Plot
plot(smaValue, "SMA", color=color.blue, linewidth=2)
`;

// State management for custom indicators
const customIndicatorState = {
    editor: null,
    currentIndicatorId: null,
    isEditing: false,
    customIndicators: [],
    templates: [],
    activeCustomIndicators: []
};

// Initialize custom indicators module
function initCustomIndicators() {
    console.log('Initializing custom indicators module...');
    setupIndicatorTabs();
    setupPineEditor();
    setupPineEditorModal();
    console.log('Custom indicators module initialized');
}

// Setup indicator modal tabs
function setupIndicatorTabs() {
    const tabs = document.querySelectorAll('.indicator-tab');
    const tabContents = document.querySelectorAll('.indicator-tab-content');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            // Remove active from all tabs
            tabs.forEach(t => t.classList.remove('active'));
            tabContents.forEach(tc => tc.classList.remove('active'));

            // Activate clicked tab
            tab.classList.add('active');
            const tabId = tab.dataset.tab + 'Tab';
            const content = document.getElementById(tabId);
            if (content) {
                content.classList.add('active');
            }

            // Load data for specific tabs
            if (tab.dataset.tab === 'custom') {
                loadCustomIndicators();
            } else if (tab.dataset.tab === 'templates') {
                loadTemplates();
            } else if (tab.dataset.tab === 'python') {
                loadPythonIndicators();
            }
        });
    });
}

// Setup Pine Script Editor (CodeMirror)
function setupPineEditor() {
    const editorContainer = document.getElementById('pineCodeEditor');
    if (!editorContainer || !window.CodeMirror) {
        console.warn('CodeMirror not loaded or editor container not found');
        return;
    }

    // Create CodeMirror editor with Pine Script-like syntax highlighting
    customIndicatorState.editor = CodeMirror(editorContainer, {
        value: DEFAULT_PINE_TEMPLATE,
        mode: 'javascript', // Using JS mode as base for similar syntax
        theme: 'dracula',
        lineNumbers: true,
        lineWrapping: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        autoCloseBrackets: true,
        matchBrackets: true,
        extraKeys: {
            'Ctrl-Enter': validatePineScript,
            'Cmd-Enter': validatePineScript,
            'Ctrl-S': savePineIndicator,
            'Cmd-S': savePineIndicator
        }
    });

    // Auto-validate on change (debounced)
    let validateTimeout;
    customIndicatorState.editor.on('change', () => {
        clearTimeout(validateTimeout);
        validateTimeout = setTimeout(() => {
            validatePineScript(true); // Silent validation
        }, 1000);
    });
}

// Setup Pine Editor Modal
function setupPineEditorModal() {
    // Open editor button
    const pineEditorBtn = document.getElementById('pineEditorBtn');
    console.log('Pine Editor button found:', pineEditorBtn);
    if (pineEditorBtn) {
        pineEditorBtn.addEventListener('click', () => {
            console.log('Pine Editor button clicked');
            openPineEditor();
        });
        console.log('Pine Editor click handler attached');
    } else {
        console.error('Pine Editor button not found in DOM');
    }

    // Create indicator button
    const createBtn = document.getElementById('createIndicatorBtn');
    if (createBtn) {
        createBtn.addEventListener('click', () => openPineEditor());
    }

    // Close editor
    const closeBtn = document.getElementById('closePineEditor');
    if (closeBtn) {
        closeBtn.addEventListener('click', closePineEditor);
    }

    // Cancel button
    const cancelBtn = document.getElementById('cancelPineEditor');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closePineEditor);
    }

    // Save button
    const saveBtn = document.getElementById('savePineIndicator');
    if (saveBtn) {
        saveBtn.addEventListener('click', savePineIndicator);
    }

    // Validate button
    const validateBtn = document.getElementById('validatePineBtn');
    if (validateBtn) {
        validateBtn.addEventListener('click', () => validatePineScript(false));
    }

    // Preview button
    const previewBtn = document.getElementById('previewPineBtn');
    if (previewBtn) {
        previewBtn.addEventListener('click', previewIndicator);
    }

    // Close on overlay click
    const modal = document.getElementById('pineEditorModal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closePineEditor();
            }
        });
    }

    // Close indicators modal on overlay click
    const indicatorsModal = document.getElementById('indicatorsModal');
    if (indicatorsModal) {
        indicatorsModal.addEventListener('click', (e) => {
            if (e.target === indicatorsModal) {
                indicatorsModal.classList.remove('show');
            }
        });
    }
}

// Open Pine Script Editor
function openPineEditor(indicatorId = null) {
    console.log('openPineEditor called with indicatorId:', indicatorId);
    const modal = document.getElementById('pineEditorModal');
    const title = document.getElementById('pineEditorTitle');

    console.log('Pine Editor modal element:', modal);

    if (!modal) {
        console.error('Pine Editor modal not found');
        return;
    }

    customIndicatorState.currentIndicatorId = indicatorId;
    customIndicatorState.isEditing = !!indicatorId;

    if (indicatorId) {
        // Editing existing indicator
        title.textContent = 'Edit Indicator';
        loadIndicatorForEdit(indicatorId);
    } else {
        // Creating new indicator
        title.textContent = 'Create Custom Indicator';
        resetEditorForm();
    }

    console.log('Adding show class to modal');
    modal.classList.add('show');
    console.log('Modal classes after:', modal.classList.toString());

    // Refresh CodeMirror after modal is visible
    setTimeout(() => {
        if (customIndicatorState.editor) {
            customIndicatorState.editor.refresh();
        }
    }, 100);
}

// Close Pine Script Editor
function closePineEditor() {
    const modal = document.getElementById('pineEditorModal');
    if (modal) {
        modal.classList.remove('show');
    }
    customIndicatorState.currentIndicatorId = null;
    customIndicatorState.isEditing = false;
}

// Reset editor form
function resetEditorForm() {
    document.getElementById('indicatorName').value = '';
    document.getElementById('indicatorShortName').value = '';
    document.getElementById('indicatorDescription').value = '';
    document.getElementById('indicatorOverlay').checked = true;

    if (customIndicatorState.editor) {
        customIndicatorState.editor.setValue(DEFAULT_PINE_TEMPLATE);
    }

    clearValidationStatus();
}

// Load indicator for editing
async function loadIndicatorForEdit(indicatorId) {
    try {
        const response = await fetch(`/api/indicators/custom/${indicatorId}`);
        if (!response.ok) throw new Error('Failed to load indicator');

        const indicator = await response.json();

        document.getElementById('indicatorName').value = indicator.name || '';
        document.getElementById('indicatorShortName').value = indicator.short_name || '';
        document.getElementById('indicatorDescription').value = indicator.description || '';
        document.getElementById('indicatorOverlay').checked = indicator.is_overlay !== false;

        if (customIndicatorState.editor) {
            customIndicatorState.editor.setValue(indicator.pine_script || DEFAULT_PINE_TEMPLATE);
        }

    } catch (error) {
        console.error('Error loading indicator:', error);
        showNotification('Error loading indicator', 'error');
    }
}

// Validate Pine Script
async function validatePineScript(silent = false) {
    const editor = customIndicatorState.editor;
    if (!editor) return false;

    const pineScript = editor.getValue();
    const statusEl = document.getElementById('validationStatus');
    const errorsEl = document.getElementById('editorErrors');

    try {
        const response = await fetch('/api/indicators/custom/validate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pine_script: pineScript })
        });

        const result = await response.json();

        if (result.valid) {
            if (!silent) {
                statusEl.innerHTML = '<span class="valid">&#10003; Valid</span>';
                statusEl.className = 'validation-status valid';
            }
            errorsEl.textContent = '';
            errorsEl.style.display = 'none';
            return true;
        } else {
            if (!silent) {
                statusEl.innerHTML = '<span class="invalid">&#10007; Invalid</span>';
                statusEl.className = 'validation-status invalid';
            }
            errorsEl.textContent = result.errors?.join('\n') || 'Unknown error';
            errorsEl.style.display = 'block';
            return false;
        }
    } catch (error) {
        if (!silent) {
            statusEl.innerHTML = '<span class="error">&#9888; Error</span>';
            statusEl.className = 'validation-status error';
            errorsEl.textContent = error.message;
            errorsEl.style.display = 'block';
        }
        return false;
    }
}

// Clear validation status
function clearValidationStatus() {
    const statusEl = document.getElementById('validationStatus');
    const errorsEl = document.getElementById('editorErrors');
    if (statusEl) statusEl.innerHTML = '';
    if (errorsEl) {
        errorsEl.textContent = '';
        errorsEl.style.display = 'none';
    }
}

// Save Pine Indicator
async function savePineIndicator(e) {
    if (e && e.preventDefault) e.preventDefault();

    const name = document.getElementById('indicatorName').value.trim();
    const shortName = document.getElementById('indicatorShortName').value.trim();
    const description = document.getElementById('indicatorDescription').value.trim();
    const isOverlay = document.getElementById('indicatorOverlay').checked;
    const pineScript = customIndicatorState.editor?.getValue() || '';

    // Validate required fields
    if (!name) {
        showNotification('Please enter an indicator name', 'error');
        return;
    }

    if (!shortName) {
        showNotification('Please enter a short name', 'error');
        return;
    }

    // Validate Pine Script
    const isValid = await validatePineScript(false);
    if (!isValid) {
        showNotification('Please fix the Pine Script errors before saving', 'error');
        return;
    }

    const indicatorData = {
        name,
        short_name: shortName,
        pine_script: pineScript,
        description,
        is_overlay: isOverlay
    };

    try {
        let response;
        if (customIndicatorState.isEditing && customIndicatorState.currentIndicatorId) {
            // Update existing
            response = await fetch(`/api/indicators/custom/${customIndicatorState.currentIndicatorId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(indicatorData)
            });
        } else {
            // Create new
            response = await fetch('/api/indicators/custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(indicatorData)
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save indicator');
        }

        const result = await response.json();
        showNotification(result.message || 'Indicator saved successfully', 'success');

        closePineEditor();
        loadCustomIndicators();

    } catch (error) {
        console.error('Error saving indicator:', error);
        showNotification(error.message, 'error');
    }
}

// Preview indicator on chart
async function previewIndicator() {
    const pineScript = customIndicatorState.editor?.getValue() || '';

    // First validate
    const isValid = await validatePineScript(false);
    if (!isValid) {
        showNotification('Please fix the Pine Script errors before previewing', 'error');
        return;
    }

    showNotification('Preview feature coming soon!', 'info');
    // TODO: Implement preview by creating a temporary indicator and calculating values
}

// Load custom indicators list
async function loadCustomIndicators() {
    const container = document.getElementById('customIndicatorList');
    if (!container) return;

    try {
        const response = await fetch('/api/indicators/custom');
        if (!response.ok) throw new Error('Failed to load indicators');

        const data = await response.json();
        customIndicatorState.customIndicators = data.indicators || [];

        if (customIndicatorState.customIndicators.length === 0) {
            container.innerHTML = '<div class="empty-state">No custom indicators yet. Create one or use a template!</div>';
            return;
        }

        container.innerHTML = customIndicatorState.customIndicators.map(indicator => `
            <div class="custom-indicator-item" data-id="${indicator.id}">
                <div class="indicator-info">
                    <span class="indicator-name">${escapeHtml(indicator.name)}</span>
                    <span class="indicator-short">${escapeHtml(indicator.short_name)}</span>
                    <span class="indicator-desc">${escapeHtml(indicator.description || '')}</span>
                </div>
                <div class="indicator-actions">
                    <button class="btn-add-custom" onclick="addCustomIndicatorToChart(${indicator.id})" title="Add to chart">
                        <span>+</span>
                    </button>
                    <button class="btn-edit-custom" onclick="openPineEditor(${indicator.id})" title="Edit">
                        <span>&#9998;</span>
                    </button>
                    <button class="btn-delete-custom" onclick="deleteCustomIndicator(${indicator.id})" title="Delete">
                        <span>&times;</span>
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading custom indicators:', error);
        container.innerHTML = '<div class="error-state">Error loading indicators. <a href="#" onclick="loadCustomIndicators()">Retry</a></div>';
    }
}

// Load templates
async function loadTemplates() {
    const container = document.getElementById('templateList');
    if (!container) return;

    try {
        // First try to seed templates if none exist
        await fetch('/api/indicators/templates/seed', { method: 'POST' });

        const response = await fetch('/api/indicators/templates');
        if (!response.ok) throw new Error('Failed to load templates');

        const data = await response.json();
        customIndicatorState.templates = data.templates || [];

        if (customIndicatorState.templates.length === 0) {
            container.innerHTML = '<div class="empty-state">No templates available</div>';
            return;
        }

        // Group templates by category
        const byCategory = {};
        customIndicatorState.templates.forEach(t => {
            const cat = t.category || 'Other';
            if (!byCategory[cat]) byCategory[cat] = [];
            byCategory[cat].push(t);
        });

        container.innerHTML = Object.entries(byCategory).map(([category, templates]) => `
            <div class="template-category">
                <h4 class="category-title">${escapeHtml(category)}</h4>
                ${templates.map(template => `
                    <div class="template-item" data-id="${template.id}">
                        <div class="template-info">
                            <span class="template-name">${escapeHtml(template.name)}</span>
                            <span class="template-desc">${escapeHtml(template.description || '')}</span>
                        </div>
                        <div class="template-actions">
                            <button class="btn-use-template" onclick="useTemplate(${template.id})" title="Use this template">
                                Use
                            </button>
                            <button class="btn-view-template" onclick="viewTemplate(${template.id})" title="View code">
                                View
                            </button>
                        </div>
                    </div>
                `).join('')}
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading templates:', error);
        container.innerHTML = '<div class="error-state">Error loading templates. <a href="#" onclick="loadTemplates()">Retry</a></div>';
    }
}

// Use template to create new indicator
async function useTemplate(templateId) {
    try {
        const response = await fetch(`/api/indicators/custom/from-template/${templateId}`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to create from template');

        const result = await response.json();
        showNotification(result.message || 'Indicator created from template!', 'success');

        // Switch to custom tab and reload
        const customTab = document.querySelector('.indicator-tab[data-tab="custom"]');
        if (customTab) customTab.click();

    } catch (error) {
        console.error('Error using template:', error);
        showNotification(error.message, 'error');
    }
}

// View template code
async function viewTemplate(templateId) {
    const template = customIndicatorState.templates.find(t => t.id === templateId);
    if (!template) {
        showNotification('Template not found', 'error');
        return;
    }

    // Open editor with template code (not editing, creating new)
    openPineEditor();

    if (customIndicatorState.editor) {
        customIndicatorState.editor.setValue(template.pine_script || DEFAULT_PINE_TEMPLATE);
    }

    document.getElementById('indicatorName').value = template.name + ' (Copy)';
    document.getElementById('indicatorShortName').value = (template.short_name || template.name.substring(0, 10));
    document.getElementById('indicatorDescription').value = template.description || '';
    document.getElementById('indicatorOverlay').checked = template.is_overlay !== false;
}

// Delete custom indicator
async function deleteCustomIndicator(indicatorId) {
    if (!confirm('Are you sure you want to delete this indicator?')) {
        return;
    }

    try {
        const response = await fetch(`/api/indicators/custom/${indicatorId}`, {
            method: 'DELETE'
        });

        if (!response.ok) throw new Error('Failed to delete indicator');

        showNotification('Indicator deleted', 'success');
        loadCustomIndicators();

    } catch (error) {
        console.error('Error deleting indicator:', error);
        showNotification(error.message, 'error');
    }
}

// Add custom indicator to chart
async function addCustomIndicatorToChart(indicatorId) {
    try {
        // Try multiple sources for symbol - trading.js uses state.symbol, app.js uses this.currentSymbol
        let symbol = 'BTC/USD';
        let timeframe = '1h';

        if (typeof state !== 'undefined' && typeof state.symbol === 'string') {
            symbol = state.symbol;
            timeframe = state.timeframe || '1h';
        } else if (typeof window.currentSymbol === 'string') {
            symbol = window.currentSymbol;
            timeframe = window.currentTimeframe || '1h';
        }

        const symbolParam = symbol.replace('/', '-');

        const response = await fetch(`/api/indicators/custom/${indicatorId}/calculate/${symbolParam}?timeframe=${timeframe}&limit=500`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to calculate indicator');
        }

        const data = await response.json();

        // Add to chart (this will integrate with trading.js chart functions)
        // Note: window.renderCustomIndicatorOnChart is defined in trading.js for chart rendering
        if (typeof window.renderCustomIndicatorOnChart === 'function') {
            window.renderCustomIndicatorOnChart(data);
        } else {
            console.log('Custom indicator data:', data);
            showNotification('Indicator calculated! Chart integration coming soon.', 'info');
        }

        // Close the indicators modal
        const modal = document.getElementById('indicatorsModal');
        if (modal) modal.classList.remove('active');

        showNotification(`Added ${data.name} to chart`, 'success');

    } catch (error) {
        console.error('Error adding indicator to chart:', error);
        showNotification(error.message, 'error');
    }
}

// Helper: Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper: Show notification (uses existing notification system or creates simple one)
function showNotification(message, type = 'info') {
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
        return;
    }

    // Simple fallback notification
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 24px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        animation: slideIn 0.3s ease-out;
        background: ${type === 'success' ? '#089981' : type === 'error' ? '#F23645' : '#2962FF'};
    `;

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'fadeOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCustomIndicators);
} else {
    // DOM is already ready
    initCustomIndicators();
}

// Also try to initialize after a delay (for dynamic loading)
setTimeout(() => {
    if (!customIndicatorState.editor) {
        console.log('Retrying custom indicators initialization...');
        initCustomIndicators();
    }
}, 1000);

// ================== PYTHON INDICATORS (BUILT-IN) ==================

// Load built-in Python indicators
async function loadPythonIndicators() {
    const listContainer = document.getElementById('pythonIndicatorList');
    if (!listContainer) {
        console.warn('Python indicators list container not found');
        return;
    }

    listContainer.innerHTML = '<div class="loading-state">Loading built-in indicators...</div>';

    try {
        const response = await fetch('/api/indicators/python');
        const data = await response.json();

        if (!data.indicators || data.indicators.length === 0) {
            listContainer.innerHTML = '<div class="empty-state">No built-in Python indicators available.</div>';
            return;
        }

        listContainer.innerHTML = data.indicators.map(indicator => `
            <div class="indicator-item python-indicator">
                <div class="indicator-info">
                    <span class="indicator-name">${escapeHtml(indicator.name)}</span>
                    <span class="indicator-badge python">Python</span>
                    <span class="indicator-desc">${escapeHtml(indicator.description || '')}</span>
                </div>
                <div class="indicator-actions">
                    <button class="btn-add-python" onclick="addPythonIndicatorToChart('${indicator.id}')" title="Add to chart">
                        <span>+</span>
                    </button>
                    <button class="btn-settings-python" onclick="showPythonIndicatorSettings('${indicator.id}')" title="Settings">
                        <span>&#9881;</span>
                    </button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Error loading Python indicators:', error);
        listContainer.innerHTML = '<div class="error-state">Error loading Python indicators</div>';
    }

    // Also load custom Python indicators
    loadCustomPythonIndicators();
}

// Add Python indicator to chart
async function addPythonIndicatorToChart(indicatorId) {
    try {
        // Get symbol and timeframe from state
        let symbol = 'BTC/USD';
        let timeframe = '5m';

        if (typeof state !== 'undefined' && typeof state.symbol === 'string') {
            symbol = state.symbol;
            timeframe = state.timeframe || '5m';
        }

        const symbolParam = symbol.replace('/', '-');

        showNotification(`Calculating ${indicatorId.toUpperCase()} indicator...`, 'info');

        const response = await fetch(`/api/indicators/python/builtin/${indicatorId}/calculate/${symbolParam}?timeframe=${timeframe}&limit=500`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to calculate indicator');
        }

        const data = await response.json();
        console.log('Python indicator data:', data);

        // Render on chart
        if (typeof window.renderPythonIndicator === 'function') {
            window.renderPythonIndicator(data);
            showNotification(`Added ${data.name} to chart`, 'success');
        } else {
            console.log('Python indicator drawings:', data.drawings);
            showNotification(`${data.name} calculated! Lines: ${data.drawings.lines.length}, Boxes: ${data.drawings.boxes.length}`, 'info');
        }

        // Close the indicators modal
        const modal = document.getElementById('indicatorsModal');
        if (modal) modal.classList.remove('active');

    } catch (error) {
        console.error('Error adding Python indicator to chart:', error);
        showNotification(error.message, 'error');
    }
}

// Show Python indicator settings modal
async function showPythonIndicatorSettings(indicatorId) {
    try {
        const response = await fetch(`/api/indicators/python/builtin/${indicatorId}`);
        const indicator = await response.json();

        // For now, just show the default settings
        const settingsHtml = Object.entries(indicator.default_settings || {}).map(([key, value]) => {
            const label = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            if (typeof value === 'boolean') {
                return `<label class="setting-item"><input type="checkbox" ${value ? 'checked' : ''} data-key="${key}"> ${label}</label>`;
            } else if (typeof value === 'number') {
                return `<label class="setting-item">${label}: <input type="number" value="${value}" data-key="${key}"></label>`;
            } else {
                return `<label class="setting-item">${label}: <input type="text" value="${value}" data-key="${key}"></label>`;
            }
        }).join('');

        showNotification(`Settings for ${indicator.name}: ${Object.keys(indicator.default_settings || {}).length} options available`, 'info');
    } catch (error) {
        console.error('Error showing Python indicator settings:', error);
        showNotification(error.message, 'error');
    }
}

// ================== CUSTOM PYTHON EDITOR ==================

// Default Python template
const DEFAULT_PYTHON_TEMPLATE = `# DR/IDR Indicator - All Sessions
# ================================================
# Draws Defining Range (DR) and IDR for NY, London, Tokyo
# ================================================

# Colors
NY_COLOR = '#4CAF50'      # Green
LONDON_COLOR = '#FF9800'  # Orange
TOKYO_COLOR = '#2196F3'   # Blue
IDR_COLOR = '#FF5252'     # Red

# ==================== NEW YORK ====================
if NYBoxHigh is not None:
    # DR Box (gray fill)
    output.add_box(
        NYOpen, NYBoxHigh, NYClose, NYBoxLow,
        border_color='rgba(128,128,128,0.5)',
        background_color='rgba(128,128,128,0.15)'
    )

    # DR Lines (solid gray)
    output.add_line(NYOpen, NYBoxHigh, NYClose, NYBoxHigh,
                    color='#808080', style='solid', label='NY DR High')
    output.add_line(NYOpen, NYBoxLow, NYClose, NYBoxLow,
                    color='#808080', style='solid', label='NY DR Low')

    # IDR Lines (dashed red)
    output.add_line(NYOpen, NYIDRHigh, NYClose, NYIDRHigh,
                    color=IDR_COLOR, style='dashed', label='NY IDR High')
    output.add_line(NYOpen, NYIDRLow, NYClose, NYIDRLow,
                    color=IDR_COLOR, style='dashed', label='NY IDR Low')

    # Middle IDR
    ny_mid = (NYIDRHigh + NYIDRLow) / 2
    output.add_line(NYOpen, ny_mid, NYClose, ny_mid,
                    color='#9E9E9E', style='dotted', label='NY Mid')

# ==================== LONDON ====================
if LondonBoxHigh is not None:
    output.add_box(
        LondonOpen, LondonBoxHigh, LondonClose, LondonBoxLow,
        border_color='rgba(128,128,128,0.5)',
        background_color='rgba(128,128,128,0.15)'
    )

    output.add_line(LondonOpen, LondonBoxHigh, LondonClose, LondonBoxHigh,
                    color='#808080', style='solid', label='London DR High')
    output.add_line(LondonOpen, LondonBoxLow, LondonClose, LondonBoxLow,
                    color='#808080', style='solid', label='London DR Low')

    output.add_line(LondonOpen, LondonIDRHigh, LondonClose, LondonIDRHigh,
                    color=IDR_COLOR, style='dashed', label='London IDR High')
    output.add_line(LondonOpen, LondonIDRLow, LondonClose, LondonIDRLow,
                    color=IDR_COLOR, style='dashed', label='London IDR Low')

# ==================== TOKYO ====================
if TokyoBoxHigh is not None:
    output.add_box(
        TokyoOpen, TokyoBoxHigh, TokyoClose, TokyoBoxLow,
        border_color='rgba(128,128,128,0.5)',
        background_color='rgba(128,128,128,0.15)'
    )

    output.add_line(TokyoOpen, TokyoBoxHigh, TokyoClose, TokyoBoxHigh,
                    color='#808080', style='solid', label='Tokyo DR High')
    output.add_line(TokyoOpen, TokyoBoxLow, TokyoClose, TokyoBoxLow,
                    color='#808080', style='solid', label='Tokyo DR Low')

    output.add_line(TokyoOpen, TokyoIDRHigh, TokyoClose, TokyoIDRHigh,
                    color=IDR_COLOR, style='dashed', label='Tokyo IDR High')
    output.add_line(TokyoOpen, TokyoIDRLow, TokyoClose, TokyoIDRLow,
                    color=IDR_COLOR, style='dashed', label='Tokyo IDR Low')
`;

// Python editor state
const pythonEditorState = {
    editor: null,
    currentIndicatorId: null,
    isEditing: false,
    customPythonIndicators: []
};

// Setup Python Editor
function setupPythonEditor() {
    const editorContainer = document.getElementById('pythonCodeEditor');
    if (!editorContainer || !window.CodeMirror) {
        console.warn('CodeMirror not loaded or Python editor container not found');
        return;
    }

    pythonEditorState.editor = CodeMirror(editorContainer, {
        value: DEFAULT_PYTHON_TEMPLATE,
        mode: 'python',
        theme: 'dracula',
        lineNumbers: true,
        lineWrapping: true,
        indentUnit: 4,
        tabSize: 4,
        indentWithTabs: false,
        autoCloseBrackets: true,
        matchBrackets: true,
        extraKeys: {
            'Ctrl-Enter': runPythonCode,
            'Cmd-Enter': runPythonCode,
            'Ctrl-S': savePythonIndicator,
            'Cmd-S': savePythonIndicator
        }
    });
}

// Setup Python Editor Modal
function setupPythonEditorModal() {
    // Create Python indicator button
    const createBtn = document.getElementById('createPythonIndicatorBtn');
    if (createBtn) {
        createBtn.addEventListener('click', () => openPythonEditor());
    }

    // Close editor
    const closeBtn = document.getElementById('closePythonEditor');
    if (closeBtn) {
        closeBtn.addEventListener('click', closePythonEditor);
    }

    // Cancel button
    const cancelBtn = document.getElementById('cancelPythonEditor');
    if (cancelBtn) {
        cancelBtn.addEventListener('click', closePythonEditor);
    }

    // Save button
    const saveBtn = document.getElementById('savePythonIndicator');
    if (saveBtn) {
        saveBtn.addEventListener('click', savePythonIndicator);
    }

    // Run button
    const runBtn = document.getElementById('runPythonBtn');
    if (runBtn) {
        runBtn.addEventListener('click', runPythonCode);
    }
}

// Open Python Editor Modal
function openPythonEditor(indicatorId = null) {
    console.log('openPythonEditor called', indicatorId);
    const modal = document.getElementById('pythonEditorModal');
    if (!modal) {
        console.error('Python editor modal not found!');
        return;
    }

    // Initialize editor if not already done
    if (!pythonEditorState.editor) {
        setupPythonEditor();
    }

    modal.classList.add('show');

    if (indicatorId) {
        // Edit existing indicator
        pythonEditorState.isEditing = true;
        pythonEditorState.currentIndicatorId = indicatorId;
        document.getElementById('pythonEditorTitle').textContent = 'Edit Python Indicator';
        loadPythonIndicatorForEdit(indicatorId);
    } else {
        // Create new indicator
        pythonEditorState.isEditing = false;
        pythonEditorState.currentIndicatorId = null;
        document.getElementById('pythonEditorTitle').textContent = 'Create Python Indicator';
        document.getElementById('pythonIndicatorName').value = '';
        document.getElementById('pythonIndicatorShortName').value = '';
        document.getElementById('pythonIndicatorDescription').value = '';
        document.getElementById('pythonIndicatorOverlay').checked = true;
        if (pythonEditorState.editor) {
            pythonEditorState.editor.setValue(DEFAULT_PYTHON_TEMPLATE);
        }
    }

    // Refresh editor after modal is visible
    setTimeout(() => {
        if (pythonEditorState.editor) {
            pythonEditorState.editor.refresh();
        }
    }, 100);
}

// Close Python Editor
function closePythonEditor() {
    const modal = document.getElementById('pythonEditorModal');
    if (modal) {
        modal.classList.remove('show');
    }
    pythonEditorState.currentIndicatorId = null;
    pythonEditorState.isEditing = false;
}

// Load Python Indicator for Editing
async function loadPythonIndicatorForEdit(indicatorId) {
    try {
        const response = await fetch(`/api/indicators/python/custom/${indicatorId}`);
        if (!response.ok) throw new Error('Failed to load indicator');

        const indicator = await response.json();

        document.getElementById('pythonIndicatorName').value = indicator.name || '';
        document.getElementById('pythonIndicatorShortName').value = indicator.short_name || '';
        document.getElementById('pythonIndicatorDescription').value = indicator.description || '';
        document.getElementById('pythonIndicatorOverlay').checked = indicator.is_overlay !== false;

        if (pythonEditorState.editor && indicator.python_code) {
            pythonEditorState.editor.setValue(indicator.python_code);
        }
    } catch (error) {
        console.error('Error loading Python indicator:', error);
        showNotification('Error loading indicator: ' + error.message, 'error');
    }
}

// Save Python Indicator
async function savePythonIndicator(event) {
    if (event) event.preventDefault();

    const name = document.getElementById('pythonIndicatorName').value.trim();
    const shortName = document.getElementById('pythonIndicatorShortName').value.trim();
    const description = document.getElementById('pythonIndicatorDescription').value.trim();
    const isOverlay = document.getElementById('pythonIndicatorOverlay').checked;
    const pythonCode = pythonEditorState.editor ? pythonEditorState.editor.getValue() : '';

    if (!name) {
        showNotification('Please enter an indicator name', 'error');
        return;
    }
    if (!shortName) {
        showNotification('Please enter a short name', 'error');
        return;
    }
    if (!pythonCode.trim()) {
        showNotification('Please enter Python code', 'error');
        return;
    }

    try {
        let response;
        if (pythonEditorState.isEditing && pythonEditorState.currentIndicatorId) {
            // Update existing
            response = await fetch(`/api/indicators/python/custom/${pythonEditorState.currentIndicatorId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    short_name: shortName,
                    description,
                    is_overlay: isOverlay,
                    python_code: pythonCode
                })
            });
        } else {
            // Create new
            response = await fetch('/api/indicators/python/custom', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    short_name: shortName,
                    description,
                    is_overlay: isOverlay,
                    python_code: pythonCode
                })
            });
        }

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save indicator');
        }

        const result = await response.json();
        showNotification(result.message || 'Python indicator saved!', 'success');
        closePythonEditor();
        loadCustomPythonIndicators();
    } catch (error) {
        console.error('Error saving Python indicator:', error);
        showNotification(error.message, 'error');
    }
}

// Run Python Code (Preview)
async function runPythonCode(event) {
    if (event) event.preventDefault();

    const pythonCode = pythonEditorState.editor ? pythonEditorState.editor.getValue() : '';
    if (!pythonCode.trim()) {
        showNotification('Please enter Python code', 'error');
        return;
    }

    const statusEl = document.getElementById('pythonValidationStatus');
    const errorsEl = document.getElementById('pythonEditorErrors');

    if (statusEl) {
        statusEl.innerHTML = '<span class="validating">Running...</span>';
    }

    try {
        // Get current symbol and timeframe
        let symbol = 'BTC/USD';
        let timeframe = '1h';

        if (typeof window.getCurrentSymbol === 'function') {
            symbol = window.getCurrentSymbol();
        } else if (document.getElementById('currentSymbol')) {
            symbol = document.getElementById('currentSymbol').textContent || 'BTC/USD';
        }

        if (typeof window.getCurrentTimeframe === 'function') {
            timeframe = window.getCurrentTimeframe();
        }

        const symbolParam = symbol.replace('/', '-');

        const response = await fetch(`/api/indicators/python/execute/${symbolParam}?timeframe=${timeframe}&limit=500`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                python_code: pythonCode,
                settings: {}
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Execution failed');
        }

        const data = await response.json();

        if (statusEl) {
            statusEl.innerHTML = '<span class="valid">Success!</span>';
        }
        if (errorsEl) {
            errorsEl.innerHTML = '';
        }

        // Render on chart
        if (typeof window.renderPythonIndicator === 'function') {
            window.renderPythonIndicator(data);
        }

        showNotification('Python code executed successfully!', 'success');
    } catch (error) {
        console.error('Error running Python code:', error);
        if (statusEl) {
            statusEl.innerHTML = '<span class="invalid">Error</span>';
        }
        if (errorsEl) {
            errorsEl.innerHTML = `<div class="error-message">${escapeHtml(error.message)}</div>`;
        }
        showNotification(error.message, 'error');
    }
}

// Load Custom Python Indicators
async function loadCustomPythonIndicators() {
    const container = document.getElementById('customPythonList');
    if (!container) return;

    try {
        const response = await fetch('/api/indicators/python/custom');
        if (!response.ok) throw new Error('Failed to load indicators');

        const data = await response.json();
        pythonEditorState.customPythonIndicators = data.indicators || [];

        if (pythonEditorState.customPythonIndicators.length === 0) {
            container.innerHTML = '<div class="empty-state">No custom Python indicators yet</div>';
            return;
        }

        container.innerHTML = pythonEditorState.customPythonIndicators.map(indicator => `
            <div class="custom-indicator-item" data-id="${indicator.id}">
                <div class="indicator-info">
                    <span class="indicator-name">${escapeHtml(indicator.name)}</span>
                    <span class="indicator-short">${escapeHtml(indicator.short_name)}</span>
                    <span class="indicator-desc">${escapeHtml(indicator.description || '')}</span>
                </div>
                <div class="indicator-actions">
                    <button class="btn-add-custom" onclick="addCustomPythonIndicatorToChart(${indicator.id})" title="Add to chart">
                        <span>+</span>
                    </button>
                    <button class="btn-edit-custom" onclick="openPythonEditor(${indicator.id})" title="Edit">
                        <span>&#9998;</span>
                    </button>
                    <button class="btn-delete-custom" onclick="deleteCustomPythonIndicator(${indicator.id})" title="Delete">
                        <span>&times;</span>
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading custom Python indicators:', error);
        container.innerHTML = '<div class="error-state">Error loading indicators</div>';
    }
}

// Add Custom Python Indicator to Chart
async function addCustomPythonIndicatorToChart(indicatorId) {
    try {
        let symbol = 'BTC/USD';
        let timeframe = '1h';

        if (typeof window.getCurrentSymbol === 'function') {
            symbol = window.getCurrentSymbol();
        } else if (document.getElementById('currentSymbol')) {
            symbol = document.getElementById('currentSymbol').textContent || 'BTC/USD';
        }

        if (typeof window.getCurrentTimeframe === 'function') {
            timeframe = window.getCurrentTimeframe();
        }

        const symbolParam = symbol.replace('/', '-');

        const response = await fetch(`/api/indicators/python/custom/${indicatorId}/calculate/${symbolParam}?timeframe=${timeframe}&limit=500`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to calculate indicator');
        }

        const data = await response.json();

        if (typeof window.renderPythonIndicator === 'function') {
            window.renderPythonIndicator(data);
        }

        showNotification(`${data.name} added to chart`, 'success');
    } catch (error) {
        console.error('Error adding custom Python indicator:', error);
        showNotification(error.message, 'error');
    }
}

// Delete Custom Python Indicator
async function deleteCustomPythonIndicator(indicatorId) {
    if (!confirm('Are you sure you want to delete this Python indicator?')) {
        return;
    }

    try {
        const response = await fetch(`/api/indicators/python/custom/${indicatorId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            throw new Error('Failed to delete indicator');
        }

        showNotification('Python indicator deleted', 'success');
        loadCustomPythonIndicators();
    } catch (error) {
        console.error('Error deleting Python indicator:', error);
        showNotification(error.message, 'error');
    }
}

// Initialize Python editor when custom indicators module loads
function initPythonEditor() {
    setupPythonEditorModal();
    // Load custom python indicators when Python tab is clicked
    const pythonTab = document.querySelector('.indicator-tab[data-tab="python"]');
    if (pythonTab) {
        pythonTab.addEventListener('click', () => {
            loadCustomPythonIndicators();
        });
    }
}

// Call init on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initPythonEditor);
} else {
    initPythonEditor();
}

// Export functions to global scope for onclick handlers
window.openPineEditor = openPineEditor;
window.deleteCustomIndicator = deleteCustomIndicator;
window.addCustomIndicatorToChart = addCustomIndicatorToChart;
window.useTemplate = useTemplate;
window.viewTemplate = viewTemplate;
window.loadCustomIndicators = loadCustomIndicators;
window.loadTemplates = loadTemplates;
window.loadPythonIndicators = loadPythonIndicators;
window.addPythonIndicatorToChart = addPythonIndicatorToChart;
window.showPythonIndicatorSettings = showPythonIndicatorSettings;
window.openPythonEditor = openPythonEditor;
window.closePythonEditor = closePythonEditor;
window.savePythonIndicator = savePythonIndicator;
window.runPythonCode = runPythonCode;
window.loadCustomPythonIndicators = loadCustomPythonIndicators;
window.addCustomPythonIndicatorToChart = addCustomPythonIndicatorToChart;
window.deleteCustomPythonIndicator = deleteCustomPythonIndicator;
