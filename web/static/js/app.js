/**
 * Robo Trader Dashboard Application
 */

// Register crosshair plugin if available
if (typeof crosshairPlugin !== 'undefined') {
    Chart.register(crosshairPlugin);
}

// Register current price line plugin if available
if (typeof currentPriceLinePlugin !== 'undefined') {
    Chart.register(currentPriceLinePlugin);
}

class RoboTrader {
    constructor() {
        this.ws = null;
        this.priceChart = null;
        this.currentSymbol = 'BTC/USD';
        this.currentTimeframe = '1h';
        this.currentChartType = 'line';
        this.currentTimezone = 'local';
        this.priceData = [];
        this.drIdrData = null;  // DR/IDR indicator data
        this.showDrIdr = false;  // Toggle for DR/IDR display - disabled

        // ICT Indicators state
        this.ictData = null;  // ICT indicators data
        this.ictToggles = {
            fvg: false,           // Fair Value Gaps
            mss: false,           // Market Structure Shift
            orderBlocks: false,   // Order Blocks
            breakerBlocks: false, // Breaker Blocks
            ote: false,           // OTE Levels
            liquidity: false,     // Liquidity Zones
            premiumDiscount: false, // Premium/Discount Zones
            displacement: false,  // Displacement candles
            bias: true            // Trading Bias (default on)
        };

        this.isTrading = false;
        this.tradingMode = 'paper';
        this.dataLimit = 100;  // Number of candles to load
        this.daysBack = 0;  // Number of days of historical data (0 = use dataLimit)

        // Live candle tracking
        this.liveCandle = null;  // Current forming candle
        this.lastTickPrice = null;  // Last tick price
        this.candleIntervalMs = this.getTimeframeMs(this.currentTimeframe);

        // Throttling for high-frequency WebSocket updates
        this.lastChartUpdate = 0;
        this.chartUpdateThrottle = 100;  // Min 100ms between chart updates (10 fps max)
        this.pendingChartUpdate = null;
        this.tickCount = 0;  // Count ticks for debug

        // Database page state
        this.dbCurrentTable = 'candle_snapshots';
        this.dbCurrentPage = 1;
        this.dbPageSize = 100;
        this.dbTotalRows = 0;

        this.init();
    }

    // Convert timeframe to milliseconds
    getTimeframeMs(timeframe) {
        const map = {
            '5m': 5 * 60 * 1000,
            '15m': 15 * 60 * 1000,
            '30m': 30 * 60 * 1000,
            '1h': 60 * 60 * 1000,
            '4h': 4 * 60 * 60 * 1000,
            '1d': 24 * 60 * 60 * 1000
        };
        return map[timeframe] || 60 * 60 * 1000;
    }

    // Get the start time for current candle period
    getCurrentCandleStartTime() {
        const now = Date.now();
        const interval = this.candleIntervalMs;
        return Math.floor(now / interval) * interval;
    }

    init() {
        this.setupNavigation();
        this.setupWebSocket();
        this.setupEventListeners();
        this.initChart();
        this.loadInitialData();

        // WebSocket handles real-time price updates
        // HTTP polling handles chart data (respects selected timeframe)
        setInterval(() => this.loadPriceData(), 10000);  // Chart every 10 seconds
        setInterval(() => {
            this.loadSignal();
            this.loadIndicators();
        }, 15000);  // Signal/indicators every 15 seconds
    }

