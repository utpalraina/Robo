/**
 * UI Polish Module
 * Provides toast notifications, rich tooltips, loading states, and animations
 */

// ============================================
// TOAST NOTIFICATION SYSTEM
// ============================================

const Toast = {
    container: null,
    queue: [],
    maxVisible: 5,

    init() {
        this.container = document.getElementById('toastContainer');
        if (!this.container) {
            this.container = document.createElement('div');
            this.container.id = 'toastContainer';
            this.container.className = 'toast-container';
            document.body.appendChild(this.container);
        }
    },

    show(message, type = 'info', options = {}) {
        if (!this.container) this.init();

        const {
            duration = 4000,
            action = null,
            actionText = 'Retry',
            persistent = false,
            icon = null
        } = options;

        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;

        const iconMap = {
            success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>',
            error: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
            warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
            info: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>'
        };

        toast.innerHTML = `
            <div class="toast-icon">${icon || iconMap[type] || iconMap.info}</div>
            <div class="toast-content">
                <span class="toast-message">${message}</span>
                ${action ? `<button class="toast-action">${actionText}</button>` : ''}
            </div>
            <button class="toast-close" aria-label="Close">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
            </button>
            ${!persistent ? `<div class="toast-progress"><div class="toast-progress-bar"></div></div>` : ''}
        `;

        // Event listeners
        const closeBtn = toast.querySelector('.toast-close');
        closeBtn.addEventListener('click', () => this.dismiss(toast));

        if (action) {
            const actionBtn = toast.querySelector('.toast-action');
            actionBtn.addEventListener('click', () => {
                action();
                this.dismiss(toast);
            });
        }

        // Add to container with animation
        this.container.appendChild(toast);
        requestAnimationFrame(() => toast.classList.add('toast-visible'));

        // Start progress bar animation
        if (!persistent) {
            const progressBar = toast.querySelector('.toast-progress-bar');
            if (progressBar) {
                progressBar.style.transition = `width ${duration}ms linear`;
                requestAnimationFrame(() => progressBar.style.width = '0%');
            }

            // Auto dismiss
            setTimeout(() => this.dismiss(toast), duration);
        }

        return toast;
    },

    dismiss(toast) {
        if (!toast || !toast.parentNode) return;

        toast.classList.remove('toast-visible');
        toast.classList.add('toast-hiding');

        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 300);
    },

    success(message, options = {}) {
        return this.show(message, 'success', options);
    },

    error(message, options = {}) {
        return this.show(message, 'error', { duration: 6000, ...options });
    },

    warning(message, options = {}) {
        return this.show(message, 'warning', options);
    },

    info(message, options = {}) {
        return this.show(message, 'info', options);
    }
};

// ============================================
// LOADING STATES
// ============================================

const Loading = {
    overlay: null,
    activeCount: 0,

    init() {
        this.overlay = document.getElementById('loadingOverlay');
    },

    show(text = 'Loading...') {
        if (!this.overlay) this.init();

        this.activeCount++;
        const textEl = this.overlay.querySelector('.loading-text');
        if (textEl) textEl.textContent = text;

        this.overlay.classList.add('visible');
    },

    hide() {
        if (!this.overlay) return;

        this.activeCount = Math.max(0, this.activeCount - 1);
        if (this.activeCount === 0) {
            this.overlay.classList.remove('visible');
        }
    },

    forceHide() {
        this.activeCount = 0;
        if (this.overlay) {
            this.overlay.classList.remove('visible');
        }
    }
};

// ============================================
// SKELETON LOADERS
// ============================================

