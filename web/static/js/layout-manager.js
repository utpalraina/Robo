/**
 * Layout Manager - Save, load, and manage custom chart layouts
 */

const LayoutManager = {
    STORAGE_KEY: 'robo_trader_layouts',
    currentLayoutId: null,

    /**
     * Initialize the layout manager
     */
    init() {
        this.bindEvents();
        this.loadSavedLayouts();
        this.restoreLastLayout();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        // Toggle dropdown
        const managerBtn = document.getElementById('layoutManagerBtn');
        const dropdown = document.getElementById('layoutManagerDropdown');

        if (managerBtn && dropdown) {
            managerBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                dropdown.classList.toggle('open');
            });

            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.layout-manager')) {
                    dropdown.classList.remove('open');
                }
            });
        }

        // Save layout button
        const saveBtn = document.getElementById('saveLayoutBtn');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => {
                this.openSaveModal();
                dropdown.classList.remove('open');
            });
        }

        // Create new layout button
        const createBtn = document.getElementById('createLayoutBtn');
        if (createBtn) {
            createBtn.addEventListener('click', () => {
                this.openSaveModal(true);
                dropdown.classList.remove('open');
            });
        }

        // Modal events
        const modal = document.getElementById('layoutSaveModal');
        const closeBtn = document.getElementById('closeLayoutModal');
        const cancelBtn = document.getElementById('cancelLayoutSave');
        const confirmBtn = document.getElementById('confirmLayoutSave');

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.closeModal());
        }
        if (cancelBtn) {
            cancelBtn.addEventListener('click', () => this.closeModal());
        }
        if (confirmBtn) {
            confirmBtn.addEventListener('click', () => this.saveLayout());
        }
        if (modal) {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) this.closeModal();
            });
        }
    },

    /**
     * Get all saved layouts from localStorage
     */
    getSavedLayouts() {
        try {
            const saved = localStorage.getItem(this.STORAGE_KEY);
            return saved ? JSON.parse(saved) : [];
        } catch (e) {
            console.error('Error loading saved layouts:', e);
            return [];
        }
    },

    /**
     * Save layouts to localStorage
     */
    saveToStorage(layouts) {
        try {
            localStorage.setItem(this.STORAGE_KEY, JSON.stringify(layouts));
        } catch (e) {
            console.error('Error saving layouts:', e);
        }
    },

    /**
     * Load and render saved layouts in the dropdown
     */
    loadSavedLayouts() {
        const container = document.getElementById('savedLayoutsList');
        if (!container) return;

        const layouts = this.getSavedLayouts();

        if (layouts.length === 0) {
            container.innerHTML = '<div class="empty-layouts">No saved layouts yet</div>';
            return;
        }

        container.innerHTML = layouts.map(layout => `
            <div class="saved-layout-item ${this.currentLayoutId === layout.id ? 'active' : ''}"
                 data-layout-id="${layout.id}">
                <div class="layout-name">
                    <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
                        <rect x="1" y="1" width="6" height="6" stroke="currentColor" stroke-width="1.5" rx="1"/>
                        <rect x="9" y="1" width="6" height="6" stroke="currentColor" stroke-width="1.5" rx="1"/>
                        <rect x="1" y="9" width="6" height="6" stroke="currentColor" stroke-width="1.5" rx="1"/>
                        <rect x="9" y="9" width="6" height="6" stroke="currentColor" stroke-width="1.5" rx="1"/>
                    </svg>
                    <span>${this.escapeHtml(layout.name)}</span>
                </div>
                <div class="layout-actions">
                    <button class="layout-action-icon" onclick="LayoutManager.editLayout('${layout.id}')" title="Edit">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                            <path d="M11.5 1.5l3 3L5 14H2v-3L11.5 1.5z" stroke="currentColor" stroke-width="1.5"/>
                        </svg>
                    </button>
                    <button class="layout-action-icon delete" onclick="LayoutManager.deleteLayout('${layout.id}')" title="Delete">
                        <svg width="12" height="12" viewBox="0 0 16 16" fill="none">
                            <path d="M2 4h12M5.5 4V2.5h5V4M6 7v5M10 7v5M3.5 4l1 10h7l1-10" stroke="currentColor" stroke-width="1.5"/>
                        </svg>
                    </button>
                </div>
            </div>
        `).join('');

        // Add click handlers for loading layouts
        container.querySelectorAll('.saved-layout-item').forEach(item => {
            item.addEventListener('click', (e) => {
                if (!e.target.closest('.layout-actions')) {
                    this.loadLayout(item.dataset.layoutId);
                }
            });
        });
    },

    /**
     * Open the save layout modal
     */
    openSaveModal(isNew = false) {
        const modal = document.getElementById('layoutSaveModal');
        const titleEl = document.getElementById('layoutModalTitle');
        const nameInput = document.getElementById('layoutName');

        if (modal) {
            modal.classList.add('show');
            titleEl.textContent = isNew ? 'Create New Layout' : 'Save Layout';
            nameInput.value = isNew ? '' : this.generateLayoutName();
            nameInput.focus();
            this.updatePreview();
        }
    },

    /**
     * Close the save layout modal
     */
    closeModal() {
        const modal = document.getElementById('layoutSaveModal');
        if (modal) {
            modal.classList.remove('show');
        }
    },

    /**
     * Generate a default layout name
     */
    generateLayoutName() {
        const layouts = this.getSavedLayouts();
        const layoutType = state.currentLayout;
        const typeNames = {
            '1': 'Single',
            '2h': 'Horizontal Split',
            '2v': 'Vertical Split',
            '4': 'Quad',
            '6': 'Grid'
        };
        const baseName = typeNames[layoutType] || 'Custom';
        let name = `${baseName} Layout`;
        let counter = 1;

        while (layouts.some(l => l.name === name)) {
            name = `${baseName} Layout ${counter}`;
            counter++;
        }

        return name;
    },

    /**
     * Update the preview in the modal
     */
    updatePreview() {
        const previewGrid = document.getElementById('layoutPreviewGrid');
        const chartCount = document.getElementById('previewChartCount');
        const layoutType = document.getElementById('previewLayoutType');

        if (!previewGrid) return;

        const layout = state.currentLayout;
        const counts = { '1': 1, '2h': 2, '2v': 2, '4': 4, '6': 6 };
        const types = {
            '1': 'Single Chart',
            '2h': 'Horizontal Split',
            '2v': 'Vertical Split',
            '4': '4-Chart Grid',
            '6': '6-Chart Grid'
        };

        const count = counts[layout] || 1;
        chartCount.textContent = `${count} chart${count > 1 ? 's' : ''}`;
        layoutType.textContent = types[layout] || 'Custom';

        // Update grid class
        previewGrid.className = `preview-grid layout-${layout}`;

        // Generate preview cells
        let cells = '';
        for (let i = 0; i < count; i++) {
            const tf = state.chartTimeframes[i] || '1h';
            cells += `<div class="preview-cell">${state.symbol.split('/')[0]}<br>${tf}</div>`;
        }
        previewGrid.innerHTML = cells;
    },

    /**
     * Save the current layout
     */
    saveLayout() {
        const nameInput = document.getElementById('layoutName');
        const name = nameInput.value.trim();

        if (!name) {
            if (window.Toast) Toast.warning('Please enter a layout name');
            nameInput.focus();
            return;
        }

        const saveIndicators = document.getElementById('saveIndicators').checked;
        const saveTimeframes = document.getElementById('saveTimeframes').checked;
        const saveSymbols = document.getElementById('saveSymbols').checked;

        const layoutData = {
            id: this.generateId(),
            name: name,
            createdAt: new Date().toISOString(),
            layoutType: state.currentLayout,
            activeCharts: state.activeCharts,
            symbol: state.symbol,
        };

        if (saveTimeframes) {
            layoutData.chartTimeframes = [...state.chartTimeframes];
        }

        if (saveSymbols) {
            // Save per-chart symbols if we implement that feature
            layoutData.chartSymbols = this.getChartSymbols();
        }

        if (saveIndicators) {
            layoutData.indicators = this.getActiveIndicators();
        }

        // Save panel visibility states
        layoutData.panels = {
            orderbook: state.orderbookVisible,
            orderForm: state.orderFormVisible
        };

        // Save to storage
        const layouts = this.getSavedLayouts();
        layouts.push(layoutData);
        this.saveToStorage(layouts);

        // Update current layout
        this.currentLayoutId = layoutData.id;
        this.updateCurrentLayoutName(name);

        // Refresh dropdown
        this.loadSavedLayouts();

        // Close modal and show toast
        this.closeModal();
        if (window.Toast) Toast.success(`Layout "${name}" saved`);
    },

    /**
     * Load a saved layout
     */
    loadLayout(layoutId) {
        const layouts = this.getSavedLayouts();
        const layout = layouts.find(l => l.id === layoutId);

        if (!layout) {
            if (window.Toast) Toast.error('Layout not found');
            return;
        }

        // Apply layout type
        if (layout.layoutType && typeof changeLayout === 'function') {
            changeLayout(layout.layoutType);
        }

        // Apply timeframes
        if (layout.chartTimeframes) {
            state.chartTimeframes = [...layout.chartTimeframes];
            // Update UI
            layout.chartTimeframes.forEach((tf, i) => {
                const select = document.querySelector(`.cell-timeframe[data-index="${i}"]`);
                if (select) {
                    select.value = tf;
                }
                updateCellTimeframeDisplay(i, tf);
            });
        }

        // Apply symbol
        if (layout.symbol && typeof changeSymbol === 'function') {
            changeSymbol(layout.symbol);
        }

        // Apply panel states
        if (layout.panels) {
            if (layout.panels.orderbook !== undefined && state.orderbookVisible !== layout.panels.orderbook) {
                toggleOrderBook();
            }
            if (layout.panels.orderForm !== undefined && state.orderFormVisible !== layout.panels.orderForm) {
                toggleOrderForm();
            }
        }

        // Apply indicators
        if (layout.indicators && Array.isArray(layout.indicators)) {
            // This would require integration with the indicators system
            // For now, we'll store the data for future use
        }

        // Update current layout tracking
        this.currentLayoutId = layoutId;
        this.updateCurrentLayoutName(layout.name);

        // Save last used layout
        localStorage.setItem('robo_trader_last_layout', layoutId);

        // Close dropdown
        document.getElementById('layoutManagerDropdown')?.classList.remove('open');

        // Refresh dropdown to show active state
        this.loadSavedLayouts();

        if (window.Toast) Toast.info(`Loaded "${layout.name}"`);
    },

    /**
     * Delete a saved layout
     */
    deleteLayout(layoutId) {
        const layouts = this.getSavedLayouts();
        const layout = layouts.find(l => l.id === layoutId);

        if (!layout) return;

        if (confirm(`Delete layout "${layout.name}"?`)) {
            const filtered = layouts.filter(l => l.id !== layoutId);
            this.saveToStorage(filtered);

            if (this.currentLayoutId === layoutId) {
                this.currentLayoutId = null;
                this.updateCurrentLayoutName('Default');
            }

            this.loadSavedLayouts();
            if (window.Toast) Toast.success('Layout deleted');
        }
    },

    /**
     * Edit a saved layout (rename)
     */
    editLayout(layoutId) {
        const layouts = this.getSavedLayouts();
        const layout = layouts.find(l => l.id === layoutId);

        if (!layout) return;

        const newName = prompt('Enter new layout name:', layout.name);
        if (newName && newName.trim()) {
            layout.name = newName.trim();
            this.saveToStorage(layouts);
            this.loadSavedLayouts();

            if (this.currentLayoutId === layoutId) {
                this.updateCurrentLayoutName(newName);
            }

            if (window.Toast) Toast.success('Layout renamed');
        }
    },

    /**
     * Update the current layout name display
     */
    updateCurrentLayoutName(name) {
        const el = document.getElementById('currentLayoutName');
        if (el) {
            el.textContent = name;
        }
    },

    /**
     * Restore the last used layout on page load
     */
    restoreLastLayout() {
        const lastLayoutId = localStorage.getItem('robo_trader_last_layout');
        if (lastLayoutId) {
            const layouts = this.getSavedLayouts();
            const layout = layouts.find(l => l.id === lastLayoutId);
            if (layout) {
                // Delay to ensure state is initialized
                setTimeout(() => {
                    this.loadLayout(lastLayoutId);
                }, 500);
            }
        }
    },

    /**
     * Get chart symbols (for future multi-symbol support)
     */
    getChartSymbols() {
        const symbols = [];
        document.querySelectorAll('.cell-symbol').forEach((el, i) => {
            symbols.push(state.symbol); // Currently all charts use the same symbol
        });
        return symbols;
    },

    /**
     * Get active indicators (placeholder for indicator integration)
     */
    getActiveIndicators() {
        // This would integrate with the indicators system
        // Return empty array for now
        return [];
    },

    /**
     * Generate a unique ID
     */
    generateId() {
        return 'layout_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    LayoutManager.init();
});

// Expose globally
window.LayoutManager = LayoutManager;