    // Navigation
    setupNavigation() {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                e.preventDefault();
                const page = item.dataset.page;
                this.showPage(page);
            });
        });
    }

    showPage(pageName) {
        // Update nav
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.toggle('active', item.dataset.page === pageName);
        });

        // Update pages
        document.querySelectorAll('.page').forEach(page => {
            page.classList.toggle('active', page.id === `page-${pageName}`);
        });

        // Update title
        const titles = {
            dashboard: 'Dashboard',
            trade: 'Trade',
            backtest: 'Backtest',
            train: 'Train Model',
            history: 'Trade History',
            database: 'Database',
            ict: 'ICT Strategy',
            mllogic: 'ML Logic',
            mlmodels: 'ML Models',
            settings: 'Settings'
        };
        document.getElementById('pageTitle').textContent = titles[pageName] || 'Dashboard';

        // Load page-specific data
        if (pageName === 'history') {
            this.loadTradeHistory();
        } else if (pageName === 'database') {
            this.loadDatabaseData();
            this.loadPredictionAccuracy();
        } else if (pageName === 'ict') {
            this.loadIctData();
        } else if (pageName === 'trade') {
            this.loadAllBotStatuses();
        }
    }

    // WebSocket
    setupWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;

        this.ws = new WebSocket(wsUrl);

        this.ws.onopen = () => {
            this.updateConnectionStatus(true);
            this.log('Connected to server', 'success');
        };

        this.ws.onclose = () => {
            this.updateConnectionStatus(false);
            this.log('Disconnected from server', 'warning');
            // Reconnect after 5 seconds
            setTimeout(() => this.setupWebSocket(), 5000);
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            // Debug: log incoming WebSocket messages (throttled to avoid console spam)
            if (data.type === 'ticker') {
                this.tickCount++;
                // Only log every 10th tick to avoid spam during high-frequency updates
                if (this.tickCount % 10 === 0) {
                    const source = data.source === 'websocket' ? 'WS-RT' : 'REST';
                    console.log(`[${source}] Price: $${data.price?.toLocaleString()} (tick #${this.tickCount})`);
                }
            }
            this.handleWebSocketMessage(data);
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };

        // Keep connection alive
        setInterval(() => {
            if (this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'ping' }));
            }
        }, 30000);
    }

    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'ticker':
                // Real-time price update (every 1 second)
                this.updateTickerDisplay(data);
                break;
            case 'candles':
                // Ignore WebSocket candles - we use HTTP to respect selected timeframe
                break;
            case 'signal':
                // ML signal and indicators (every 5 seconds)
                this.updateSignalFromWebSocket(data);
                break;
            case 'account':
                // Account/portfolio data (every 2 seconds)
                this.updateAccountFromWebSocket(data);
                break;
            case 'update':
                this.updatePriceDisplay(data);
                this.updateSignalDisplay(data);
                break;
            case 'status':
                this.updateTradingStatus(data);
                break;
            case 'training':
                this.updateTrainingStatus(data);
                break;
            case 'trade':
                this.log(`Trade: ${data.side.toUpperCase()} ${data.amount} ${data.symbol} @ $${data.price}`,
                    data.side === 'buy' ? 'success' : 'info');
                break;
        }
    }

    // Handle real-time ticker updates from WebSocket (every 1 second)
    updateTickerDisplay(data) {
        const priceEl = document.getElementById('currentPrice');
        if (!priceEl) return;

        const oldPrice = parseFloat(priceEl.textContent.replace(/[$,]/g, '')) || 0;
        const newPrice = data.price;

        if (newPrice) {
            // Live candle feature disabled - causes rendering issues with candlestick chart
            // this.updateLiveCandle(newPrice);

            // Update current price line on chart (with exchange timestamp for accuracy)
            this.updateCurrentPriceLine(newPrice, oldPrice, data.exchange_ts);

            // Update price display and flash effect only on change
            if (newPrice !== oldPrice) {
                priceEl.textContent = this.formatCurrency(newPrice);

                // Flash effect on price change
                priceEl.classList.remove('price-up', 'price-down');
                priceEl.classList.add(newPrice > oldPrice ? 'price-up' : 'price-down');
                setTimeout(() => priceEl.classList.remove('price-up', 'price-down'), 300);
            }
        }
    }

    // Update the current price line on the chart (throttled for high-frequency updates)
    updateCurrentPriceLine(newPrice, oldPrice, exchangeTs) {
        if (!this.priceChart || !this.priceChart.currentPriceData) return;

        const priceData = this.priceChart.currentPriceData;
        priceData.previousPrice = priceData.price;
        priceData.price = newPrice;
        priceData.isUp = newPrice >= (oldPrice || newPrice);
        priceData.timezone = this.currentTimezone;  // Pass selected timezone
        priceData.exchangeTs = exchangeTs;  // Exchange timestamp (ms) for accurate time display

        // Throttle chart updates to avoid overwhelming the browser during high-frequency updates
        const now = Date.now();
        if (now - this.lastChartUpdate >= this.chartUpdateThrottle) {
            // Enough time has passed, update immediately
            this.lastChartUpdate = now;
            this.priceChart.update('none');
        } else if (!this.pendingChartUpdate) {
            // Schedule an update for when throttle period ends
            const delay = this.chartUpdateThrottle - (now - this.lastChartUpdate);
            this.pendingChartUpdate = setTimeout(() => {
                this.pendingChartUpdate = null;
                this.lastChartUpdate = Date.now();
                if (this.priceChart) {
                    this.priceChart.update('none');
                }
            }, delay);
        }
        // If there's already a pending update, it will use the latest price data
    }

    // Update or create the live (forming) candle
    updateLiveCandle(price) {
        if (!this.priceData || this.priceData.length === 0) {
            console.log('[LiveCandle] No price data yet');
            return;
        }

        const now = Date.now();
        const currentCandleStart = this.getCurrentCandleStartTime();
        const lastCandle = this.priceData[this.priceData.length - 1];
        const lastCandleTime = new Date(lastCandle.time).getTime();

        // Check if we need to create a new live candle
        if (!this.liveCandle || this.liveCandle.startTime !== currentCandleStart) {
            // Create new live candle
            this.liveCandle = {
                startTime: currentCandleStart,
                time: new Date(currentCandleStart).toISOString(),
                open: price,
                high: price,
                low: price,
                close: price,
                isLive: true
            };
            console.log(`[LiveCandle] Created new candle at ${new Date(currentCandleStart).toLocaleTimeString()}, price: $${price}`);
        } else {
            // Update existing live candle
            this.liveCandle.high = Math.max(this.liveCandle.high, price);
            this.liveCandle.low = Math.min(this.liveCandle.low, price);
            this.liveCandle.close = price;
        }

        this.lastTickPrice = price;

        // Update chart with live candle
        this.updateChartWithLiveCandle();
    }

    // Update chart to include live candle
    updateChartWithLiveCandle() {
        if (!this.priceChart || !this.liveCandle || !this.priceData.length) {
            console.log('[LiveCandle] Chart update skipped - missing data');
            return;
        }

        // Get timezone for display
        const zone = this.currentTimezone === 'local'
            ? luxon.DateTime.local().zoneName
            : this.currentTimezone;

        if (this.currentChartType === 'candle') {
            // For candlestick chart
            const dataset = this.priceChart.data.datasets[0];
            if (!dataset || !dataset.data) return;

            // Check if last data point is our live candle (by timestamp)
            const liveTime = this.liveCandle.startTime;
            const lastDataPoint = dataset.data[dataset.data.length - 1];

            if (lastDataPoint && lastDataPoint.x === liveTime) {
                // Update existing live candle
                lastDataPoint.o = this.liveCandle.open;
                lastDataPoint.h = this.liveCandle.high;
                lastDataPoint.l = this.liveCandle.low;
                lastDataPoint.c = this.liveCandle.close;
            } else {
                // Add new live candle
                dataset.data.push({
                    x: liveTime,
                    o: this.liveCandle.open,
                    h: this.liveCandle.high,
                    l: this.liveCandle.low,
                    c: this.liveCandle.close
                });

                // Update x-axis max to show live candle
                this.priceChart.options.scales.x.max = liveTime;
            }
        } else {
            // For line chart
            const dataset = this.priceChart.data.datasets[0];
            const labels = this.priceChart.data.labels;
            if (!dataset || !labels) return;

            const liveTime = new Date(this.liveCandle.startTime);
            const lastLabel = labels[labels.length - 1];
            const lastLabelTime = lastLabel ? lastLabel.getTime() : 0;

            if (lastLabelTime === this.liveCandle.startTime) {
                // Update existing live point
                dataset.data[dataset.data.length - 1] = this.liveCandle.close;
            } else {
                // Add new live point
                labels.push(liveTime);
                dataset.data.push(this.liveCandle.close);

                // Update x-axis max to show live point
                this.priceChart.options.scales.x.max = this.liveCandle.startTime;
            }
        }

        // Update chart without animation for smooth tick updates
        this.priceChart.update('none');
    }

    // Handle candle data from WebSocket (every 5 seconds)
    updateCandlesFromWebSocket(data) {
        if (data.data && data.data.length > 0) {
            this.priceData = data.data;
            this.updateChart();
        }
    }

    // Handle signal and indicators from WebSocket (every 5 seconds)
    updateSignalFromWebSocket(data) {
        // Update signal badge
        const signalBadge = document.querySelector('.signal-badge');
        if (signalBadge) {
            const signal = data.signal?.toLowerCase() || 'hold';
            signalBadge.textContent = signal.toUpperCase();
            signalBadge.className = `signal-badge ${signal}`;
        }

        // Update confidence
        const confidence = (data.confidence * 100).toFixed(0);
        const confidenceFill = document.getElementById('confidenceFill');
        const confidenceValue = document.getElementById('confidenceValue');
        if (confidenceFill) confidenceFill.style.width = confidence + '%';
        if (confidenceValue) confidenceValue.textContent = confidence + '%';

        // Update indicators
        if (data.indicators) {
            const rsiEl = document.getElementById('rsiValue');
            const macdEl = document.getElementById('macdValue');
            const volumeEl = document.getElementById('volumeValue');

            if (rsiEl && data.indicators.rsi_14 != null) {
                rsiEl.textContent = data.indicators.rsi_14.toFixed(2);
            }
            if (macdEl && data.indicators.macd != null) {
                macdEl.textContent = data.indicators.macd.toFixed(4);
            }
            if (volumeEl && data.indicators.volume_ratio != null) {
                volumeEl.textContent = data.indicators.volume_ratio.toFixed(2) + 'x';
            }
        }
    }

    // Handle account data from WebSocket (every 2 seconds)
    updateAccountFromWebSocket(data) {
        const portfolioEl = document.getElementById('portfolioValue');
        const totalPnlEl = document.getElementById('totalPnl');
        const dailyPnlEl = document.getElementById('dailyPnl');
        const positionsEl = document.getElementById('openPositions');

        if (portfolioEl && data.equity != null) {
            portfolioEl.textContent = this.formatCurrency(data.equity);
        }
        if (totalPnlEl && data.total_pnl != null) {
            totalPnlEl.textContent = this.formatCurrency(data.total_pnl);
            totalPnlEl.className = `stat-value ${data.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
        }
        if (dailyPnlEl && data.daily_pnl != null) {
            dailyPnlEl.textContent = this.formatCurrency(data.daily_pnl);
            dailyPnlEl.className = `stat-value ${data.daily_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
        }
        if (positionsEl && data.positions != null) {
            positionsEl.textContent = data.positions;
        }
    }

    updateConnectionStatus(connected) {
        const statusEl = document.getElementById('connectionStatus');
        const dot = statusEl.querySelector('.status-dot');
        const text = statusEl.querySelector('span:last-child');

        dot.classList.toggle('connected', connected);
        text.textContent = connected ? 'Connected' : 'Disconnected';
    }

    // Event Listeners
    setupEventListeners() {
        // Symbol select
        document.getElementById('symbolSelect').addEventListener('change', (e) => {
            this.currentSymbol = e.target.value;
            this.loadPriceData();
            this.loadSignal();
            this.loadIndicators();
        });

        // Timezone select
        document.getElementById('timezoneSelect').addEventListener('change', (e) => {
            this.currentTimezone = e.target.value;
            this.updateChartTimezone();
            this.updateChart();
        });

        // Trading mode toggle
        document.querySelectorAll('.toggle-btn[data-mode]').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.toggle-btn[data-mode]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.tradingMode = btn.dataset.mode;
            });
        });

        // Start trading (if trading controls exist)
        document.getElementById('startTrading')?.addEventListener('click', () => this.startTrading());
        document.getElementById('stopTrading')?.addEventListener('click', () => this.stopTrading());

        // Scalping bot controls
        document.getElementById('startScalping')?.addEventListener('click', () => this.startScalpingBot());
        document.getElementById('pauseScalping')?.addEventListener('click', () => this.pauseScalpingBot());
        document.getElementById('stopScalping')?.addEventListener('click', () => this.stopScalpingBot());

        // Trading mode selector
        this.initTradingModeSelector();

        // Confluence selector
        this.initConfluenceSelector();

        // Trading strategy tabs
        this.initTradingTabs();

        // Initialize other bot controls
        this.initBotControls();

        // Initialize the Live Bot Monitor
        this.initBotMonitor();

        // Start scalping status polling when on trade page
        setInterval(() => {
            if (document.getElementById('page-trade')?.classList.contains('active')) {
                this.loadScalpingStatus();
            }
        }, 3000);

        // Backtest
        document.getElementById('runBacktest').addEventListener('click', () => this.runBacktest());

        // Train model
        document.getElementById('trainModel').addEventListener('click', () => this.trainModel());

        // Chart timeframe buttons
        document.querySelectorAll('.timeframe-group .btn-sm').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.timeframe-group .btn-sm').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentTimeframe = btn.dataset.timeframe || '1h';
                // Update candle interval for live candle tracking
                this.candleIntervalMs = this.getTimeframeMs(this.currentTimeframe);
                this.liveCandle = null;  // Reset live candle
                this.loadPriceData();
                this.loadIndicators();
            });
        });

        // Chart type buttons (line/candle)
        document.querySelectorAll('.chart-type-group .btn-sm').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.chart-type-group .btn-sm').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.currentChartType = btn.dataset.charttype || 'line';
                this.updateChart();
            });
        });

        // Reset zoom button
        document.getElementById('resetZoom')?.addEventListener('click', () => {
            if (this.priceChart) {
                this.priceChart.resetZoom();
            }
        });

        // History range selector
        document.getElementById('historyRange')?.addEventListener('change', (e) => {
            this.daysBack = parseInt(e.target.value) || 0;
            if (this.daysBack > 0) {
                // Warn about limitations for small timeframes
                if (this.daysBack > 7 && ['5m', '15m'].includes(this.currentTimeframe)) {
                    this.log(`Note: ${this.currentTimeframe} data is limited to ~2-3 days on Kraken. Use 1H or 1D for longer history.`, 'warning');
                } else if (this.daysBack > 30 && this.currentTimeframe === '30m') {
                    this.log(`Note: 30M data is limited on Kraken. Use 1H or 1D for longer history.`, 'warning');
                }
                this.log(`Loading ${this.daysBack} days of history...`, 'info');
            }
            this.loadPriceData();
        });

        // Signal tab switching
        document.querySelectorAll('.signal-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.tab;
                // Update tab buttons
                document.querySelectorAll('.signal-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                // Update tab content
                document.querySelectorAll('.signal-tab-content').forEach(c => c.classList.remove('active'));
                document.getElementById(`tab-${tabName}`)?.classList.add('active');
            });
        });

        // Database page event listeners
        document.getElementById('dbTableSelect')?.addEventListener('change', (e) => {
            this.dbCurrentTable = e.target.value;
            this.dbCurrentPage = 1;
            this.loadDatabaseData();
        });

        document.getElementById('dbRefreshBtn')?.addEventListener('click', () => {
            this.loadDatabaseData();
        });

        document.getElementById('dbApplyFilters')?.addEventListener('click', () => {
            this.dbCurrentPage = 1;
            this.loadDatabaseData();
        });

        document.getElementById('dbClearFilters')?.addEventListener('click', () => {
            document.getElementById('dbFilterSymbol').value = '';
            document.getElementById('dbFilterPrediction').value = '';
            document.getElementById('dbFilterStartDate').value = '';
            document.getElementById('dbFilterEndDate').value = '';
            document.getElementById('dbFilterLimit').value = '100';
            this.dbCurrentPage = 1;
            this.loadDatabaseData();
        });

        document.getElementById('dbFilterLimit')?.addEventListener('change', (e) => {
            this.dbPageSize = parseInt(e.target.value);
        });

        document.getElementById('dbPrevPage')?.addEventListener('click', () => {
            if (this.dbCurrentPage > 1) {
                this.dbCurrentPage--;
                this.loadDatabaseData();
            }
        });

        document.getElementById('dbNextPage')?.addEventListener('click', () => {
            const maxPages = Math.ceil(this.dbTotalRows / this.dbPageSize);
            if (this.dbCurrentPage < maxPages) {
                this.dbCurrentPage++;
                this.loadDatabaseData();
            }
        });

        // Prediction Accuracy event listeners
        document.getElementById('refreshAccuracy')?.addEventListener('click', () => {
            this.loadPredictionAccuracy();
        });

        document.getElementById('accuracyDays')?.addEventListener('change', () => {
            this.loadPredictionAccuracy();
        });

        document.getElementById('validatePending')?.addEventListener('click', () => {
            this.validatePendingPredictions();
        });

        // Database page tab switching
        document.querySelectorAll('.db-page-tab').forEach(tab => {
            tab.addEventListener('click', () => {
                const tabName = tab.dataset.dbTab;
                // Update tab buttons
                document.querySelectorAll('.db-page-tab').forEach(t => t.classList.remove('active'));
                tab.classList.add('active');
                // Update tab content
                document.querySelectorAll('.db-tab-content').forEach(c => c.classList.remove('active'));
                document.getElementById(`db-tab-${tabName}`)?.classList.add('active');

                // Load accuracy data when switching to accuracy tab
                if (tabName === 'accuracy') {
                    this.loadPredictionAccuracy();
                }
                // Load levels data when switching to levels tab
                if (tabName === 'levels') {
                    this.loadOrderBlocksAndLevels();
                }
            });
        });

        // Export CSV button
        document.getElementById('dbExportBtn')?.addEventListener('click', () => {
            this.exportDatabaseToCSV();
        });

        // Refresh Levels button
        document.getElementById('refreshLevels')?.addEventListener('click', () => {
            this.loadOrderBlocksAndLevels();
        });

        // ICT Strategy event listeners
        document.getElementById('refreshIctSignal')?.addEventListener('click', () => {
            this.loadIctData();
        });

        document.getElementById('runIctBacktest')?.addEventListener('click', () => {
            this.runIctBacktest();
        });

        // SMT Divergence refresh
        document.getElementById('refreshSmt')?.addEventListener('click', () => {
            this.loadSmtDivergence();
        });

        // MTF Analysis refresh
        document.getElementById('refreshMtf')?.addEventListener('click', () => {
            this.loadMtfAnalysis();
        });

        // MTF tabs switching
        document.querySelectorAll('.mtf-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const targetTab = e.target.dataset.mtfTab;

                // Update tab buttons
                document.querySelectorAll('.mtf-tab').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');

                // Update tab content
                document.querySelectorAll('.mtf-tab-content').forEach(content => {
                    content.classList.remove('active');
                });

                if (targetTab === 'analysis') {
                    document.getElementById('mtfAnalysisTab')?.classList.add('active');
                } else if (targetTab === 'reasoning') {
                    document.getElementById('mtfReasoningTab')?.classList.add('active');
                }
            });
        });

        // Confluence tabs switching
        document.querySelectorAll('.confluence-tab').forEach(tab => {
            tab.addEventListener('click', (e) => {
                const targetTab = e.target.dataset.tab;

                // Update tab buttons
                document.querySelectorAll('.confluence-tab').forEach(t => t.classList.remove('active'));
                e.target.classList.add('active');

                // Update tab content
                document.querySelectorAll('.confluence-tab-content').forEach(content => {
                    content.classList.remove('active');
                });

                if (targetTab === 'factors') {
                    document.getElementById('confluenceFactorsTab')?.classList.add('active');
                } else if (targetTab === 'explanation') {
                    document.getElementById('confluenceExplanationTab')?.classList.add('active');
                }
            });
        });
    }

    // Export database data to CSV
    exportDatabaseToCSV() {
        const table = document.getElementById('dbDataTable');
        if (!table) return;

        const rows = [];
        const headers = [];

        // Get headers
        const thead = table.querySelector('thead tr');
        if (thead) {
            thead.querySelectorAll('th').forEach(th => {
                headers.push(th.textContent);
            });
            rows.push(headers.join(','));
        }

        // Get data rows
        const tbody = table.querySelector('tbody');
        if (tbody) {
            tbody.querySelectorAll('tr:not(.empty-row)').forEach(tr => {
                const rowData = [];
                tr.querySelectorAll('td').forEach(td => {
                    // Escape commas and quotes in cell content
                    let cellText = td.getAttribute('title') || td.textContent;
                    if (cellText.includes(',') || cellText.includes('"') || cellText.includes('\n')) {
                        cellText = '"' + cellText.replace(/"/g, '""') + '"';
                    }
                    rowData.push(cellText);
                });
                rows.push(rowData.join(','));
            });
        }

        if (rows.length <= 1) {
            this.log('No data to export', 'warning');
            return;
        }

        // Create and download CSV file
        const csvContent = rows.join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        const timestamp = new Date().toISOString().slice(0, 19).replace(/[:-]/g, '');
        link.href = URL.createObjectURL(blob);
        link.download = `${this.dbCurrentTable}_${timestamp}.csv`;
        link.style.display = 'none';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

        this.log(`Exported ${rows.length - 1} rows to CSV`, 'success');
    }

    // Chart
    initChart() {
        this.createChart('line');
    }

    // Create or recreate chart with specific type
    createChart(chartType) {
        const ctx = document.getElementById('priceChart').getContext('2d');

        // Destroy existing chart if it exists
        if (this.priceChart) {
            this.priceChart.destroy();
        }

        // Get timezone for adapter
        let zone = this.currentTimezone === 'local'
            ? luxon.DateTime.local().zoneName
            : this.currentTimezone;

        const commonOptions = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    mode: 'index',
                    intersect: false,
                    backgroundColor: '#1e1e2d',
                    titleColor: '#fff',
                    bodyColor: '#8b8b9e',
                    borderColor: '#2a2a3d',
                    borderWidth: 1
                },
                annotation: {
                    annotations: {}  // DR/IDR lines will be added here
                },
                zoom: {
                    pan: {
                        enabled: true,
                        mode: 'x',  // Pan only horizontally
                        threshold: 5  // Minimum pixels to move before panning
                    },
                    zoom: {
                        wheel: {
                            enabled: true,  // Enable mouse wheel zoom
                            speed: 0.05  // Slower zoom for better control
                        },
                        pinch: {
                            enabled: true  // Enable pinch zoom on touch devices
                        },
                        mode: 'x'  // Zoom only horizontally
                    },
                    limits: {
                        x: {
                            minRange: 3600000  // Minimum 1 hour range to prevent over-zoom
                        }
                    }
                }
            },
            scales: {
                x: {
                    type: 'time',
                    time: {
                        displayFormats: {
                            minute: 'HH:mm',
                            hour: 'HH:mm',
                            day: 'MMM dd'
                        },
                        tooltipFormat: 'MMM dd, yyyy HH:mm'
                    },
                    adapters: {
                        date: {
                            zone: zone
                        }
                    },
                    grid: {
                        color: '#2a2a3d'
                    },
                    ticks: {
                        color: '#8b8b9e',
                        maxRotation: 0
                    },
                    offset: false,  // No extra padding on sides
                    bounds: 'ticks',  // Fit to tick marks
                    min: undefined,  // Will be set dynamically
                    max: undefined   // Will be set dynamically
                },
                y: {
                    grid: {
                        color: '#2a2a3d'
                    },
                    ticks: {
                        color: '#8b8b9e',
                        callback: (value) => '$' + value.toLocaleString()
                    }
                }
            },
            interaction: {
                mode: 'nearest',
                axis: 'x',
                intersect: false
            },
            layout: {
                padding: {
                    right: 10,  // Minimal padding
                    bottom: 5
                }
            }
        };

        if (chartType === 'candle') {
            // Candlestick chart using chartjs-chart-financial
            // Enable zoom with same settings as line chart for consistent behavior
            const candleOptions = JSON.parse(JSON.stringify(commonOptions));

            this.priceChart = new Chart(ctx, {
                type: 'candlestick',
                data: {
                    datasets: [{
                        label: 'BTC/USD',
                        data: [],
                        barThickness: 'flex'  // Allow flexible bar width
                    }]
                },
                options: {
                    ...candleOptions,
                    plugins: {
                        ...candleOptions.plugins,
                        tooltip: {
                            ...candleOptions.plugins.tooltip,
                            callbacks: {
                                label: (context) => {
                                    const point = context.raw;
                                    if (!point) return '';
                                    return [
                                        `Open: $${point.o?.toLocaleString() || '--'}`,
                                        `High: $${point.h?.toLocaleString() || '--'}`,
                                        `Low: $${point.l?.toLocaleString() || '--'}`,
                                        `Close: $${point.c?.toLocaleString() || '--'}`
                                    ];
                                }
                            }
                        }
                    }
                }
            });
        } else {
            // Line chart
            this.priceChart = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [{
                        label: 'Price',
                        data: [],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointRadius: 0,
                        pointHoverRadius: 4
                    }]
                },
                options: commonOptions
            });
        }
    }

    // Update chart timezone
    updateChartTimezone() {
        // Get the timezone string for Luxon
        let zone;
        if (this.currentTimezone === 'local') {
            zone = luxon.DateTime.local().zoneName;  // Get actual local timezone name
        } else {
            zone = this.currentTimezone;
        }

        // Recreate the chart with the new timezone
        this.createChart(this.currentChartType);

        // Update timezone display in header if exists
        const tzLabels = {
            'local': 'Local',
            'Europe/London': 'London',
            'America/New_York': 'New York',
            'Asia/Tokyo': 'Tokyo'
        };

        console.log(`Timezone changed to: ${tzLabels[this.currentTimezone] || this.currentTimezone} (${zone})`);
    }

    // Update chart based on type (line or candlestick)
    updateChart() {
        if (!this.priceData || this.priceData.length === 0) return;

        // Check if we need to recreate the chart (type changed)
        const currentType = this.priceChart?.config?.type;
        const needsRecreate = (this.currentChartType === 'candle' && currentType !== 'candlestick') ||
                              (this.currentChartType === 'line' && currentType !== 'line');

        if (needsRecreate) {
            this.createChart(this.currentChartType);
        }

        // Convert timestamps to the selected timezone using Luxon
        const labels = this.priceData.map(d => {
            const dt = luxon.DateTime.fromISO(d.time, { zone: 'UTC' });
            return dt.toJSDate();
        });

        // Get first and last timestamps for x-axis bounds
        const firstTime = labels[0]?.getTime();
        const lastTime = labels[labels.length - 1]?.getTime();

        if (this.currentChartType === 'candle') {
            // Candlestick chart data format for chartjs-chart-financial
            const candleData = this.priceData.map(d => ({
                x: luxon.DateTime.fromISO(d.time, { zone: 'UTC' }).toJSDate().getTime(),
                o: d.open,
                h: d.high,
                l: d.low,
                c: d.close
            }));

            this.priceChart.data.datasets[0].data = candleData;
            this.priceChart.data.datasets[0].label = this.currentSymbol;

            // Set candlestick colors
            this.priceChart.data.datasets[0].color = {
                up: '#22c55e',       // Green for bullish
                down: '#ef4444',     // Red for bearish
                unchanged: '#999999'
            };
            this.priceChart.data.datasets[0].borderColor = {
                up: '#22c55e',
                down: '#ef4444',
                unchanged: '#999999'
            };
        } else {
            // Line chart
            const prices = this.priceData.map(d => d.close);

            this.priceChart.data.labels = labels;
            this.priceChart.data.datasets[0].data = prices;
        }

        // Set x-axis bounds to fit data tightly (remove empty space on right)
        if (firstTime && lastTime) {
            this.priceChart.options.scales.x.min = firstTime;
            this.priceChart.options.scales.x.max = lastTime;
        }

        // Initialize current price line with latest close price
        if (this.priceData.length > 0 && this.priceChart.currentPriceData) {
            const lastCandle = this.priceData[this.priceData.length - 1];
            const prevCandle = this.priceData.length > 1 ? this.priceData[this.priceData.length - 2] : lastCandle;
            this.priceChart.currentPriceData.price = lastCandle.close;
            this.priceChart.currentPriceData.previousPrice = prevCandle.close;
            this.priceChart.currentPriceData.isUp = lastCandle.close >= prevCandle.close;
        }

        this.priceChart.update('none'); // 'none' for no animation during updates
    }

    // Data Loading
    async loadInitialData() {
        await Promise.all([
            this.loadAccountData(),
            this.loadPriceData(),
            this.loadSignal(),
            this.loadIndicators(),
            this.loadPositions(),
            this.loadStatus()
        ]);
    }

    async refreshData() {
        await Promise.all([
            this.loadAccountData(),
            this.loadPriceData(),  // Now includes chart updates
            this.loadSignal(),
            this.loadIndicators(),
            this.loadPositions()
        ]);
    }

    async loadAccountData() {
        try {
            // Get filter mode from dropdown
            const modeSelect = document.getElementById('dashboardModeSelect');
            const filterMode = modeSelect ? modeSelect.value : 'all';

            const response = await fetch(`/api/account?filter_mode=${filterMode}`);
            const data = await response.json();

            document.getElementById('portfolioValue').textContent = this.formatCurrency(data.equity);
            document.getElementById('totalPnl').textContent = this.formatCurrency(data.total_pnl);
            document.getElementById('totalPnl').className = `stat-value ${data.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
            document.getElementById('dailyPnl').textContent = this.formatCurrency(data.daily_pnl);
            document.getElementById('dailyPnl').className = `stat-value ${data.daily_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
            document.getElementById('openPositions').textContent = data.positions;

            // Update dashboard mode indicator with bot counts
            const modeIndicator = document.getElementById('dashboardModeIndicator');
            if (modeIndicator && data.paper_bots !== undefined) {
                const paperCount = data.paper_bots || 0;
                const liveCount = data.live_bots || 0;

                if (filterMode === 'all') {
                    modeIndicator.innerHTML = `
                        <span class="count-badge paper">${paperCount} Paper</span>
                        <span class="count-badge live">${liveCount} Live</span>
                    `;
                } else if (filterMode === 'paper') {
                    modeIndicator.innerHTML = `<span class="count-badge paper">${paperCount} Paper Bot${paperCount !== 1 ? 's' : ''}</span>`;
                } else if (filterMode === 'live') {
                    modeIndicator.innerHTML = `<span class="count-badge live">${liveCount} Live Bot${liveCount !== 1 ? 's' : ''}</span>`;
                }
            }

            // Update trading mode badge
            const modeBadge = document.getElementById('tradingModeBadge');
            if (modeBadge) {
                const mode = data.mode || 'none';
                let modeText = '--';
                let modeClass = '';

                if (mode === 'paper' || mode === 'bots') {
                    // Use counts from API response
                    const hasPaper = (data.paper_bots || 0) > 0;
                    const hasLive = (data.live_bots || 0) > 0;

                    if (hasLive && hasPaper) {
                        modeText = 'MIXED';
                        modeClass = 'live';
                    } else if (hasLive) {
                        modeText = 'LIVE';
                        modeClass = 'live';
                    } else if (hasPaper || mode === 'bots') {
                        modeText = 'PAPER';
                        modeClass = 'paper';
                    }
                } else if (mode === 'live') {
                    modeText = 'LIVE';
                    modeClass = 'live';
                } else if (mode === 'none' && data.equity > 0) {
                    modeText = 'PAPER';
                    modeClass = 'paper';
                }

                modeBadge.textContent = modeText;
                modeBadge.className = `trading-mode-badge ${modeClass}`;
            }
        } catch (error) {
            console.error('Error loading account data:', error);
        }
    }

    async loadPriceData() {
        try {
            const symbol = this.currentSymbol.replace('/', '-');
            let url = `/api/prices/${symbol}?timeframe=${this.currentTimeframe}`;

            // Use days_back for extended history, otherwise use limit
            if (this.daysBack > 0) {
                url += `&days_back=${this.daysBack}`;
            } else {
                url += `&limit=${this.dataLimit}`;
            }

            const response = await fetch(url);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading prices:', data.error);
                return;
            }

            // Store OHLCV data for candle chart
            this.priceData = data.data;

            // Reset live candle when new data is loaded (will be recreated on next tick)
            this.liveCandle = null;

            // Log loaded data count
            if (this.daysBack > 0) {
                this.log(`Loaded ${data.count || this.priceData.length} candles (${this.daysBack} days)`, 'success');
            }

            // Update chart based on current chart type
            this.updateChart();

            // Update current price and timeframe display
            if (this.priceData.length > 0) {
                const currentPrice = this.priceData[this.priceData.length - 1].close;
                const prevPrice = this.priceData.length > 1 ? this.priceData[this.priceData.length - 2].close : currentPrice;
                const change = ((currentPrice - prevPrice) / prevPrice * 100).toFixed(2);
                const changeSign = change >= 0 ? '+' : '';

                document.getElementById('currentPrice').textContent = this.formatCurrency(currentPrice);

                // Update timeframe indicator if exists
                const tfIndicator = document.getElementById('timeframeIndicator');
                if (tfIndicator) {
                    tfIndicator.textContent = this.currentTimeframe.toUpperCase();
                }
            }
        } catch (error) {
            console.error('Error loading price data:', error);
        }
    }

    // Load DR/IDR (Defining Range / Initial Defining Range) levels
    async loadDrIdr() {
        try {
            const symbol = this.currentSymbol.replace('/', '-');
            // Use 5m timeframe for DR/IDR calculation (intraday indicator)
            const response = await fetch(`/api/dr-idr/${symbol}?timeframe=5m`);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading DR/IDR:', data.error);
                this.drIdrData = null;
                return;
            }

            this.drIdrData = data;
            console.log('DR/IDR loaded:', data);

            // Update chart annotations
            this.updateDrIdrAnnotations();
        } catch (error) {
            console.error('Error loading DR/IDR:', error);
            this.drIdrData = null;
        }
    }

    // Update chart with DR/IDR horizontal lines and session boxes
    updateDrIdrAnnotations() {
        if (!this.priceChart || !this.drIdrData || !this.showDrIdr) {
            // Clear annotations if no data
            if (this.priceChart && this.priceChart.options.plugins.annotation) {
                this.priceChart.options.plugins.annotation.annotations = {};
                this.priceChart.update('none');
            }
            return;
        }

        const annotations = {};
        const lines = this.drIdrData.lines || [];

        // Add horizontal lines with time boundaries
        lines.forEach((line, index) => {
            if (line.y === null || line.y === undefined) return;

            const borderDash = line.style === 'dashed' ? [6, 6] :
                              line.style === 'dotted' ? [2, 2] : [];

            // Use xMin/xMax for time-bounded lines
            const annotation = {
                type: 'line',
                yMin: line.y,
                yMax: line.y,
                borderColor: line.color,
                borderWidth: line.width || 1,
                borderDash: borderDash,
                label: {
                    display: line.showLabel !== false,
                    content: line.label,
                    position: 'end',
                    backgroundColor: 'rgba(0,0,0,0.7)',
                    color: line.color,
                    font: { size: 10 }
                }
            };

            // Add time boundaries if available
            if (line.xMin) annotation.xMin = line.xMin;
            if (line.xMax) annotation.xMax = line.xMax;

            annotations[`line_${line.id || index}`] = annotation;
        });

        // Add session boxes with time boundaries (IDR shaded areas)
        const boxes = this.drIdrData.boxes || [];
        boxes.forEach((box, index) => {
            if (box.yMin === null || box.yMax === null) return;

            const annotation = {
                type: 'box',
                yMin: box.yMin,
                yMax: box.yMax,
                backgroundColor: box.backgroundColor || 'rgba(239, 68, 68, 0.1)',
                borderColor: box.borderColor || '#ef4444',
                borderWidth: box.borderWidth || 1
            };

            // Add time boundaries for session boxes
            if (box.xMin) annotation.xMin = box.xMin;
            if (box.xMax) annotation.xMax = box.xMax;

            annotations[`box_${box.id || index}`] = annotation;
        });

        // Update chart annotations
        if (!this.priceChart.options.plugins.annotation) {
            this.priceChart.options.plugins.annotation = {};
        }
        this.priceChart.options.plugins.annotation.annotations = annotations;
        this.priceChart.update('none');

        console.log(`DR/IDR: Rendered ${lines.length} lines and ${boxes.length} boxes`);
    }

    async loadSignal() {
        try {
            const symbol = this.currentSymbol.replace('/', '-');
            const response = await fetch(`/api/signal/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading signal:', data.error);
                return;
            }

            this.updateSignalDisplay(data);
        } catch (error) {
            console.error('Error loading signal:', error);
        }
    }

    async loadIndicators() {
        try {
            const symbol = this.currentSymbol.replace('/', '-');
            const response = await fetch(`/api/indicators/symbol/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('Error loading indicators:', data.error);
                return;
            }

            // Momentum indicators
            const rsiEl = document.getElementById('rsiValue');
            const rsi = data.rsi_14;
            rsiEl.textContent = rsi?.toFixed(1) || '--';
            rsiEl.className = 'ind-value ' + (rsi > 70 ? 'bearish' : rsi < 30 ? 'bullish' : 'neutral');

            const rsi7El = document.getElementById('rsi7Value');
            const rsi7 = data.rsi_7;
            rsi7El.textContent = rsi7?.toFixed(1) || '--';
            rsi7El.className = 'ind-value ' + (rsi7 > 70 ? 'bearish' : rsi7 < 30 ? 'bullish' : 'neutral');

            const stochEl = document.getElementById('stochValue');
            const stochK = data.stoch_k;
            const stochD = data.stoch_d;
            stochEl.textContent = stochK && stochD ? `${stochK.toFixed(0)}/${stochD.toFixed(0)}` : '--';
            stochEl.className = 'ind-value ' + (stochK > 80 ? 'bearish' : stochK < 20 ? 'bullish' : 'neutral');

            const cciEl = document.getElementById('cciValue');
            const cci = data.cci;
            cciEl.textContent = cci?.toFixed(0) || '--';
            cciEl.className = 'ind-value ' + (cci > 100 ? 'bullish' : cci < -100 ? 'bearish' : 'neutral');

            const rocEl = document.getElementById('rocValue');
            const roc = data.roc_10;
            rocEl.textContent = roc?.toFixed(2) + '%' || '--';
            rocEl.className = 'ind-value ' + (roc > 0 ? 'bullish' : roc < 0 ? 'bearish' : 'neutral');

            // Trend indicators
            const macdEl = document.getElementById('macdValue');
            const macdHist = data.macd_hist;
            macdEl.textContent = macdHist?.toFixed(2) || '--';
            macdEl.className = 'ind-value ' + (macdHist > 0 ? 'bullish' : macdHist < 0 ? 'bearish' : 'neutral');

            const adxEl = document.getElementById('adxValue');
            const adx = data.adx;
            adxEl.textContent = adx?.toFixed(1) || '--';
            adxEl.className = 'ind-value ' + (adx > 25 ? 'bullish' : 'neutral');

            const diEl = document.getElementById('diValue');
            const diPlus = data.di_plus;
            const diMinus = data.di_minus;
            if (diPlus && diMinus) {
                const diTrend = diPlus > diMinus ? 'bullish' : 'bearish';
                diEl.textContent = `${diPlus.toFixed(0)}/${diMinus.toFixed(0)}`;
                diEl.className = 'ind-value ' + diTrend;
            } else {
                diEl.textContent = '--';
            }

            const emaEl = document.getElementById('emaValue');
            const ema9 = data.ema_9;
            const ema21 = data.ema_21;
            if (ema9 && ema21) {
                const emaTrend = ema9 > ema21 ? 'bullish' : 'bearish';
                emaEl.textContent = emaTrend === 'bullish' ? 'UP' : 'DOWN';
                emaEl.className = 'ind-value ' + emaTrend;
            } else {
                emaEl.textContent = '--';
            }

            const smaEl = document.getElementById('smaValue');
            const sma20 = data.sma_20;
            const sma50 = data.sma_50;
            if (sma20 && sma50) {
                const smaTrend = sma20 > sma50 ? 'bullish' : 'bearish';
                smaEl.textContent = smaTrend === 'bullish' ? 'UP' : 'DOWN';
                smaEl.className = 'ind-value ' + smaTrend;
            } else {
                smaEl.textContent = '--';
            }

            // Volatility indicators
            const atrEl = document.getElementById('atrValue');
            const atrPct = data.atr_pct;
            atrEl.textContent = atrPct ? (atrPct * 100).toFixed(2) + '%' : '--';
            atrEl.className = 'ind-value ' + (atrPct > 0.03 ? 'bearish' : atrPct < 0.01 ? 'bullish' : 'neutral');

            const bbEl = document.getElementById('bbValue');
            const bbPct = data.bb_pct;
            bbEl.textContent = bbPct ? (bbPct * 100).toFixed(0) + '%' : '--';
            bbEl.className = 'ind-value ' + (bbPct > 0.8 ? 'bearish' : bbPct < 0.2 ? 'bullish' : 'neutral');

            const bbWidthEl = document.getElementById('bbWidthValue');
            const bbWidth = data.bb_width;
            bbWidthEl.textContent = bbWidth ? (bbWidth * 100).toFixed(2) + '%' : '--';
            bbWidthEl.className = 'ind-value ' + (bbWidth > 0.05 ? 'bearish' : 'neutral');

            const volEl = document.getElementById('volumeValue');
            const volRatio = data.volume_ratio;
            volEl.textContent = volRatio?.toFixed(2) + 'x' || '--';
            volEl.className = 'ind-value ' + (volRatio > 1.5 ? 'bullish' : volRatio < 0.5 ? 'bearish' : 'neutral');

            const obvEl = document.getElementById('obvValue');
            const obv = data.obv;
            if (obv) {
                const obvFormatted = obv > 1e9 ? (obv / 1e9).toFixed(1) + 'B' :
                                     obv > 1e6 ? (obv / 1e6).toFixed(1) + 'M' :
                                     obv > 1e3 ? (obv / 1e3).toFixed(1) + 'K' : obv.toFixed(0);
                obvEl.textContent = obvFormatted;
                obvEl.className = 'ind-value neutral';
            } else {
                obvEl.textContent = '--';
            }

            // Update explanation tab
            this.updateExplanation(data);
        } catch (error) {
            console.error('Error loading indicators:', error);
        }
    }

    updateExplanation(data) {
        const reasons = [];

        // 1. RSI(14) analysis
        const rsi = data.rsi_14;
        if (rsi !== null && rsi !== undefined) {
            if (rsi < 30) {
                reasons.push({ type: 'bullish', text: `RSI(14) at ${rsi.toFixed(1)} - oversold, potential bounce` });
            } else if (rsi > 70) {
                reasons.push({ type: 'bearish', text: `RSI(14) at ${rsi.toFixed(1)} - overbought, potential pullback` });
            } else {
                reasons.push({ type: 'neutral', text: `RSI(14) at ${rsi.toFixed(1)} - neutral zone` });
            }
        }

        // 2. MACD analysis
        const macdHist = data.macd_hist;
        if (macdHist !== null && macdHist !== undefined) {
            if (macdHist > 0) {
                reasons.push({ type: 'bullish', text: `MACD histogram positive (${macdHist.toFixed(2)}) - bullish momentum` });
            } else if (macdHist < 0) {
                reasons.push({ type: 'bearish', text: `MACD histogram negative (${macdHist.toFixed(2)}) - bearish momentum` });
            } else {
                reasons.push({ type: 'neutral', text: `MACD histogram flat - neutral momentum` });
            }
        }

        // 3. ADX analysis
        const adx = data.adx;
        if (adx !== null && adx !== undefined) {
            if (adx > 25) {
                reasons.push({ type: 'neutral', text: `ADX at ${adx.toFixed(1)} - strong trend present` });
            } else {
                reasons.push({ type: 'neutral', text: `ADX at ${adx.toFixed(1)} - weak/ranging market` });
            }
        }

        // 4. DI+/DI- analysis
        const diPlus = data.di_plus;
        const diMinus = data.di_minus;
        if (diPlus && diMinus) {
            if (diPlus > diMinus) {
                reasons.push({ type: 'bullish', text: `DI+ (${diPlus.toFixed(0)}) > DI- (${diMinus.toFixed(0)}) - bullish trend` });
            } else {
                reasons.push({ type: 'bearish', text: `DI- (${diMinus.toFixed(0)}) > DI+ (${diPlus.toFixed(0)}) - bearish trend` });
            }
        }

        // 5. EMA 9/21 crossover
        const ema9 = data.ema_9;
        const ema21 = data.ema_21;
        if (ema9 && ema21) {
            if (ema9 > ema21) {
                reasons.push({ type: 'bullish', text: 'EMA 9 above EMA 21 - short-term bullish trend' });
            } else {
                reasons.push({ type: 'bearish', text: 'EMA 9 below EMA 21 - short-term bearish trend' });
            }
        }

        // 6. SMA 20/50 crossover
        const sma20 = data.sma_20;
        const sma50 = data.sma_50;
        if (sma20 && sma50) {
            if (sma20 > sma50) {
                reasons.push({ type: 'bullish', text: 'SMA 20 above SMA 50 - medium-term bullish' });
            } else {
                reasons.push({ type: 'bearish', text: 'SMA 20 below SMA 50 - medium-term bearish' });
            }
        }

        // 7. ATR volatility analysis
        const atrPct = data.atr_pct;
        if (atrPct !== null && atrPct !== undefined) {
            if (atrPct > 0.03) {
                reasons.push({ type: 'neutral', text: `ATR at ${(atrPct*100).toFixed(2)}% - high volatility` });
            } else if (atrPct < 0.01) {
                reasons.push({ type: 'neutral', text: `ATR at ${(atrPct*100).toFixed(2)}% - low volatility, potential breakout` });
            } else {
                reasons.push({ type: 'neutral', text: `ATR at ${(atrPct*100).toFixed(2)}% - normal volatility` });
            }
        }

        // 8. Bollinger Band position
        const bbPct = data.bb_pct;
        if (bbPct !== null && bbPct !== undefined) {
            if (bbPct < 0.2) {
                reasons.push({ type: 'bullish', text: `Price near lower BB (${(bbPct*100).toFixed(0)}%) - potential bounce` });
            } else if (bbPct > 0.8) {
                reasons.push({ type: 'bearish', text: `Price near upper BB (${(bbPct*100).toFixed(0)}%) - potential reversal` });
            } else {
                reasons.push({ type: 'neutral', text: `Price at ${(bbPct*100).toFixed(0)}% of BB - within bands` });
            }
        }

        // 9. Volume analysis
        const volRatio = data.volume_ratio;
        if (volRatio !== null && volRatio !== undefined) {
            if (volRatio > 1.5) {
                reasons.push({ type: 'bullish', text: `High volume (${volRatio.toFixed(2)}x avg) - confirms price action` });
            } else if (volRatio < 0.5) {
                reasons.push({ type: 'bearish', text: `Low volume (${volRatio.toFixed(2)}x avg) - weak conviction` });
            } else {
                reasons.push({ type: 'neutral', text: `Normal volume (${volRatio.toFixed(2)}x avg)` });
            }
        }

        // 10. Price vs VWAP
        const vwap = data.vwap;
        const price = data.price;
        if (vwap && price) {
            if (price > vwap) {
                reasons.push({ type: 'bullish', text: `Price above VWAP - bullish intraday bias` });
            } else {
                reasons.push({ type: 'bearish', text: `Price below VWAP - bearish intraday bias` });
            }
        }

        // Count signals from the reasons array (counts now match displayed items exactly)
        const bullish = reasons.filter(r => r.type === 'bullish').length;
        const bearish = reasons.filter(r => r.type === 'bearish').length;
        const neutral = reasons.filter(r => r.type === 'neutral').length;

        // Determine signal based on counts
        let signal, summary, signalClass;
        if (bullish > bearish + 2) {
            signal = 'BUY';
            signalClass = 'buy';
            summary = `${bullish} bullish, ${bearish} bearish, ${neutral} neutral signals`;
        } else if (bearish > bullish + 2) {
            signal = 'SELL';
            signalClass = 'sell';
            summary = `${bullish} bullish, ${bearish} bearish, ${neutral} neutral signals`;
        } else {
            signal = 'HOLD';
            signalClass = 'hold';
            summary = `${bullish} bullish, ${bearish} bearish, ${neutral} neutral signals`;
        }

        // Update DOM
        const explainSignal = document.getElementById('explainSignal');
        explainSignal.textContent = signal;
        explainSignal.className = 'explain-signal ' + signalClass;

        document.getElementById('explainSummary').textContent = summary;

        // Update reasons list
        const reasonsEl = document.getElementById('explainReasons');
        reasonsEl.innerHTML = reasons.map(r => `
            <div class="reason-item ${r.type}">
                <span class="reason-icon">●</span>
                <span class="reason-text">${r.text}</span>
            </div>
        `).join('');

        // Update score bars
        const maxScore = Math.max(bullish, bearish, neutral, 1);
        document.getElementById('bullishScore').style.width = (bullish / maxScore * 100) + '%';
        document.getElementById('bearishScore').style.width = (bearish / maxScore * 100) + '%';
        document.getElementById('neutralScore').style.width = (neutral / maxScore * 100) + '%';
        document.getElementById('bullishCount').textContent = bullish;
        document.getElementById('bearishCount').textContent = bearish;
        document.getElementById('neutralCount').textContent = neutral;
    }

    async loadPositions() {
        try {
            const response = await fetch('/api/positions');
            const data = await response.json();

            const tbody = document.getElementById('positionsTable');
            const openPosCount = document.getElementById('openPositions');

            if (!data.positions || data.positions.length === 0) {
                tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No open positions</td></tr>';
                if (openPosCount) openPosCount.textContent = '0';
                return;
            }

            // Update positions count
            if (openPosCount) openPosCount.textContent = data.positions.length;

            tbody.innerHTML = data.positions.map(pos => {
                // Format TP/SL display
                const tp = pos.take_profit ? this.formatCurrency(pos.take_profit) : '--';
                const sl = pos.stop_loss ? this.formatCurrency(pos.stop_loss) : '--';
                const tpSl = `${tp} / ${sl}`;

                return `
                    <tr>
                        <td><span class="bot-type-badge ${pos.bot_type}">${pos.bot}</span></td>
                        <td>${pos.symbol}</td>
                        <td><span class="badge ${pos.side}">${pos.side.toUpperCase()}</span></td>
                        <td>${pos.size.toFixed(6)}</td>
                        <td>${this.formatCurrency(pos.entry_price)}</td>
                        <td class="text-muted">${tpSl}</td>
                        <td class="${pos.unrealized_pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}">
                            ${this.formatCurrency(pos.unrealized_pnl)}
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('Error loading positions:', error);
        }
    }

    async loadStatus() {
        try {
            const response = await fetch('/api/status');
            const data = await response.json();

            this.isTrading = data.is_trading;
            this.updateTradingStatus(data);
        } catch (error) {
            console.error('Error loading status:', error);
        }
    }

    async loadTradeHistory() {
        try {
            const response = await fetch('/api/trades?limit=50');
            const data = await response.json();

            const tbody = document.getElementById('historyTable');

            if (!data.trades || data.trades.length === 0) {
                tbody.innerHTML = '<tr class="empty-row"><td colspan="10">No trade history</td></tr>';
                return;
            }

            tbody.innerHTML = data.trades.map(trade => {
                // Check if this is a scalping bot trade (has entry/exit prices and pnl)
                const isScalpTrade = trade.source === 'scalping_bot' || trade.exit_price !== undefined;

                // Format time - use entry_time for scalp trades, timestamp for others
                const tradeTime = trade.entry_time || trade.timestamp;
                const timeStr = tradeTime ? new Date(tradeTime).toLocaleString() : '--';

                // Entry price
                const entryPrice = trade.entry_price || trade.price || 0;

                // Exit price (only for scalp trades)
                const exitPrice = trade.exit_price;
                const exitPriceStr = exitPrice ? this.formatCurrency(exitPrice) : '--';

                // P&L
                const pnl = trade.pnl;
                const pnlStr = pnl !== undefined ? (pnl >= 0 ? '+' : '') + '$' + pnl.toFixed(2) : '--';
                const pnlClass = pnl !== undefined ? (pnl >= 0 ? 'pnl-positive' : 'pnl-negative') : '';

                // Parse exit_reason to extract bot type and actual result
                // Format: "bot_type:reason" (e.g., "short_term:take_profit") or just "reason"
                let botType = 'Scalping';  // Default
                let result = trade.exit_reason || (trade.side === 'buy' ? 'OPEN' : 'CLOSE');

                if (trade.exit_reason && trade.exit_reason.includes(':')) {
                    const parts = trade.exit_reason.split(':');
                    const botTypeRaw = parts[0];
                    result = parts.slice(1).join(':');  // Rest is the actual reason

                    // Map bot type to display name
                    const botTypeMap = {
                        'scalping': 'Scalping',
                        'short_term': 'Short Term',
                        'swing': 'Swing',
                        'long_term': 'Long Term'
                    };
                    botType = botTypeMap[botTypeRaw] || botTypeRaw;
                }

                // Bot type badge class
                const botTypeClass = {
                    'Scalping': 'bot-type-scalping',
                    'Short Term': 'bot-type-short',
                    'Swing': 'bot-type-swing',
                    'Long Term': 'bot-type-long'
                }[botType] || '';

                const resultClass = result === 'take_profit' ? 'pnl-positive' :
                                   result === 'stop_loss' ? 'pnl-negative' : '';

                // Side display
                const sideDisplay = isScalpTrade ? trade.side.toUpperCase() : trade.side.toUpperCase();
                const sideClass = trade.side === 'long' || trade.side === 'buy' ? 'pnl-positive' : 'pnl-negative';

                return `
                    <tr>
                        <td>${timeStr}</td>
                        <td>${trade.symbol}</td>
                        <td><span class="bot-type-badge ${botTypeClass}">${botType}</span></td>
                        <td class="${sideClass}">${sideDisplay}</td>
                        <td>${this.formatCurrency(entryPrice)}</td>
                        <td>${exitPriceStr}</td>
                        <td>${(trade.amount || trade.size || 0).toFixed(6)}</td>
                        <td class="${pnlClass}">${pnlStr}</td>
                        <td class="${resultClass}">${result.replace('_', ' ').toUpperCase()}</td>
                        <td>${trade.is_paper ? 'Paper' : 'Live'}</td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('Error loading trade history:', error);
        }
    }

    // Database Functions
    async loadDatabaseData() {
        const table = this.dbCurrentTable;
        const limit = parseInt(document.getElementById('dbFilterLimit')?.value || '100');
        const offset = (this.dbCurrentPage - 1) * limit;

        // Build query params
        const params = new URLSearchParams({
            table: table,
            limit: limit,
            offset: offset
        });

        // Add filters
        const symbol = document.getElementById('dbFilterSymbol')?.value;
        const prediction = document.getElementById('dbFilterPrediction')?.value;
        const startDate = document.getElementById('dbFilterStartDate')?.value;
        const endDate = document.getElementById('dbFilterEndDate')?.value;

        if (symbol) params.append('symbol', symbol);
        if (prediction) params.append('prediction', prediction);
        if (startDate) params.append('start_date', startDate);
        if (endDate) params.append('end_date', endDate);

        try {
            const response = await fetch(`/api/database/query?${params}`);
            const data = await response.json();

            if (data.error) {
                console.error('Database error:', data.error);
                this.renderDatabaseError(data.error);
                return;
            }

            this.dbTotalRows = data.total || data.rows?.length || 0;
            this.renderDatabaseTable(data.columns, data.rows);
            this.updateDatabaseStats(data.rows?.length || 0, this.dbTotalRows);
            this.updatePagination();
        } catch (error) {
            console.error('Error loading database data:', error);
            this.renderDatabaseError(error.message);
        }
    }

    renderDatabaseTable(columns, rows) {
        const thead = document.getElementById('dbTableHead');
        const tbody = document.getElementById('dbTableBody');

        if (!columns || columns.length === 0) {
            thead.innerHTML = '<tr><th>No data</th></tr>';
            tbody.innerHTML = '<tr class="empty-row"><td>No data available</td></tr>';
            return;
        }

        // Define which columns to show for each table - include ALL indicators for candle_snapshots
        const columnConfigs = {
            candle_snapshots: [
                'id', 'symbol', 'timestamp_ny', 'day_of_week', 'month',
                // OHLCV
                'open', 'high', 'low', 'close', 'volume',
                // Momentum Indicators
                'rsi_14', 'rsi_7', 'stoch_k', 'stoch_d', 'cci', 'roc_10', 'momentum_10',
                // Trend Indicators
                'macd', 'macd_signal', 'macd_hist', 'adx', 'di_plus', 'di_minus',
                'ema_9', 'ema_21', 'ema_50', 'sma_20', 'sma_50',
                // Volatility Indicators
                'atr_14', 'atr_pct', 'bb_upper', 'bb_middle', 'bb_lower', 'bb_width', 'bb_pct',
                // Volume Indicators
                'volume_ratio', 'obv', 'vwap',
                // Prediction
                'prediction', 'confidence', 'bullish_count', 'bearish_count', 'neutral_count'
            ],
            trades: ['id', 'symbol', 'side', 'price', 'amount', 'cost', 'timestamp', 'day_of_week', 'month', 'is_paper'],
            ohlcv: ['id', 'symbol', 'timeframe', 'timestamp', 'day_of_week', 'month', 'open', 'high', 'low', 'close', 'volume'],
            model_performance: ['id', 'model_name', 'symbol', 'accuracy', 'precision_score', 'recall', 'f1_score', 'profit_factor', 'sharpe_ratio', 'timestamp']
        };

        // Helper function to get day of week and month from timestamp
        const getDayOfWeek = (timestamp) => {
            if (!timestamp) return '--';
            const date = new Date(timestamp);
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            return days[date.getDay()];
        };

        const getMonth = (timestamp) => {
            if (!timestamp) return '--';
            const date = new Date(timestamp);
            const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
            return months[date.getMonth()];
        };

        // Add computed columns to rows
        const timestampCol = this.dbCurrentTable === 'candle_snapshots' ? 'timestamp_ny' : 'timestamp';
        rows = rows.map(row => ({
            ...row,
            day_of_week: getDayOfWeek(row[timestampCol]),
            month: getMonth(row[timestampCol])
        }));

        // Add computed columns to the columns array if not present
        if (!columns.includes('day_of_week')) columns = [...columns, 'day_of_week'];
        if (!columns.includes('month')) columns = [...columns, 'month'];

        const visibleColumns = columnConfigs[this.dbCurrentTable] || columns;
        const filteredColumns = columns.filter(col => visibleColumns.includes(col));

        // Render header with friendly names
        const headerNames = {
            'timestamp_ny': 'Time (NY)',
            'day_of_week': 'Day',
            'month': 'Month',
            'rsi_14': 'RSI(14)',
            'rsi_7': 'RSI(7)',
            'stoch_k': 'Stoch K',
            'stoch_d': 'Stoch D',
            'cci': 'CCI',
            'roc_10': 'ROC',
            'momentum_10': 'Momentum',
            'macd': 'MACD',
            'macd_signal': 'MACD Sig',
            'macd_hist': 'MACD Hist',
            'adx': 'ADX',
            'di_plus': 'DI+',
            'di_minus': 'DI-',
            'ema_9': 'EMA 9',
            'ema_21': 'EMA 21',
            'ema_50': 'EMA 50',
            'sma_20': 'SMA 20',
            'sma_50': 'SMA 50',
            'atr_14': 'ATR',
            'atr_pct': 'ATR %',
            'bb_upper': 'BB Upper',
            'bb_middle': 'BB Mid',
            'bb_lower': 'BB Lower',
            'bb_width': 'BB Width',
            'bb_pct': 'BB %',
            'volume_ratio': 'Vol Ratio',
            'obv': 'OBV',
            'vwap': 'VWAP',
            'bullish_count': 'Bullish',
            'bearish_count': 'Bearish',
            'neutral_count': 'Neutral'
        };
        thead.innerHTML = `<tr>${filteredColumns.map(col => `<th>${headerNames[col] || col}</th>`).join('')}</tr>`;

        if (!rows || rows.length === 0) {
            tbody.innerHTML = `<tr class="empty-row"><td colspan="${filteredColumns.length}">No data found</td></tr>`;
            return;
        }

        // Render rows
        tbody.innerHTML = rows.map(row => {
            return `<tr>${filteredColumns.map(col => {
                let value = row[col];
                let className = '';

                // Special formatting
                if (col === 'prediction') {
                    className = `prediction-cell ${(value || '').toLowerCase()}`;
                } else if (col === 'side') {
                    className = value === 'buy' ? 'pnl-positive' : 'pnl-negative';
                } else if (['open', 'high', 'low', 'close', 'price', 'ema_9', 'ema_21', 'ema_50', 'sma_20', 'sma_50', 'bb_upper', 'bb_middle', 'bb_lower', 'vwap'].includes(col) && value) {
                    value = this.formatCurrency(value);
                } else if (['confidence', 'accuracy', 'precision_score', 'recall', 'f1_score'].includes(col) && value) {
                    value = parseFloat(value).toFixed(1) + '%';
                } else if (['atr_pct', 'bb_width', 'bb_pct'].includes(col) && value) {
                    value = (parseFloat(value) * 100).toFixed(2) + '%';
                } else if (['rsi_14', 'rsi_7', 'stoch_k', 'stoch_d', 'cci', 'roc_10', 'momentum_10', 'macd', 'macd_signal', 'macd_hist', 'adx', 'di_plus', 'di_minus', 'atr_14', 'volume_ratio', 'profit_factor', 'sharpe_ratio'].includes(col) && value) {
                    value = parseFloat(value).toFixed(2);
                } else if (col === 'obv' && value) {
                    value = parseFloat(value).toFixed(4);
                } else if (col === 'explanation' && value) {
                    // Truncate JSON and make expandable
                    value = value.length > 50 ? value.substring(0, 50) + '...' : value;
                    className = 'expandable';
                }

                return `<td class="${className}" title="${row[col] || ''}">${value ?? '--'}</td>`;
            }).join('')}</tr>`;
        }).join('');
    }

    updateDatabaseStats(rowCount, totalRows) {
        document.getElementById('dbRowCount').textContent = `${rowCount} rows (${totalRows} total)`;
        document.getElementById('dbLastUpdate').textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
    }

    updatePagination() {
        const maxPages = Math.ceil(this.dbTotalRows / this.dbPageSize) || 1;
        document.getElementById('dbPageInfo').textContent = `Page ${this.dbCurrentPage} of ${maxPages}`;
        document.getElementById('dbPrevPage').disabled = this.dbCurrentPage <= 1;
        document.getElementById('dbNextPage').disabled = this.dbCurrentPage >= maxPages;
    }

    renderDatabaseError(message) {
        const tbody = document.getElementById('dbTableBody');
        tbody.innerHTML = `<tr class="empty-row"><td colspan="10" style="color: var(--accent-red);">Error: ${message}</td></tr>`;
    }

    // Prediction Accuracy Methods
    async loadPredictionAccuracy() {
        const symbol = this.currentSymbol.replace('/', '-');
        const days = document.getElementById('accuracyDays')?.value || 7;

        try {
            const response = await fetch(`/api/prediction-accuracy/${symbol}?days=${days}`);
            const data = await response.json();

            if (data.error) {
                console.error('Accuracy error:', data.error);
                return;
            }

            this.updateAccuracyDisplay(data);
        } catch (error) {
            console.error('Error loading accuracy:', error);
        }
    }

    updateAccuracyDisplay(data) {
        const overall = data.overall || {};
        const byType = data.by_prediction_type || {};
        const last24h = data.last_24h || {};

        // Update circular progress
        const accuracy = overall.accuracy || 0;
        const progressEl = document.getElementById('accuracyProgress');
        const percentageEl = document.getElementById('accuracyPercentage');
        const totalEl = document.getElementById('accuracyTotal');

        if (progressEl) {
            progressEl.setAttribute('stroke-dasharray', `${accuracy}, 100`);
            // Color based on accuracy
            if (accuracy >= 60) {
                progressEl.style.stroke = 'var(--accent-green)';
            } else if (accuracy >= 40) {
                progressEl.style.stroke = 'var(--accent-yellow)';
            } else {
                progressEl.style.stroke = 'var(--accent-red)';
            }
        }
        if (percentageEl) {
            percentageEl.textContent = `${accuracy.toFixed(1)}%`;
        }
        if (totalEl) {
            totalEl.textContent = `${overall.correct_predictions || 0} / ${overall.total_predictions || 0} predictions`;
        }

        // Update BUY accuracy
        const buyData = byType.BUY || { accuracy: 0, correct: 0, total: 0 };
        this.updateAccuracyBar('buy', buyData);

        // Update SELL accuracy
        const sellData = byType.SELL || { accuracy: 0, correct: 0, total: 0 };
        this.updateAccuracyBar('sell', sellData);

        // Update HOLD accuracy
        const holdData = byType.HOLD || { accuracy: 0, correct: 0, total: 0 };
        this.updateAccuracyBar('hold', holdData);

        // Update 24h stats
        const accuracy24hEl = document.getElementById('accuracy24h');
        if (accuracy24hEl) {
            const acc24h = last24h.accuracy || 0;
            accuracy24hEl.textContent = `${acc24h.toFixed(1)}% (${last24h.correct || 0}/${last24h.total || 0})`;
        }
    }

    updateAccuracyBar(type, data) {
        const barEl = document.getElementById(`${type}AccuracyBar`);
        const valueEl = document.getElementById(`${type}Accuracy`);
        const countEl = document.getElementById(`${type}Count`);

        if (barEl) {
            barEl.style.width = `${data.accuracy || 0}%`;
        }
        if (valueEl) {
            valueEl.textContent = `${(data.accuracy || 0).toFixed(1)}%`;
        }
        if (countEl) {
            countEl.textContent = `(${data.correct || 0}/${data.total || 0})`;
        }
    }

    async validatePendingPredictions() {
        const symbol = this.currentSymbol.replace('/', '-');

        try {
            const response = await fetch(`/api/validate-predictions/${symbol}`, {
                method: 'POST'
            });
            const data = await response.json();

            if (data.error) {
                this.log(`Validation error: ${data.error}`, 'error');
                return;
            }

            this.log(`Validated ${data.validated_count} predictions`, 'success');
            // Reload accuracy stats
            this.loadPredictionAccuracy();
        } catch (error) {
            this.log(`Error validating: ${error.message}`, 'error');
        }
    }

    // Order Blocks & Levels Methods
    async loadOrderBlocksAndLevels() {
        const symbol = this.currentSymbol.replace('/', '-');

        try {
            const response = await fetch(`/api/order-blocks/${symbol}?lookback=100`);
            const data = await response.json();

            if (data.error) {
                console.error('Order blocks error:', data.error);
                return;
            }

            this.updateLevelsDisplay(data);
        } catch (error) {
            console.error('Error loading order blocks:', error);
        }
    }

    updateLevelsDisplay(data) {
        // Update current price and ATR
        const priceEl = document.getElementById('levelsCurrentPrice');
        const atrEl = document.getElementById('levelsATR');

        if (priceEl) {
            priceEl.textContent = `$${data.current_price?.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2}) || '--'}`;
        }
        if (atrEl) {
            atrEl.textContent = `$${data.atr?.toFixed(2) || '--'}`;
        }

        // Update Order Blocks
        const obContainer = document.getElementById('orderBlocksContainer');
        if (obContainer) {
            if (data.order_blocks && data.order_blocks.length > 0) {
                obContainer.innerHTML = data.order_blocks.map(ob => `
                    <div class="order-block ${ob.type}">
                        <div class="ob-type">${ob.type === 'demand' ? 'Demand Zone' : 'Supply Zone'}</div>
                        <div class="ob-range">$${ob.low.toLocaleString(undefined, {minimumFractionDigits: 2})} - $${ob.high.toLocaleString(undefined, {minimumFractionDigits: 2})}</div>
                        <div class="ob-meta">
                            <span class="ob-strength">
                                Strength:
                                <span class="strength-bar"><span class="strength-fill" style="width: ${ob.strength}%"></span></span>
                                ${ob.strength}%
                            </span>
                            <span>${ob.touched ? 'Tested' : 'Untested'}</span>
                        </div>
                    </div>
                `).join('');
            } else {
                obContainer.innerHTML = '<div class="empty-state">No order blocks detected</div>';
            }
        }

        // Update Resistance Levels
        const resContainer = document.getElementById('resistanceLevels');
        if (resContainer) {
            if (data.resistance_levels && data.resistance_levels.length > 0) {
                resContainer.innerHTML = data.resistance_levels.map(level => `
                    <div class="sr-level">
                        <span class="price">$${level.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                        <span class="touches">${level.touches} touches</span>
                    </div>
                `).join('');
            } else {
                resContainer.innerHTML = '<div class="empty-state">No resistance levels found</div>';
            }
        }

        // Update Support Levels
        const supContainer = document.getElementById('supportLevels');
        if (supContainer) {
            if (data.support_levels && data.support_levels.length > 0) {
                supContainer.innerHTML = data.support_levels.map(level => `
                    <div class="sr-level">
                        <span class="price">$${level.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                        <span class="touches">${level.touches} touches</span>
                    </div>
                `).join('');
            } else {
                supContainer.innerHTML = '<div class="empty-state">No support levels found</div>';
            }
        }

        // Update SL/TP suggestions for Long positions
        const longSL = document.getElementById('longStopLoss');
        const longTP = document.getElementById('longTakeProfit');
        const sltp = data.sl_tp_levels || {};

        if (longSL && sltp.long) {
            longSL.innerHTML = sltp.long.stop_loss?.map(sl => `
                <div class="sl-tp-value sl">
                    <span class="price">$${sl.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                    <span class="percent">(-${sl.risk_reward}%)</span>
                </div>
            `).join('') || '--';
        }

        if (longTP && sltp.long) {
            longTP.innerHTML = sltp.long.take_profit?.map(tp => `
                <div class="sl-tp-value tp">
                    <span class="price">$${tp.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                    <span class="percent">(+${tp.reward}%)</span>
                </div>
            `).join('') || '--';
        }

        // Update SL/TP suggestions for Short positions
        const shortSL = document.getElementById('shortStopLoss');
        const shortTP = document.getElementById('shortTakeProfit');

        if (shortSL && sltp.short) {
            shortSL.innerHTML = sltp.short.stop_loss?.map(sl => `
                <div class="sl-tp-value sl">
                    <span class="price">$${sl.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                    <span class="percent">(+${sl.risk_reward}%)</span>
                </div>
            `).join('') || '--';
        }

        if (shortTP && sltp.short) {
            shortTP.innerHTML = sltp.short.take_profit?.map(tp => `
                <div class="sl-tp-value tp">
                    <span class="price">$${tp.price.toLocaleString(undefined, {minimumFractionDigits: 2})}</span>
                    <span class="percent">(+${tp.reward}%)</span>
                </div>
            `).join('') || '--';
        }
    }

    // Trading Controls
    async startTrading() {
        const symbols = [];
        document.querySelectorAll('.symbol-checkboxes input:checked').forEach(cb => {
            symbols.push(cb.value);
        });

        if (symbols.length === 0) {
            this.log('Please select at least one symbol', 'warning');
            return;
        }

        try {
            const response = await fetch('/api/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbols: symbols,
                    mode: this.tradingMode
                })
            });

            const data = await response.json();

            if (response.ok) {
                this.isTrading = true;
                this.updateTradingStatus({ is_trading: true, trading_mode: this.tradingMode });
                this.log(`Started ${this.tradingMode} trading for ${symbols.join(', ')}`, 'success');
            } else {
                this.log(`Failed to start: ${data.detail}`, 'error');
            }
        } catch (error) {
            this.log(`Error starting trading: ${error.message}`, 'error');
        }
    }

    async stopTrading() {
        try {
            const response = await fetch('/api/stop', { method: 'POST' });
            const data = await response.json();

            this.isTrading = false;
            this.updateTradingStatus({ is_trading: false });
            this.log('Trading stopped', 'info');
        } catch (error) {
            this.log(`Error stopping trading: ${error.message}`, 'error');
        }
    }

    // Backtest
    async runBacktest() {
        const symbol = document.getElementById('backtestSymbol').value;
        const startDate = document.getElementById('backtestStart').value;
        const endDate = document.getElementById('backtestEnd').value;

        this.log(`Running backtest for ${symbol}...`, 'info');

        try {
            const response = await fetch('/api/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    start_date: startDate,
                    end_date: endDate
                })
            });

            const data = await response.json();

            if (response.ok) {
                document.getElementById('backtestResults').style.display = 'block';
                document.getElementById('btReturn').textContent = (data.total_return * 100).toFixed(2) + '%';
                document.getElementById('btReturn').className = `result-value ${data.total_return >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
                document.getElementById('btSharpe').textContent = data.sharpe_ratio.toFixed(2);
                document.getElementById('btDrawdown').textContent = (data.max_drawdown * 100).toFixed(2) + '%';
                document.getElementById('btWinRate').textContent = (data.win_rate * 100).toFixed(2) + '%';
                document.getElementById('btProfitFactor').textContent = data.profit_factor.toFixed(2);
                document.getElementById('btTotalTrades').textContent = data.total_trades;

                this.log('Backtest completed', 'success');
            } else {
                this.log(`Backtest failed: ${data.detail}`, 'error');
            }
        } catch (error) {
            this.log(`Error running backtest: ${error.message}`, 'error');
        }
    }

    // Train Model
    async trainModel() {
        const modelType = document.getElementById('trainModelType').value;
        const symbol = document.getElementById('trainSymbol').value;
        const startDate = document.getElementById('trainStart').value;
        const endDate = document.getElementById('trainEnd').value;

        const modelNames = {
            'xgboost': 'XGBoost',
            'lightgbm': 'LightGBM',
            'random_forest': 'Random Forest',
            'prophet': 'Prophet',
            'transformer': 'Transformer',
            'ppo': 'PPO'
        };

        this.log(`Starting ${modelNames[modelType]} training for ${symbol}...`, 'info');
        document.getElementById('trainingProgress').style.width = '10%';
        document.getElementById('trainingStatusText').textContent = `Training ${modelNames[modelType]}...`;

        try {
            const response = await fetch('/api/train', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    model_type: modelType,
                    symbol: symbol,
                    start_date: startDate,
                    end_date: endDate
                })
            });

            const data = await response.json();
            if (data.error) {
                this.log(`Training error: ${data.error}`, 'error');
                document.getElementById('trainingStatusText').textContent = `Error: ${data.error}`;
            } else {
                this.log(`${modelNames[modelType]} training started in background`, 'info');
                document.getElementById('trainingStatusText').textContent = 'Training in progress...';
            }
        } catch (error) {
            this.log(`Error starting training: ${error.message}`, 'error');
            document.getElementById('trainingStatusText').textContent = `Error: ${error.message}`;
        }
    }

    // UI Updates
    updateSignalDisplay(data) {
        const signalBadge = document.querySelector('.signal-badge');
        const signal = data.signal?.toLowerCase() || 'hold';

        signalBadge.textContent = signal.toUpperCase();
        signalBadge.className = `signal-badge ${signal}`;

        const confidence = (data.confidence * 100).toFixed(0);
        document.getElementById('confidenceFill').style.width = confidence + '%';
        document.getElementById('confidenceValue').textContent = confidence + '%';
    }

    updatePriceDisplay(data) {
        if (data.price) {
            document.getElementById('currentPrice').textContent = this.formatCurrency(data.price);
        }
    }

    updateAccountDisplay(data) {
        document.getElementById('portfolioValue').textContent = this.formatCurrency(data.equity);
        document.getElementById('totalPnl').textContent = this.formatCurrency(data.pnl);
        document.getElementById('totalPnl').className = `stat-value ${data.pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
    }

    updateTradingStatus(data) {
        const statusBadge = document.querySelector('.status-badge');
        const startBtn = document.getElementById('startTrading');
        const stopBtn = document.getElementById('stopTrading');

        if (data.is_trading) {
            statusBadge.textContent = `${data.trading_mode || 'Paper'} Trading`;
            statusBadge.className = 'status-badge running';
            startBtn.disabled = true;
            stopBtn.disabled = false;
        } else {
            statusBadge.textContent = 'Stopped';
            statusBadge.className = 'status-badge stopped';
            startBtn.disabled = false;
            stopBtn.disabled = true;
        }
    }

    updateTrainingStatus(data) {
        const progressBar = document.getElementById('trainingProgress');
        const statusText = document.getElementById('trainingStatusText');
        const metricsDiv = document.getElementById('trainingMetrics');

        switch (data.status) {
            case 'fetching_data':
                progressBar.style.width = '25%';
                statusText.textContent = 'Fetching historical data...';
                break;
            case 'generating_features':
                progressBar.style.width = '50%';
                statusText.textContent = 'Generating features...';
                break;
            case 'training_model':
                progressBar.style.width = '75%';
                statusText.textContent = 'Training ML model...';
                break;
            case 'completed':
                progressBar.style.width = '100%';
                statusText.textContent = 'Training completed!';
                metricsDiv.style.display = 'grid';

                if (data.metrics) {
                    document.getElementById('trainAccuracy').textContent = (data.metrics.accuracy * 100).toFixed(2) + '%';
                    document.getElementById('trainPrecision').textContent = (data.metrics.precision * 100).toFixed(2) + '%';
                    document.getElementById('trainRecall').textContent = (data.metrics.recall * 100).toFixed(2) + '%';
                    document.getElementById('trainF1').textContent = (data.metrics.f1_score * 100).toFixed(2) + '%';
                }

                this.log('Model training completed!', 'success');
                break;
            case 'error':
                progressBar.style.width = '0%';
                statusText.textContent = `Error: ${data.message}`;
                this.log(`Training error: ${data.message}`, 'error');
                break;
        }
    }

    // Utilities
    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value || 0);
    }

    log(message, type = 'info') {
        const logContainer = document.getElementById('tradingLog');
        if (!logContainer) {
            console.log(`[${type.toUpperCase()}] ${message}`);
            return;
        }
        const entry = document.createElement('div');
        entry.className = `log-entry ${type}`;
        entry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
        logContainer.insertBefore(entry, logContainer.firstChild);

        // Keep only last 100 entries
        while (logContainer.children.length > 100) {
            logContainer.removeChild(logContainer.lastChild);
        }
    }

    // ==========================================
    // ICT STRATEGY METHODS
    // ==========================================

    // Load all ICT data for the ICT page
    async loadIctData() {
        const symbol = this.currentSymbol.replace('/', '-');

        // Load all ICT data in parallel
        await Promise.all([
            this.loadIctSession(),
            this.loadIctDailyBias(symbol),
            this.loadIctSignal(symbol),
            this.loadIctConfluence(symbol),
            this.loadSilverBullet(),
            this.loadSmtDivergence(),
            this.loadMtfAnalysis()
        ]);
    }

    // Load current trading session
    async loadIctSession() {
        try {
            const response = await fetch('/api/ict-strategy/session');
            const data = await response.json();

            if (data.error) {
                console.error('ICT session error:', data.error);
                return;
            }

            // Update session display
            const sessionEl = document.getElementById('ictCurrentSession');
            const sessionTimeEl = document.getElementById('ictSessionTime');

            if (sessionEl) {
                const sessionName = data.session?.replace(/_/g, ' ').toUpperCase() || 'OFF HOURS';
                sessionEl.textContent = sessionName;
            }
            if (sessionTimeEl) {
                sessionTimeEl.textContent = data.is_killzone ? 'Killzone Active' : 'Standard Session';
            }

            // Update session timing factor display
            const cfSessionEl = document.getElementById('cfSession');
            if (cfSessionEl && data.is_killzone) {
                cfSessionEl.textContent = '2/2';
                document.getElementById('cfSessionFill').style.width = '100%';
            }
        } catch (error) {
            console.error('Error loading ICT session:', error);
        }
    }

    // Load daily bias
    async loadIctDailyBias(symbol) {
        try {
            const response = await fetch(`/api/ict-strategy/daily-bias/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('ICT daily bias error:', data.error);
                return;
            }

            // Update daily bias display
            const biasEl = document.getElementById('ictDailyBias');
            const biasIconEl = document.getElementById('ictBiasIcon');
            const biasConfEl = document.getElementById('ictBiasConfidence');

            if (biasEl) {
                const bias = data.bias?.toUpperCase() || 'NEUTRAL';
                biasEl.textContent = bias;

                // Update icon based on bias
                if (biasIconEl) {
                    if (bias.includes('BULLISH')) {
                        biasIconEl.textContent = '📈';
                        biasIconEl.className = 'stat-icon green';
                    } else if (bias.includes('BEARISH')) {
                        biasIconEl.textContent = '📉';
                        biasIconEl.className = 'stat-icon';
                        biasIconEl.style.background = 'rgba(239, 68, 68, 0.2)';
                    } else {
                        biasIconEl.textContent = '📊';
                        biasIconEl.className = 'stat-icon yellow';
                    }
                }
            }

            if (biasConfEl) {
                biasConfEl.textContent = `${(data.confidence).toFixed(0)}% confidence`;
            }

            // Update key levels - convert array to map for easy lookup
            const keyLevelsArray = data.key_levels || [];
            const levelsMap = {};
            keyLevelsArray.forEach(level => {
                levelsMap[level.name] = level.price;
            });

            // Update level displays
            const pdh = levelsMap['PDH'];
            const pdl = levelsMap['PDL'];
            const pwh = levelsMap['PWH'];
            const pwl = levelsMap['PWL'];
            const asianHigh = levelsMap['Asian High'];
            const asianLow = levelsMap['Asian Low'];

            document.getElementById('ictPDH').textContent = pdh ? this.formatCurrency(pdh) : '--';
            document.getElementById('ictPDL').textContent = pdl ? this.formatCurrency(pdl) : '--';
            document.getElementById('ictPWH').textContent = pwh ? this.formatCurrency(pwh) : '--';
            document.getElementById('ictPWL').textContent = pwl ? this.formatCurrency(pwl) : '--';

            // Calculate equilibrium (midpoint of PDH and PDL)
            const equilibrium = (pdh && pdl) ? (pdh + pdl) / 2 : null;
            document.getElementById('ictEquilibrium').textContent = equilibrium ? this.formatCurrency(equilibrium) : '--';

            // Midnight open could be calculated or use Asian session data
            const midnightOpen = asianLow; // Use Asian Low as approximation
            document.getElementById('ictMidnightOpen').textContent = midnightOpen ? this.formatCurrency(midnightOpen) : '--';

            // Premium/Discount zones (using PDR - Previous Day Range)
            if (pdh && pdl) {
                const range = pdh - pdl;
                const premiumZone = pdl + (range * 0.75);  // Above 75% is premium
                const discountZone = pdl + (range * 0.25); // Below 25% is discount

                const premiumZoneEl = document.getElementById('ictPremiumZone');
                const discountZoneEl = document.getElementById('ictDiscountZone');

                if (premiumZoneEl) {
                    premiumZoneEl.textContent = `> ${this.formatCurrency(premiumZone)}`;
                }
                if (discountZoneEl) {
                    discountZoneEl.textContent = `< ${this.formatCurrency(discountZone)}`;
                }

                // Determine current position in range from factors
                const factors = data.factors || {};
                const positionEl = document.getElementById('ictCurrentPosition');
                if (positionEl && factors.previous_day) {
                    const pdReason = factors.previous_day.reason || '';
                    if (pdReason.includes('lower half')) {
                        positionEl.textContent = 'DISCOUNT';
                        positionEl.className = 'level-value discount';
                    } else if (pdReason.includes('upper half')) {
                        positionEl.textContent = 'PREMIUM';
                        positionEl.className = 'level-value premium';
                    } else {
                        positionEl.textContent = 'EQUILIBRIUM';
                        positionEl.className = 'level-value';
                    }
                }
            }
        } catch (error) {
            console.error('Error loading ICT daily bias:', error);
        }
    }

    // Load ICT signal
    async loadIctSignal(symbol) {
        try {
            const response = await fetch(`/api/ict-strategy/signal/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('ICT signal error:', data.error);
                return;
            }

            // Update signal header card
            const signalValueEl = document.getElementById('ictSignalValue');
            const signalIconEl = document.getElementById('ictSignalIcon');
            const signalConfEl = document.getElementById('ictSignalConfidence');

            const signal = data.signal?.toUpperCase() || 'HOLD';

            if (signalValueEl) {
                signalValueEl.textContent = signal;
            }

            if (signalIconEl) {
                if (signal === 'BUY' || signal === 'STRONG_BUY') {
                    signalIconEl.textContent = '🟢';
                    signalIconEl.className = 'stat-icon green';
                } else if (signal === 'SELL' || signal === 'STRONG_SELL') {
                    signalIconEl.textContent = '🔴';
                    signalIconEl.className = 'stat-icon';
                    signalIconEl.style.background = 'rgba(239, 68, 68, 0.2)';
                } else {
                    signalIconEl.textContent = '🎯';
                    signalIconEl.className = 'stat-icon yellow';
                }
            }

            if (signalConfEl) {
                signalConfEl.textContent = `${(data.confidence * 100).toFixed(0)}% confidence`;
            }

            // Update signal badge
            const signalBadgeEl = document.getElementById('ictSignalBadge');
            if (signalBadgeEl) {
                signalBadgeEl.textContent = signal;
                signalBadgeEl.className = `signal-badge-large ${signal.toLowerCase().replace('_', '-')}`;
            }

            // Update signal details
            document.getElementById('ictDirection').textContent = data.direction || '--';
            document.getElementById('ictEntryPrice').textContent = data.entry_price ? this.formatCurrency(data.entry_price) : '--';
            document.getElementById('ictStopLoss').textContent = data.stop_loss ? this.formatCurrency(data.stop_loss) : '--';
            document.getElementById('ictTakeProfit').textContent = data.take_profit ? this.formatCurrency(data.take_profit) : '--';
            document.getElementById('ictRiskReward').textContent = data.risk_reward ? `1:${data.risk_reward.toFixed(1)}` : '--';

            // Update signal reasons
            const reasonsEl = document.getElementById('ictSignalReasons');
            if (reasonsEl && data.reasons) {
                const reasonsList = reasonsEl.querySelector('.reason-list');
                if (reasonsList) {
                    reasonsList.innerHTML = data.reasons.map(reason => {
                        const type = reason.type || 'neutral';
                        return `<div class="reason-item ${type}">${reason.text || reason}</div>`;
                    }).join('');
                }
            }

            // Update patterns
            this.updateIctPatterns(data.patterns || {});

        } catch (error) {
            console.error('Error loading ICT signal:', error);
        }
    }

    // Update ICT patterns display
    updateIctPatterns(patterns) {
        // FVG
        const fvgEl = document.getElementById('patternFVG');
        if (fvgEl) {
            if (patterns.fvg) {
                fvgEl.textContent = `${patterns.fvg.type?.toUpperCase() || 'Detected'} @ ${this.formatCurrency(patterns.fvg.price)}`;
                fvgEl.className = 'pattern-status detected ' + (patterns.fvg.type || '');
            } else {
                fvgEl.textContent = 'Not Detected';
                fvgEl.className = 'pattern-status';
            }
        }

        // MSS
        const mssEl = document.getElementById('patternMSS');
        if (mssEl) {
            if (patterns.mss) {
                mssEl.textContent = `${patterns.mss.direction?.toUpperCase() || 'Detected'}`;
                mssEl.className = 'pattern-status detected ' + (patterns.mss.direction || '');
            } else {
                mssEl.textContent = 'Not Detected';
                mssEl.className = 'pattern-status';
            }
        }

        // Order Block
        const obEl = document.getElementById('patternOB');
        if (obEl) {
            if (patterns.order_block) {
                obEl.textContent = `${patterns.order_block.type?.toUpperCase() || 'Detected'} @ ${this.formatCurrency(patterns.order_block.price)}`;
                obEl.className = 'pattern-status detected ' + (patterns.order_block.type === 'demand' ? 'bullish' : 'bearish');
            } else {
                obEl.textContent = 'Not Detected';
                obEl.className = 'pattern-status';
            }
        }

        // OTE
        const oteEl = document.getElementById('patternOTE');
        if (oteEl) {
            if (patterns.ote) {
                oteEl.textContent = `${patterns.ote.level || 'Active'} Zone`;
                oteEl.className = 'pattern-status detected';
            } else {
                oteEl.textContent = 'Not Detected';
                oteEl.className = 'pattern-status';
            }
        }

        // Liquidity
        const liqEl = document.getElementById('patternLiquidity');
        if (liqEl) {
            if (patterns.liquidity) {
                liqEl.textContent = `${patterns.liquidity.type?.toUpperCase() || 'Sweep'} Detected`;
                liqEl.className = 'pattern-status detected';
            } else {
                liqEl.textContent = 'Not Detected';
                liqEl.className = 'pattern-status';
            }
        }
    }

    // Load ICT confluence data
    async loadIctConfluence(symbol) {
        try {
            const response = await fetch(`/api/ict-strategy/confluence/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('ICT confluence error:', data.error);
                return;
            }

            // Update total confluence score
            const totalScore = data.total_score || 0;
            const maxScore = data.max_score || 26;

            document.getElementById('ictConfluenceScore').textContent = `${totalScore}/${maxScore}`;
            document.getElementById('ictConfluenceTotalScore').textContent = totalScore;

            // Update confluence bar
            const confluenceFillEl = document.getElementById('ictConfluenceFill');
            if (confluenceFillEl) {
                confluenceFillEl.style.width = `${(totalScore / maxScore) * 100}%`;
            }

            // Convert factors array to map for easy lookup (include reason and is_aligned)
            const factorsArray = data.factors || [];
            const factorMap = {};
            factorsArray.forEach(f => {
                factorMap[f.name] = {
                    points: f.points,
                    max_points: f.max_points,
                    reason: f.reason || '',
                    is_aligned: f.is_aligned || false
                };
            });

            // Update individual factors with scores and reasons (map API names to UI element IDs)
            this.updateConfluenceFactor('cfMarketStructure', factorMap['Market Structure']);
            this.updateConfluenceFactor('cfPremiumDiscount', factorMap['Premium/Discount Zone']);
            this.updateConfluenceFactor('cfOrderBlock', factorMap['Order Block']);
            this.updateConfluenceFactor('cfFVG', factorMap['Fair Value Gap']);
            this.updateConfluenceFactor('cfOTE', factorMap['OTE Level']);
            this.updateConfluenceFactor('cfMSS', factorMap['Market Structure Shift']);
            this.updateConfluenceFactor('cfLiquidity', factorMap['Liquidity Zone']);
            this.updateConfluenceFactor('cfDisplacement', factorMap['Displacement']);
            this.updateConfluenceFactor('cfSession', factorMap['Session']);
            this.updateConfluenceFactor('cfML', factorMap['ML Model']);

        } catch (error) {
            console.error('Error loading ICT confluence:', error);
        }
    }

    // Helper to update a confluence factor display
    updateConfluenceFactor(elementId, factorData) {
        const scoreEl = document.getElementById(elementId);
        const fillEl = document.getElementById(elementId + 'Fill');
        const reasonEl = document.getElementById(elementId + 'Reason');

        // Handle both old format (score, maxScore) and new format (factorData object)
        let score, maxScore, reason, isAligned;
        if (typeof factorData === 'object' && factorData !== null) {
            score = factorData.points || 0;
            maxScore = factorData.max_points || 3;
            reason = factorData.reason || '--';
            isAligned = factorData.is_aligned || false;
        } else {
            score = factorData || 0;
            maxScore = 3;
            reason = '--';
            isAligned = score > 0;
        }

        if (scoreEl) {
            scoreEl.textContent = `${score}/${maxScore}`;
        }

        if (fillEl) {
            const percentage = (score / maxScore) * 100;
            fillEl.style.width = `${percentage}%`;

            // Color based on score percentage
            if (percentage >= 75) {
                fillEl.className = 'factor-fill high';
            } else if (percentage >= 40) {
                fillEl.className = 'factor-fill medium';
            } else if (percentage > 0) {
                fillEl.className = 'factor-fill low';
            } else {
                fillEl.className = 'factor-fill';
            }
        }

        // Update reason text and styling
        if (reasonEl) {
            reasonEl.textContent = reason;
            reasonEl.className = isAligned ? 'factor-reason aligned' : 'factor-reason not-aligned';
        }
    }

    // Run ICT backtest
    async runIctBacktest() {
        const symbol = document.getElementById('ictBacktestSymbol')?.value || 'BTC/USD';
        const startDate = document.getElementById('ictBacktestStart')?.value;
        const endDate = document.getElementById('ictBacktestEnd')?.value;
        const minConfluence = parseInt(document.getElementById('ictMinConfluence')?.value || '15');

        this.log(`Running ICT backtest for ${symbol}...`, 'info');

        try {
            const response = await fetch('/api/ict-strategy/backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    symbol: symbol,
                    start_date: startDate,
                    end_date: endDate,
                    min_confluence: minConfluence
                })
            });

            const data = await response.json();

            if (data.error) {
                this.log(`ICT backtest error: ${data.error}`, 'error');
                return;
            }

            // Show results
            const resultsEl = document.getElementById('ictBacktestResults');
            if (resultsEl) {
                resultsEl.style.display = 'grid';
            }

            // Update result values
            document.getElementById('ictBtTotalTrades').textContent = data.total_trades || '--';

            const winRateEl = document.getElementById('ictBtWinRate');
            if (winRateEl) {
                const winRate = data.win_rate_pct ?? (data.win_rate ? data.win_rate * 100 : NaN);
                winRateEl.textContent = !isNaN(winRate) ? `${winRate.toFixed(1)}%` : '--';
                winRateEl.className = `result-value ${winRate >= 50 ? 'pnl-positive' : 'pnl-negative'}`;
            }

            document.getElementById('ictBtProfitFactor').textContent = data.profit_factor?.toFixed(2) || '--';

            const returnEl = document.getElementById('ictBtReturn');
            if (returnEl) {
                const totalReturn = data.total_return_pct ?? (data.total_return ? data.total_return * 100 : NaN);
                returnEl.textContent = !isNaN(totalReturn) ? `${totalReturn.toFixed(2)}%` : '--';
                returnEl.className = `result-value ${totalReturn >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
            }

            // Calculate avg R:R from trades if available
            let avgRR = '--';
            if (data.trades && data.trades.length > 0) {
                const winningTrades = data.trades.filter(t => t.pnl_pct > 0);
                const losingTrades = data.trades.filter(t => t.pnl_pct <= 0);
                if (winningTrades.length > 0 && losingTrades.length > 0) {
                    const avgWin = winningTrades.reduce((sum, t) => sum + t.pnl_pct, 0) / winningTrades.length;
                    const avgLoss = Math.abs(losingTrades.reduce((sum, t) => sum + t.pnl_pct, 0) / losingTrades.length);
                    if (avgLoss > 0) {
                        avgRR = `1:${(avgWin / avgLoss).toFixed(1)}`;
                    }
                }
            }
            document.getElementById('ictBtAvgRR').textContent = avgRR;

            const maxDrawdown = data.max_drawdown_pct ?? (data.max_drawdown ? data.max_drawdown * 100 : NaN);
            document.getElementById('ictBtDrawdown').textContent = !isNaN(maxDrawdown) ? `${maxDrawdown.toFixed(2)}%` : '--';

            this.log('ICT backtest completed', 'success');

        } catch (error) {
            this.log(`ICT backtest error: ${error.message}`, 'error');
        }
    }

    // ==========================================
    // SILVER BULLET & SMT METHODS
    // ==========================================

    // Load Silver Bullet status and setup
    async loadSilverBullet() {
        const symbol = this.currentSymbol.replace('/', '-');

        try {
            // Load status and setup in parallel
            const [statusRes, setupRes] = await Promise.all([
                fetch('/api/ict-strategy/silver-bullet/status'),
                fetch(`/api/ict-strategy/silver-bullet/${symbol}`)
            ]);

            const status = await statusRes.json();
            const setup = await setupRes.json();

            // Update window badge
            const windowBadge = document.getElementById('sbWindowBadge');
            if (windowBadge) {
                if (status.current_window === 'am') {
                    windowBadge.textContent = 'AM WINDOW ACTIVE';
                    windowBadge.className = 'sb-window-badge am-active';
                } else if (status.current_window === 'pm') {
                    windowBadge.textContent = 'PM WINDOW ACTIVE';
                    windowBadge.className = 'sb-window-badge pm-active';
                } else {
                    windowBadge.textContent = 'OFF HOURS';
                    windowBadge.className = 'sb-window-badge';
                }
            }

            // Update next window
            const nextWindowEl = document.getElementById('sbNextWindow');
            if (nextWindowEl && status.time_until_next) {
                const seconds = status.time_until_seconds;
                const hours = Math.floor(seconds / 3600);
                const mins = Math.floor((seconds % 3600) / 60);
                nextWindowEl.textContent = `${status.next_window.toUpperCase()} in ${hours}h ${mins}m`;
            }

            // Update signal badge
            const signalBadge = document.getElementById('sbSignalBadge');
            if (signalBadge) {
                const signal = setup.signal || 'no_setup';
                if (signal === 'long') {
                    signalBadge.textContent = 'LONG SETUP';
                    signalBadge.className = 'sb-signal-badge long';
                } else if (signal === 'short') {
                    signalBadge.textContent = 'SHORT SETUP';
                    signalBadge.className = 'sb-signal-badge short';
                } else {
                    signalBadge.textContent = 'NO SETUP';
                    signalBadge.className = 'sb-signal-badge';
                }
            }

            // Update setup details
            if (setup.liquidity_sweep) {
                document.getElementById('sbLiquiditySwept').textContent =
                    `${setup.liquidity_sweep.type} @ ${this.formatCurrency(setup.liquidity_sweep.level)}`;
            } else {
                document.getElementById('sbLiquiditySwept').textContent = 'Not detected';
            }

            if (setup.mss) {
                document.getElementById('sbMssConfirmed').textContent =
                    setup.mss.confirmed ? `Yes (${setup.mss.direction})` : 'No';
            }

            if (setup.entry_zone) {
                document.getElementById('sbEntryZone').textContent =
                    setup.entry_zone.type?.toUpperCase() || '--';
            }

            if (setup.risk_management) {
                const rm = setup.risk_management;
                document.getElementById('sbEntryPrice').textContent =
                    rm.entry ? this.formatCurrency(rm.entry) : '--';
                document.getElementById('sbStopLoss').textContent =
                    rm.stop_loss ? this.formatCurrency(rm.stop_loss) : '--';
                document.getElementById('sbTakeProfit1').textContent =
                    rm.take_profit_1 ? this.formatCurrency(rm.take_profit_1) : '--';
                document.getElementById('sbRiskReward').textContent =
                    rm.risk_reward ? `1:${rm.risk_reward.toFixed(1)}` : '--';
            }

            document.getElementById('sbConfidence').textContent =
                setup.confidence ? `${setup.confidence.toFixed(0)}%` : '--';

            // Update reasons
            const reasonList = document.getElementById('sbReasonList');
            if (reasonList && setup.reasons) {
                reasonList.innerHTML = setup.reasons.map(reason => {
                    return `<div class="reason-item">${reason}</div>`;
                }).join('');
            }

        } catch (error) {
            console.error('Error loading Silver Bullet:', error);
        }
    }

    // Load SMT Divergence analysis
    async loadSmtDivergence() {
        const symbol = this.currentSymbol.replace('/', '-');

        try {
            const response = await fetch(`/api/ict-strategy/smt-divergence/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('SMT error:', data.error);
                return;
            }

            // Update correlation
            const corrEl = document.getElementById('smtCorrelation');
            if (corrEl) {
                const corr = data.correlation || 0;
                corrEl.textContent = corr.toFixed(4);
            }

            // Update asset names
            document.getElementById('smtAssetA').textContent = data.primary_symbol || this.currentSymbol;
            document.getElementById('smtAssetB').textContent = data.comparison_symbol || 'ETH/USD';

            // Update signal badge and divergence info
            const signalBadge = document.getElementById('smtSignalBadge');
            const div = data.divergence;

            if (div) {
                // Update signal badge
                if (signalBadge) {
                    if (div.type === 'bullish') {
                        signalBadge.textContent = 'BULLISH DIVERGENCE';
                        signalBadge.className = 'smt-signal-badge bullish';
                    } else if (div.type === 'bearish') {
                        signalBadge.textContent = 'BEARISH DIVERGENCE';
                        signalBadge.className = 'smt-signal-badge bearish';
                    }
                }

                // Update VS icon
                const vsIcon = document.getElementById('smtVsIcon');
                if (vsIcon) {
                    vsIcon.textContent = div.type === 'bullish' ? '↗' : '↘';
                    vsIcon.className = `vs-icon ${div.type}`;
                }
                document.getElementById('smtDivType').textContent = div.type?.toUpperCase() || '--';

                // Update primary asset swing
                const swingA = document.getElementById('smtSwingA');
                if (swingA && div.primary) {
                    swingA.textContent = div.primary.swing_type?.replace('_', ' ').toUpperCase() || '--';
                    swingA.className = `asset-swing ${div.primary.swing_type?.replace('_', '-') || ''}`;
                }

                // Update comparison asset swing
                const swingB = document.getElementById('smtSwingB');
                if (swingB && div.comparison) {
                    swingB.textContent = div.comparison.swing_type?.replace('_', ' ').toUpperCase() || '--';
                    swingB.className = `asset-swing ${div.comparison.swing_type?.replace('_', '-') || ''}`;
                }

                // Update prices
                if (div.primary) {
                    document.getElementById('smtPriceA').textContent =
                        this.formatCurrency(div.primary.current_price);
                    document.getElementById('smtPrevPriceA').textContent =
                        this.formatCurrency(div.primary.previous_price);
                }
                if (div.comparison) {
                    document.getElementById('smtPriceB').textContent =
                        this.formatCurrency(div.comparison.current_price);
                    document.getElementById('smtPrevPriceB').textContent =
                        this.formatCurrency(div.comparison.previous_price);
                }

                // Update analysis details
                document.getElementById('smtType').textContent = div.type?.toUpperCase() || 'None';
                document.getElementById('smtSignal').textContent = div.signal || '--';
                document.getElementById('smtStrength').textContent =
                    div.strength ? `${div.strength.toFixed(4)}%` : '--';
                document.getElementById('smtConfidence').textContent =
                    div.confidence ? `${div.confidence.toFixed(0)}%` : '--';

            } else {
                // No divergence detected
                if (signalBadge) {
                    signalBadge.textContent = 'NO DIVERGENCE';
                    signalBadge.className = 'smt-signal-badge';
                }

                document.getElementById('smtSwingA').textContent = '--';
                document.getElementById('smtSwingA').className = 'asset-swing';
                document.getElementById('smtSwingB').textContent = '--';
                document.getElementById('smtSwingB').className = 'asset-swing';

                document.getElementById('smtVsIcon').textContent = '⟷';
                document.getElementById('smtVsIcon').className = 'vs-icon';
                document.getElementById('smtDivType').textContent = '--';

                document.getElementById('smtType').textContent = 'None Detected';
                document.getElementById('smtSignal').textContent = '--';
                document.getElementById('smtStrength').textContent = '--';
                document.getElementById('smtConfidence').textContent = '--';
            }

        } catch (error) {
            console.error('Error loading SMT divergence:', error);
        }
    }

    // Load Multi-Timeframe Analysis
    async loadMtfAnalysis() {
        const symbol = this.currentSymbol.replace('/', '-');

        try {
            const response = await fetch(`/api/ict-strategy/mtf/${symbol}`);
            const data = await response.json();

            if (data.error) {
                console.error('MTF analysis error:', data.error);
                this.updateMtfLoadingState('Error loading MTF data');
                return;
            }

            // Update overall bias summary
            const overallBiasEl = document.getElementById('mtfOverallBias');
            if (overallBiasEl) {
                const bias = data.overall_bias || 'neutral';
                overallBiasEl.textContent = bias.toUpperCase().replace('_', ' ');
                overallBiasEl.className = `mtf-bias-badge ${bias}`;
            }

            const overallConfEl = document.getElementById('mtfOverallConfidence');
            if (overallConfEl) {
                overallConfEl.textContent = `${((data.overall_confidence || 0) * 100).toFixed(0)}% confidence`;
            }

            // Update alignment score
            const alignmentScoreEl = document.getElementById('mtfAlignmentScore');
            if (alignmentScoreEl) {
                alignmentScoreEl.textContent = (data.alignment_score || 0).toFixed(0);
            }

            // Update alignment badge color based on score
            const alignmentBadgeEl = document.getElementById('mtfAlignmentBadge');
            if (alignmentBadgeEl) {
                const score = data.alignment_score || 0;
                if (score >= 80) {
                    alignmentBadgeEl.style.background = 'rgba(34, 197, 94, 0.2)';
                    alignmentBadgeEl.style.color = '#22c55e';
                } else if (score >= 60) {
                    alignmentBadgeEl.style.background = 'rgba(234, 179, 8, 0.2)';
                    alignmentBadgeEl.style.color = '#eab308';
                } else {
                    alignmentBadgeEl.style.background = 'rgba(239, 68, 68, 0.2)';
                    alignmentBadgeEl.style.color = '#ef4444';
                }
            }

            // Update recommended direction
            const directionEl = document.getElementById('mtfDirection');
            if (directionEl) {
                const direction = data.recommended_direction || 'wait';
                directionEl.textContent = direction.toUpperCase();
                directionEl.className = `mtf-direction-badge ${direction}`;
            }

            const entryTfEl = document.getElementById('mtfEntryTf');
            if (entryTfEl) {
                entryTfEl.textContent = `Entry TF: ${data.entry_timeframe || '5m'}`;
            }

            // Update each timeframe row
            const tfMapping = {
                '1d': 'Daily',
                '4h': '4h',
                '1h': '1h',
                '15m': '15m',
                '5m': '5m'
            };

            for (const [tf, tfData] of Object.entries(data.timeframes || {})) {
                this.updateMtfTimeframeRow(tf, tfData);
            }

            // Update key levels
            this.updateMtfKeyLevels(data.key_levels || {});

            // Update reasoning tab
            if (data.reasoning) {
                this.updateMtfReasoning(data.reasoning);
            }

        } catch (error) {
            console.error('Error loading MTF analysis:', error);
            this.updateMtfLoadingState('Error loading MTF data');
        }
    }

    // Update MTF Reasoning Tab with detailed analysis
    updateMtfReasoning(reasoning) {
        // Summary
        const summaryEl = document.getElementById('mtfReasoningSummary');
        if (summaryEl) {
            summaryEl.textContent = reasoning.summary || 'Analysis not available';
        }

        // Direction reason
        const dirReasonEl = document.getElementById('mtfDirectionReason');
        if (dirReasonEl) {
            dirReasonEl.textContent = reasoning.direction_reason || '--';
        }

        // Confidence reason
        const confReasonEl = document.getElementById('mtfConfidenceReason');
        if (confReasonEl) {
            confReasonEl.textContent = reasoning.confidence_reason || '--';
        }

        // Alignment reason
        const alignReasonEl = document.getElementById('mtfAlignmentReason');
        if (alignReasonEl) {
            alignReasonEl.textContent = reasoning.alignment_reason || '--';
        }

        // Timeframe reasoning
        const tfReasonsEl = document.getElementById('mtfTimeframeReasons');
        if (tfReasonsEl && reasoning.timeframe_reasons) {
            const tfOrder = ['1d', '4h', '1h', '15m', '5m'];
            const tfNames = {
                '1d': { badge: 'daily', name: 'Daily', short: '1D' },
                '4h': { badge: 'h4', name: '4-Hour', short: '4H' },
                '1h': { badge: 'h1', name: 'Hourly', short: '1H' },
                '15m': { badge: 'm15', name: '15-Minute', short: '15m' },
                '5m': { badge: 'm5', name: '5-Minute', short: '5m' }
            };

            let tfHtml = '';
            for (const tf of tfOrder) {
                if (reasoning.timeframe_reasons[tf]) {
                    const tfr = reasoning.timeframe_reasons[tf];
                    const tfInfo = tfNames[tf];
                    tfHtml += `
                        <div class="tf-reasoning-item">
                            <div class="tf-reasoning-header">
                                <div class="tf-reasoning-name">
                                    <span class="tf-reasoning-badge ${tfInfo.badge}">${tfInfo.short}</span>
                                    <span class="tf-reasoning-title">${tfInfo.name}</span>
                                </div>
                                <span class="tf-reasoning-bias ${tfr.bias}">${tfr.bias.replace('_', ' ').toUpperCase()}</span>
                            </div>
                            <div class="tf-reasoning-details">
                                <div class="tf-detail-item">
                                    <div class="tf-detail-label">Structure Analysis</div>
                                    <div class="tf-detail-value">${tfr.structure_summary || 'N/A'}</div>
                                </div>
                                <div class="tf-detail-item">
                                    <div class="tf-detail-label">Pattern Observation</div>
                                    <div class="tf-detail-value">${tfr.pattern_observation || 'N/A'}</div>
                                </div>
                                ${tfr.key_level_observation ? `
                                <div class="tf-detail-item">
                                    <div class="tf-detail-label">Key Levels</div>
                                    <div class="tf-detail-value">${tfr.key_level_observation}</div>
                                </div>
                                ` : ''}
                            </div>
                        </div>
                    `;
                }
            }
            tfReasonsEl.innerHTML = tfHtml || '<div class="tf-reasoning-item">No timeframe data available</div>';
        }

        // Key observations
        const obsEl = document.getElementById('mtfObservations');
        if (obsEl && reasoning.key_observations) {
            if (reasoning.key_observations.length > 0) {
                obsEl.innerHTML = reasoning.key_observations.map(obs => `<li>${obs}</li>`).join('');
            } else {
                obsEl.innerHTML = '<li>No specific observations at this time</li>';
            }
        }

        // Warnings
        const warningsSection = document.getElementById('mtfWarningsSection');
        const warningsEl = document.getElementById('mtfWarnings');
        if (warningsSection && warningsEl) {
            if (reasoning.warnings && reasoning.warnings.length > 0) {
                warningsSection.style.display = 'block';
                warningsEl.innerHTML = reasoning.warnings.map(w => `<li>${w}</li>`).join('');
            } else {
                warningsSection.style.display = 'none';
            }
        }

        // Action items
        const actionsEl = document.getElementById('mtfActionItems');
        if (actionsEl && reasoning.action_items) {
            if (reasoning.action_items.length > 0) {
                actionsEl.innerHTML = reasoning.action_items.map(a => `<li>${a}</li>`).join('');
            } else {
                actionsEl.innerHTML = '<li>No specific actions recommended</li>';
            }
        }
    }

    // Update a single timeframe row in the MTF display
    updateMtfTimeframeRow(tf, tfData) {
        const tfIdMap = {
            '1d': 'Daily',
            '4h': '4h',
            '1h': '1h',
            '15m': '15m',
            '5m': '5m'
        };

        const tfId = tfIdMap[tf];
        if (!tfId) return;

        // Update bias indicator
        const biasEl = document.getElementById(`mtf${tfId}Bias`);
        if (biasEl) {
            const bias = tfData.bias || 'neutral';
            biasEl.textContent = bias.toUpperCase().replace('_', ' ');
            biasEl.className = `mtf-bias-indicator ${bias}`;
        }

        // Update structure counts
        const structure = tfData.structure || {};
        const hhEl = document.getElementById(`mtf${tfId}HH`);
        const hlEl = document.getElementById(`mtf${tfId}HL`);
        const lhEl = document.getElementById(`mtf${tfId}LH`);
        const llEl = document.getElementById(`mtf${tfId}LL`);

        if (hhEl) hhEl.textContent = `HH: ${structure.hh_count || 0}`;
        if (hlEl) hlEl.textContent = `HL: ${structure.hl_count || 0}`;
        if (lhEl) lhEl.textContent = `LH: ${structure.lh_count || 0}`;
        if (llEl) llEl.textContent = `LL: ${structure.ll_count || 0}`;

        // Update confidence
        const confEl = document.getElementById(`mtf${tfId}Conf`);
        if (confEl) {
            confEl.textContent = `${((tfData.confidence || 0) * 100).toFixed(0)}%`;
        }

        // Update lookback period
        const periodEl = document.getElementById(`mtf${tfId}Period`);
        if (periodEl && tfData.lookback_period) {
            periodEl.textContent = tfData.lookback_period;
        }
    }

    // Update MTF key levels display
    updateMtfKeyLevels(keyLevels) {
        // Daily levels
        const dailyLevelsEl = document.getElementById('mtfDailyLevels');
        if (dailyLevelsEl) {
            const dailyLevels = keyLevels.daily || [];
            if (dailyLevels.length > 0) {
                dailyLevelsEl.innerHTML = dailyLevels.slice(0, 6).map(level => `
                    <div class="level-item ${level.type || ''}">
                        <span class="level-name">${level.name || 'Level'}</span>
                        <span class="level-price">${this.formatCurrency(level.price)}</span>
                    </div>
                `).join('');
            } else {
                dailyLevelsEl.innerHTML = '<div class="level-item">No levels detected</div>';
            }
        }

        // Intermediate levels (4H/1H)
        const intermediateLevelsEl = document.getElementById('mtfIntermediateLevels');
        if (intermediateLevelsEl) {
            const intermediateLevels = keyLevels.intermediate || [];
            if (intermediateLevels.length > 0) {
                intermediateLevelsEl.innerHTML = intermediateLevels.slice(0, 6).map(level => `
                    <div class="level-item ${level.type || ''}">
                        <span class="level-name">${level.name || 'Level'}</span>
                        <span class="level-price">${this.formatCurrency(level.price)}</span>
                    </div>
                `).join('');
            } else {
                intermediateLevelsEl.innerHTML = '<div class="level-item">No levels detected</div>';
            }
        }

        // Entry levels (15m/5m)
        const entryLevelsEl = document.getElementById('mtfEntryLevels');
        if (entryLevelsEl) {
            const entryLevels = keyLevels.entry || [];
            if (entryLevels.length > 0) {
                entryLevelsEl.innerHTML = entryLevels.slice(0, 6).map(level => `
                    <div class="level-item ${level.type || ''}">
                        <span class="level-name">${level.name || 'Level'}</span>
                        <span class="level-price">${this.formatCurrency(level.price)}</span>
                    </div>
                `).join('');
            } else {
                entryLevelsEl.innerHTML = '<div class="level-item">No levels detected</div>';
            }
        }
    }

    // Update MTF loading state with message
    updateMtfLoadingState(message) {
        const dailyLevelsEl = document.getElementById('mtfDailyLevels');
        const intermediateLevelsEl = document.getElementById('mtfIntermediateLevels');
        const entryLevelsEl = document.getElementById('mtfEntryLevels');

        const loadingHtml = `<div class="level-item">${message}</div>`;

        if (dailyLevelsEl) dailyLevelsEl.innerHTML = loadingHtml;
        if (intermediateLevelsEl) intermediateLevelsEl.innerHTML = loadingHtml;
        if (entryLevelsEl) entryLevelsEl.innerHTML = loadingHtml;
    }

    // ==========================================
    // SCALPING BOT METHODS
    // ==========================================

    // Trading mode descriptions
    tradingModeDescriptions = {
        safe: "Conservative trading - waits for strong confluence (fewer trades, higher win rate)",
        medium: "Balanced trading - moderate confluence requirements",
        fast: "Aggressive trading - lower confluence, more trades (higher risk)",
        custom: "Custom parameters - configure your own confluence settings"
    };

    initTradingModeSelector() {
        const modeBtns = document.querySelectorAll('.mode-btn');
        const modeInput = document.getElementById('tradingModeValue');
        const modeDesc = document.querySelector('.mode-desc-text');
        const customParams = document.getElementById('customParams');
        const simpleRiskRow = document.getElementById('simpleRiskRow');

        modeBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                // Update active state
                modeBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');

                const mode = btn.dataset.mode;
                if (modeInput) modeInput.value = mode;

                // Update description
                if (modeDesc) {
                    modeDesc.textContent = this.tradingModeDescriptions[mode] || '';
                }

                // Show/hide custom params
                if (customParams && simpleRiskRow) {
                    if (mode === 'custom') {
                        customParams.style.display = 'block';
                        simpleRiskRow.style.display = 'none';
                    } else {
                        customParams.style.display = 'none';
                        simpleRiskRow.style.display = 'flex';
                    }
                }

                // Update description border color based on mode
                const descEl = document.getElementById('modeDescription');
                if (descEl) {
                    const colors = {
                        safe: 'var(--accent-green)',
                        medium: 'var(--accent-blue)',
                        fast: 'var(--accent-yellow)',
                        custom: 'var(--accent-purple)'
                    };
                    descEl.style.borderLeftColor = colors[mode] || 'var(--accent-blue)';
                }
            });
        });
    }

    initConfluenceSelector() {
        const checkboxes = document.querySelectorAll('input[name="confluence"]');
        const countEl = document.getElementById('confluenceCount');
        const selectAllBtn = document.getElementById('selectAllConfluence');
        const deselectAllBtn = document.getElementById('deselectAllConfluence');

        // Update count when checkboxes change
        const updateCount = () => {
            const total = checkboxes.length;
            const checked = document.querySelectorAll('input[name="confluence"]:checked').length;
            if (countEl) {
                countEl.textContent = `${checked}/${total} Active`;
                // Change color based on count
                if (checked === total) {
                    countEl.style.background = 'var(--accent-green)';
                } else if (checked >= total / 2) {
                    countEl.style.background = 'var(--accent-blue)';
                } else if (checked > 0) {
                    countEl.style.background = 'var(--accent-yellow)';
                    countEl.style.color = '#1a1a24';
                } else {
                    countEl.style.background = 'var(--accent-red)';
                    countEl.style.color = 'white';
                }
            }
        };

        checkboxes.forEach(cb => {
            cb.addEventListener('change', updateCount);
        });

        // Select all button
        selectAllBtn?.addEventListener('click', () => {
            checkboxes.forEach(cb => cb.checked = true);
            updateCount();
        });

        // Deselect all button
        deselectAllBtn?.addEventListener('click', () => {
            checkboxes.forEach(cb => cb.checked = false);
            updateCount();
        });

        // Initial count
        updateCount();
    }

    initTradingTabs() {
        const tabs = document.querySelectorAll('.trading-tab');
        const tabContents = document.querySelectorAll('.trading-tab-content');

        tabs.forEach(tab => {
            tab.addEventListener('click', () => {
                const targetTab = tab.dataset.tab;

                // Update active tab
                tabs.forEach(t => t.classList.remove('active'));
                tab.classList.add('active');

                // Update active content
                tabContents.forEach(content => {
                    content.classList.remove('active');
                    if (content.id === `tab-${targetTab}`) {
                        content.classList.add('active');
                    }
                });
            });
        });
    }

    initBotControls() {
        // Short Term Bot Controls
        document.getElementById('startShortTerm')?.addEventListener('click', () => this.startBot('short-term'));
        document.getElementById('pauseShortTerm')?.addEventListener('click', () => this.pauseBot('short-term'));
        document.getElementById('stopShortTerm')?.addEventListener('click', () => this.stopBot('short-term'));

        // Swing Bot Controls
        document.getElementById('startSwing')?.addEventListener('click', () => this.startBot('swing'));
        document.getElementById('pauseSwing')?.addEventListener('click', () => this.pauseBot('swing'));
        document.getElementById('stopSwing')?.addEventListener('click', () => this.stopBot('swing'));

        // Long Term Bot Controls
        document.getElementById('startLongTerm')?.addEventListener('click', () => this.startBot('long-term'));
        document.getElementById('pauseLongTerm')?.addEventListener('click', () => this.pauseBot('long-term'));
        document.getElementById('stopLongTerm')?.addEventListener('click', () => this.stopBot('long-term'));

        // Mode selectors for each bot with dynamic descriptions
        const botModeConfigs = {
            'shortTermModeSelector': {
                descEl: 'shortTermModeDesc',
                modeDisplayEl: 'shortTermModeDisplay',
                descriptions: {
                    conservative: '4H timeframe • 3% target • 1.5% stop loss • Fewer trades, higher win rate',
                    medium: '4H timeframe • 2% target • 1% stop loss • Balanced approach',
                    aggressive: '4H timeframe • 1.5% target • 0.75% stop loss • More trades, higher risk'
                }
            },
            'swingModeSelector': {
                descEl: 'swingModeDesc',
                modeDisplayEl: 'swingModeDisplay',
                descriptions: {
                    conservative: 'Daily timeframe • 15% target • 5% stop loss • Fewer trades, higher win rate',
                    medium: 'Daily timeframe • 12% target • 4% stop loss • Balanced approach',
                    aggressive: 'Daily timeframe • 8% target • 3% stop loss • More trades, higher risk'
                }
            },
            'longTermModeSelector': {
                descEl: 'longTermModeDesc',
                modeDisplayEl: 'longTermModeDisplay',
                descriptions: {
                    conservative: 'Weekly timeframe • 50% target • 15% stop loss • DCA enabled • Fewer trades',
                    medium: 'Weekly timeframe • 35% target • 10% stop loss • DCA enabled • Balanced',
                    aggressive: 'Weekly timeframe • 25% target • 7% stop loss • DCA enabled • More trades'
                }
            }
        };

        Object.entries(botModeConfigs).forEach(([selectorId, config]) => {
            const selector = document.getElementById(selectorId);
            if (selector) {
                selector.querySelectorAll('.mode-btn').forEach(btn => {
                    btn.addEventListener('click', () => {
                        selector.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
                        btn.classList.add('active');

                        // Update description
                        const mode = btn.dataset.mode;
                        const descEl = document.getElementById(config.descEl);
                        if (descEl) {
                            const descText = descEl.querySelector('.mode-desc-text');
                            if (descText && config.descriptions[mode]) {
                                descText.textContent = config.descriptions[mode];
                            }
                            // Update border color based on mode
                            const colors = {
                                conservative: 'var(--accent-green)',
                                medium: 'var(--accent-blue)',
                                aggressive: 'var(--accent-yellow)'
                            };
                            descEl.style.borderLeftColor = colors[mode] || 'var(--accent-blue)';
                        }

                        // Update Mode display in Live Statistics
                        const modeDisplay = document.getElementById(config.modeDisplayEl);
                        if (modeDisplay) {
                            const displayNames = {
                                conservative: 'CONSERV',
                                medium: 'MEDIUM',
                                aggressive: 'AGGRESS'
                            };
                            modeDisplay.textContent = displayNames[mode] || mode.toUpperCase();
                            // Color code the mode
                            modeDisplay.classList.remove('mode-conservative', 'mode-medium', 'mode-aggressive');
                            modeDisplay.classList.add(`mode-${mode}`);
                        }
                    });
                });
            }
        });

        // Poll all bot statuses
        setInterval(() => {
            if (document.getElementById('page-trade')?.classList.contains('active')) {
                this.loadAllBotStatuses();
            }
        }, 5000);

        // Load bot statuses immediately on init
        this.loadAllBotStatuses();
    }

    async startBot(botType) {
        const configMap = {
            'short-term': {
                modeEl: 'shortTermMode',
                capitalEl: 'shortTermCapital',
                modeSelectorEl: 'shortTermModeSelector'
            },
            'swing': {
                modeEl: 'swingMode',
                capitalEl: 'swingCapital',
                modeSelectorEl: 'swingModeSelector'
            },
            'long-term': {
                modeEl: 'longTermMode',
                capitalEl: 'longTermCapital',
                modeSelectorEl: 'longTermModeSelector'
            }
        };

        const config = configMap[botType];
        if (!config) return;

        const mode = document.getElementById(config.modeEl)?.value || 'paper';
        const capital = parseFloat(document.getElementById(config.capitalEl)?.value) || 1000;
        const tradingMode = document.getElementById(config.modeSelectorEl)?.querySelector('.mode-btn.active')?.dataset.mode || 'medium';

        try {
            const response = await fetch(`/api/${botType}/start`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    mode: mode,
                    capital: capital,
                    symbol: 'BTC/USD',
                    trading_mode: tradingMode
                })
            });

            const result = await response.json();
            if (result.status === 'started') {
                this.updateBotButtons(botType, 'running');
                this.showNotification(`${botType} bot started successfully`, 'success');
            } else if (result.error) {
                this.showNotification(result.error, 'error');
            }
        } catch (error) {
            console.error(`Error starting ${botType} bot:`, error);
            this.showNotification(`Failed to start ${botType} bot`, 'error');
        }
    }

    async stopBot(botType) {
        try {
            const response = await fetch(`/api/${botType}/stop`, { method: 'POST' });
            const result = await response.json();
            if (result.status === 'stopped') {
                this.updateBotButtons(botType, 'stopped');
                this.showNotification(`${botType} bot stopped`, 'info');
            }
        } catch (error) {
            console.error(`Error stopping ${botType} bot:`, error);
        }
    }

    async pauseBot(botType) {
        try {
            const response = await fetch(`/api/${botType}/pause`, { method: 'POST' });
            const result = await response.json();
            if (result.status === 'paused') {
                this.updateBotButtons(botType, 'paused');
                this.showNotification(`${botType} bot paused`, 'info');
            }
        } catch (error) {
            console.error(`Error pausing ${botType} bot:`, error);
        }
    }

    updateBotButtons(botType, status) {
        const buttonMap = {
            'short-term': { start: 'startShortTerm', pause: 'pauseShortTerm', stop: 'stopShortTerm' },
            'swing': { start: 'startSwing', pause: 'pauseSwing', stop: 'stopSwing' },
            'long-term': { start: 'startLongTerm', pause: 'pauseLongTerm', stop: 'stopLongTerm' }
        };

        const buttons = buttonMap[botType];
        if (!buttons) return;

        const startBtn = document.getElementById(buttons.start);
        const pauseBtn = document.getElementById(buttons.pause);
        const stopBtn = document.getElementById(buttons.stop);

        if (status === 'running') {
            if (startBtn) startBtn.disabled = true;
            if (pauseBtn) pauseBtn.disabled = false;
            if (stopBtn) stopBtn.disabled = false;
        } else if (status === 'paused') {
            if (startBtn) startBtn.disabled = false;
            if (pauseBtn) pauseBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = false;
        } else {
            if (startBtn) startBtn.disabled = false;
            if (pauseBtn) pauseBtn.disabled = true;
            if (stopBtn) stopBtn.disabled = true;
        }
    }

    async loadAllBotStatuses() {
        try {
            const response = await fetch('/api/bots/status');
            const data = await response.json();

            let activeCount = 0;

            // Update Short Term
            if (data.short_term) {
                this.updateBotDisplay('shortTerm', data.short_term);
                this.updateBotMonitor('shortTerm', data.short_term);
                if (data.short_term.status === 'running') activeCount++;
            }

            // Update Swing
            if (data.swing) {
                this.updateBotDisplay('swing', data.swing);
                this.updateBotMonitor('swing', data.swing);
                if (data.swing.status === 'running') activeCount++;
            }

            // Update Long Term
            if (data.long_term) {
                this.updateBotDisplay('longTerm', data.long_term);
                this.updateBotMonitor('longTerm', data.long_term);
                if (data.long_term.status === 'running') activeCount++;
            }

            // Also update scalping in monitor
            await this.updateScalpingMonitor();

            // Update active count
            const countEl = document.getElementById('activeBotsCount');
            if (countEl) {
                const scalpingStatus = document.getElementById('scalpingIndicator')?.classList.contains('running') ? 1 : 0;
                const totalActive = activeCount + scalpingStatus;
                countEl.textContent = `${totalActive} Active`;
                countEl.classList.toggle('has-active', totalActive > 0);
            }
        } catch (error) {
            console.error('Error loading bot statuses:', error);
        }
    }

    async updateScalpingMonitor() {
        try {
            const response = await fetch('/api/scalping/status');
            const data = await response.json();

            const indicator = document.getElementById('scalpingIndicator');
            const modeEl = document.getElementById('scalpingModeMonitor');
            const signalEl = document.getElementById('scalpingSignalMonitor');
            const pnlEl = document.getElementById('scalpingPnLMonitor');
            const tradesEl = document.getElementById('scalpingTradesMonitor');
            const itemEl = document.getElementById('monitorScalping');

            const status = data.status === 'not_initialized' ? 'stopped' : data.status;

            if (indicator) {
                indicator.className = 'bot-status-indicator ' + status;
            }

            if (itemEl) {
                itemEl.classList.toggle('active', status === 'running');
                itemEl.classList.toggle('scanning', status === 'running');
            }

            if (modeEl) {
                const mode = data.trading_mode?.name || 'Medium';
                modeEl.textContent = mode.replace(' Mode', '');
            }

            if (signalEl) {
                if (status === 'running') {
                    const signal = data.last_signal || 'Scanning...';
                    signalEl.textContent = signal;
                    signalEl.className = 'bot-signal ' + (signal.toLowerCase().includes('buy') ? 'bullish' : signal.toLowerCase().includes('sell') ? 'bearish' : 'scanning');
                } else {
                    signalEl.textContent = 'No Signal';
                    signalEl.className = 'bot-signal';
                }
            }

            if (pnlEl) {
                const pnl = data.stats?.total_pnl || 0;
                pnlEl.textContent = `$${pnl.toFixed(2)}`;
                pnlEl.style.color = pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
            }

            if (tradesEl) {
                tradesEl.textContent = `${data.stats?.total_trades || 0} trades`;
            }

            // Add activity if there's a new signal
            if (status === 'running' && data.last_signal && data.last_signal !== this.lastScalpingSignal) {
                this.addBotActivity('Scalping', data.last_signal, 'signal');
                this.lastScalpingSignal = data.last_signal;
            }
        } catch (error) {
            console.error('Error updating scalping monitor:', error);
        }
    }

    updateBotMonitor(prefix, data) {
        const indicator = document.getElementById(`${prefix}Indicator`);
        const modeEl = document.getElementById(`${prefix}ModeMonitor`);
        const signalEl = document.getElementById(`${prefix}SignalMonitor`);
        const pnlEl = document.getElementById(`${prefix}PnLMonitor`);
        const tradesEl = document.getElementById(`${prefix}TradesMonitor`);
        const itemEl = document.getElementById(`monitor${prefix.charAt(0).toUpperCase() + prefix.slice(1)}`);

        const status = data.status || 'stopped';

        if (indicator) {
            indicator.className = 'bot-status-indicator ' + status;
        }

        if (itemEl) {
            itemEl.classList.toggle('active', status === 'running');
            itemEl.classList.toggle('scanning', status === 'running');
        }

        if (modeEl) {
            const mode = data.trading_mode || 'Medium';
            modeEl.textContent = typeof mode === 'string' ? mode : (mode.name || 'Medium').replace(' Mode', '');
        }

        if (signalEl) {
            if (status === 'running') {
                const signal = data.last_signal || 'Scanning...';
                signalEl.textContent = signal;
                signalEl.className = 'bot-signal ' + (signal.toLowerCase().includes('buy') ? 'bullish' : signal.toLowerCase().includes('sell') ? 'bearish' : 'scanning');
            } else {
                signalEl.textContent = 'No Signal';
                signalEl.className = 'bot-signal';
            }
        }

        if (pnlEl && data.stats) {
            const pnl = data.stats.total_pnl || 0;
            pnlEl.textContent = `$${pnl.toFixed(2)}`;
            pnlEl.style.color = pnl >= 0 ? 'var(--accent-green)' : 'var(--accent-red)';
        }

        if (tradesEl && data.stats) {
            tradesEl.textContent = `${data.stats.total_trades || 0} trades`;
        }
    }

    addBotActivity(botName, message, type = 'info') {
        const feed = document.getElementById('botActivityFeed');
        if (!feed) return;

        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });

        const item = document.createElement('div');
        item.className = `activity-item ${type}`;
        item.innerHTML = `
            <span class="activity-time">${timeStr}</span>
            <span class="activity-bot">${botName}</span>
            <span class="activity-message">${message}</span>
        `;

        // Insert at top
        feed.insertBefore(item, feed.firstChild);

        // Keep only last 50 items
        while (feed.children.length > 50) {
            feed.removeChild(feed.lastChild);
        }
    }

    initBotMonitor() {
        // Clear activity log button
        document.getElementById('clearActivityLog')?.addEventListener('click', () => {
            const feed = document.getElementById('botActivityFeed');
            if (feed) {
                feed.innerHTML = `
                    <div class="activity-item info">
                        <span class="activity-time">${new Date().toLocaleTimeString('en-US', { hour12: false })}</span>
                        <span class="activity-bot">System</span>
                        <span class="activity-message">Activity log cleared</span>
                    </div>
                `;
            }
        });

        // Initialize with startup message
        this.addBotActivity('System', 'Bot monitor initialized', 'info');
    }

    updateBotDisplay(prefix, data) {
        const statusEl = document.getElementById(`${prefix}Status`);
        const capitalEl = document.getElementById(`${prefix}CapitalDisplay`);
        const pnlEl = document.getElementById(`${prefix}PnL`);
        const winRateEl = document.getElementById(`${prefix}WinRate`);
        const totalTradesEl = document.getElementById(`${prefix}TotalTrades`);
        const profitFactorEl = document.getElementById(`${prefix}ProfitFactor`);
        const positionEl = document.getElementById(`${prefix}Position`);

        if (statusEl) {
            statusEl.textContent = (data.status || 'STOPPED').toUpperCase();
            statusEl.className = 'stat-value';
            if (data.status === 'running') statusEl.classList.add('positive');
            else if (data.status === 'stopped') statusEl.classList.add('negative');
        }

        if (capitalEl) capitalEl.textContent = `$${(data.capital || 0).toLocaleString('en-US', { minimumFractionDigits: 2 })}`;

        if (pnlEl && data.stats) {
            const pnl = data.stats.total_pnl || 0;
            pnlEl.textContent = `$${pnl.toFixed(2)}`;
            pnlEl.className = 'stat-value ' + (pnl >= 0 ? 'positive' : 'negative');
        }

        if (winRateEl && data.stats) winRateEl.textContent = `${(data.stats.win_rate || 0).toFixed(1)}%`;
        if (totalTradesEl && data.stats) totalTradesEl.textContent = data.stats.total_trades || 0;
        if (profitFactorEl && data.stats) profitFactorEl.textContent = (data.stats.profit_factor || 0).toFixed(2);

        // DCA count for long term
        const dcaEl = document.getElementById(`${prefix}DCA`);
        if (dcaEl && data.dca_count !== undefined) dcaEl.textContent = data.dca_count;

        // Position display
        if (positionEl) {
            if (data.position) {
                positionEl.innerHTML = `
                    <div class="position-active">
                        <div class="pos-item">
                            <span class="pos-label">Side</span>
                            <span class="pos-value ${data.position.side}">${data.position.side.toUpperCase()}</span>
                        </div>
                        <div class="pos-item">
                            <span class="pos-label">Entry</span>
                            <span class="pos-value">$${data.position.entry_price.toFixed(2)}</span>
                        </div>
                        <div class="pos-item">
                            <span class="pos-label">Unrealized</span>
                            <span class="pos-value ${data.position.unrealized_pnl >= 0 ? 'positive' : 'negative'}">$${data.position.unrealized_pnl.toFixed(2)}</span>
                        </div>
                    </div>
                `;
            } else {
                positionEl.innerHTML = '<span class="no-position">No open position</span>';
            }
        }

        // Update button states
        const botTypeMap = { 'shortTerm': 'short-term', 'swing': 'swing', 'longTerm': 'long-term' };
        if (botTypeMap[prefix]) {
            this.updateBotButtons(botTypeMap[prefix], data.status || 'stopped');
        }
    }

    getSelectedConfluences() {
        const checkboxes = document.querySelectorAll('input[name="confluence"]:checked');
        return Array.from(checkboxes).map(cb => cb.value);
    }

    async startScalpingBot() {
        const mode = document.getElementById('scalpingMode')?.value || 'paper';
        const capital = parseFloat(document.getElementById('scalpingCapital')?.value) || 1000;
        const tradingMode = document.getElementById('tradingModeValue')?.value || 'medium';
        const risk = parseFloat(document.getElementById('scalpingRiskSimple')?.value || document.getElementById('scalpingRisk')?.value) / 100 || 0.01;

        // Get selected confluences
        const selectedConfluences = this.getSelectedConfluences();

        // Build config based on trading mode
        const config = {
            mode: mode,
            symbol: this.currentSymbol,
            initial_capital: capital,
            risk_per_trade: risk,
            trading_mode: tradingMode,
            enabled_confluences: selectedConfluences
        };

        // Add custom params if in custom mode
        if (tradingMode === 'custom') {
            const tp = parseFloat(document.getElementById('scalpingTP')?.value) / 100;
            const sl = parseFloat(document.getElementById('scalpingSL')?.value) / 100;
            const maxTrades = parseInt(document.getElementById('scalpingMaxTrades')?.value);
            const minConf = parseInt(document.getElementById('minConfidence')?.value);
            const minConfluence = parseInt(document.getElementById('minConfluenceScore')?.value);
            const minAligned = parseInt(document.getElementById('minAlignedSignals')?.value);
            const cooldown = parseInt(document.getElementById('cooldownSeconds')?.value);

            if (tp) config.take_profit_pct = tp;
            if (sl) config.stop_loss_pct = sl;
            if (maxTrades) config.max_trades_per_hour = maxTrades;
            if (minConf) config.min_confidence = minConf;
            if (minConfluence) config.min_confluence_score = minConfluence;
            if (minAligned) config.min_aligned_signals = minAligned;
            if (cooldown) config.cooldown_seconds = cooldown;
        }

        this.log(`Starting scalping bot in ${mode} mode (${tradingMode})...`, 'info');

        try {
            const response = await fetch('/api/scalping/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            const data = await response.json();

            if (data.error) {
                this.log(`Failed to start scalping: ${data.error}`, 'error');
                return;
            }

            const modeInfo = data.trading_mode || {};
            this.log(`Scalping bot started: ${data.mode} mode, ${modeInfo.name || tradingMode}, $${data.capital} capital`, 'success');

            // Update UI
            document.getElementById('startScalping').disabled = true;
            document.getElementById('pauseScalping').disabled = false;
            document.getElementById('stopScalping').disabled = false;

            this.loadScalpingStatus();

        } catch (error) {
            this.log(`Error starting scalping bot: ${error.message}`, 'error');
        }
    }

    async pauseScalpingBot() {
        try {
            const response = await fetch('/api/scalping/pause', { method: 'POST' });
            const data = await response.json();

            if (data.status === 'paused') {
                this.log('Scalping bot paused', 'warning');
                document.getElementById('pauseScalping').textContent = 'Resume';
                document.getElementById('pauseScalping').onclick = () => this.resumeScalpingBot();
            }
        } catch (error) {
            this.log(`Error pausing bot: ${error.message}`, 'error');
        }
    }

    async resumeScalpingBot() {
        try {
            const response = await fetch('/api/scalping/resume', { method: 'POST' });
            const data = await response.json();

            if (data.status === 'resumed') {
                this.log('Scalping bot resumed', 'success');
                document.getElementById('pauseScalping').textContent = 'Pause';
                document.getElementById('pauseScalping').onclick = () => this.pauseScalpingBot();
            }
        } catch (error) {
            this.log(`Error resuming bot: ${error.message}`, 'error');
        }
    }

    async stopScalpingBot() {
        try {
            const response = await fetch('/api/scalping/stop', { method: 'POST' });
            const data = await response.json();

            this.log('Scalping bot stopped', 'info');

            // Update UI
            document.getElementById('startScalping').disabled = false;
            document.getElementById('pauseScalping').disabled = true;
            document.getElementById('stopScalping').disabled = true;
            document.getElementById('pauseScalping').textContent = 'Pause';

            // Show final stats
            if (data.final_stats) {
                const stats = data.final_stats.stats;
                this.log(`Final: ${stats.total_trades} trades, ${stats.win_rate.toFixed(1)}% win rate, $${data.final_stats.total_pnl.toFixed(2)} PnL`, 'info');
            }

            this.loadScalpingStatus();

        } catch (error) {
            this.log(`Error stopping bot: ${error.message}`, 'error');
        }
    }

    async loadScalpingStatus() {
        try {
            const response = await fetch('/api/scalping/status');
            const data = await response.json();

            // Update status badge
            const statusBadge = document.getElementById('scalpingStatus');
            if (statusBadge) {
                // Convert "not_initialized" to "stopped" for display
                const displayStatus = (data.status === 'not_initialized') ? 'stopped' : (data.status || 'stopped');
                statusBadge.textContent = displayStatus.toUpperCase();
                statusBadge.className = 'bot-status-badge ' + displayStatus;
            }

            // Update buttons based on status
            const isRunning = data.status === 'running';
            const isPaused = data.status === 'paused';

            if (document.getElementById('startScalping')) {
                document.getElementById('startScalping').disabled = isRunning || isPaused;
                document.getElementById('pauseScalping').disabled = !isRunning && !isPaused;
                document.getElementById('stopScalping').disabled = !isRunning && !isPaused;

                if (isPaused) {
                    document.getElementById('pauseScalping').textContent = 'Resume';
                } else {
                    document.getElementById('pauseScalping').textContent = 'Pause';
                }
            }

            if (data.status === 'not_initialized') {
                return;
            }

            // Update stats
            document.getElementById('scalpCapital').textContent = `$${(data.capital || 0).toFixed(2)}`;

            const pnl = data.total_pnl || 0;
            const pnlEl = document.getElementById('scalpPnL');
            if (pnlEl) {
                pnlEl.textContent = `$${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)}`;
                pnlEl.className = `stat-value ${pnl >= 0 ? 'pnl-positive' : 'pnl-negative'}`;
            }

            document.getElementById('scalpTodayTrades').textContent = data.daily_trades || 0;
            document.getElementById('scalpTotalTrades').textContent = data.stats?.total_trades || 0;
            document.getElementById('scalpWinRate').textContent = `${(data.stats?.win_rate || 0).toFixed(1)}%`;
            document.getElementById('scalpProfitFactor').textContent = (data.stats?.profit_factor || 0).toFixed(2);

            // Update position
            const posEl = document.getElementById('scalpPosition');
            if (posEl) {
                if (data.position_details && data.position_details.length > 0) {
                    const pos = data.position_details[0];
                    posEl.innerHTML = `
                        <div class="position-active ${pos.side}">
                            <div class="pos-item">
                                <span class="pos-label">Side</span>
                                <span class="pos-value ${pos.side}">${pos.side.toUpperCase()}</span>
                            </div>
                            <div class="pos-item">
                                <span class="pos-label">Entry</span>
                                <span class="pos-value">$${pos.entry_price.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                            </div>
                            <div class="pos-item">
                                <span class="pos-label">Stop Loss</span>
                                <span class="pos-value">$${pos.stop_loss.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                            </div>
                            <div class="pos-item">
                                <span class="pos-label">Take Profit</span>
                                <span class="pos-value">$${pos.take_profit.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
                            </div>
                            <div class="pos-item">
                                <span class="pos-label">Unrealized P&L</span>
                                <span class="pos-value ${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                                    ${pos.unrealized_pnl >= 0 ? '+' : ''}$${pos.unrealized_pnl.toFixed(2)}
                                </span>
                            </div>
                        </div>
                    `;
                } else {
                    posEl.innerHTML = '<span class="no-position">No open position</span>';
                }
            }

            // Update recent trades
            const tradesEl = document.getElementById('scalpRecentTrades');
            if (tradesEl && data.recent_trades) {
                if (data.recent_trades.length > 0) {
                    tradesEl.innerHTML = data.recent_trades.map(t => `
                        <div class="trade-item ${t.pnl >= 0 ? 'win' : 'loss'}">
                            <span class="trade-side">${t.side}</span>
                            <span class="trade-pnl">${t.pnl >= 0 ? '+' : ''}$${t.pnl.toFixed(2)}</span>
                            <span class="trade-reason">${t.reason}</span>
                        </div>
                    `).join('');
                } else {
                    tradesEl.innerHTML = '<span class="no-trades">No trades yet</span>';
                }
            }

            // Update Live Confluence Status Panel
            this.updateLiveConfluenceStatus(data);

        } catch (error) {
            console.error('Error loading scalping status:', error);
        }
    }

    updateLiveConfluenceStatus(data) {
        if (!data.current_signal) return;

        const signal = data.current_signal;

        // Update confluence score badge
        const scoreBadge = document.getElementById('liveConfluenceScore');
        if (scoreBadge) {
            const score = signal.ict_confluence_score || 0;
            scoreBadge.textContent = `${score}/30`;
            scoreBadge.className = 'confluence-score-badge';
            if (score < 8) scoreBadge.classList.add('low');
            else if (score < 15) scoreBadge.classList.add('medium');
            else scoreBadge.classList.add('high');
        }

        // Update score bar
        const scoreFill = document.getElementById('confluenceScoreFill');
        if (scoreFill) {
            const score = signal.ict_confluence_score || 0;
            scoreFill.style.width = `${(score / 30) * 100}%`;
        }

        // Update signal direction
        const signalDir = document.getElementById('liveSignalDirection');
        if (signalDir) {
            const dirValue = signalDir.querySelector('.direction-value');
            const signalText = signal.signal || 'HOLD';
            const direction = signal.direction || 'neutral';
            dirValue.textContent = signalText;
            dirValue.className = 'direction-value';
            if (signalText.includes('BUY') || direction === 'long') {
                dirValue.classList.add('buy');
            } else if (signalText.includes('SELL') || direction === 'short') {
                dirValue.classList.add('sell');
            } else {
                dirValue.classList.add('hold');
            }
        }

        // Update confidence
        const confEl = document.getElementById('liveSignalConfidence');
        if (confEl) {
            const confValue = confEl.querySelector('.confidence-value');
            confValue.textContent = `${(signal.confidence || 0).toFixed(1)}%`;
        }

        // Update reason text
        const reasonEl = document.getElementById('confluenceReason');
        if (reasonEl) {
            reasonEl.textContent = signal.reason || 'Analyzing market conditions...';
        }

        // Parse signal breakdown from reason to update individual indicators
        const reason = signal.reason || '';

        // ICT Signals
        this.updateStatusIndicator('status-fvg', reason.includes('FVG') && !reason.includes('No FVG'), signal.direction);
        this.updateStatusIndicator('status-mss', reason.includes('MSS') || reason.includes('BOS'), signal.direction);
        this.updateStatusIndicator('status-ob', reason.includes('OB') || reason.includes('Order Block'), signal.direction);
        this.updateStatusIndicator('status-ote', reason.includes('OTE'), signal.direction);
        this.updateStatusIndicator('status-liquidity', reason.includes('Liquidity'), signal.direction);
        this.updateStatusIndicator('status-premium-discount', reason.includes('Premium') || reason.includes('Discount'), signal.direction);

        // SMT
        this.updateStatusIndicator('status-smt', reason.includes('SMT') && !reason.includes('Disabled'), signal.direction);

        // MTF - check for bullish/bearish percentage
        const mtfMatch = reason.match(/MTF:.*?(\d+)%/);
        const mtfBullish = mtfMatch ? parseInt(mtfMatch[1]) > 50 : false;
        this.updateStatusIndicator('status-mtf-1m', reason.includes('1m') && mtfBullish, mtfBullish ? 'long' : 'short');
        this.updateStatusIndicator('status-mtf-5m', reason.includes('5m') && mtfBullish, mtfBullish ? 'long' : 'short');
        this.updateStatusIndicator('status-mtf-15m', reason.includes('15m') && mtfBullish, mtfBullish ? 'long' : 'short');

        // ML
        const mlPred = signal.ml_prediction;
        const mlActive = mlPred && mlPred.enabled && mlPred.signal !== 'HOLD';
        this.updateStatusIndicator('status-ml', mlActive, mlPred?.signal === 'BUY' ? 'long' : 'short');

        // Momentum indicators
        this.updateStatusIndicator('status-rsi',
            reason.includes('RSI') && !reason.includes('neutral'),
            reason.includes('oversold') ? 'long' : (reason.includes('overbought') ? 'short' : signal.direction)
        );
        this.updateStatusIndicator('status-macd', reason.includes('MACD'), signal.direction);
        this.updateStatusIndicator('status-bb', reason.includes('Bollinger') || reason.includes('BB'), signal.direction);
        this.updateStatusIndicator('status-volume', reason.includes('Volume') || reason.includes('volume'), signal.direction);
    }

    updateStatusIndicator(elementId, isActive, direction) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const indicator = el.querySelector('.status-indicator');
        if (!indicator) return;

        indicator.className = 'status-indicator';
        el.classList.remove('active');

        if (isActive) {
            el.classList.add('active');
            if (direction === 'long' || direction === 'bullish') {
                indicator.classList.add('bullish');
            } else if (direction === 'short' || direction === 'bearish') {
                indicator.classList.add('bearish');
            } else {
                indicator.classList.add('neutral');
            }
        } else {
            indicator.classList.add('inactive');
        }
    }
}

// Multi-Model Configuration Manager
class MultiModelManager {
    constructor() {
        this.modelInfo = {
            xgboost: { name: 'XGBoost', icon: '🚀', color: 'var(--success)' },
            lightgbm: { name: 'LightGBM', icon: '⚡', color: 'var(--primary)' },
            random_forest: { name: 'Random Forest', icon: '🌲', color: 'var(--accent-purple)' },
            prophet: { name: 'Prophet', icon: '📈', color: 'var(--accent-yellow)' },
            transformer: { name: 'Transformer', icon: '🤖', color: 'var(--accent-blue)' },
            ppo: { name: 'PPO', icon: '🎯', color: 'var(--accent-orange)' }
        };

        this.selectedModels = ['xgboost', 'lightgbm'];
        this.weights = { xgboost: 50, lightgbm: 50 };
        this.isActive = false;

        this.init();
    }

    init() {
        this.bindCheckboxes();
        this.bindSliders();
        this.bindButtons();
        this.updateUI();
    }

    bindCheckboxes() {
        const checkboxes = document.querySelectorAll('.model-checkbox input[type="checkbox"]');
        checkboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const model = e.target.value;
                if (e.target.checked) {
                    if (!this.selectedModels.includes(model)) {
                        this.selectedModels.push(model);
                        this.weights[model] = 50;
                    }
                } else {
                    this.selectedModels = this.selectedModels.filter(m => m !== model);
                    delete this.weights[model];
                }
                this.normalizeWeights();
                this.updateUI();
            });
        });
    }

    bindSliders() {
        const slidersContainer = document.getElementById('weight-sliders');
        if (slidersContainer) {
            slidersContainer.addEventListener('input', (e) => {
                if (e.target.classList.contains('weight-slider')) {
                    const item = e.target.closest('.weight-slider-item');
                    const model = item.dataset.model;
                    this.weights[model] = parseInt(e.target.value);
                    this.updateSliderDisplay(item, e.target.value);
                    this.updateWeightBar();
                    this.updatePreview();
                }
            });
        }
    }

    bindButtons() {
        const applyBtn = document.getElementById('apply-multi-model');
        const resetBtn = document.getElementById('reset-multi-model');

        if (applyBtn) {
            applyBtn.addEventListener('click', () => this.applyConfiguration());
        }

        if (resetBtn) {
            resetBtn.addEventListener('click', () => this.resetConfiguration());
        }
    }

    normalizeWeights() {
        const total = Object.values(this.weights).reduce((sum, w) => sum + w, 0);
        if (total > 0) {
            Object.keys(this.weights).forEach(model => {
                this.weights[model] = Math.round((this.weights[model] / total) * 100);
            });
        } else if (this.selectedModels.length > 0) {
            const equalWeight = Math.floor(100 / this.selectedModels.length);
            this.selectedModels.forEach(model => {
                this.weights[model] = equalWeight;
            });
        }
    }

    updateUI() {
        this.updateSliders();
        this.updateWeightBar();
        this.updatePreview();
    }

    updateSliders() {
        const container = document.getElementById('weight-sliders');
        if (!container) return;

        container.innerHTML = '';

        this.selectedModels.forEach(model => {
            const info = this.modelInfo[model];
            const weight = this.weights[model] || 50;

            const sliderHtml = `
                <div class="weight-slider-item" data-model="${model}">
                    <label>
                        <span class="slider-model-name">${info.name}</span>
                        <span class="slider-value">${weight}%</span>
                    </label>
                    <input type="range" min="0" max="100" value="${weight}" class="weight-slider">
                </div>
            `;
            container.insertAdjacentHTML('beforeend', sliderHtml);
        });
    }

    updateSliderDisplay(item, value) {
        const valueSpan = item.querySelector('.slider-value');
        if (valueSpan) {
            valueSpan.textContent = `${value}%`;
        }
    }

    updateWeightBar() {
        const bar = document.getElementById('weight-bar');
        if (!bar) return;

        bar.innerHTML = '';

        const total = Object.values(this.weights).reduce((sum, w) => sum + w, 0);

        this.selectedModels.forEach(model => {
            const info = this.modelInfo[model];
            const weight = this.weights[model] || 0;
            const percentage = total > 0 ? (weight / total) * 100 : 0;

            const shortName = model === 'random_forest' ? 'RF' :
                              model === 'xgboost' ? 'XGB' :
                              model === 'lightgbm' ? 'LGBM' :
                              model === 'prophet' ? 'PRO' : model.toUpperCase();

            const segment = document.createElement('div');
            segment.className = 'weight-segment';
            segment.style.width = `${percentage}%`;
            segment.style.background = info.color;
            segment.dataset.model = model;
            segment.innerHTML = `<span>${shortName} ${Math.round(percentage)}%</span>`;
            bar.appendChild(segment);
        });
    }

    updatePreview() {
        const container = document.getElementById('preview-models');
        if (!container) return;

        container.innerHTML = '';

        const total = Object.values(this.weights).reduce((sum, w) => sum + w, 0);

        this.selectedModels.forEach(model => {
            const info = this.modelInfo[model];
            const weight = this.weights[model] || 0;
            const percentage = total > 0 ? Math.round((weight / total) * 100) : 0;

            const modelHtml = `
                <div class="preview-model active" data-model="${model}">
                    <span class="pm-icon">${info.icon}</span>
                    <span class="pm-name">${info.name}</span>
                    <span class="pm-weight">${percentage}%</span>
                </div>
            `;
            container.insertAdjacentHTML('beforeend', modelHtml);
        });
    }

    async applyConfiguration() {
        if (this.selectedModels.length < 2) {
            alert('Please select at least 2 models for multi-model configuration.');
            return;
        }

        const total = Object.values(this.weights).reduce((sum, w) => sum + w, 0);
        const normalizedWeights = {};
        this.selectedModels.forEach(model => {
            normalizedWeights[model] = (this.weights[model] || 0) / total;
        });

        const config = {
            models: this.selectedModels,
            weights: normalizedWeights
        };

        try {
            const response = await fetch('/api/multi-model/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (response.ok) {
                this.isActive = true;
                this.updateStatus(true);
                console.log('Multi-model configuration applied:', config);
            } else {
                console.error('Failed to apply configuration');
                alert('Failed to apply configuration. Check console for details.');
            }
        } catch (error) {
            console.error('Error applying multi-model config:', error);
            // For now, just update UI since endpoint may not exist yet
            this.isActive = true;
            this.updateStatus(true);
        }
    }

    resetConfiguration() {
        this.selectedModels = ['xgboost', 'lightgbm'];
        this.weights = { xgboost: 50, lightgbm: 50 };
        this.isActive = false;

        // Reset checkboxes
        document.querySelectorAll('.model-checkbox input[type="checkbox"]').forEach(cb => {
            cb.checked = this.selectedModels.includes(cb.value);
        });

        this.updateUI();
        this.updateStatus(false);
    }

    updateStatus(active) {
        const statusDiv = document.getElementById('multi-model-status');
        if (statusDiv) {
            if (active) {
                statusDiv.classList.add('active');
                statusDiv.querySelector('.status-text').textContent =
                    `Active (${this.selectedModels.length} models)`;
            } else {
                statusDiv.classList.remove('active');
                statusDiv.querySelector('.status-text').textContent = 'Not Active';
            }
        }
    }
}

// ============================================
// PREDICTIONS PAGE MANAGER
// ============================================

class PredictionsManager {
    constructor() {
        this.autoRefreshInterval = null;
        this.isAutoRefreshEnabled = true;
        this.currentSymbol = 'BTC/USD';

        this.initEventListeners();
    }

    initEventListeners() {
        // Symbol selector
        const symbolSelect = document.getElementById('predictions-symbol');
        if (symbolSelect) {
            symbolSelect.addEventListener('change', (e) => {
                this.currentSymbol = e.target.value;
                this.loadPredictions();
            });
        }

        // Refresh button
        const refreshBtn = document.getElementById('refresh-predictions');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadPredictions());
        }

        // Auto-refresh toggle
        const autoRefreshToggle = document.getElementById('auto-refresh-predictions');
        if (autoRefreshToggle) {
            autoRefreshToggle.addEventListener('change', (e) => {
                this.isAutoRefreshEnabled = e.target.checked;
                if (this.isAutoRefreshEnabled) {
                    this.startAutoRefresh();
                } else {
                    this.stopAutoRefresh();
                }
            });
        }

        // Start auto-refresh when predictions page is shown
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', () => {
                if (item.dataset.page === 'predictions') {
                    this.loadPredictions();
                    if (this.isAutoRefreshEnabled) {
                        this.startAutoRefresh();
                    }
                } else {
                    this.stopAutoRefresh();
                }
            });
        });
    }

    startAutoRefresh() {
        this.stopAutoRefresh();
        this.autoRefreshInterval = setInterval(() => {
            this.loadPredictions();
        }, 30000); // 30 seconds
    }

    stopAutoRefresh() {
        if (this.autoRefreshInterval) {
            clearInterval(this.autoRefreshInterval);
            this.autoRefreshInterval = null;
        }
    }

    async loadPredictions() {
        try {
            const symbol = this.currentSymbol.replace('/', '-');
            const response = await fetch(`/api/multi-model/predictions/${symbol}`);
            const data = await response.json();

            if (data.error) {
                this.showError(data.error);
                return;
            }

            this.updateUI(data);
        } catch (error) {
            console.error('Error loading predictions:', error);
            this.showError('Failed to load predictions');
        }
    }

    updateUI(data) {
        // Update current price
        const priceEl = document.getElementById('predictions-current-price');
        if (priceEl && data.current_price) {
            priceEl.textContent = `$${data.current_price.toLocaleString(undefined, {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2
            })}`;
        }

        // Update timestamp
        const timestampEl = document.getElementById('predictions-timestamp');
        if (timestampEl && data.timestamp) {
            const date = new Date(data.timestamp);
            timestampEl.textContent = `Last updated: ${date.toLocaleTimeString()}`;
        }

        // Update ensemble signal
        const ensembleSignalEl = document.getElementById('ensemble-signal');
        if (ensembleSignalEl) {
            ensembleSignalEl.textContent = data.ensemble.signal;
            ensembleSignalEl.className = 'ensemble-signal ' + data.ensemble.signal.toLowerCase();
        }

        // Update ensemble confidence
        const ensembleConfEl = document.getElementById('ensemble-confidence');
        if (ensembleConfEl) {
            ensembleConfEl.textContent = `${data.ensemble.confidence}%`;
        }

        // Update active model count
        const modelCountEl = document.getElementById('active-model-count');
        if (modelCountEl) {
            modelCountEl.textContent = `${data.ensemble.active_models} models active`;
        }

        // Update agreement bars
        this.updateAgreementBars(data.agreement);

        // Update model cards grid
        this.updateModelCards(data.predictions);

        // Update predictions table
        this.updatePredictionsTable(data.predictions);
    }

    updateAgreementBars(agreement) {
        const total = agreement.total_active || 1;

        // Buy bar
        const buyBar = document.getElementById('agreement-buy-bar');
        const buyCount = document.getElementById('agreement-buy-count');
        if (buyBar) buyBar.style.setProperty('--fill-percent', `${(agreement.buy / total) * 100}%`);
        if (buyCount) buyCount.textContent = agreement.buy;

        // Hold bar
        const holdBar = document.getElementById('agreement-hold-bar');
        const holdCount = document.getElementById('agreement-hold-count');
        if (holdBar) holdBar.style.setProperty('--fill-percent', `${(agreement.hold / total) * 100}%`);
        if (holdCount) holdCount.textContent = agreement.hold;

        // Sell bar
        const sellBar = document.getElementById('agreement-sell-bar');
        const sellCount = document.getElementById('agreement-sell-count');
        if (sellBar) sellBar.style.setProperty('--fill-percent', `${(agreement.sell / total) * 100}%`);
        if (sellCount) sellCount.textContent = agreement.sell;
    }

    updateModelCards(predictions) {
        const grid = document.getElementById('model-predictions-grid');
        if (!grid) return;

        let html = '';

        for (const [key, pred] of Object.entries(predictions)) {
            const signalClass = pred.signal === 'N/A' ? 'na' : pred.signal.toLowerCase();
            const isInactive = pred.status !== 'active';

            html += `
                <div class="model-prediction-card ${isInactive ? 'inactive' : ''}">
                    <div class="model-header">
                        <span class="model-icon">${pred.icon}</span>
                        <div class="model-info">
                            <h4>${pred.name}</h4>
                            <span class="model-type">${pred.type}</span>
                        </div>
                    </div>
                    <div class="model-signal ${signalClass}">
                        <span class="signal-value">${pred.signal}</span>
                    </div>
                    <div class="model-stats">
                        <div class="stat-item">
                            <div class="stat-label">Confidence</div>
                            <div class="stat-value">${pred.confidence}%</div>
                        </div>
                        <div class="stat-item">
                            <div class="stat-label">Prob (Up)</div>
                            <div class="stat-value">${pred.probability}%</div>
                        </div>
                    </div>
                    <div class="model-status ${pred.status}">
                        ${this.getStatusText(pred.status, pred.error)}
                    </div>
                </div>
            `;
        }

        grid.innerHTML = html;
    }

    updatePredictionsTable(predictions) {
        const tbody = document.getElementById('predictions-table-body');
        if (!tbody) return;

        let html = '';

        for (const [key, pred] of Object.entries(predictions)) {
            const signalClass = pred.signal === 'N/A' ? 'na' : pred.signal.toLowerCase();

            html += `
                <tr>
                    <td><strong>${pred.icon} ${pred.name}</strong></td>
                    <td>${pred.type}</td>
                    <td class="signal-cell ${signalClass}">${pred.signal}</td>
                    <td>${pred.confidence}%</td>
                    <td>${pred.probability}%</td>
                    <td>${pred.weight ? (pred.weight * 100).toFixed(0) + '%' : '-'}</td>
                    <td class="status-cell ${pred.status}">${this.getStatusText(pred.status)}</td>
                </tr>
            `;
        }

        tbody.innerHTML = html;
    }

    getStatusText(status, error = '') {
        switch (status) {
            case 'active':
                return 'Active';
            case 'not_trained':
                return 'Not Trained';
            case 'error':
                return error ? `Error: ${error.substring(0, 30)}...` : 'Error';
            default:
                return status;
        }
    }

    showError(message) {
        const grid = document.getElementById('model-predictions-grid');
        if (grid) {
            grid.innerHTML = `
                <div class="loading-placeholder" style="grid-column: 1 / -1;">
                    <p style="color: var(--accent-red);">${message}</p>
                    <button class="btn btn-primary" onclick="window.predictionsManager.loadPredictions()">
                        Retry
                    </button>
                </div>
            `;
        }
    }
}

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new RoboTrader();
    window.multiModelManager = new MultiModelManager();
    window.predictionsManager = new PredictionsManager();

    // Dashboard mode selector - reload account data when changed
    const dashboardModeSelect = document.getElementById('dashboardModeSelect');
    if (dashboardModeSelect) {
        dashboardModeSelect.addEventListener('change', () => {
            if (window.app) {
                window.app.loadAccountData();
            }
        });
    }
});