const Skeleton = {
    create(type = 'text', options = {}) {
        const { width = '100%', height = '16px', count = 1, className = '' } = options;

        const skeletons = [];
        for (let i = 0; i < count; i++) {
            const el = document.createElement('div');
            el.className = `skeleton skeleton-${type} ${className}`;

            if (type === 'text') {
                el.style.width = width;
                el.style.height = height;
            } else if (type === 'circle') {
                el.style.width = height;
                el.style.height = height;
            } else if (type === 'rect') {
                el.style.width = width;
                el.style.height = height;
            }

            skeletons.push(el);
        }

        return count === 1 ? skeletons[0] : skeletons;
    },

    // Create skeleton for orderbook rows
    orderbook(container, rows = 10) {
        container.innerHTML = '';
        for (let i = 0; i < rows; i++) {
            const row = document.createElement('div');
            row.className = 'skeleton-row';
            row.innerHTML = `
                <div class="skeleton skeleton-text" style="width: 80px"></div>
                <div class="skeleton skeleton-text" style="width: 60px"></div>
                <div class="skeleton skeleton-text" style="width: 70px"></div>
            `;
            container.appendChild(row);
        }
    },

    // Create skeleton for chart
    chart(container) {
        container.innerHTML = `
            <div class="skeleton-chart">
                <div class="skeleton-bars">
                    ${Array(20).fill().map(() =>
                        `<div class="skeleton skeleton-bar" style="height: ${30 + Math.random() * 50}%"></div>`
                    ).join('')}
                </div>
            </div>
        `;
    },

    // Remove all skeletons from container
    remove(container) {
        const skeletons = container.querySelectorAll('.skeleton, .skeleton-row, .skeleton-chart');
        skeletons.forEach(s => s.remove());
    }
};

// ============================================
// RICH TOOLTIPS
// ============================================

const RichTooltip = {
    element: null,
    hideTimeout: null,

    init() {
        this.element = document.getElementById('richTooltip');
        if (!this.element) {
            this.element = document.createElement('div');
            this.element.id = 'richTooltip';
            this.element.className = 'rich-tooltip';
            this.element.innerHTML = `
                <div class="tooltip-header"></div>
                <div class="tooltip-body"></div>
                <div class="tooltip-footer"></div>
            `;
            document.body.appendChild(this.element);
        }

        // Setup event delegation for elements with data-tooltip
        document.addEventListener('mouseenter', this.handleMouseEnter.bind(this), true);
        document.addEventListener('mouseleave', this.handleMouseLeave.bind(this), true);
    },

    handleMouseEnter(e) {
        const target = e.target.closest('[data-tooltip]');
        if (!target) return;

        clearTimeout(this.hideTimeout);

        const tooltip = target.dataset.tooltip;
        const title = target.dataset.tooltipTitle || '';
        const footer = target.dataset.tooltipFooter || '';

        this.show(target, { title, body: tooltip, footer });
    },

    handleMouseLeave(e) {
        const target = e.target.closest('[data-tooltip]');
        if (!target) return;

        this.hideTimeout = setTimeout(() => this.hide(), 100);
    },

    show(anchor, content = {}) {
        const { title = '', body = '', footer = '' } = content;

        const header = this.element.querySelector('.tooltip-header');
        const bodyEl = this.element.querySelector('.tooltip-body');
        const footerEl = this.element.querySelector('.tooltip-footer');

        header.innerHTML = title;
        header.style.display = title ? 'block' : 'none';

        bodyEl.innerHTML = body;

        footerEl.innerHTML = footer;
        footerEl.style.display = footer ? 'block' : 'none';

        // Position tooltip
        const rect = anchor.getBoundingClientRect();
        const tooltipRect = this.element.getBoundingClientRect();

        let left = rect.left + (rect.width / 2);
        let top = rect.top - 8;

        this.element.classList.remove('tooltip-bottom');

        // Check if tooltip would go off screen top
        if (top - tooltipRect.height < 10) {
            top = rect.bottom + 8;
            this.element.classList.add('tooltip-bottom');
        }

        // Adjust horizontal position
        left = Math.max(10, Math.min(left, window.innerWidth - tooltipRect.width / 2 - 10));

        this.element.style.left = `${left}px`;
        this.element.style.top = `${top}px`;
        this.element.classList.add('visible');
    },

    hide() {
        this.element.classList.remove('visible');
    }
};

// ============================================
// EMPTY STATES
// ============================================

