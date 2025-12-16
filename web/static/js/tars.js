/**
 * TARS - Trading AI Response System
 * Frontend JavaScript for chat interface
 */

class TARSChat {
    constructor() {
        this.panel = document.getElementById('tarsPanel');
        this.messagesContainer = document.getElementById('tarsMessages');
        this.suggestionsContainer = document.getElementById('tarsSuggestions');
        this.input = document.getElementById('tarsInput');
        this.sendBtn = document.getElementById('tarsSendBtn');
        this.clearBtn = document.getElementById('tarsClearBtn');
        this.toggleBtn = document.getElementById('tarsToggle');
        this.statusIndicator = document.getElementById('tarsStatus');

        this.isOpen = false;
        this.isTyping = false;

        this.init();
    }

    init() {
        // Toggle panel
        this.toggleBtn?.addEventListener('click', () => this.togglePanel());

        // Send message
        this.sendBtn?.addEventListener('click', () => this.sendMessage());
        this.input?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // Clear chat
        this.clearBtn?.addEventListener('click', () => this.clearChat());

        // Suggestion buttons
        this.suggestionsContainer?.addEventListener('click', (e) => {
            if (e.target.classList.contains('suggestion-btn')) {
                const message = e.target.dataset.message;
                if (message) {
                    this.input.value = message;
                    this.sendMessage();
                }
            }
        });

        // Resize controls
        this.panel?.querySelectorAll('.resize-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const action = e.currentTarget.dataset.action;
                this.resizePanel(action);
            });
        });

        // Check TARS status
        this.checkStatus();
    }

    togglePanel() {
        this.isOpen = !this.isOpen;

        if (this.isOpen) {
            this.panel.style.display = 'flex';
            this.panel.dataset.state = 'default';
            this.toggleBtn.classList.add('active');
            this.input?.focus();
        } else {
            this.panel.dataset.state = 'hidden';
            setTimeout(() => {
                if (!this.isOpen) {
                    this.panel.style.display = 'none';
                }
            }, 300);
            this.toggleBtn.classList.remove('active');
        }
    }

    resizePanel(action) {
        this.panel.dataset.state = action;
    }

    async sendMessage() {
        const message = this.input.value.trim();
        if (!message || this.isTyping) return;

        // Add user message to chat
        this.addMessage(message, 'user');
        this.input.value = '';

        // Show typing indicator
        this.showTyping();

        try {
            // Build context from current chart state
            const context = this.buildContext();

            // Send to TARS API
            const response = await fetch('/api/tars/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: message,
                    context: context
                })
            });

            const data = await response.json();

            // Hide typing indicator
            this.hideTyping();

            // Add bot response
            this.addMessage(data.message, 'bot', data.actions);

            // Update suggestions
            this.updateSuggestions(data.suggestions);

            // Execute any actions
            if (data.actions && data.actions.length > 0) {
                this.executeActions(data.actions);
            }

        } catch (error) {
            this.hideTyping();
            this.addMessage('Sorry, I encountered an error. Please try again.', 'bot');
            console.error('TARS error:', error);
        }
    }

    buildContext() {
        // Get current chart/trading context
        const context = {};

        // Try to get current price from page
        const priceEl = document.getElementById('currentPrice');
        if (priceEl) {
            context.current_price = parseFloat(priceEl.textContent.replace(/[$,]/g, ''));
        }

        // Get current symbol
        const symbolEl = document.getElementById('currentSymbol');
        if (symbolEl) {
            context.symbol = symbolEl.textContent;
        }

        return context;
    }

    addMessage(text, sender, actions = []) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `tars-message tars-message-${sender}`;

        const avatar = sender === 'bot' ? '🤖' : '👤';
        const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

        // Format message text (handle markdown-like formatting)
        const formattedText = this.formatMessage(text);

        messageDiv.innerHTML = `
            <div class="message-avatar">${avatar}</div>
            <div class="message-content">
                <div class="message-text">${formattedText}</div>
                ${this.renderActions(actions)}
                <div class="message-time">${time}</div>
            </div>
        `;

        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatMessage(text) {
        // Convert markdown-like syntax to HTML
        return text
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Code
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // Line breaks
            .replace(/\n/g, '<br>')
            // Bullet points
            .replace(/^• /gm, '<li>')
            .replace(/<li>(.*?)(?=<br>|$)/g, '<li>$1</li>');
    }

    renderActions(actions) {
        if (!actions || actions.length === 0) return '';

        return actions.map(action => {
            let className = 'tars-action';
            let icon = '✓';

            if (action.action === 'place_order') {
                className += ' tars-action-warning';
                icon = '⚠️';
            } else if (action.action === 'draw_level' || action.action === 'draw_zone') {
                className += ' tars-action-info';
                icon = '📈';
            }

            return `<div class="${className}">${icon} ${action.action}: ${JSON.stringify(action.params)}</div>`;
        }).join('');
    }

    updateSuggestions(suggestions) {
        if (!suggestions || suggestions.length === 0) return;

        this.suggestionsContainer.innerHTML = suggestions.map(s =>
            `<button class="suggestion-btn" data-message="${s}">${s}</button>`
        ).join('');
    }

    executeActions(actions) {
        actions.forEach(action => {
            switch (action.action) {
                case 'draw_level':
                    this.drawLevel(action.params);
                    break;
                case 'draw_zone':
                    this.drawZone(action.params);
                    break;
                case 'set_alert':
                    this.setAlert(action.params);
                    break;
                case 'place_order':
                    // Orders require confirmation - don't auto-execute
                    this.showOrderConfirmation(action.params);
                    break;
            }
        });
    }

    drawLevel(params) {
        // Draw horizontal line on chart using state from trading.js
        const chart = window.state?.charts?.[0];
        const candleSeries = window.state?.candleSeries?.[0];

        if (chart && candleSeries) {
            try {
                // Map color names to hex
                const colorMap = {
                    'green': '#0ecb81',
                    'red': '#f6465d',
                    'blue': '#1e80ff',
                    'yellow': '#f0b90b',
                    'purple': '#8358ff',
                    'orange': '#ff6b00'
                };
                const lineColor = colorMap[params.color] || params.color || '#8358ff';

                // Create a price line on the candle series (more reliable)
                candleSeries.createPriceLine({
                    price: params.price,
                    color: lineColor,
                    lineWidth: 2,
                    lineStyle: 2, // Dashed
                    axisLabelVisible: true,
                    title: params.label || 'Level'
                });

                console.log('TARS drew level:', params);
                this.addMessage(`Drew ${params.label || 'level'} at $${params.price.toLocaleString()}`, 'bot');
            } catch (e) {
                console.error('Failed to draw level:', e);
                this.addMessage(`Failed to draw level: ${e.message}`, 'bot');
            }
        } else {
            console.warn('Chart not available for drawing');
            this.addMessage('Chart not ready - please try again in a moment', 'bot');
        }
    }

    drawZone(params) {
        // Draw zone as two horizontal lines (top and bottom)
        console.log('TARS drawing zone:', params);
        const zoneColor = params.color || 'blue';

        // Draw top and bottom lines silently (without extra messages)
        const chart = window.state?.charts?.[0];
        const candleSeries = window.state?.candleSeries?.[0];

        if (chart && candleSeries) {
            const colorMap = {
                'green': '#0ecb81',
                'red': '#f6465d',
                'blue': '#1e80ff',
                'yellow': '#f0b90b',
                'purple': '#8358ff',
                'orange': '#ff6b00'
            };
            const lineColor = colorMap[zoneColor] || zoneColor || '#1e80ff';

            try {
                // Draw top line
                candleSeries.createPriceLine({
                    price: params.top,
                    color: lineColor,
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: `${params.label || 'Zone'} Top`
                });

                // Draw bottom line
                candleSeries.createPriceLine({
                    price: params.bottom,
                    color: lineColor,
                    lineWidth: 1,
                    lineStyle: 2,
                    axisLabelVisible: true,
                    title: `${params.label || 'Zone'} Bottom`
                });

                console.log('TARS drew zone:', params);
                this.addMessage(`Drew ${params.label || 'zone'}: $${params.bottom.toLocaleString()} - $${params.top.toLocaleString()}`, 'bot');
            } catch (e) {
                console.error('Failed to draw zone:', e);
            }
        }
    }

    setAlert(params) {
        console.log('TARS setting alert:', params);
        // Store alert in localStorage or send to backend
        const alerts = JSON.parse(localStorage.getItem('tars_alerts') || '[]');
        alerts.push({
            ...params,
            created: new Date().toISOString()
        });
        localStorage.setItem('tars_alerts', JSON.stringify(alerts));

        // Show notification
        if (Notification.permission === 'granted') {
            new Notification('TARS Alert Set', {
                body: `Alert for ${params.symbol} ${params.condition} $${params.price}`,
                icon: '/static/img/tars-icon.png'
            });
        }
    }

    showOrderConfirmation(params) {
        // Show confirmation dialog before executing order
        const confirmed = confirm(
            `TARS wants to place an order:\n\n` +
            `${params.side.toUpperCase()} ${params.amount} ${params.symbol}\n` +
            `Type: ${params.type}\n` +
            `Mode: ${params.paper ? 'PAPER (simulated)' : 'LIVE (real money!)'}\n\n` +
            `Confirm?`
        );

        if (confirmed) {
            this.input.value = 'confirm';
            this.sendMessage();
        } else {
            this.input.value = 'cancel';
            this.sendMessage();
        }
    }

    showTyping() {
        this.isTyping = true;
        const typingDiv = document.createElement('div');
        typingDiv.className = 'tars-message tars-message-bot';
        typingDiv.id = 'tarsTyping';
        typingDiv.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <div class="message-text">
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
            </div>
        `;
        this.messagesContainer.appendChild(typingDiv);
        this.scrollToBottom();
    }

    hideTyping() {
        this.isTyping = false;
        const typingEl = document.getElementById('tarsTyping');
        if (typingEl) {
            typingEl.remove();
        }
    }

    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }

    async clearChat() {
        try {
            await fetch('/api/tars/clear', { method: 'POST' });

            // Keep only the welcome message
            const welcomeMsg = this.messagesContainer.querySelector('.tars-message');
            this.messagesContainer.innerHTML = '';
            if (welcomeMsg) {
                this.messagesContainer.appendChild(welcomeMsg.cloneNode(true));
            }

            // Reset suggestions
            this.suggestionsContainer.innerHTML = `
                <button class="suggestion-btn" data-message="BTC price">BTC price</button>
                <button class="suggestion-btn" data-message="List strategies">Strategies</button>
                <button class="suggestion-btn" data-message="Explain ICT">ICT concepts</button>
                <button class="suggestion-btn" data-message="Market analysis">Analysis</button>
            `;
        } catch (error) {
            console.error('Failed to clear chat:', error);
        }
    }

    async checkStatus() {
        try {
            const response = await fetch('/api/tars/status');
            const data = await response.json();

            if (data.status === 'online') {
                this.statusIndicator.style.color = '#0ecb81';
                this.statusIndicator.title = `TARS online (${data.provider})`;
            } else {
                this.statusIndicator.style.color = '#f6465d';
                this.statusIndicator.title = 'TARS offline';
            }
        } catch (error) {
            this.statusIndicator.style.color = '#f6465d';
            console.error('TARS status check failed:', error);
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.tarsChat = new TARSChat();
});