const EmptyState = {
    create(type, options = {}) {
        const {
            title = 'No data',
            message = '',
            action = null,
            actionText = 'Refresh'
        } = options;

        const illustrations = {
            positions: `<svg viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="20" y="30" width="80" height="50" rx="4" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <line x1="20" y1="45" x2="100" y2="45" stroke="currentColor" stroke-width="2" opacity="0.2"/>
                <circle cx="60" cy="55" r="15" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <path d="M55 55h10M60 50v10" stroke="currentColor" stroke-width="2" opacity="0.5"/>
            </svg>`,
            orders: `<svg viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="25" y="20" width="70" height="15" rx="2" stroke="currentColor" stroke-width="2" opacity="0.2"/>
                <rect x="25" y="42" width="70" height="15" rx="2" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <rect x="25" y="64" width="70" height="15" rx="2" stroke="currentColor" stroke-width="2" opacity="0.2"/>
                <circle cx="85" cy="50" r="20" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <path d="M85 40v20M75 50h20" stroke="currentColor" stroke-width="2" opacity="0.5"/>
            </svg>`,
            trades: `<svg viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M20 80 L40 50 L60 65 L80 35 L100 45" stroke="currentColor" stroke-width="2" opacity="0.3" fill="none"/>
                <circle cx="40" cy="50" r="4" fill="currentColor" opacity="0.3"/>
                <circle cx="60" cy="65" r="4" fill="currentColor" opacity="0.3"/>
                <circle cx="80" cy="35" r="4" fill="currentColor" opacity="0.3"/>
                <path d="M95 20l10 10-10 10" stroke="currentColor" stroke-width="2" opacity="0.5" fill="none"/>
            </svg>`,
            balances: `<svg viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <circle cx="60" cy="50" r="30" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <path d="M60 30v40M45 45h30M50 55h20" stroke="currentColor" stroke-width="2" opacity="0.4"/>
                <circle cx="90" cy="25" r="10" stroke="currentColor" stroke-width="2" opacity="0.2"/>
                <circle cx="30" cy="75" r="8" stroke="currentColor" stroke-width="2" opacity="0.2"/>
            </svg>`,
            default: `<svg viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="30" y="25" width="60" height="50" rx="4" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <circle cx="60" cy="50" r="15" stroke="currentColor" stroke-width="2" opacity="0.3"/>
                <path d="M60 42v8M60 56v2" stroke="currentColor" stroke-width="2" opacity="0.5"/>
            </svg>`
        };

        const container = document.createElement('div');
        container.className = 'empty-state';
        container.innerHTML = `
            <div class="empty-state-illustration">
                ${illustrations[type] || illustrations.default}
            </div>
            <div class="empty-state-title">${title}</div>
            ${message ? `<div class="empty-state-message">${message}</div>` : ''}
            ${action ? `<button class="empty-state-action">${actionText}</button>` : ''}
        `;

        if (action) {
            container.querySelector('.empty-state-action').addEventListener('click', action);
        }

        return container;
    },

    // Apply empty state to a table body
    applyToTable(tbody, type, options = {}) {
        const colCount = tbody.closest('table')?.querySelectorAll('thead th').length || 1;
        tbody.innerHTML = '';

        const tr = document.createElement('tr');
        tr.className = 'empty-state-row';

        const td = document.createElement('td');
        td.colSpan = colCount;
        td.appendChild(this.create(type, options));

        tr.appendChild(td);
        tbody.appendChild(tr);
    }
};

// ============================================
// MICRO ANIMATIONS
// ============================================

const Animate = {
    // Fade in element
    fadeIn(element, duration = 300) {
        element.style.opacity = '0';
        element.style.display = '';
        element.style.transition = `opacity ${duration}ms ease`;

        requestAnimationFrame(() => {
            element.style.opacity = '1';
        });
    },

    // Fade out element
    fadeOut(element, duration = 300) {
        element.style.transition = `opacity ${duration}ms ease`;
        element.style.opacity = '0';

        setTimeout(() => {
            element.style.display = 'none';
        }, duration);
    },

    // Slide in from direction
    slideIn(element, direction = 'bottom', duration = 300) {
        const transforms = {
            top: 'translateY(-20px)',
            bottom: 'translateY(20px)',
            left: 'translateX(-20px)',
            right: 'translateX(20px)'
        };

        element.style.opacity = '0';
        element.style.transform = transforms[direction];
        element.style.transition = `opacity ${duration}ms ease, transform ${duration}ms ease`;

        requestAnimationFrame(() => {
            element.style.opacity = '1';
            element.style.transform = 'translate(0)';
        });
    },

    // Number counter animation
    countUp(element, target, duration = 1000) {
        const start = parseFloat(element.textContent) || 0;
        const startTime = performance.now();
        const isPrice = element.dataset.format === 'price';
        const decimals = isPrice ? 2 : (target.toString().includes('.') ? target.toString().split('.')[1].length : 0);

        const update = (currentTime) => {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = start + (target - start) * eased;

            if (isPrice) {
                element.textContent = '$' + current.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
            } else {
                element.textContent = current.toFixed(decimals);
            }

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        };

        requestAnimationFrame(update);
    },

    // Pulse effect
    pulse(element, color = 'var(--accent-blue)') {
        element.style.boxShadow = `0 0 0 0 ${color}`;
        element.style.transition = 'box-shadow 0.3s ease';

        requestAnimationFrame(() => {
            element.style.boxShadow = `0 0 0 4px transparent`;
        });
    },

    // Shake effect for errors
    shake(element) {
        element.classList.add('animate-shake');
        setTimeout(() => element.classList.remove('animate-shake'), 500);
    },

    // Highlight row for new data
    highlightRow(element, type = 'neutral') {
        element.classList.add(`highlight-${type}`);
        setTimeout(() => element.classList.remove(`highlight-${type}`), 1000);
    }
};

// ============================================
// NUMBER FORMATTING WITH MONOSPACE
// ============================================

const NumberFormat = {
    // Format price with proper styling
    price(value, element) {
        const formatted = parseFloat(value).toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        });

        if (element) {
            element.innerHTML = `<span class="num-mono">$${formatted}</span>`;
        }
        return `$${formatted}`;
    },

    // Format crypto amount
    crypto(value, element, decimals = 8) {
        const formatted = parseFloat(value).toFixed(decimals);

        if (element) {
            element.innerHTML = `<span class="num-mono">${formatted}</span>`;
        }
        return formatted;
    },

    // Format percentage
    percent(value, element, showSign = true) {
        const num = parseFloat(value);
        const sign = showSign && num > 0 ? '+' : '';
        const formatted = `${sign}${num.toFixed(2)}%`;

        if (element) {
            const colorClass = num > 0 ? 'num-positive' : num < 0 ? 'num-negative' : '';
            element.innerHTML = `<span class="num-mono ${colorClass}">${formatted}</span>`;
        }
        return formatted;
    },

    // Apply monospace to all number elements
    applyMonospace() {
        document.querySelectorAll('[data-num]').forEach(el => {
            el.classList.add('num-mono');
        });
    }
};

// ============================================
// INITIALIZE
// ============================================

document.addEventListener('DOMContentLoaded', () => {
    Toast.init();
    Loading.init();
    RichTooltip.init();
    NumberFormat.applyMonospace();

    // Add tooltips to existing elements
    addDefaultTooltips();
});

function addDefaultTooltips() {
    // Add tooltips to buttons and controls
    const tooltipData = {
        '#indicatorsBtn': { tooltip: 'Add technical indicators to the chart', title: 'Indicators' },
        '#chartTypeBtn': { tooltip: 'Change chart type (candles, line, area, etc.)', title: 'Chart Type' },
        '#orderBookToggle': { tooltip: 'Show or hide the order book panel', title: 'Order Book' },
        '#goToDateBtn': { tooltip: 'Navigate to a specific date on the chart', title: 'Go to Date' },
        '#startBot': { tooltip: 'Start the automated trading bot', title: 'Start Bot', footer: 'Uses ML signals for trading' },
        '#stopBot': { tooltip: 'Stop the automated trading bot', title: 'Stop Bot' }
    };

    Object.entries(tooltipData).forEach(([selector, data]) => {
        const el = document.querySelector(selector);
        if (el) {
            el.setAttribute('data-tooltip', data.tooltip);
            if (data.title) el.setAttribute('data-tooltip-title', data.title);
            if (data.footer) el.setAttribute('data-tooltip-footer', data.footer);
        }
    });
}

// Export for global use
window.Toast = Toast;
window.Loading = Loading;
window.Skeleton = Skeleton;
window.RichTooltip = RichTooltip;
window.EmptyState = EmptyState;
window.Animate = Animate;
window.NumberFormat = NumberFormat;
