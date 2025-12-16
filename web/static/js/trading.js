/**
 * Robo Trader Pro - Trading Interface JavaScript
 * Uses Lightweight Charts for professional candlestick charts
 */

// Global state
const state = {
    symbol: 'BTC/USD',
    timeframe: '1h',
    ws: null,
    // Multi-chart support
    charts: [],           // Array of chart objects
    candleSeries: [],     // Array of candle series (main price series)
    volumeSeries: [],     // Array of volume series
    chartTimeframes: ['1h', '15m', '4h', '1d', '1m', '5m'], // Default timeframes for each chart
    currentLayout: '1',   // Current layout: '1', '2h', '2v', '4', '6'
    activeCharts: 1,      // Number of active charts
    activeChartIndex: 0,  // Currently selected/focused chart index
    chartType: 'candlestick', // Chart type: 'candlestick', 'hollow', 'bar', 'line', 'area', 'baseline'
    candleData: [],       // Cached candle data for chart type switching
    volumeData: [],       // Cached volume data
    // Infinite scroll tracking
    oldestTimestamp: [],  // Oldest timestamp loaded for each chart
    isLoadingMore: [],    // Loading flag to prevent duplicate requests
    hasMoreData: [],      // Whether there's more historical data available
    // Legacy single chart references (for backward compatibility)
    chart: null,
    candleSerie: null,
    volumeSerie: null,
    currentPrice: 0,
    lastPrice: 0,
    orderSide: 'buy',
    orderType: 'market',
    botRunning: false,
    orderbookVisible: true,
    orderbookDepth: 25,
    orderbookInterval: null,
    orderFormVisible: true,
    // Timezone settings - Default to New York (EST/EDT)
    timezone: 'America/New_York',
    timezoneOffset: -5,  // EST offset from UTC (changes to -4 during EDT)
    // Drawing tools
    drawingTools: null
};

// Expose state globally for other modules
window.state = state;

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    initWebSocket();
    initEventListeners();
    initTimezoneSelector();
    loadInitialData();
    initOrderBook();
});

/**
 * Initialize the Lightweight Charts - supports multiple charts
 */
function initChart() {
    // Initialize first chart (always visible)
    createChartAt(0);

    // Set up layout button listeners
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const layout = btn.dataset.layout;
            changeLayout(layout);
        });
    });

    // Set up chart cell click to set active chart
    document.querySelectorAll('.chart-cell').forEach(cell => {
        cell.addEventListener('click', (e) => {
            // Don't trigger if clicking on the timeframe select
            if (e.target.closest('.cell-timeframe')) return;

            const index = parseInt(cell.dataset.index);
            setActiveChart(index);
        });
    });

    // Set up per-chart timeframe selectors
    document.querySelectorAll('.cell-timeframe').forEach(select => {
        select.addEventListener('change', (e) => {
            const index = parseInt(e.target.dataset.index);
            const timeframe = e.target.value;
            state.chartTimeframes[index] = timeframe;
            // Update the cell-tf display
            updateCellTimeframeDisplay(index, timeframe);
            // Update main toolbar if this is the active chart
            if (index === state.activeChartIndex) {
                syncMainToolbarTimeframe(timeframe);
            }
            loadCandlesForChart(index);
        });
    });

    // Set up chart type selector
    initChartTypeSelector();
}

/**
 * Set the active chart
 */
function setActiveChart(index) {
    state.activeChartIndex = index;

    // Update visual state
    document.querySelectorAll('.chart-cell').forEach(cell => {
        cell.classList.toggle('active', parseInt(cell.dataset.index) === index);
    });

    // Sync main toolbar timeframe with the active chart's timeframe
    const activeTimeframe = state.chartTimeframes[index];
    syncMainToolbarTimeframe(activeTimeframe);
}

/**
 * Update the cell timeframe display (BTC/USD - 1h)
 */
function updateCellTimeframeDisplay(index, timeframe) {
    const cellSymbol = document.querySelector(`.cell-symbol[data-index="${index}"] .cell-tf`);
    if (cellSymbol) {
        // Format timeframe for display (uppercase for clarity)
        const displayTf = timeframe.toUpperCase();
        cellSymbol.textContent = displayTf;
    }
}

/**
 * Sync main toolbar timeframe buttons with given timeframe
 */
function syncMainToolbarTimeframe(timeframe) {
    const normalizedTf = timeframe.toLowerCase();

    // Check if it's a regular button or dropdown item
    const regularBtn = document.querySelector(`.tf-btn[data-tf="${normalizedTf}"]`);
    const dropdownItem = document.querySelector(`.tf-dropdown-item[data-tf="${normalizedTf}"]`);

    // Remove active from all
    document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tf-dropdown-item').forEach(i => i.classList.remove('active'));

    const dropdownLabel = document.getElementById('tfDropdownLabel');

    if (regularBtn) {
        regularBtn.classList.add('active');
        if (dropdownLabel) dropdownLabel.textContent = 'More';
    } else if (dropdownItem) {
        const dropdownBtn = document.getElementById('tfDropdownBtn');
        if (dropdownBtn) dropdownBtn.classList.add('active');
        dropdownItem.classList.add('active');
        if (dropdownLabel) dropdownLabel.textContent = dropdownItem.textContent;
    }
}

/**
 * Create a chart at specified index
 */
function createChartAt(index) {
    const container = document.getElementById(`chart-${index}`);
    if (!container) return;

    // Remove existing chart if any
    if (state.charts[index]) {
        state.charts[index].remove();
    }

    // Chart options
    const chartOptions = {
        layout: {
            background: { type: 'solid', color: '#0b0e11' },
            textColor: '#848e9c',
        },
        grid: {
            vertLines: { color: '#1a1d21' },
            horzLines: { color: '#1a1d21' },
        },
        crosshair: {
            mode: LightweightCharts.CrosshairMode.Normal,
            vertLine: {
                width: 1,
                color: '#363c45',
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#1e80ff',
            },
            horzLine: {
                width: 1,
                color: '#363c45',
                style: LightweightCharts.LineStyle.Dashed,
                labelBackgroundColor: '#1e80ff',
            },
        },
        rightPriceScale: {
            borderColor: '#2b3139',
            scaleMargins: {
                top: 0.1,
                bottom: 0.2,
            },
        },
        timeScale: {
            borderColor: '#2b3139',
            timeVisible: true,
            secondsVisible: false,
        },
        handleScroll: {
            mouseWheel: true,
            pressedMouseMove: true,
        },
        handleScale: {
            axisPressedMouseMove: true,
            mouseWheel: true,
            pinch: true,
        },
    };

    // Create chart
    const chart = LightweightCharts.createChart(container, chartOptions);
    state.charts[index] = chart;

    // Create candlestick series
    const candleSeries = chart.addCandlestickSeries({
        upColor: '#0ecb81',
        downColor: '#f6465d',
        borderUpColor: '#0ecb81',
        borderDownColor: '#f6465d',
        wickUpColor: '#0ecb81',
        wickDownColor: '#f6465d',
    });
    state.candleSeries[index] = candleSeries;

    // Create volume series
    const volumeSeries = chart.addHistogramSeries({
        color: '#26a69a',
        priceFormat: {
            type: 'volume',
        },
        priceScaleId: '',
        scaleMargins: {
            top: 0.85,
            bottom: 0,
        },
    });
    state.volumeSeries[index] = volumeSeries;

    // Subscribe to crosshair move for OHLC display (only for first chart)
    if (index === 0) {
        chart.subscribeCrosshairMove((param) => {
            if (param.time) {
                const data = param.seriesData.get(candleSeries);
                if (data) {
                    updateOHLCDisplay(data);
                }
            }
        });
    }

    // Handle resize
    const resizeObserver = new ResizeObserver(entries => {
        for (let entry of entries) {
            const { width, height } = entry.contentRect;
            if (width > 0 && height > 0) {
                chart.applyOptions({ width, height });
            }
        }
    });
    resizeObserver.observe(container);

    // Keep backward compatibility - first chart is the "main" chart
    if (index === 0) {
        state.chart = chart;
        state.candleSerie = candleSeries;
        state.volumeSerie = volumeSeries;

        // Initialize drawing tools for the main chart
        if (typeof initDrawingTools === 'function') {
            state.drawingTools = initDrawingTools(container, chart, candleSeries);
        }
    }

    // Initialize infinite scroll tracking for this chart
    state.isLoadingMore[index] = false;
    state.hasMoreData[index] = true;
    state.oldestTimestamp[index] = null;

    // Subscribe to visible time range changes for infinite scroll
    // Trigger when user scrolls near the left (oldest) edge of the chart
    let lastLogTime = 0;
    let lastLoadTriggerTime = 0;

    chart.timeScale().subscribeVisibleLogicalRangeChange((logicalRange) => {
        const now = Date.now();
        const shouldLog = now - lastLogTime > 2000; // Log at most once per 2 seconds

        if (logicalRange === null) {
            return; // Chart not ready
        }

        if (!state.oldestTimestamp[index]) {
            return; // No data loaded yet
        }

        const totalBars = state.candleData[index]?.length || 0;
        if (totalBars === 0) return;

        // Use a fixed threshold of 100 bars from the left edge
        // This is simpler and more predictable than percentage-based
        const threshold = 100;

        // Log scroll position periodically for debugging
        if (shouldLog) {
            console.log(`[InfiniteScroll] Chart ${index}: from=${logicalRange.from.toFixed(1)}, threshold=${threshold}, totalBars=${totalBars}, isLoading=${state.isLoadingMore[index]}, hasMore=${state.hasMoreData[index]}`);
            lastLogTime = now;
        }

        // Prevent triggering too frequently (wait at least 500ms between triggers)
        const canTrigger = now - lastLoadTriggerTime > 500;

        if (logicalRange.from < threshold && !state.isLoadingMore[index] && state.hasMoreData[index] && canTrigger) {
            console.log(`[InfiniteScroll] TRIGGERING load for chart ${index}: from=${logicalRange.from.toFixed(0)} < threshold=${threshold}, totalBars=${totalBars}`);
            lastLoadTriggerTime = now;
            loadMoreHistoricalData(index);
        }
    });

    return chart;
}

/**
 * Change the chart layout
 */
function changeLayout(layout) {
    state.currentLayout = layout;

    // Update layout button states
    document.querySelectorAll('.layout-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.layout === layout);
    });

    // Update wrapper layout
    const wrapper = document.getElementById('multiChartWrapper');
    wrapper.dataset.layout = layout;

    // Determine number of visible charts
    const chartCounts = { '1': 1, '2h': 2, '2v': 2, '4': 4, '6': 6 };
    state.activeCharts = chartCounts[layout] || 1;

    // Show/hide chart cells
    document.querySelectorAll('.chart-cell').forEach((cell, index) => {
        if (index < state.activeCharts) {
            cell.style.display = 'flex';
            // Create chart if it doesn't exist
            if (!state.charts[index]) {
                createChartAt(index);
                loadCandlesForChart(index);
            } else {
                // Resize existing chart
                setTimeout(() => {
                    const container = document.getElementById(`chart-${index}`);
                    if (container && state.charts[index]) {
                        const { width, height } = container.getBoundingClientRect();
                        if (width > 0 && height > 0) {
                            state.charts[index].applyOptions({ width, height });
                            state.charts[index].timeScale().fitContent();
                        }
                    }
                }, 100);
            }
        } else {
            cell.style.display = 'none';
        }
    });

    // Update symbols in headers
    document.querySelectorAll('.cell-symbol').forEach(el => {
        el.textContent = state.symbol;
    });
}

/**
 * Load candles for a specific chart
 */
async function loadCandlesForChart(index) {
    if (!state.charts[index]) return;

    const timeframe = state.chartTimeframes[index];

    try {
        const response = await fetch(
            `/api/candles/${encodeURIComponent(state.symbol)}?timeframe=${timeframe}&limit=500`
        );
        if (!response.ok) throw new Error('Failed to load candles');

        const data = await response.json();
        if (!data.candles || data.candles.length === 0) {
            console.warn(`No candle data for chart ${index}`);
            return;
        }

        // Format candles
        const candles = data.candles.map(c => ({
            time: Math.floor(new Date(c.timestamp || c.time).getTime() / 1000),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

        const volumes = data.candles.map(c => ({
            time: Math.floor(new Date(c.timestamp || c.time).getTime() / 1000),
            value: c.volume,
            color: c.close >= c.open ? 'rgba(14, 203, 129, 0.5)' : 'rgba(246, 70, 93, 0.5)',
        }));

        // Cache candle and volume data for chart type switching and infinite scroll
        state.candleData[index] = candles;
        state.volumeData[index] = volumes;

        // Track oldest timestamp for infinite scroll
        if (candles.length > 0) {
            state.oldestTimestamp[index] = candles[0].time;
            state.hasMoreData[index] = true;
        }

        // Set data based on chart type (only main chart uses chart type setting)
        const chartType = index === 0 ? state.chartType : 'candlestick';
        setSeriesData(state.candleSeries[index], candles, chartType);
        state.volumeSeries[index].setData(volumes);
        state.charts[index].timeScale().fitContent();

        // Update current price from last candle (first chart only)
        if (index === 0 && candles.length > 0) {
            const lastCandle = candles[candles.length - 1];
            updateTicker({ price: lastCandle.close });

            // Update drawing tools price data for magnet mode
            if (state.drawingTools) {
                state.drawingTools.setPriceData(candles);
            }
        }

    } catch (error) {
        console.error(`Error loading candles for chart ${index}:`, error);
    }
}

/**
 * Update OHLC display in toolbar
 */
function updateOHLCDisplay(data) {
    document.getElementById('ohlcOpen').textContent = formatPrice(data.open);
    document.getElementById('ohlcHigh').textContent = formatPrice(data.high);
    document.getElementById('ohlcLow').textContent = formatPrice(data.low);
    document.getElementById('ohlcClose').textContent = formatPrice(data.close);
}

/**
 * Initialize WebSocket connection
 */
function initWebSocket() {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;

    state.ws = new WebSocket(wsUrl);

    state.ws.onopen = () => {
        console.log('WebSocket connected');
        updateConnectionStatus(true);
        // Show success toast
        if (window.Toast) {
            Toast.success('Connected to trading server');
        }
        // Subscribe to symbol
        state.ws.send(JSON.stringify({ type: 'subscribe', symbol: state.symbol }));
    };

    state.ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateConnectionStatus(false);
        // Show warning toast
        if (window.Toast) {
            Toast.warning('Disconnected from server. Reconnecting...');
        }
        // Attempt to reconnect after 3 seconds
        setTimeout(initWebSocket, 3000);
    };

    state.ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateConnectionStatus(false);
        // Show error toast
        if (window.Toast) {
            Toast.error('Connection error occurred');
        }
    };

    state.ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('Error parsing WebSocket message:', e);
        }
    };
}

/**
 * Handle incoming WebSocket messages
 */
function handleWebSocketMessage(data) {
    switch (data.type) {
        case 'ticker':
            updateTicker(data);
            break;
        case 'candle':
            updateCandle(data);
            break;
        case 'signal':
            updateSignal(data);
            break;
        case 'position':
            updatePositions(data);
            break;
        case 'trade':
            addTrade(data);
            break;
        case 'bot_status':
            updateBotStatus(data);
            break;
    }
}

/**
 * Update ticker display
 */
function updateTicker(data) {
    state.lastPrice = state.currentPrice;
    state.currentPrice = data.price;

    const priceEl = document.getElementById('currentPrice');
    const priceValueEl = priceEl.querySelector('.price-value');
    priceValueEl.textContent = formatPrice(data.price);

    // Color based on price direction
    priceEl.classList.remove('up', 'down');
    if (state.currentPrice > state.lastPrice) {
        priceEl.classList.add('up');
    } else if (state.currentPrice < state.lastPrice) {
        priceEl.classList.add('down');
    }

    // Update stats
    if (data.change !== undefined) {
        const changeEl = document.getElementById('priceChange');
        changeEl.textContent = (data.change >= 0 ? '+' : '') + data.change.toFixed(2) + '%';
        changeEl.classList.remove('positive', 'negative');
        changeEl.classList.add(data.change >= 0 ? 'positive' : 'negative');
    }

    if (data.high !== undefined && data.high !== null) {
        document.getElementById('highPrice').textContent = formatPrice(data.high);
    }
    if (data.low !== undefined && data.low !== null) {
        document.getElementById('lowPrice').textContent = formatPrice(data.low);
    }
    if (data.volume !== undefined && data.volume !== null) {
        document.getElementById('volume24h').textContent = formatVolume(data.volume);
    }

    // Update current price line on chart
    if (state.candleSerie) {
        state.candleSerie.applyOptions({
            lastValueVisible: true,
            priceLineVisible: true,
        });
    }
}

/**
 * Update candle on chart
 */
function updateCandle(data) {
    if (!state.candleSerie) return;

    const candle = {
        time: data.time,
        open: data.open,
        high: data.high,
        low: data.low,
        close: data.close,
    };

    state.candleSerie.update(candle);

    // Update volume
    if (state.volumeSerie && data.volume !== undefined) {
        state.volumeSerie.update({
            time: data.time,
            value: data.volume,
            color: data.close >= data.open ? 'rgba(14, 203, 129, 0.5)' : 'rgba(246, 70, 93, 0.5)',
        });
    }
}

/**
 * Update ML signal display
 */
function updateSignal(data) {
    const predictionEl = document.getElementById('signalPrediction').querySelector('.signal-value');
    predictionEl.textContent = data.signal || 'HOLD';
    predictionEl.className = 'signal-value ' + (data.signal || 'hold').toLowerCase();

    if (data.confidence !== undefined) {
        const confidence = Math.round(data.confidence * 100);
        document.getElementById('confidenceFill').style.width = confidence + '%';
        document.getElementById('confidenceValue').textContent = confidence + '%';
    }

    if (data.time) {
        document.getElementById('signalTime').textContent = new Date(data.time).toLocaleTimeString();
    }

    // Update indicators
    if (data.indicators) {
        if (data.indicators.rsi !== undefined) {
            document.getElementById('rsiValue').textContent = data.indicators.rsi.toFixed(1);
        }
        if (data.indicators.macd !== undefined) {
            document.getElementById('macdValue').textContent = data.indicators.macd.toFixed(2);
        }
        if (data.indicators.trend !== undefined) {
            document.getElementById('trendValue').textContent = data.indicators.trend;
        }
    }
}

/**
 * Update connection status indicator
 */
function updateConnectionStatus(connected) {
    // Sidebar status
    const statusDot = document.getElementById('wsStatus');
    const statusText = document.getElementById('wsStatusText');

    // Chart toolbar status
    const chartStatusDot = document.getElementById('chartWsStatus');
    const chartStatusText = document.getElementById('chartWsStatusText');

    if (connected) {
        statusDot?.classList.add('connected');
        if (statusText) statusText.textContent = 'Connected';
        chartStatusDot?.classList.add('connected');
        if (chartStatusText) chartStatusText.textContent = 'Connected';
    } else {
        statusDot?.classList.remove('connected');
        if (statusText) statusText.textContent = 'Disconnected';
        chartStatusDot?.classList.remove('connected');
        if (chartStatusText) chartStatusText.textContent = 'Disconnected';
    }
}

/**
 * Load initial data from REST API
 */
async function loadInitialData() {
    try {
        // Load ticker for 24h stats (high, low, change, volume)
        await loadTicker();

        // Load candles
        await loadCandles();

        // Load positions
        await loadPositions();

        // Load trades
        await loadTrades();

        // Load balances
        await loadBalances();

        // Load signal
        await loadLatestSignal();

    } catch (error) {
        console.error('Error loading initial data:', error);
    }
}

/**
 * Load ticker data (24h stats)
 */
async function loadTicker() {
    try {
        const response = await fetch(`/api/ticker/${encodeURIComponent(state.symbol)}`);
        if (!response.ok) return;

        const data = await response.json();
        if (data.error) {
            console.warn('Ticker error:', data.error);
            return;
        }

        // Update ticker display with 24h stats
        updateTicker({
            price: data.last,
            high: data.high,
            low: data.low,
            change: data.change,
            volume: data.volume
        });

    } catch (error) {
        console.error('Error loading ticker:', error);
    }
}

/**
 * Load historical candles
 */
async function loadCandles() {
    try {
        const response = await fetch(`/api/candles/${encodeURIComponent(state.symbol)}?timeframe=${state.timeframe}&limit=500`);
        if (!response.ok) throw new Error('Failed to load candles');

        const data = await response.json();
        if (!data.candles || data.candles.length === 0) {
            console.warn('No candle data received');
            return;
        }

        // Format candles for Lightweight Charts
        const candles = data.candles.map(c => ({
            time: Math.floor(new Date(c.timestamp || c.time).getTime() / 1000),
            open: c.open,
            high: c.high,
            low: c.low,
            close: c.close,
        }));

        const volumes = data.candles.map(c => ({
            time: Math.floor(new Date(c.timestamp || c.time).getTime() / 1000),
            value: c.volume,
            color: c.close >= c.open ? 'rgba(14, 203, 129, 0.5)' : 'rgba(246, 70, 93, 0.5)',
        }));

        // Cache candle and volume data for chart type switching and infinite scroll
        state.candleData[0] = candles;
        state.volumeData[0] = volumes;

        // Track oldest timestamp for infinite scroll
        if (candles.length > 0) {
            state.oldestTimestamp[0] = candles[0].time;
            state.hasMoreData[0] = true;
            console.log(`[InfiniteScroll] Initial data loaded: ${candles.length} candles, oldest=${candles[0].time} (${new Date(candles[0].time * 1000).toISOString()})`);
        }

        // Set data based on chart type
        setSeriesData(state.candleSerie, candles, state.chartType);
        state.volumeSerie.setData(volumes);

        // Update current price from last candle
        if (candles.length > 0) {
            const lastCandle = candles[candles.length - 1];
            updateTicker({ price: lastCandle.close });
        }

        // Fit content
        state.chart.timeScale().fitContent();

    } catch (error) {
        console.error('Error loading candles:', error);
    }
}

/**
 * Set series data based on chart type
 */
function setSeriesData(series, candles, chartType) {
    if (!series || !candles || candles.length === 0) return;

    // Line, area, and baseline use value format, others use OHLC
    if (chartType === 'line' || chartType === 'area' || chartType === 'baseline') {
        const lineData = candles.map(c => ({
            time: c.time,
            value: c.close,
        }));
        series.setData(lineData);
    } else {
        series.setData(candles);
    }
}

/**
 * Load more historical data for infinite scroll
 */
async function loadMoreHistoricalData(index) {
    if (state.isLoadingMore[index]) {
        console.log(`[InfiniteScroll] Already loading more data for chart ${index}, skipping...`);
        return;
    }

    if (!state.hasMoreData[index]) {
        console.log(`[InfiniteScroll] No more data available for chart ${index}`);
        return;
    }

    const oldestTimestamp = state.oldestTimestamp[index];
    if (!oldestTimestamp) {
        console.log(`[InfiniteScroll] No oldest timestamp for chart ${index}, cannot load more`);
        return;
    }

    state.isLoadingMore[index] = true;

    const timeframe = index === 0 ? state.timeframe : state.chartTimeframes[index];
    const oldestDate = new Date(oldestTimestamp * 1000).toISOString();
    console.log(`[InfiniteScroll] Loading more data for chart ${index}... (tf=${timeframe}, before=${oldestTimestamp}, date=${oldestDate})`);

    try {
        const url = `/api/candles/${encodeURIComponent(state.symbol)}?timeframe=${timeframe}&limit=500&before=${oldestTimestamp}`;
        console.log(`[InfiniteScroll] Fetching: ${url}`);

        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to load more candles: ${response.status} ${response.statusText}`);
        }

        const data = await response.json();
        console.log(`[InfiniteScroll] Received: ${data.candles ? data.candles.length : 0} candles`);

        if (!data.candles || data.candles.length === 0) {
            state.hasMoreData[index] = false;
            console.log(`[InfiniteScroll] No more historical data for chart ${index}`);
            return;
        }

        // Format new candles - use the timestamp field which is an ISO string
        const newCandles = data.candles.map(c => {
            // Handle both ISO string timestamp and Unix seconds time
            let timeVal;
            if (c.timestamp) {
                timeVal = Math.floor(new Date(c.timestamp).getTime() / 1000);
            } else if (typeof c.time === 'number' && c.time > 1000000000000) {
                // Already in milliseconds
                timeVal = Math.floor(c.time / 1000);
            } else {
                // Already in seconds
                timeVal = c.time;
            }
            return {
                time: timeVal,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close,
            };
        });

        const newVolumes = data.candles.map(c => {
            let timeVal;
            if (c.timestamp) {
                timeVal = Math.floor(new Date(c.timestamp).getTime() / 1000);
            } else if (typeof c.time === 'number' && c.time > 1000000000000) {
                timeVal = Math.floor(c.time / 1000);
            } else {
                timeVal = c.time;
            }
            return {
                time: timeVal,
                value: c.volume || 0,
                color: c.close >= c.open ? 'rgba(14, 203, 129, 0.5)' : 'rgba(246, 70, 93, 0.5)',
            };
        });

        // Sort by time (ascending)
        newCandles.sort((a, b) => a.time - b.time);
        newVolumes.sort((a, b) => a.time - b.time);

        // Filter out duplicates
        const existingTimes = new Set(state.candleData[index].map(c => c.time));
        const uniqueNewCandles = newCandles.filter(c => !existingTimes.has(c.time));
        const uniqueNewVolumes = newVolumes.filter(v => !existingTimes.has(v.time));

        console.log(`[InfiniteScroll] After filtering: ${uniqueNewCandles.length} unique candles (raw: ${newCandles.length})`);

        if (uniqueNewCandles.length === 0) {
            state.hasMoreData[index] = false;
            console.log(`[InfiniteScroll] No unique historical data for chart ${index}`);
            return;
        }

        // Log the time range of new candles
        const newOldest = new Date(uniqueNewCandles[0].time * 1000).toISOString();
        const newNewest = new Date(uniqueNewCandles[uniqueNewCandles.length - 1].time * 1000).toISOString();
        console.log(`[InfiniteScroll] New candles range: ${newOldest} to ${newNewest}`);

        // Prepend new data to existing data
        state.candleData[index] = [...uniqueNewCandles, ...state.candleData[index]];
        state.volumeData[index] = [...uniqueNewVolumes, ...state.volumeData[index]];

        // Sort combined data by time (ascending)
        state.candleData[index].sort((a, b) => a.time - b.time);
        state.volumeData[index].sort((a, b) => a.time - b.time);

        // Update oldest timestamp
        state.oldestTimestamp[index] = state.candleData[index][0].time;

        // Update chart series
        const chartType = index === 0 ? state.chartType : 'candlestick';
        const series = index === 0 ? state.candleSerie : state.candleSeries[index];
        const volumeSeries = index === 0 ? state.volumeSerie : state.volumeSeries[index];

        setSeriesData(series, state.candleData[index], chartType);
        volumeSeries.setData(state.volumeData[index]);

        console.log(`[InfiniteScroll] Loaded ${uniqueNewCandles.length} more candles. Total: ${state.candleData[index].length}. New oldest: ${new Date(state.oldestTimestamp[index] * 1000).toISOString()}`);

    } catch (error) {
        console.error(`[InfiniteScroll] Error loading more candles for chart ${index}:`, error);
    } finally {
        state.isLoadingMore[index] = false;
    }
}

/**
 * Load positions
 */
async function loadPositions() {
    try {
        const response = await fetch('/api/positions');
        if (!response.ok) return;

        const data = await response.json();
        const tbody = document.getElementById('positionsBody');

        if (!data.positions || data.positions.length === 0) {
            if (window.EmptyState) {
                EmptyState.applyToTable(tbody, 'positions', { colspan: 7 });
            } else {
                tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No open positions</td></tr>';
            }
            return;
        }

        tbody.innerHTML = data.positions.map(pos => `
            <tr>
                <td>${pos.symbol}</td>
                <td class="${pos.side === 'long' ? 'buy' : 'sell'}">${pos.side.toUpperCase()}</td>
                <td>${pos.size.toFixed(6)}</td>
                <td>${formatPrice(pos.entry_price)}</td>
                <td>${formatPrice(pos.mark_price || state.currentPrice)}</td>
                <td class="${pos.pnl >= 0 ? 'positive' : 'negative'}">${formatPrice(pos.pnl || 0)}</td>
                <td><button class="btn-close" onclick="closePosition('${pos.symbol}')">Close</button></td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading positions:', error);
    }
}

/**
 * Load trade history
 */
async function loadTrades() {
    try {
        const response = await fetch('/api/trades?limit=50');
        if (!response.ok) return;

        const data = await response.json();
        const tbody = document.getElementById('tradesBody');

        if (!data.trades || data.trades.length === 0) {
            if (window.EmptyState) {
                EmptyState.applyToTable(tbody, 'trades', { colspan: 7 });
            } else {
                tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No trades yet</td></tr>';
            }
            return;
        }

        tbody.innerHTML = data.trades.map(trade => `
            <tr>
                <td>${new Date(trade.timestamp).toLocaleString()}</td>
                <td>${trade.symbol}</td>
                <td class="${trade.side === 'buy' ? 'buy' : 'sell'}">${trade.side.toUpperCase()}</td>
                <td>${formatPrice(trade.price)}</td>
                <td>${trade.amount.toFixed(6)}</td>
                <td>${formatPrice(trade.cost || trade.price * trade.amount)}</td>
                <td>${trade.is_paper ? 'Paper' : 'Live'}</td>
            </tr>
        `).join('');

    } catch (error) {
        console.error('Error loading trades:', error);
    }
}

/**
 * Load account balances
 */
async function loadBalances() {
    try {
        const response = await fetch('/api/account');
        if (!response.ok) return;

        const data = await response.json();
        const tbody = document.getElementById('balancesBody');

        if (!data.balances || Object.keys(data.balances).length === 0) {
            // Show paper trading balance
            if (data.cash !== undefined) {
                tbody.innerHTML = `
                    <tr>
                        <td>USD</td>
                        <td>${formatPrice(data.cash)}</td>
                        <td>$0.00</td>
                        <td>${formatPrice(data.cash)}</td>
                        <td>${formatPrice(data.cash)}</td>
                    </tr>
                `;
                document.getElementById('availableBalance').textContent = formatPrice(data.cash) + ' USD';
            } else {
                if (window.EmptyState) {
                    EmptyState.applyToTable(tbody, 'balances', { colspan: 5 });
                } else {
                    tbody.innerHTML = '<tr class="empty-row"><td colspan="5">No balances</td></tr>';
                }
            }
            return;
        }

        const rows = Object.entries(data.balances).map(([asset, balance]) => `
            <tr>
                <td>${asset}</td>
                <td>${typeof balance === 'object' ? balance.free?.toFixed(8) || '0' : balance}</td>
                <td>${typeof balance === 'object' ? balance.used?.toFixed(8) || '0' : '0'}</td>
                <td>${typeof balance === 'object' ? balance.total?.toFixed(8) || '0' : balance}</td>
                <td>--</td>
            </tr>
        `).join('');

        tbody.innerHTML = rows;

        // Update available balance
        const usdBalance = data.balances['USD'] || data.balances['USDT'] || {};
        const available = typeof usdBalance === 'object' ? usdBalance.free : usdBalance;
        if (available) {
            document.getElementById('availableBalance').textContent = formatPrice(available) + ' USD';
        }

    } catch (error) {
        console.error('Error loading balances:', error);
    }
}

/**
 * Load latest ML signal
 */
async function loadLatestSignal() {
    try {
        const response = await fetch(`/api/signal/${encodeURIComponent(state.symbol)}`);
        if (!response.ok) return;

        const data = await response.json();
        updateSignal(data);

    } catch (error) {
        console.error('Error loading signal:', error);
    }
}

/**
 * Initialize event listeners
 */
function initEventListeners() {
    // Symbol selector
    const symbolDropdown = document.getElementById('symbolDropdown');
    const symbolSearch = document.getElementById('symbolSearch');

    document.getElementById('symbolBtn').addEventListener('click', () => {
        symbolDropdown.classList.toggle('show');
        if (symbolDropdown.classList.contains('show') && symbolSearch) {
            setTimeout(() => symbolSearch.focus(), 100);
        }
    });

    // Symbol search functionality
    if (symbolSearch) {
        symbolSearch.addEventListener('input', (e) => {
            const searchTerm = e.target.value.toLowerCase();
            const options = document.querySelectorAll('.symbol-option');
            const categories = document.querySelectorAll('.symbol-category');

            options.forEach(option => {
                const symbol = option.dataset.symbol.toLowerCase();
                if (symbol.includes(searchTerm)) {
                    option.classList.remove('hidden');
                } else {
                    option.classList.add('hidden');
                }
            });

            // Hide empty categories
            categories.forEach(category => {
                let nextEl = category.nextElementSibling;
                let hasVisibleOption = false;
                while (nextEl && !nextEl.classList.contains('symbol-category')) {
                    if (nextEl.classList.contains('symbol-option') && !nextEl.classList.contains('hidden')) {
                        hasVisibleOption = true;
                        break;
                    }
                    nextEl = nextEl.nextElementSibling;
                }
                category.style.display = hasVisibleOption ? '' : 'none';
            });
        });

        // Prevent dropdown from closing when clicking on search
        symbolSearch.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    document.querySelectorAll('.symbol-option').forEach(option => {
        option.addEventListener('click', () => {
            const newSymbol = option.dataset.symbol;
            changeSymbol(newSymbol);
            symbolDropdown.classList.remove('show');
            // Reset search
            if (symbolSearch) {
                symbolSearch.value = '';
                document.querySelectorAll('.symbol-option').forEach(o => o.classList.remove('hidden'));
                document.querySelectorAll('.symbol-category').forEach(c => c.style.display = '');
            }
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.symbol-selector')) {
            symbolDropdown.classList.remove('show');
        }
    });

    // Timeframe buttons (excluding dropdown button)
    document.querySelectorAll('.tf-btn[data-tf]').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
            document.querySelectorAll('.tf-dropdown-item').forEach(i => i.classList.remove('active'));
            btn.classList.add('active');
            // Reset dropdown label
            const dropdownLabel = document.getElementById('tfDropdownLabel');
            if (dropdownLabel) dropdownLabel.textContent = 'More';
            changeTimeframe(btn.dataset.tf);
        });
    });

    // Timeframe dropdown
    const tfDropdownBtn = document.getElementById('tfDropdownBtn');
    const tfDropdownMenu = document.getElementById('tfDropdownMenu');

    if (tfDropdownBtn && tfDropdownMenu) {
        tfDropdownBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            tfDropdownMenu.classList.toggle('open');
        });

        // Dropdown items
        document.querySelectorAll('.tf-dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                const tf = item.dataset.tf;
                // Remove active from all tf buttons and dropdown items
                document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
                document.querySelectorAll('.tf-dropdown-item').forEach(i => i.classList.remove('active'));
                // Set dropdown button and item as active
                tfDropdownBtn.classList.add('active');
                item.classList.add('active');
                // Update dropdown label
                document.getElementById('tfDropdownLabel').textContent = item.textContent;
                // Close dropdown
                tfDropdownMenu.classList.remove('open');
                // Change timeframe
                changeTimeframe(tf);
            });
        });

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!e.target.closest('.tf-dropdown')) {
                tfDropdownMenu.classList.remove('open');
            }
        });
    }

    // Panel tabs
    document.querySelectorAll('.panel-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.panel-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.panel-section').forEach(s => s.classList.remove('active'));

            tab.classList.add('active');
            document.getElementById(tab.dataset.panel + 'Panel').classList.add('active');
        });
    });

    // Order tabs
    document.querySelectorAll('.order-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            document.querySelectorAll('.order-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            state.orderType = tab.dataset.type;

            // Show/hide limit price input
            const limitInput = document.querySelector('.limit-only');
            limitInput.style.display = state.orderType === 'limit' ? 'block' : 'none';
        });
    });

    // Order side buttons
    document.querySelectorAll('.side-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.side-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            state.orderSide = btn.dataset.side;

            // Update submit button
            const submitBtn = document.getElementById('submitOrder');
            submitBtn.className = 'order-submit-btn ' + state.orderSide;
            submitBtn.textContent = state.orderSide === 'buy' ? 'Buy BTC' : 'Sell BTC';
        });
    });

    // Amount presets
    document.querySelectorAll('.preset-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            // TODO: Calculate percentage of balance
            console.log('Preset:', btn.dataset.pct + '%');
        });
    });

    // Order amount input
    document.getElementById('orderAmount').addEventListener('input', updateOrderSummary);
    document.getElementById('orderPrice').addEventListener('input', updateOrderSummary);

    // Submit order
    document.getElementById('submitOrder').addEventListener('click', submitOrder);

    // Bot controls
    document.getElementById('startBot').addEventListener('click', startBot);
    document.getElementById('stopBot').addEventListener('click', stopBot);

    // Go to date button
    initGoToDate();
}

/**
 * Change trading symbol
 */
async function changeSymbol(newSymbol) {
    state.symbol = newSymbol;
    document.getElementById('currentSymbol').textContent = newSymbol;

    // Update all cell-symbol displays
    document.querySelectorAll('.cell-symbol').forEach(cellSymbol => {
        const tfSpan = cellSymbol.querySelector('.cell-tf');
        if (tfSpan) {
            const currentTf = tfSpan.textContent;
            cellSymbol.innerHTML = `${newSymbol} - <span class="cell-tf">${currentTf}</span>`;
        }
    });

    // Resubscribe to WebSocket
    if (state.ws && state.ws.readyState === WebSocket.OPEN) {
        state.ws.send(JSON.stringify({ type: 'subscribe', symbol: newSymbol }));
    }

    // Reload candles for all active charts
    for (let i = 0; i < state.activeCharts; i++) {
        await loadCandlesForChart(i);
    }

    // Notify Market Summary of symbol change
    if (window.MarketSummary) {
        MarketSummary.onSymbolChange(newSymbol);
    }
}

/**
 * Change timeframe
 */
async function changeTimeframe(newTimeframe) {
    // Clear Python indicator drawings before changing timeframe
    if (typeof clearPythonIndicatorDrawings === 'function') {
        clearPythonIndicatorDrawings();
    }

    // Update the active chart's timeframe
    const activeIndex = state.activeChartIndex;
    state.chartTimeframes[activeIndex] = newTimeframe;
    state.timeframe = newTimeframe; // Keep global state in sync for backward compatibility
    state.currentTimeframe = newTimeframe; // Also update currentTimeframe

    // Update the cell-timeframe dropdown to match
    const cellSelect = document.querySelector(`.cell-timeframe[data-index="${activeIndex}"]`);
    if (cellSelect) {
        cellSelect.value = newTimeframe;
    }

    // Update the cell-tf display
    updateCellTimeframeDisplay(activeIndex, newTimeframe);

    // Load candles for the active chart
    await loadCandlesForChart(activeIndex);

    // Refresh structure-based indicators (BOS/MSS, Swing Points)
    await refreshStructureIndicators();
}

/**
 * Refresh all structure-based indicators after timeframe change
 */
async function refreshStructureIndicators() {
    const chart = state.charts[0];
    if (!chart) return;

    // Find all BOS/MSS and swing_points indicators
    const structureIndicators = indicatorState.activeIndicators.filter(
        ind => ind.type === 'bos_mss' || ind.type === 'swing_points'
    );

    for (const indicator of structureIndicators) {
        // Remove old line series
        if (indicator.series && indicator.series.length > 0) {
            indicator.series.forEach(series => {
                try {
                    chart.removeSeries(series);
                } catch (e) {
                    console.warn('Error removing series:', e);
                }
            });
        }

        // Re-add indicator with new timeframe data
        await addMarkerBasedIndicator(indicator, chart, indicator.settings);
    }

    console.log(`[BOS/MSS] Refreshed ${structureIndicators.length} structure indicators for new timeframe`);
}

/**
 * Update order summary
 */
function updateOrderSummary() {
    const amount = parseFloat(document.getElementById('orderAmount').value) || 0;
    const price = state.orderType === 'limit'
        ? parseFloat(document.getElementById('orderPrice').value) || state.currentPrice
        : state.currentPrice;

    const total = amount * price;
    const fee = total * 0.0025; // 0.25% fee

    document.getElementById('orderTotal').textContent = formatPrice(total);
    document.getElementById('orderFee').textContent = formatPrice(fee);
}

/**
 * Submit order
 */
async function submitOrder() {
    const amountInput = document.getElementById('orderAmount');
    const amount = parseFloat(amountInput.value);
    if (!amount || amount <= 0) {
        if (window.Toast) {
            Toast.warning('Please enter a valid amount');
        }
        if (window.Animate) {
            Animate.shake(amountInput);
        }
        return;
    }

    const orderData = {
        symbol: state.symbol,
        side: state.orderSide,
        type: state.orderType,
        amount: amount,
    };

    if (state.orderType === 'limit') {
        orderData.price = parseFloat(document.getElementById('orderPrice').value);
    }

    try {
        const response = await fetch('/api/order', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(orderData),
        });

        const result = await response.json();

        if (response.ok) {
            if (window.Toast) {
                Toast.success(`Order placed: ${result.message || 'Success'}`);
            }
            amountInput.value = '';
            loadPositions();
            loadTrades();
            loadBalances();
        } else {
            if (window.Toast) {
                Toast.error(`Order failed: ${result.error || 'Unknown error'}`);
            }
        }
    } catch (error) {
        console.error('Error submitting order:', error);
        if (window.Toast) {
            Toast.error('Failed to submit order');
        }
    }
}

/**
 * Start trading bot
 */
async function startBot() {
    try {
        const response = await fetch('/api/bot/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: state.symbol, mode: 'paper' }),
        });

        if (response.ok) {
            state.botRunning = true;
            updateBotUI();
            if (window.Toast) {
                Toast.success('Trading bot started');
            }
        } else {
            if (window.Toast) {
                Toast.error('Failed to start bot');
            }
        }
    } catch (error) {
        console.error('Error starting bot:', error);
        if (window.Toast) {
            Toast.error('Error starting bot');
        }
    }
}

/**
 * Stop trading bot
 */
async function stopBot() {
    try {
        const response = await fetch('/api/bot/stop', {
            method: 'POST',
        });

        if (response.ok) {
            state.botRunning = false;
            updateBotUI();
            if (window.Toast) {
                Toast.info('Trading bot stopped');
            }
        } else {
            if (window.Toast) {
                Toast.error('Failed to stop bot');
            }
        }
    } catch (error) {
        console.error('Error stopping bot:', error);
        if (window.Toast) {
            Toast.error('Error stopping bot');
        }
    }
}

/**
 * Update bot status from WebSocket
 */
function updateBotStatus(data) {
    state.botRunning = data.running;
    updateBotUI();
}

/**
 * Update bot UI elements
 */
function updateBotUI() {
    const indicator = document.getElementById('botIndicator');
    const statusText = document.getElementById('botStatusText');
    const startBtn = document.getElementById('startBot');
    const stopBtn = document.getElementById('stopBot');

    if (state.botRunning) {
        indicator.classList.add('running');
        indicator.classList.remove('stopped');
        statusText.textContent = 'Running';
        startBtn.disabled = true;
        stopBtn.disabled = false;
    } else {
        indicator.classList.remove('running');
        indicator.classList.add('stopped');
        statusText.textContent = 'Stopped';
        startBtn.disabled = false;
        stopBtn.disabled = true;
    }
}

/**
 * Close position
 */
async function closePosition(symbol) {
    if (!confirm(`Close position for ${symbol}?`)) return;

    try {
        const response = await fetch('/api/position/close', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol }),
        });

        if (response.ok) {
            loadPositions();
            loadTrades();
            loadBalances();
        }
    } catch (error) {
        console.error('Error closing position:', error);
    }
}

/**
 * Update positions from WebSocket
 */
function updatePositions(data) {
    loadPositions();
}

/**
 * Add new trade from WebSocket
 */
function addTrade(data) {
    loadTrades();
}

/**
 * Format price with currency symbol
 */
function formatPrice(price) {
    if (price === null || price === undefined) return '$0.00';
    return '$' + parseFloat(price).toLocaleString(undefined, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    });
}

/**
 * Format volume
 */
function formatVolume(volume) {
    if (volume >= 1000000000) {
        return (volume / 1000000000).toFixed(2) + 'B';
    } else if (volume >= 1000000) {
        return (volume / 1000000).toFixed(2) + 'M';
    } else if (volume >= 1000) {
        return (volume / 1000).toFixed(2) + 'K';
    }
    return volume.toFixed(2);
}

// =====================================================
// ORDER BOOK FUNCTIONS
// =====================================================

/**
 * Initialize order book
 */
function initOrderBook() {
    // Set up order book toggle button
    const toggleBtn = document.getElementById('orderBookToggle');
    if (toggleBtn) {
        toggleBtn.classList.add('active');
        toggleBtn.addEventListener('click', toggleOrderBook);
    }

    // Set up order form toggle button
    const orderFormToggleBtn = document.getElementById('orderFormToggle');
    if (orderFormToggleBtn) {
        orderFormToggleBtn.addEventListener('click', toggleOrderForm);
    }

    // Set up depth selector
    const depthSelect = document.getElementById('orderbookDepth');
    if (depthSelect) {
        depthSelect.addEventListener('change', (e) => {
            state.orderbookDepth = parseInt(e.target.value);
            loadOrderBook();
        });
    }

    // Set up orderbook view tabs (Book / Depth)
    initOrderBookTabs();

    // Initialize depth chart
    if (typeof initDepthChart === 'function') {
        initDepthChart();
    }

    // Load order book initially
    loadOrderBook();

    // Set up auto-refresh (every 2 seconds)
    state.orderbookInterval = setInterval(loadOrderBook, 2000);
}

/**
 * Initialize order book tabs (Book / Depth)
 */
function initOrderBookTabs() {
    const tabs = document.querySelectorAll('.orderbook-tab');
    const bookView = document.getElementById('orderbookBookView');
    const depthView = document.getElementById('orderbookDepthView');
    const analysisView = document.getElementById('orderbookAnalysisView');
    const depthRec = document.getElementById('depthRecommendation');

    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            const view = tab.dataset.view;

            // Update tab states
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Hide all views first
            bookView.classList.remove('active');
            depthView.classList.remove('active');
            if (analysisView) analysisView.classList.remove('active');
            if (depthRec) depthRec.classList.remove('visible');

            // Show selected view
            if (view === 'book') {
                bookView.classList.add('active');
            } else if (view === 'depth') {
                depthView.classList.add('active');
                if (depthRec) depthRec.classList.add('visible');

                // Resize depth chart when shown
                if (window.depthChart) {
                    setTimeout(() => window.depthChart.resize(), 100);
                }
            } else if (view === 'analysis') {
                if (analysisView) analysisView.classList.add('active');

                // Update analysis view when shown
                if (window.depthChart && window.depthChart.updateAnalysisView) {
                    window.depthChart.updateAnalysisView();
                }
            }
        });
    });
}

/**
 * Toggle order book visibility
 */
function toggleOrderBook() {
    const panel = document.getElementById('orderbookPanel');
    const toggleBtn = document.getElementById('orderBookToggle');

    state.orderbookVisible = !state.orderbookVisible;

    if (state.orderbookVisible) {
        panel.classList.remove('hidden');
        toggleBtn.classList.add('active');
        loadOrderBook();
        // Resume auto-refresh
        if (!state.orderbookInterval) {
            state.orderbookInterval = setInterval(loadOrderBook, 2000);
        }
    } else {
        panel.classList.add('hidden');
        toggleBtn.classList.remove('active');
        // Pause auto-refresh when hidden
        if (state.orderbookInterval) {
            clearInterval(state.orderbookInterval);
            state.orderbookInterval = null;
        }
    }

    // Resize chart after toggle
    setTimeout(() => {
        if (state.chart) {
            state.chart.timeScale().fitContent();
        }
    }, 350);
}

/**
 * Toggle order form visibility
 */
function toggleOrderForm() {
    const panel = document.getElementById('orderPanel');
    const toggleBtn = document.getElementById('orderFormToggle');

    state.orderFormVisible = !state.orderFormVisible;

    if (state.orderFormVisible) {
        panel.classList.remove('hidden');
        toggleBtn.classList.add('active');
    } else {
        panel.classList.add('hidden');
        toggleBtn.classList.remove('active');
    }

    // Resize chart after toggle
    setTimeout(() => {
        if (state.chart) {
            state.chart.timeScale().fitContent();
        }
    }, 350);
}

/**
 * Load order book data from API
 */
async function loadOrderBook() {
    if (!state.orderbookVisible) return;

    try {
        const response = await fetch(
            `/api/orderbook/${encodeURIComponent(state.symbol)}?limit=${state.orderbookDepth}`
        );

        if (!response.ok) {
            console.error('Failed to load order book');
            return;
        }

        const data = await response.json();

        if (data.error) {
            console.error('Order book error:', data.error);
            return;
        }

        renderOrderBook(data);

    } catch (error) {
        console.error('Error loading order book:', error);
    }
}

/**
 * Render order book data
 */
function renderOrderBook(data) {
    const asksContainer = document.getElementById('asksRows');
    const bidsContainer = document.getElementById('bidsRows');

    if (!data.asks || !data.bids) return;

    // Calculate totals and max for depth visualization
    let askTotal = 0;
    let bidTotal = 0;
    const asksWithTotal = data.asks.map(([price, size]) => {
        askTotal += size;
        return { price, size, total: askTotal };
    });

    const bidsWithTotal = data.bids.map(([price, size]) => {
        bidTotal += size;
        return { price, size, total: bidTotal };
    });

    const maxTotal = Math.max(askTotal, bidTotal);

    // Render asks (reversed so lowest price is at bottom, near mid price)
    asksContainer.innerHTML = asksWithTotal.reverse().map(({ price, size, total }) => {
        const depthPct = (total / maxTotal) * 100;
        return `
            <div class="orderbook-row ask" onclick="setOrderPrice(${price})">
                <div class="depth-bar" style="width: ${depthPct}%"></div>
                <span class="col-price">${formatOrderBookPrice(price)}</span>
                <span class="col-size">${size.toFixed(6)}</span>
                <span class="col-total">${total.toFixed(4)}</span>
            </div>
        `;
    }).join('');

    // Render bids
    bidsContainer.innerHTML = bidsWithTotal.map(({ price, size, total }) => {
        const depthPct = (total / maxTotal) * 100;
        return `
            <div class="orderbook-row bid" onclick="setOrderPrice(${price})">
                <div class="depth-bar" style="width: ${depthPct}%"></div>
                <span class="col-price">${formatOrderBookPrice(price)}</span>
                <span class="col-size">${size.toFixed(6)}</span>
                <span class="col-total">${total.toFixed(4)}</span>
            </div>
        `;
    }).join('');

    // Calculate and display spread
    if (data.asks.length > 0 && data.bids.length > 0) {
        const bestAsk = data.asks[0][0];
        const bestBid = data.bids[0][0];
        const spread = bestAsk - bestBid;
        const spreadPct = (spread / bestAsk) * 100;
        const midPrice = (bestAsk + bestBid) / 2;

        document.getElementById('spreadValue').textContent = spread.toFixed(1);
        document.getElementById('spreadPct').textContent = `(${spreadPct.toFixed(4)}%)`;

        const midPriceEl = document.getElementById('midPrice');
        const midArrowEl = document.getElementById('midArrow');

        midPriceEl.textContent = formatPrice(midPrice);

        // Update arrow direction based on price movement
        if (midPrice > state.lastPrice && state.lastPrice > 0) {
            midArrowEl.className = 'mid-arrow up';
            midArrowEl.innerHTML = '&#9650;';
        } else if (midPrice < state.lastPrice) {
            midArrowEl.className = 'mid-arrow down';
            midArrowEl.innerHTML = '&#9660;';
        }

        // Update depth chart
        if (typeof updateDepthChart === 'function') {
            const bids = data.bids.map(([price, size]) => ({ price, size }));
            const asks = data.asks.map(([price, size]) => ({ price, size }));
            updateDepthChart(bids, asks, midPrice);
        }
    }
}

/**
 * Format order book price (without $ symbol for cleaner look)
 */
function formatOrderBookPrice(price) {
    return parseFloat(price).toLocaleString(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 1,
    });
}

/**
 * Set order price from order book click
 */
function setOrderPrice(price) {
    const priceInput = document.getElementById('orderPrice');
    if (priceInput) {
        priceInput.value = price.toFixed(2);
        // Switch to limit order
        document.querySelectorAll('.order-tab').forEach(t => t.classList.remove('active'));
        document.querySelector('.order-tab[data-type="limit"]').classList.add('active');
        state.orderType = 'limit';
        document.querySelector('.limit-only').style.display = 'block';
        updateOrderSummary();
    }
}

// =====================================================
// TIMEZONE FUNCTIONS
// =====================================================

/**
 * Initialize timezone selector
 */
function initTimezoneSelector() {
    const timezoneBtn = document.getElementById('timezoneBtn');
    const timezoneDropdown = document.getElementById('timezoneDropdown');
    const timezoneSearch = document.getElementById('timezoneSearch');
    const timezoneList = document.getElementById('timezoneList');

    if (!timezoneBtn || !timezoneDropdown) return;

    // Toggle dropdown on button click
    timezoneBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const isOpen = timezoneDropdown.classList.contains('show');

        // Close other dropdowns
        document.querySelectorAll('.timezone-dropdown.show, .chart-type-dropdown.show').forEach(d => {
            d.classList.remove('show');
        });

        if (!isOpen) {
            timezoneDropdown.classList.add('show');
            if (timezoneSearch) {
                timezoneSearch.focus();
                timezoneSearch.value = '';
                filterTimezones('');
            }
        }
    });

    // Handle search input
    if (timezoneSearch) {
        timezoneSearch.addEventListener('input', (e) => {
            filterTimezones(e.target.value.toLowerCase());
        });

        // Prevent clicks in search from closing dropdown
        timezoneSearch.addEventListener('click', (e) => {
            e.stopPropagation();
        });
    }

    // Handle timezone option clicks
    if (timezoneList) {
        timezoneList.addEventListener('click', (e) => {
            const option = e.target.closest('.timezone-option');
            if (option) {
                const tz = option.dataset.tz;
                const offset = parseFloat(option.dataset.offset);
                const name = option.querySelector('.tz-name').textContent;
                selectTimezone(tz, offset, name);
                timezoneDropdown.classList.remove('show');
            }
        });
    }

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!timezoneDropdown.contains(e.target) && !timezoneBtn.contains(e.target)) {
            timezoneDropdown.classList.remove('show');
        }
    });

    // Load saved timezone preference or default to New York
    const savedTz = localStorage.getItem('chartTimezone') || 'America/New_York';
    const savedOption = timezoneList?.querySelector(`[data-tz="${savedTz}"]`);
    if (savedOption) {
        const offset = parseFloat(savedOption.dataset.offset);
        const name = savedOption.querySelector('.tz-name').textContent;
        selectTimezone(savedTz, offset, name, false);
    } else {
        // Fallback to New York if option not found in list
        selectTimezone('America/New_York', -5, 'New York', false);
    }
}

/**
 * Filter timezones by search query
 */
function filterTimezones(query) {
    const options = document.querySelectorAll('.timezone-option');
    const groups = document.querySelectorAll('.timezone-group-label');

    options.forEach(option => {
        const name = option.querySelector('.tz-name').textContent.toLowerCase();
        const tz = option.dataset.tz.toLowerCase();
        if (name.includes(query) || tz.includes(query)) {
            option.classList.remove('hidden');
        } else {
            option.classList.add('hidden');
        }
    });

    // Hide empty group labels
    groups.forEach(group => {
        let hasVisibleOption = false;
        let sibling = group.nextElementSibling;
        while (sibling && !sibling.classList.contains('timezone-group-label')) {
            if (sibling.classList.contains('timezone-option') && !sibling.classList.contains('hidden')) {
                hasVisibleOption = true;
                break;
            }
            sibling = sibling.nextElementSibling;
        }
        group.style.display = hasVisibleOption ? '' : 'none';
    });
}

/**
 * Select a timezone and apply to chart
 */
function selectTimezone(tz, offset, displayName, reload = true) {
    state.timezone = tz;
    state.timezoneOffset = offset;

    // Update button label
    const label = document.getElementById('timezoneLabel');
    if (label) {
        // Show short name for button
        if (tz === 'UTC') {
            label.textContent = 'UTC';
        } else {
            const shortName = tz.split('/').pop().replace(/_/g, ' ');
            label.textContent = shortName;
        }
    }

    // Update active state in dropdown
    document.querySelectorAll('.timezone-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.tz === tz);
    });

    // Save preference
    localStorage.setItem('chartTimezone', tz);

    // Apply timezone to all charts
    applyTimezoneToCharts();

    console.log(`Timezone set to: ${tz} (offset: ${offset}h)`);
}

/**
 * Apply timezone offset to chart time scale
 */
function applyTimezoneToCharts() {
    const offsetSeconds = state.timezoneOffset * 3600;

    // Apply to all active charts
    state.charts.forEach((chart, index) => {
        if (chart) {
            chart.applyOptions({
                localization: {
                    timeFormatter: (timestamp) => {
                        const date = new Date((timestamp + offsetSeconds) * 1000);
                        return formatChartTime(date);
                    },
                },
                timeScale: {
                    tickMarkFormatter: (timestamp) => {
                        const date = new Date((timestamp + offsetSeconds) * 1000);
                        return formatTickMark(date);
                    },
                },
            });
        }
    });
}

/**
 * Format time for chart tooltip
 */
function formatChartTime(date) {
    const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const month = months[date.getUTCMonth()];
    const day = date.getUTCDate();
    const hours = date.getUTCHours().toString().padStart(2, '0');
    const minutes = date.getUTCMinutes().toString().padStart(2, '0');
    return `${month} ${day}, ${hours}:${minutes}`;
}

/**
 * Format tick mark for time scale
 */
function formatTickMark(date) {
    const hours = date.getUTCHours().toString().padStart(2, '0');
    const minutes = date.getUTCMinutes().toString().padStart(2, '0');
    return `${hours}:${minutes}`;
}

// =====================================================
// CHART TYPE FUNCTIONS
// =====================================================

/**
 * Initialize chart type selector
 */
function initChartTypeSelector() {
    const chartTypeBtn = document.getElementById('chartTypeBtn');
    const chartTypeDropdown = document.getElementById('chartTypeDropdown');

    if (!chartTypeBtn || !chartTypeDropdown) return;

    // Toggle dropdown on button click
    chartTypeBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        chartTypeDropdown.classList.toggle('show');
    });

    // Handle chart type option clicks
    document.querySelectorAll('.chart-type-option').forEach(option => {
        option.addEventListener('click', () => {
            const type = option.dataset.type;
            changeChartType(type);
            chartTypeDropdown.classList.remove('show');
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.chart-type-selector')) {
            chartTypeDropdown.classList.remove('show');
        }
    });
}

/**
 * Change chart type
 */
function changeChartType(type) {
    if (state.chartType === type) return;

    state.chartType = type;

    // Update button label
    const labelMap = {
        'candlestick': 'Candles',
        'hollow': 'Hollow candles',
        'bar': 'Bars',
        'line': 'Line',
        'area': 'Area',
        'baseline': 'Baseline'
    };
    document.getElementById('chartTypeLabel').textContent = labelMap[type] || 'Candles';

    // Update active state in dropdown
    document.querySelectorAll('.chart-type-option').forEach(opt => {
        opt.classList.toggle('active', opt.dataset.type === type);
    });

    // Recreate the main chart with new type
    recreateChartWithType(0, type);
}

/**
 * Recreate chart with new type
 */
function recreateChartWithType(index, type) {
    const chart = state.charts[index];
    if (!chart) return;

    // Store current data
    const currentData = state.candleData[index] || [];

    // Remove old series
    if (state.candleSeries[index]) {
        chart.removeSeries(state.candleSeries[index]);
    }

    // Create new series based on type
    let newSeries;
    const upColor = '#0ecb81';
    const downColor = '#f6465d';

    switch (type) {
        case 'candlestick':
            newSeries = chart.addCandlestickSeries({
                upColor: upColor,
                downColor: downColor,
                borderUpColor: upColor,
                borderDownColor: downColor,
                wickUpColor: upColor,
                wickDownColor: downColor,
            });
            if (currentData.length > 0) {
                newSeries.setData(currentData);
            }
            break;

        case 'hollow':
            // Hollow candles - up candles are hollow (border only), down candles are filled
            newSeries = chart.addCandlestickSeries({
                upColor: 'transparent',
                downColor: downColor,
                borderUpColor: upColor,
                borderDownColor: downColor,
                wickUpColor: upColor,
                wickDownColor: downColor,
            });
            if (currentData.length > 0) {
                newSeries.setData(currentData);
            }
            break;

        case 'bar':
            newSeries = chart.addBarSeries({
                upColor: upColor,
                downColor: downColor,
            });
            if (currentData.length > 0) {
                newSeries.setData(currentData);
            }
            break;

        case 'line':
            newSeries = chart.addLineSeries({
                color: '#1e80ff',
                lineWidth: 2,
            });
            if (currentData.length > 0) {
                const lineData = currentData.map(c => ({
                    time: c.time,
                    value: c.close,
                }));
                newSeries.setData(lineData);
            }
            break;

        case 'area':
            newSeries = chart.addAreaSeries({
                lineColor: '#1e80ff',
                topColor: 'rgba(30, 128, 255, 0.4)',
                bottomColor: 'rgba(30, 128, 255, 0.0)',
                lineWidth: 2,
            });
            if (currentData.length > 0) {
                const areaData = currentData.map(c => ({
                    time: c.time,
                    value: c.close,
                }));
                newSeries.setData(areaData);
            }
            break;

        case 'baseline':
            // Calculate baseline as average price
            let baselineValue = 0;
            if (currentData.length > 0) {
                const sum = currentData.reduce((acc, c) => acc + c.close, 0);
                baselineValue = sum / currentData.length;
            }
            newSeries = chart.addBaselineSeries({
                baseValue: { type: 'price', price: baselineValue },
                topLineColor: upColor,
                topFillColor1: 'rgba(14, 203, 129, 0.28)',
                topFillColor2: 'rgba(14, 203, 129, 0.05)',
                bottomLineColor: downColor,
                bottomFillColor1: 'rgba(246, 70, 93, 0.05)',
                bottomFillColor2: 'rgba(246, 70, 93, 0.28)',
                lineWidth: 2,
            });
            if (currentData.length > 0) {
                const baselineData = currentData.map(c => ({
                    time: c.time,
                    value: c.close,
                }));
                newSeries.setData(baselineData);
            }
            break;
    }

    // Store new series reference
    state.candleSeries[index] = newSeries;

    // Update backward compatibility reference
    if (index === 0) {
        state.candleSerie = newSeries;
    }

    // Subscribe to crosshair move for OHLC display (only for first chart and OHLC types)
    if (index === 0 && (type === 'candlestick' || type === 'hollow' || type === 'bar')) {
        chart.subscribeCrosshairMove((param) => {
            if (param.time) {
                const data = param.seriesData.get(newSeries);
                if (data) {
                    updateOHLCDisplay(data);
                }
            }
        });
    }

    chart.timeScale().fitContent();
}

// =====================================================
// INDICATORS FUNCTIONS
// =====================================================

// Store for active indicators
const indicatorState = {
    activeIndicators: [], // Array of { id, type, settings, series }
    indicatorColors: ['#1e80ff', '#f0b90b', '#0ecb81', '#f6465d', '#8358ff', '#00bcd4', '#ff9800', '#e91e63'],
    colorIndex: 0,
    pendingIndicator: null // For settings modal
};

// Indicator definitions with default settings
const indicatorDefinitions = {
    sma: {
        name: 'Simple Moving Average',
        shortName: 'SMA',
        overlay: true,
        defaultSettings: { period: 20, source: 'close', color: '#1e80ff', lineWidth: 2 },
        settingsForm: [
            { key: 'period', label: 'Period', type: 'number', min: 1, max: 500 },
            { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    ema: {
        name: 'Exponential Moving Average',
        shortName: 'EMA',
        overlay: true,
        defaultSettings: { period: 20, source: 'close', color: '#f0b90b', lineWidth: 2 },
        settingsForm: [
            { key: 'period', label: 'Period', type: 'number', min: 1, max: 500 },
            { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    wma: {
        name: 'Weighted Moving Average',
        shortName: 'WMA',
        overlay: true,
        defaultSettings: { period: 20, source: 'close', color: '#0ecb81', lineWidth: 2 },
        settingsForm: [
            { key: 'period', label: 'Period', type: 'number', min: 1, max: 500 },
            { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low', 'hl2', 'hlc3', 'ohlc4'] },
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    bollinger: {
        name: 'Bollinger Bands',
        shortName: 'BB',
        overlay: true,
        defaultSettings: { period: 20, stdDev: 2, source: 'close', color: '#8358ff', lineWidth: 1 },
        settingsForm: [
            { key: 'period', label: 'Period', type: 'number', min: 1, max: 500 },
            { key: 'stdDev', label: 'Std Deviation', type: 'number', min: 0.5, max: 5, step: 0.5 },
            { key: 'source', label: 'Source', type: 'select', options: ['close', 'open', 'high', 'low'] },
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    rsi: {
        name: 'RSI',
        shortName: 'RSI',
        overlay: false,
        defaultSettings: { period: 14, overbought: 70, oversold: 30, color: '#f0b90b', lineWidth: 2 },
        settingsForm: [
            { key: 'period', label: 'Period', type: 'number', min: 1, max: 100 },
            { key: 'overbought', label: 'Overbought', type: 'number', min: 50, max: 100 },
            { key: 'oversold', label: 'Oversold', type: 'number', min: 0, max: 50 },
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    macd: {
        name: 'MACD',
        shortName: 'MACD',
        overlay: false,
        defaultSettings: { fastPeriod: 12, slowPeriod: 26, signalPeriod: 9, macdColor: '#1e80ff', signalColor: '#f0b90b', histogramUp: '#0ecb81', histogramDown: '#f6465d' },
        settingsForm: [
            { key: 'fastPeriod', label: 'Fast Period', type: 'number', min: 1, max: 100 },
            { key: 'slowPeriod', label: 'Slow Period', type: 'number', min: 1, max: 100 },
            { key: 'signalPeriod', label: 'Signal Period', type: 'number', min: 1, max: 100 },
            { key: 'macdColor', label: 'MACD Color', type: 'color' },
            { key: 'signalColor', label: 'Signal Color', type: 'color' }
        ]
    },
    vwap: {
        name: 'VWAP',
        shortName: 'VWAP',
        overlay: true,
        defaultSettings: { color: '#00bcd4', lineWidth: 2 },
        settingsForm: [
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    atr: {
        name: 'ATR',
        shortName: 'ATR',
        overlay: false,
        defaultSettings: { period: 14, color: '#ff9800', lineWidth: 2 },
        settingsForm: [
            { key: 'period', label: 'Period', type: 'number', min: 1, max: 100 },
            { key: 'color', label: 'Color', type: 'color' },
            { key: 'lineWidth', label: 'Line Width', type: 'number', min: 1, max: 5 }
        ]
    },
    bos_mss: {
        name: 'BOS/MSS (Structure Breaks)',
        shortName: 'BOS/MSS',
        overlay: true,
        isMarker: true,  // Uses async fetch for structure data
        defaultSettings: {
            swingLookback: 5,
            showSwings: true,
            swingHighColor: '#26a69a',  // Teal for resistance levels
            swingLowColor: '#ef5350'    // Red for support levels
        },
        settingsForm: [
            { key: 'swingLookback', label: 'Swing Lookback', type: 'number', min: 2, max: 20 },
            { key: 'showSwings', label: 'Show Swing Levels', type: 'checkbox' },
            { key: 'swingHighColor', label: 'High Level Color', type: 'color' },
            { key: 'swingLowColor', label: 'Low Level Color', type: 'color' }
        ]
    },
    swing_points: {
        name: 'Swing Points',
        shortName: 'Swings',
        overlay: true,
        isMarker: true,
        defaultSettings: {
            swingLookback: 5,
            swingHighColor: '#26a69a',  // Teal for resistance levels
            swingLowColor: '#ef5350'    // Red for support levels
        },
        settingsForm: [
            { key: 'swingLookback', label: 'Swing Lookback', type: 'number', min: 2, max: 20 },
            { key: 'swingHighColor', label: 'High Level Color', type: 'color' },
            { key: 'swingLowColor', label: 'Low Level Color', type: 'color' }
        ]
    }
};

/**
 * Initialize indicators functionality
 */
function initIndicators() {
    console.log('Initializing indicators...');

    // Indicators button click
    const indicatorsBtn = document.getElementById('indicatorsBtn');
    if (indicatorsBtn) {
        indicatorsBtn.addEventListener('click', openIndicatorsModal);
    }

    // Modal close buttons
    document.getElementById('closeIndicatorsModal')?.addEventListener('click', closeIndicatorsModal);
    document.getElementById('closeSettingsModal')?.addEventListener('click', closeSettingsModal);

    // Close modals on overlay click
    document.getElementById('indicatorsModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'indicatorsModal') closeIndicatorsModal();
    });
    document.getElementById('indicatorSettingsModal')?.addEventListener('click', (e) => {
        if (e.target.id === 'indicatorSettingsModal') closeSettingsModal();
    });

    // Search functionality
    document.getElementById('indicatorSearch')?.addEventListener('input', filterIndicators);

    // Add button clicks
    document.querySelectorAll('.add-indicator-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const item = btn.closest('.indicator-item');
            const indicatorType = item.dataset.indicator;
            openIndicatorSettings(indicatorType);
        });
    });

    // Settings modal buttons
    document.getElementById('cancelIndicatorSettings')?.addEventListener('click', closeSettingsModal);
    document.getElementById('applyIndicatorSettings')?.addEventListener('click', applyIndicatorSettings);

    console.log('Indicators initialized');
}

/**
 * Open indicators modal
 */
function openIndicatorsModal() {
    const modal = document.getElementById('indicatorsModal');
    if (modal) {
        modal.classList.add('show');
        updateActiveIndicatorsList();
    }
}

/**
 * Close indicators modal
 */
function closeIndicatorsModal() {
    const modal = document.getElementById('indicatorsModal');
    if (modal) {
        modal.classList.remove('show');
    }
}

/**
 * Open indicator settings modal
 */
function openIndicatorSettings(indicatorType, existingId = null) {
    const definition = indicatorDefinitions[indicatorType];
    if (!definition) return;

    indicatorState.pendingIndicator = {
        type: indicatorType,
        existingId: existingId
    };

    // Set modal title
    document.getElementById('settingsIndicatorName').textContent = definition.name + ' Settings';

    // Build settings form
    const form = document.getElementById('indicatorSettingsForm');
    const existingIndicator = existingId ? indicatorState.activeIndicators.find(i => i.id === existingId) : null;
    const settings = existingIndicator ? existingIndicator.settings : { ...definition.defaultSettings };

    // Assign next color if new
    if (!existingIndicator && settings.color === definition.defaultSettings.color) {
        settings.color = indicatorState.indicatorColors[indicatorState.colorIndex % indicatorState.indicatorColors.length];
    }

    let formHtml = '';
    definition.settingsForm.forEach(field => {
        formHtml += `<div class="settings-group">`;
        formHtml += `<label>${field.label}</label>`;

        if (field.type === 'number') {
            formHtml += `<input type="number" name="${field.key}" value="${settings[field.key]}"
                min="${field.min || 1}" max="${field.max || 500}" step="${field.step || 1}">`;
        } else if (field.type === 'select') {
            formHtml += `<select name="${field.key}">`;
            field.options.forEach(opt => {
                formHtml += `<option value="${opt}" ${settings[field.key] === opt ? 'selected' : ''}>${opt}</option>`;
            });
            formHtml += `</select>`;
        } else if (field.type === 'color') {
            formHtml += `<div class="color-input-wrapper">
                <input type="color" name="${field.key}" value="${settings[field.key]}">
                <span>${settings[field.key]}</span>
            </div>`;
        } else if (field.type === 'checkbox') {
            formHtml += `<label class="checkbox-wrapper">
                <input type="checkbox" name="${field.key}" ${settings[field.key] ? 'checked' : ''}>
                <span class="checkmark"></span>
            </label>`;
        }

        formHtml += `</div>`;
    });

    form.innerHTML = formHtml;

    // Add color preview update
    form.querySelectorAll('input[type="color"]').forEach(input => {
        input.addEventListener('input', (e) => {
            e.target.nextElementSibling.textContent = e.target.value;
        });
    });

    // Show modal
    document.getElementById('indicatorSettingsModal').classList.add('show');
}

/**
 * Close settings modal
 */
function closeSettingsModal() {
    document.getElementById('indicatorSettingsModal').classList.remove('show');
    indicatorState.pendingIndicator = null;
}

/**
 * Apply indicator settings
 */
function applyIndicatorSettings() {
    if (!indicatorState.pendingIndicator) return;

    const { type, existingId } = indicatorState.pendingIndicator;
    const form = document.getElementById('indicatorSettingsForm');
    const definition = indicatorDefinitions[type];

    // Collect settings from form
    const settings = {};
    definition.settingsForm.forEach(field => {
        const input = form.querySelector(`[name="${field.key}"]`);
        if (input) {
            if (field.type === 'number') {
                settings[field.key] = parseFloat(input.value);
            } else if (field.type === 'checkbox') {
                settings[field.key] = input.checked;
            } else {
                settings[field.key] = input.value;
            }
        }
    });

    if (existingId) {
        // Update existing indicator
        updateIndicator(existingId, settings);
    } else {
        // Add new indicator
        addIndicator(type, settings);
        indicatorState.colorIndex++;
    }

    closeSettingsModal();
    closeIndicatorsModal();
}

/**
 * Add indicator to chart
 */
async function addIndicator(type, settings) {
    const definition = indicatorDefinitions[type];
    if (!definition) return;

    const id = `${type}_${Date.now()}`;
    const indicator = {
        id,
        type,
        settings: { ...settings },
        series: [],
        isMarker: definition.isMarker || false,
        markers: []
    };

    // Create series on chart
    const chart = state.charts[0];
    if (!chart) return;

    // Handle marker-based indicators (BOS/MSS, Swing Points)
    if (definition.isMarker) {
        await addMarkerBasedIndicator(indicator, chart, settings);
    } else {
        // Calculate indicator data for line-based indicators
        const data = calculateIndicator(type, settings);
        if (!data) return;

        if (definition.overlay) {
            // Overlay indicators (on price chart)
            if (type === 'bollinger') {
                // Bollinger bands - 3 lines
                const upperSeries = chart.addLineSeries({
                    color: settings.color,
                    lineWidth: settings.lineWidth,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                });
                const middleSeries = chart.addLineSeries({
                    color: settings.color,
                    lineWidth: settings.lineWidth,
                });
                const lowerSeries = chart.addLineSeries({
                    color: settings.color,
                    lineWidth: settings.lineWidth,
                    lineStyle: LightweightCharts.LineStyle.Dashed,
                });

                upperSeries.setData(data.upper);
                middleSeries.setData(data.middle);
                lowerSeries.setData(data.lower);

                indicator.series = [upperSeries, middleSeries, lowerSeries];
            } else {
                // Single line indicator
                const series = chart.addLineSeries({
                    color: settings.color,
                    lineWidth: settings.lineWidth,
                });
                series.setData(data);
                indicator.series = [series];
            }
        } else {
            // Non-overlay indicators - displayed below price chart
            // For now, we'll overlay them but with different scale
            if (type === 'macd') {
                // MACD has histogram + 2 lines
                const histSeries = chart.addHistogramSeries({
                    color: settings.histogramUp,
                    priceFormat: { type: 'price' },
                    priceScaleId: 'macd',
                    scaleMargins: { top: 0.8, bottom: 0 },
                });
                const macdSeries = chart.addLineSeries({
                    color: settings.macdColor,
                    lineWidth: 2,
                    priceScaleId: 'macd',
                });
                const signalSeries = chart.addLineSeries({
                    color: settings.signalColor,
                    lineWidth: 2,
                    priceScaleId: 'macd',
                });

                histSeries.setData(data.histogram);
                macdSeries.setData(data.macd);
                signalSeries.setData(data.signal);

                indicator.series = [histSeries, macdSeries, signalSeries];
            } else {
                // RSI, ATR, etc - single line with separate scale
                const series = chart.addLineSeries({
                    color: settings.color,
                    lineWidth: settings.lineWidth,
                    priceScaleId: type,
                    scaleMargins: { top: 0.8, bottom: 0 },
                });
                series.setData(data);
                indicator.series = [series];
            }
        }
    }

    indicatorState.activeIndicators.push(indicator);
    updateActiveIndicatorsList();
    updateIndicatorBadges();

    console.log(`Added indicator: ${type}`, settings);
}

/**
 * Add marker-based indicator (BOS/MSS, Swing Points)
 */
async function addMarkerBasedIndicator(indicator, chart, settings) {
    const symbol = state.currentPair || 'BTC/USD';
    // Use the actual chart timeframe - check multiple sources
    const timeframe = state.currentTimeframe || state.chartTimeframes?.[0] || state.timeframe || '1h';
    const lookback = settings.swingLookback || 5;

    console.log(`[BOS/MSS] Fetching data for ${symbol} @ ${timeframe} with lookback=${lookback}`);

    // Fetch structure break data from API
    const structureData = await fetchStructureBreaks(symbol, timeframe, lookback);

    if (!structureData) {
        console.warn(`[BOS/MSS] No structure data available for ${symbol}`);
        return;
    }

    console.log(`[BOS/MSS] Got data:`, {
        swing_highs: structureData.swing_highs?.length || 0,
        swing_lows: structureData.swing_lows?.length || 0,
        bos_events: structureData.bos_events?.length || 0,
        mss_events: structureData.mss_events?.length || 0
    });

    // Create horizontal lines for swing levels (TradingView style)
    const lineSeries = [];
    const candleData = state.candleData[0] || [];

    if (candleData.length === 0) {
        console.warn('[BOS/MSS] No candle data available');
        return;
    }

    const firstCandleTime = candleData[0].time;
    const lastCandleTime = candleData[candleData.length - 1].time;

    console.log(`[BOS/MSS] Chart data range: ${firstCandleTime} to ${lastCandleTime}`);

    // Helper to find where a level was broken
    const findBreakTime = (startTime, price, isSwingHigh) => {
        // Find the starting index in candle data
        let startIdx = -1;
        for (let i = 0; i < candleData.length; i++) {
            if (candleData[i].time >= startTime) {
                startIdx = i;
                break;
            }
        }
        if (startIdx === -1) return null;

        // Skip first few candles after swing (give it room to form)
        const skipCandles = 2;

        // Find candles after the swing point
        for (let i = startIdx + skipCandles; i < candleData.length; i++) {
            const candle = candleData[i];

            // For swing high: broken when candle body closes above the level
            // For swing low: broken when candle body closes below the level
            if (isSwingHigh && candle.close > price) {
                return candle.time;
            }
            if (!isSwingHigh && candle.close < price) {
                return candle.time;
            }
        }
        return null; // Not broken yet
    };

    // Helper to create a line series safely
    const createSwingLine = (swing, color, fadedColor, isSwingHigh) => {
        try {
            const startTime = timestampToUnix(swing.timestamp);
            if (!startTime || startTime < firstCandleTime) {
                console.log(`[BOS/MSS] Skipping swing - startTime: ${startTime}, firstCandleTime: ${firstCandleTime}`);
                return null;
            }

            // Find where the level was broken (if at all)
            const breakTime = findBreakTime(startTime, swing.price, isSwingHigh);
            const isBroken = breakTime !== null;

            console.log(`[BOS/MSS] Swing ${isSwingHigh ? 'HIGH' : 'LOW'} @ ${swing.price}: startTime=${startTime}, breakTime=${breakTime}, isBroken=${isBroken}`);

            // Line extends to break point or current time if unbroken
            const endTime = isBroken ? breakTime : lastCandleTime;

            const series = chart.addLineSeries({
                color: isBroken ? fadedColor : color,
                lineWidth: isBroken ? 1 : 2,
                lineStyle: isBroken ? 2 : 0, // Dashed if broken
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
            });

            const lineData = [
                { time: startTime, value: swing.price },
                { time: endTime, value: swing.price }
            ];
            series.setData(lineData);
            return series;
        } catch (e) {
            console.warn('[BOS/MSS] Error creating swing line:', e);
            return null;
        }
    };

    // Limit to most recent swings for cleaner display
    const maxSwings = 15;

    // Process swing highs - draw horizontal lines (teal)
    if (structureData.swing_highs && settings.showSwings !== false) {
        const highColor = settings.swingHighColor || '#26a69a';
        // Take only the most recent swings
        const recentHighs = structureData.swing_highs.slice(-maxSwings);
        console.log(`[BOS/MSS] Processing ${recentHighs.length} swing highs`);
        recentHighs.forEach(swing => {
            const series = createSwingLine(swing, highColor, 'rgba(38, 166, 154, 0.4)', true);
            if (series) lineSeries.push(series);
        });
    }

    // Process swing lows - draw horizontal lines (red)
    if (structureData.swing_lows && settings.showSwings !== false) {
        const lowColor = settings.swingLowColor || '#ef5350';
        // Take only the most recent swings
        const recentLows = structureData.swing_lows.slice(-maxSwings);
        console.log(`[BOS/MSS] Processing ${recentLows.length} swing lows`);
        recentLows.forEach(swing => {
            const series = createSwingLine(swing, lowColor, 'rgba(239, 83, 80, 0.4)', false);
            if (series) lineSeries.push(series);
        });
    }

    // Store line series for removal
    indicator.series = lineSeries;
    indicator.isMarker = false; // Changed to line-based

    console.log(`[BOS/MSS] Created ${lineSeries.length} horizontal lines for swing levels`);
}

/**
 * Get existing markers from all active marker-based indicators
 */
function getExistingMarkers() {
    const markers = [];
    indicatorState.activeIndicators.forEach(ind => {
        if (ind.isMarker && ind.markers) {
            markers.push(...ind.markers);
        }
    });
    return markers;
}

/**
 * Refresh all markers on the chart
 */
function refreshAllMarkers() {
    const candleSeries = state.candleSeries[0] || state.candleSerie;
    if (!candleSeries) return;

    const allMarkers = getExistingMarkers();
    allMarkers.sort((a, b) => a.time - b.time);
    candleSeries.setMarkers(allMarkers);
}

/**
 * Remove indicator from chart
 */
function removeIndicator(id) {
    const index = indicatorState.activeIndicators.findIndex(i => i.id === id);
    if (index === -1) return;

    const indicator = indicatorState.activeIndicators[index];
    const chart = state.charts[0];

    // Handle marker-based indicators
    if (indicator.isMarker) {
        // Clear markers from this indicator
        indicator.markers = [];
        // Remove from active indicators first
        indicatorState.activeIndicators.splice(index, 1);
        // Refresh all remaining markers
        refreshAllMarkers();
    } else {
        // Remove series from chart for line-based indicators
        indicator.series.forEach(series => {
            try {
                chart.removeSeries(series);
            } catch (e) {
                console.warn('Error removing series:', e);
            }
        });
        indicatorState.activeIndicators.splice(index, 1);
    }

    updateActiveIndicatorsList();
    updateIndicatorBadges();

    console.log(`Removed indicator: ${id}`);
}

/**
 * Update indicator settings
 */
function updateIndicator(id, newSettings) {
    const indicator = indicatorState.activeIndicators.find(i => i.id === id);
    if (!indicator) return;

    // Remove old series
    const chart = state.charts[0];
    indicator.series.forEach(series => {
        try {
            chart.removeSeries(series);
        } catch (e) {}
    });

    // Update settings and recalculate
    indicator.settings = { ...newSettings };
    indicator.series = [];

    // Re-add with new settings
    const data = calculateIndicator(indicator.type, indicator.settings);
    if (!data) return;

    const definition = indicatorDefinitions[indicator.type];

    if (definition.overlay) {
        if (indicator.type === 'bollinger') {
            const upperSeries = chart.addLineSeries({ color: newSettings.color, lineWidth: newSettings.lineWidth, lineStyle: LightweightCharts.LineStyle.Dashed });
            const middleSeries = chart.addLineSeries({ color: newSettings.color, lineWidth: newSettings.lineWidth });
            const lowerSeries = chart.addLineSeries({ color: newSettings.color, lineWidth: newSettings.lineWidth, lineStyle: LightweightCharts.LineStyle.Dashed });
            upperSeries.setData(data.upper);
            middleSeries.setData(data.middle);
            lowerSeries.setData(data.lower);
            indicator.series = [upperSeries, middleSeries, lowerSeries];
        } else {
            const series = chart.addLineSeries({ color: newSettings.color, lineWidth: newSettings.lineWidth });
            series.setData(data);
            indicator.series = [series];
        }
    }

    updateActiveIndicatorsList();
    console.log(`Updated indicator: ${id}`, newSettings);
}

/**
 * Calculate indicator values
 */
function calculateIndicator(type, settings) {
    const candles = state.candleData[0];
    if (!candles || candles.length === 0) return null;

    switch (type) {
        case 'sma':
            return calculateSMA(candles, settings.period, settings.source);
        case 'ema':
            return calculateEMA(candles, settings.period, settings.source);
        case 'wma':
            return calculateWMA(candles, settings.period, settings.source);
        case 'bollinger':
            return calculateBollingerBands(candles, settings.period, settings.stdDev, settings.source);
        case 'rsi':
            return calculateRSI(candles, settings.period);
        case 'macd':
            return calculateMACD(candles, settings.fastPeriod, settings.slowPeriod, settings.signalPeriod);
        case 'vwap':
            return calculateVWAP(candles);
        case 'atr':
            return calculateATR(candles, settings.period);
        default:
            return null;
    }
}

/**
 * Get price based on source
 */
function getSourcePrice(candle, source) {
    switch (source) {
        case 'open': return candle.open;
        case 'high': return candle.high;
        case 'low': return candle.low;
        case 'close': return candle.close;
        case 'hl2': return (candle.high + candle.low) / 2;
        case 'hlc3': return (candle.high + candle.low + candle.close) / 3;
        case 'ohlc4': return (candle.open + candle.high + candle.low + candle.close) / 4;
        default: return candle.close;
    }
}

/**
 * Calculate Simple Moving Average
 */
function calculateSMA(candles, period, source = 'close') {
    const result = [];
    for (let i = period - 1; i < candles.length; i++) {
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += getSourcePrice(candles[i - j], source);
        }
        result.push({
            time: candles[i].time,
            value: sum / period
        });
    }
    return result;
}

/**
 * Calculate Exponential Moving Average
 */
function calculateEMA(candles, period, source = 'close') {
    const result = [];
    const multiplier = 2 / (period + 1);

    // First EMA is SMA
    let sum = 0;
    for (let i = 0; i < period; i++) {
        sum += getSourcePrice(candles[i], source);
    }
    let prevEma = sum / period;
    result.push({ time: candles[period - 1].time, value: prevEma });

    // Calculate EMA for rest
    for (let i = period; i < candles.length; i++) {
        const price = getSourcePrice(candles[i], source);
        const ema = (price - prevEma) * multiplier + prevEma;
        result.push({ time: candles[i].time, value: ema });
        prevEma = ema;
    }

    return result;
}

/**
 * Calculate Weighted Moving Average
 */
function calculateWMA(candles, period, source = 'close') {
    const result = [];
    const weightSum = (period * (period + 1)) / 2;

    for (let i = period - 1; i < candles.length; i++) {
        let sum = 0;
        for (let j = 0; j < period; j++) {
            const weight = period - j;
            sum += getSourcePrice(candles[i - j], source) * weight;
        }
        result.push({
            time: candles[i].time,
            value: sum / weightSum
        });
    }
    return result;
}

/**
 * Calculate Bollinger Bands
 */
function calculateBollingerBands(candles, period, stdDev, source = 'close') {
    const sma = calculateSMA(candles, period, source);
    const upper = [];
    const middle = [];
    const lower = [];

    for (let i = 0; i < sma.length; i++) {
        const startIdx = i;
        const endIdx = i + period;
        const candleSlice = candles.slice(startIdx, endIdx);

        // Calculate standard deviation
        let sumSquares = 0;
        candleSlice.forEach(c => {
            const diff = getSourcePrice(c, source) - sma[i].value;
            sumSquares += diff * diff;
        });
        const std = Math.sqrt(sumSquares / period);

        middle.push({ time: sma[i].time, value: sma[i].value });
        upper.push({ time: sma[i].time, value: sma[i].value + stdDev * std });
        lower.push({ time: sma[i].time, value: sma[i].value - stdDev * std });
    }

    return { upper, middle, lower };
}

/**
 * Calculate RSI
 */
function calculateRSI(candles, period) {
    const result = [];
    const gains = [];
    const losses = [];

    // Calculate price changes
    for (let i = 1; i < candles.length; i++) {
        const change = candles[i].close - candles[i - 1].close;
        gains.push(change > 0 ? change : 0);
        losses.push(change < 0 ? Math.abs(change) : 0);
    }

    // First RSI - simple average
    let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period;
    let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period;

    for (let i = period; i < candles.length; i++) {
        if (i > period) {
            avgGain = (avgGain * (period - 1) + gains[i - 1]) / period;
            avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period;
        }

        const rs = avgLoss === 0 ? 100 : avgGain / avgLoss;
        const rsi = 100 - (100 / (1 + rs));

        result.push({
            time: candles[i].time,
            value: rsi
        });
    }

    return result;
}

/**
 * Calculate MACD
 */
function calculateMACD(candles, fastPeriod, slowPeriod, signalPeriod) {
    const fastEMA = calculateEMA(candles, fastPeriod, 'close');
    const slowEMA = calculateEMA(candles, slowPeriod, 'close');

    // MACD line
    const macdLine = [];
    const startIdx = slowPeriod - fastPeriod;

    for (let i = 0; i < slowEMA.length; i++) {
        const fastIdx = i + startIdx;
        if (fastIdx >= 0 && fastIdx < fastEMA.length) {
            macdLine.push({
                time: slowEMA[i].time,
                value: fastEMA[fastIdx].value - slowEMA[i].value
            });
        }
    }

    // Signal line (EMA of MACD)
    const signalLine = [];
    const multiplier = 2 / (signalPeriod + 1);
    let sum = 0;
    for (let i = 0; i < signalPeriod && i < macdLine.length; i++) {
        sum += macdLine[i].value;
    }
    let prevSignal = sum / signalPeriod;

    for (let i = signalPeriod - 1; i < macdLine.length; i++) {
        if (i === signalPeriod - 1) {
            signalLine.push({ time: macdLine[i].time, value: prevSignal });
        } else {
            const signal = (macdLine[i].value - prevSignal) * multiplier + prevSignal;
            signalLine.push({ time: macdLine[i].time, value: signal });
            prevSignal = signal;
        }
    }

    // Histogram
    const histogram = [];
    for (let i = 0; i < signalLine.length; i++) {
        const macdIdx = i + signalPeriod - 1;
        if (macdIdx < macdLine.length) {
            const value = macdLine[macdIdx].value - signalLine[i].value;
            histogram.push({
                time: signalLine[i].time,
                value: value,
                color: value >= 0 ? '#0ecb81' : '#f6465d'
            });
        }
    }

    return {
        macd: macdLine.slice(signalPeriod - 1),
        signal: signalLine,
        histogram: histogram
    };
}

/**
 * Calculate VWAP
 */
function calculateVWAP(candles) {
    const result = [];
    let cumulativeTPV = 0;
    let cumulativeVolume = 0;

    candles.forEach(candle => {
        const typicalPrice = (candle.high + candle.low + candle.close) / 3;
        const volume = candle.volume || 1;

        cumulativeTPV += typicalPrice * volume;
        cumulativeVolume += volume;

        result.push({
            time: candle.time,
            value: cumulativeTPV / cumulativeVolume
        });
    });

    return result;
}

/**
 * Calculate ATR
 */
function calculateATR(candles, period) {
    const result = [];
    const trueRanges = [];

    for (let i = 1; i < candles.length; i++) {
        const high = candles[i].high;
        const low = candles[i].low;
        const prevClose = candles[i - 1].close;

        const tr = Math.max(
            high - low,
            Math.abs(high - prevClose),
            Math.abs(low - prevClose)
        );
        trueRanges.push(tr);
    }

    // First ATR is simple average
    let atr = trueRanges.slice(0, period).reduce((a, b) => a + b, 0) / period;
    result.push({ time: candles[period].time, value: atr });

    // Smoothed ATR
    for (let i = period; i < trueRanges.length; i++) {
        atr = (atr * (period - 1) + trueRanges[i]) / period;
        result.push({ time: candles[i + 1].time, value: atr });
    }

    return result;
}

/**
 * Fetch BOS/MSS structure break data from API
 */
async function fetchStructureBreaks(symbol, timeframe, lookback = 5) {
    try {
        // Convert BTC/USD to BTC-USD format for API
        const apiSymbol = symbol.replace('/', '-');
        console.log(`[BOS/MSS] Calling API: /api/structure/${apiSymbol}?timeframe=${timeframe}&lookback=${lookback}`);
        const response = await fetch(`/api/structure/${apiSymbol}?timeframe=${timeframe}&lookback=${lookback}`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log(`[BOS/MSS] API response:`, data);
        // Check for error field in response
        if (data.error) {
            console.error(`[BOS/MSS] API error: ${data.error}`);
            return null;
        }
        return data;
    } catch (error) {
        console.error('[BOS/MSS] Error fetching structure breaks:', error);
        return null;
    }
}

/**
 * Convert timestamp string to Unix timestamp (seconds)
 */
function timestampToUnix(timestamp) {
    if (typeof timestamp === 'number') return timestamp;
    const date = new Date(timestamp);
    return Math.floor(date.getTime() / 1000);
}

/**
 * Create markers for BOS/MSS indicator
 */
function createBossMssMarkers(structureData, settings) {
    const markers = [];

    if (!structureData) return markers;

    // Add swing point markers if enabled
    if (settings.showSwings) {
        // Process swing highs
        if (structureData.swing_highs) {
            structureData.swing_highs.forEach(swing => {
                const time = timestampToUnix(swing.timestamp);
                if (time) {
                    markers.push({
                        time: time,
                        position: 'aboveBar',
                        color: settings.swingHighColor,
                        shape: 'arrowDown',
                        text: 'SH',
                        size: 1
                    });
                }
            });
        }

        // Process swing lows
        if (structureData.swing_lows) {
            structureData.swing_lows.forEach(swing => {
                const time = timestampToUnix(swing.timestamp);
                if (time) {
                    markers.push({
                        time: time,
                        position: 'belowBar',
                        color: settings.swingLowColor,
                        shape: 'arrowUp',
                        text: 'SL',
                        size: 1
                    });
                }
            });
        }
    }

    // Add BOS markers
    if (structureData.bos_events) {
        structureData.bos_events.forEach(brk => {
            const time = timestampToUnix(brk.timestamp);
            if (time) {
                const isBullish = brk.direction === 'bullish';
                markers.push({
                    time: time,
                    position: isBullish ? 'belowBar' : 'aboveBar',
                    color: settings.bosColor,
                    shape: 'circle',
                    text: isBullish ? 'BOS↑' : 'BOS↓',
                    size: 2
                });
            }
        });
    }

    // Add MSS markers
    if (structureData.mss_events) {
        structureData.mss_events.forEach(brk => {
            const time = timestampToUnix(brk.timestamp);
            if (time) {
                const isBullish = brk.direction === 'bullish';
                markers.push({
                    time: time,
                    position: isBullish ? 'belowBar' : 'aboveBar',
                    color: settings.mssColor,
                    shape: 'square',
                    text: isBullish ? 'MSS↑' : 'MSS↓',
                    size: 2
                });
            }
        });
    }

    // Sort markers by time
    markers.sort((a, b) => a.time - b.time);

    return markers;
}

/**
 * Create markers for swing points only indicator
 */
function createSwingPointMarkers(structureData, settings) {
    const markers = [];

    if (!structureData) return markers;

    // Process swing highs
    if (structureData.swing_highs) {
        structureData.swing_highs.forEach(swing => {
            const time = timestampToUnix(swing.timestamp);
            if (time) {
                markers.push({
                    time: time,
                    position: 'aboveBar',
                    color: settings.swingHighColor,
                    shape: 'arrowDown',
                    text: 'SH',
                    size: 1
                });
            }
        });
    }

    // Process swing lows
    if (structureData.swing_lows) {
        structureData.swing_lows.forEach(swing => {
            const time = timestampToUnix(swing.timestamp);
            if (time) {
                markers.push({
                    time: time,
                    position: 'belowBar',
                    color: settings.swingLowColor,
                    shape: 'arrowUp',
                    text: 'SL',
                    size: 1
                });
            }
        });
    }

    // Sort markers by time
    markers.sort((a, b) => a.time - b.time);

    return markers;
}

/**
 * Update active indicators list in modal
 */
function updateActiveIndicatorsList() {
    const container = document.getElementById('activeIndicatorList');
    if (!container) return;

    if (indicatorState.activeIndicators.length === 0) {
        container.innerHTML = '<div class="empty-state">No indicators active</div>';
        return;
    }

    container.innerHTML = indicatorState.activeIndicators.map(indicator => {
        const definition = indicatorDefinitions[indicator.type];
        return `
            <div class="indicator-item active" data-id="${indicator.id}">
                <div class="indicator-info">
                    <span class="indicator-name">${definition.name}</span>
                    <span class="indicator-desc">${getIndicatorDescription(indicator)}</span>
                </div>
                <div class="indicator-controls">
                    <button class="indicator-settings-btn" onclick="openIndicatorSettings('${indicator.type}', '${indicator.id}')" title="Settings">
                        <svg width="14" height="14" viewBox="0 0 14 14"><path fill="currentColor" d="M7 9.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zm0-1a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"/><path fill="currentColor" d="M12.5 7.83l.88.51a.5.5 0 0 1 .18.68l-1 1.73a.5.5 0 0 1-.68.18l-.88-.51a4.5 4.5 0 0 1-.98.57v1a.5.5 0 0 1-.5.5h-2a.5.5 0 0 1-.5-.5v-1a4.5 4.5 0 0 1-.98-.57l-.88.51a.5.5 0 0 1-.68-.18l-1-1.73a.5.5 0 0 1 .18-.68l.88-.51a4.5 4.5 0 0 1 0-1.66l-.88-.51a.5.5 0 0 1-.18-.68l1-1.73a.5.5 0 0 1 .68-.18l.88.51a4.5 4.5 0 0 1 .98-.57v-1a.5.5 0 0 1 .5-.5h2a.5.5 0 0 1 .5.5v1a4.5 4.5 0 0 1 .98.57l.88-.51a.5.5 0 0 1 .68.18l1 1.73a.5.5 0 0 1-.18.68l-.88.51a4.5 4.5 0 0 1 0 1.66z"/></svg>
                    </button>
                    <button class="indicator-remove-btn" onclick="removeIndicator('${indicator.id}')" title="Remove">
                        <svg width="14" height="14" viewBox="0 0 14 14"><path fill="currentColor" d="M3.5 3.5l7 7m0-7l-7 7" stroke="currentColor" stroke-width="1.5"/></svg>
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

/**
 * Get indicator description string
 */
function getIndicatorDescription(indicator) {
    const s = indicator.settings;
    switch (indicator.type) {
        case 'sma':
        case 'ema':
        case 'wma':
            return `Period: ${s.period}`;
        case 'bollinger':
            return `Period: ${s.period}, StdDev: ${s.stdDev}`;
        case 'rsi':
            return `Period: ${s.period}`;
        case 'macd':
            return `${s.fastPeriod}/${s.slowPeriod}/${s.signalPeriod}`;
        case 'atr':
            return `Period: ${s.period}`;
        case 'bos_mss':
            return `Lookback: ${s.swingLookback}`;
        case 'swing_points':
            return `Lookback: ${s.swingLookback}`;
        default:
            return '';
    }
}

/**
 * Update indicator badges in toolbar
 */
function updateIndicatorBadges() {
    // Update the indicators button to show count
    const btn = document.getElementById('indicatorsBtn');
    if (btn) {
        const count = indicatorState.activeIndicators.length;
        const existingBadge = btn.querySelector('.indicator-count');

        if (count > 0) {
            if (existingBadge) {
                existingBadge.textContent = count;
            } else {
                const badge = document.createElement('span');
                badge.className = 'indicator-count';
                badge.style.cssText = 'background: var(--accent-blue); color: white; border-radius: 50%; width: 16px; height: 16px; font-size: 10px; display: inline-flex; align-items: center; justify-content: center; margin-left: 4px;';
                badge.textContent = count;
                btn.appendChild(badge);
            }
        } else if (existingBadge) {
            existingBadge.remove();
        }
    }
}

/**
 * Filter indicators in modal
 */
function filterIndicators() {
    const searchTerm = document.getElementById('indicatorSearch').value.toLowerCase();
    const items = document.querySelectorAll('#availableIndicatorList .indicator-item');

    items.forEach(item => {
        const name = item.querySelector('.indicator-name').textContent.toLowerCase();
        const desc = item.querySelector('.indicator-desc').textContent.toLowerCase();
        const matches = name.includes(searchTerm) || desc.includes(searchTerm);
        item.style.display = matches ? 'flex' : 'none';
    });
}

/**
 * Recalculate all indicators (after data update)
 */
function recalculateIndicators() {
    indicatorState.activeIndicators.forEach(indicator => {
        const chart = state.charts[0];
        const data = calculateIndicator(indicator.type, indicator.settings);

        if (data && indicator.series.length > 0) {
            const definition = indicatorDefinitions[indicator.type];

            if (indicator.type === 'bollinger') {
                indicator.series[0].setData(data.upper);
                indicator.series[1].setData(data.middle);
                indicator.series[2].setData(data.lower);
            } else if (indicator.type === 'macd') {
                indicator.series[0].setData(data.histogram);
                indicator.series[1].setData(data.macd);
                indicator.series[2].setData(data.signal);
            } else {
                indicator.series[0].setData(data);
            }
        }
    });
}

// Initialize indicators when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    setTimeout(initIndicators, 200);
});

// =====================================================
// PANEL RESIZE FUNCTIONS
// =====================================================

/**
 * Initialize panel resize controls
 */
function initPanelResize() {
    console.log('Initializing panel resize controls...');

    // Find all resize buttons
    const buttons = document.querySelectorAll('.resize-btn');
    console.log(`Found ${buttons.length} resize buttons`);

    // Remove any existing click handlers and add new ones
    buttons.forEach((btn) => {
        // Clone button to remove old event listeners
        const newBtn = btn.cloneNode(true);
        btn.parentNode.replaceChild(newBtn, btn);

        newBtn.addEventListener('click', handleResizeButtonClick);
    });

    // Load saved panel states from localStorage
    loadPanelStates();

    // Set default active state for 'default' buttons
    document.querySelectorAll('.resizable-panel').forEach(panel => {
        const currentState = panel.getAttribute('data-state') || 'default';
        const activeBtn = panel.querySelector(`.resize-btn[data-action="${currentState}"]`);
        if (activeBtn) {
            activeBtn.classList.add('active');
        }
    });

    console.log('Panel resize controls initialized');
}

/**
 * Handle resize button click
 */
function handleResizeButtonClick(e) {
    e.preventDefault();
    e.stopPropagation();

    const btn = e.currentTarget;
    const action = btn.getAttribute('data-action');
    const panel = btn.closest('.resizable-panel');

    console.log(`Resize button clicked: action=${action}, panel=${panel?.getAttribute('data-panel')}`);

    if (panel && action) {
        resizePanel(panel, action);
    }
}

/**
 * Resize a panel to specified state
 */
function resizePanel(panel, action) {
    const panelId = panel.getAttribute('data-panel');
    const currentState = panel.getAttribute('data-state') || 'default';

    console.log(`Resizing panel: ${panelId}, current=${currentState}, action=${action}`);

    // If clicking the same state button, return to default
    let newState = action;
    if (currentState === action && action !== 'default') {
        newState = 'default';
    }

    console.log(`New state will be: ${newState}`);

    // Update panel state using setAttribute for better CSS selector compatibility
    panel.setAttribute('data-state', newState);

    // Update active button state
    panel.querySelectorAll('.resize-btn').forEach(btn => {
        const isActive = btn.getAttribute('data-action') === newState;
        btn.classList.toggle('active', isActive);
    });

    // Save state to localStorage
    savePanelState(panelId, newState);

    // Trigger chart resize after panel transition
    setTimeout(() => {
        resizeAllCharts();
    }, 350);

    console.log(`Panel ${panelId} resized to ${newState}, data-state is now: ${panel.getAttribute('data-state')}`);
}

/**
 * Resize all charts after panel resize
 */
function resizeAllCharts() {
    for (let i = 0; i < state.activeCharts; i++) {
        if (state.charts[i]) {
            const container = document.getElementById(`chart-${i}`);
            if (container) {
                const { width, height } = container.getBoundingClientRect();
                if (width > 0 && height > 0) {
                    state.charts[i].applyOptions({ width, height });
                    state.charts[i].timeScale().fitContent();
                }
            }
        }
    }
}

/**
 * Save panel state to localStorage
 */
function savePanelState(panelId, panelState) {
    try {
        const states = JSON.parse(localStorage.getItem('panelStates') || '{}');
        states[panelId] = panelState;
        localStorage.setItem('panelStates', JSON.stringify(states));
    } catch (e) {
        console.warn('Could not save panel state:', e);
    }
}

/**
 * Load panel states from localStorage
 */
function loadPanelStates() {
    try {
        const states = JSON.parse(localStorage.getItem('panelStates') || '{}');
        Object.entries(states).forEach(([panelId, panelState]) => {
            const panel = document.querySelector(`[data-panel="${panelId}"]`);
            if (panel && panelState) {
                panel.setAttribute('data-state', panelState);
                panel.querySelectorAll('.resize-btn').forEach(btn => {
                    btn.classList.toggle('active', btn.getAttribute('data-action') === panelState);
                });
            }
        });
    } catch (e) {
        console.warn('Could not load panel states:', e);
    }
}

// Initialize panel resize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Small delay to ensure all elements are rendered
    setTimeout(() => {
        initPanelResize();
    }, 100);

    // Initialize volume toggle
    initVolumeToggle();
});

/**
 * Initialize Volume Toggle functionality
 */
function initVolumeToggle() {
    const volumeToggle = document.getElementById('volumeToggle');
    if (!volumeToggle) return;

    // Load saved preference
    const savedState = localStorage.getItem('volumeVisible');
    if (savedState !== null) {
        volumeToggle.checked = savedState === 'true';
        if (!volumeToggle.checked) {
            setVolumeVisibility(false);
        }
    }

    volumeToggle.addEventListener('change', (e) => {
        const isVisible = e.target.checked;
        setVolumeVisibility(isVisible);
        localStorage.setItem('volumeVisible', isVisible);
    });
}

/**
 * Set volume series visibility
 */
function setVolumeVisibility(visible) {
    // Handle main volume series
    if (state.volumeSerie) {
        state.volumeSerie.applyOptions({ visible: visible });
    }

    // Handle all volume series in array
    if (state.volumeSeries && state.volumeSeries.length > 0) {
        state.volumeSeries.forEach(series => {
            if (series) {
                series.applyOptions({ visible: visible });
            }
        });
    }
}

// ==================== Go To Date Feature ====================

/**
 * Initialize Go To Date functionality
 */
function initGoToDate() {
    const modal = document.getElementById('goToDateModal');
    const openBtn = document.getElementById('goToDateBtn');
    const closeBtn = document.getElementById('closeGoToModal');
    const cancelBtn = document.getElementById('cancelGoTo');
    const applyBtn = document.getElementById('applyGoTo');
    const dateInput = document.getElementById('gotoDate');
    const timeInput = document.getElementById('gotoTime');
    const tabs = document.querySelectorAll('.goto-tab');
    const presetBtns = document.querySelectorAll('.goto-presets .preset-btn');

    let currentCalendarDate = new Date();
    let selectedDate = new Date();

    // Set default date to today
    const today = new Date();
    dateInput.value = formatDateForInput(today);
    selectedDate = today;

    // Open modal
    openBtn.addEventListener('click', () => {
        modal.classList.add('show');
        renderCalendar(currentCalendarDate);
    });

    // Close modal
    closeBtn.addEventListener('click', () => modal.classList.remove('show'));
    cancelBtn.addEventListener('click', () => modal.classList.remove('show'));

    // Close on overlay click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.classList.remove('show');
    });

    // Tab switching
    tabs.forEach(tab => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            document.getElementById('gotoDateTab').classList.toggle('hidden', tab.dataset.tab !== 'date');
            document.getElementById('gotoRangeTab').classList.toggle('hidden', tab.dataset.tab !== 'range');
        });
    });

    // Calendar navigation
    document.getElementById('calendarPrev').addEventListener('click', () => {
        currentCalendarDate.setMonth(currentCalendarDate.getMonth() - 1);
        renderCalendar(currentCalendarDate);
    });

    document.getElementById('calendarNext').addEventListener('click', () => {
        currentCalendarDate.setMonth(currentCalendarDate.getMonth() + 1);
        renderCalendar(currentCalendarDate);
    });

    // Date input change
    dateInput.addEventListener('change', () => {
        if (dateInput.value) {
            selectedDate = new Date(dateInput.value + 'T' + (timeInput.value || '00:00'));
            currentCalendarDate = new Date(selectedDate);
            renderCalendar(currentCalendarDate);
        }
    });

    // Preset buttons
    presetBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const preset = btn.dataset.preset;
            const now = new Date();

            switch(preset) {
                case 'today':
                    selectedDate = now;
                    break;
                case '1w':
                    selectedDate = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
                    break;
                case '1m':
                    selectedDate = new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
                    break;
                case '3m':
                    selectedDate = new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
                    break;
                case '6m':
                    selectedDate = new Date(now.getFullYear(), now.getMonth() - 6, now.getDate());
                    break;
                case '1y':
                    selectedDate = new Date(now.getFullYear() - 1, now.getMonth(), now.getDate());
                    break;
            }

            dateInput.value = formatDateForInput(selectedDate);
            currentCalendarDate = new Date(selectedDate);
            renderCalendar(currentCalendarDate);
        });
    });

    // Apply - navigate chart to selected date
    applyBtn.addEventListener('click', () => {
        const dateStr = dateInput.value;
        const timeStr = timeInput.value || '00:00';

        if (!dateStr) {
            console.warn('No date selected');
            return;
        }

        const targetDate = new Date(dateStr + 'T' + timeStr);
        navigateChartToDate(targetDate);
        modal.classList.remove('show');
    });

    // Render calendar
    function renderCalendar(date) {
        const year = date.getFullYear();
        const month = date.getMonth();

        // Update header
        const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                          'July', 'August', 'September', 'October', 'November', 'December'];
        document.getElementById('calendarMonth').textContent = `${monthNames[month]} ${year}`;

        // Get first day of month and total days
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const startingDay = (firstDay.getDay() + 6) % 7; // Monday = 0
        const totalDays = lastDay.getDate();

        // Get previous month's last days
        const prevLastDay = new Date(year, month, 0).getDate();

        const calendarDays = document.getElementById('calendarDays');
        calendarDays.innerHTML = '';

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        // Previous month days
        for (let i = startingDay - 1; i >= 0; i--) {
            const day = document.createElement('div');
            day.className = 'calendar-day other-month';
            day.textContent = prevLastDay - i;
            day.addEventListener('click', () => {
                const newDate = new Date(year, month - 1, prevLastDay - i);
                selectCalendarDate(newDate);
            });
            calendarDays.appendChild(day);
        }

        // Current month days
        for (let i = 1; i <= totalDays; i++) {
            const day = document.createElement('div');
            day.className = 'calendar-day';
            day.textContent = i;

            const dayDate = new Date(year, month, i);
            dayDate.setHours(0, 0, 0, 0);

            // Mark today
            if (dayDate.getTime() === today.getTime()) {
                day.classList.add('today');
            }

            // Mark selected
            const selectedDateNorm = new Date(selectedDate);
            selectedDateNorm.setHours(0, 0, 0, 0);
            if (dayDate.getTime() === selectedDateNorm.getTime()) {
                day.classList.add('selected');
            }

            // Disable future dates
            if (dayDate > today) {
                day.classList.add('disabled');
            } else {
                day.addEventListener('click', () => selectCalendarDate(dayDate));
            }

            calendarDays.appendChild(day);
        }

        // Next month days (fill remaining)
        const remainingDays = 42 - (startingDay + totalDays);
        for (let i = 1; i <= remainingDays; i++) {
            const day = document.createElement('div');
            day.className = 'calendar-day other-month';
            day.textContent = i;
            day.addEventListener('click', () => {
                const newDate = new Date(year, month + 1, i);
                selectCalendarDate(newDate);
            });
            calendarDays.appendChild(day);
        }
    }

    function selectCalendarDate(date) {
        selectedDate = date;
        dateInput.value = formatDateForInput(date);
        currentCalendarDate = new Date(date);
        renderCalendar(currentCalendarDate);
    }

    function formatDateForInput(date) {
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }
}

/**
 * Navigate chart to a specific date
 */
async function navigateChartToDate(targetDate) {
    const chart = state.charts[0];
    if (!chart) {
        console.warn('No chart available');
        return;
    }

    const targetTimestamp = Math.floor(targetDate.getTime() / 1000);
    const candleData = state.candleData[0];

    if (!candleData || candleData.length === 0) {
        console.warn('No candle data available');
        return;
    }

    // Check if we have data for this date
    const oldestCandle = candleData[0];
    const newestCandle = candleData[candleData.length - 1];

    console.log(`[GoTo] Navigating to ${targetDate.toISOString()}`);
    console.log(`[GoTo] Current data range: ${new Date(oldestCandle.time * 1000).toISOString()} to ${new Date(newestCandle.time * 1000).toISOString()}`);

    // If target is older than our oldest data, we need to fetch more
    if (targetTimestamp < oldestCandle.time) {
        console.log('[GoTo] Target date is older than available data, fetching historical data...');

        // Show loading indicator
        const loadingMsg = document.createElement('div');
        loadingMsg.id = 'gotoLoading';
        loadingMsg.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);background:var(--bg-card);padding:20px 40px;border-radius:8px;z-index:10000;color:var(--text-primary);';
        loadingMsg.textContent = 'Loading historical data...';
        document.body.appendChild(loadingMsg);

        try {
            // Fetch data for the target date range
            // We'll fetch from the target date up to our current oldest
            const response = await fetch(
                `/api/candles/${encodeURIComponent(state.symbol)}?timeframe=${state.timeframe}&limit=1000&before=${oldestCandle.time}`
            );

            if (!response.ok) throw new Error('Failed to fetch historical data');

            const data = await response.json();

            if (data.candles && data.candles.length > 0) {
                // Process and prepend candles
                const newCandles = data.candles.map(c => ({
                    time: c.time,
                    open: c.open,
                    high: c.high,
                    low: c.low,
                    close: c.close
                })).sort((a, b) => a.time - b.time);

                // Filter out duplicates
                const existingTimes = new Set(candleData.map(c => c.time));
                const uniqueNewCandles = newCandles.filter(c => !existingTimes.has(c.time));

                if (uniqueNewCandles.length > 0) {
                    // Prepend new candles
                    state.candleData[0] = [...uniqueNewCandles, ...candleData];
                    state.candleSeries[0].setData(state.candleData[0]);
                    console.log(`[GoTo] Added ${uniqueNewCandles.length} historical candles`);
                }
            }
        } catch (error) {
            console.error('[GoTo] Error fetching historical data:', error);
        } finally {
            loadingMsg.remove();
        }
    }

    // Now scroll to the target date
    // Find the closest candle to the target timestamp
    const updatedCandleData = state.candleData[0];
    let closestIndex = 0;
    let closestDiff = Infinity;

    for (let i = 0; i < updatedCandleData.length; i++) {
        const diff = Math.abs(updatedCandleData[i].time - targetTimestamp);
        if (diff < closestDiff) {
            closestDiff = diff;
            closestIndex = i;
        }
    }

    console.log(`[GoTo] Closest candle index: ${closestIndex}, timestamp: ${new Date(updatedCandleData[closestIndex].time * 1000).toISOString()}`);

    // Calculate visible range (show ~50 bars centered on target)
    const visibleBars = 50;
    const fromIndex = Math.max(0, closestIndex - Math.floor(visibleBars / 2));
    const toIndex = Math.min(updatedCandleData.length - 1, closestIndex + Math.floor(visibleBars / 2));

    const fromTime = updatedCandleData[fromIndex].time;
    const toTime = updatedCandleData[toIndex].time;

    // Set visible range
    chart.timeScale().setVisibleRange({
        from: fromTime,
        to: toTime
    });

    console.log(`[GoTo] Set visible range: ${new Date(fromTime * 1000).toISOString()} to ${new Date(toTime * 1000).toISOString()}`);
}

// ================== PYTHON INDICATOR RENDERING ==================

// Store active Python indicator drawings
const pythonIndicatorState = {
    lineSeries: [],   // Line series for drawing lines
    priceLines: [],   // Price lines for horizontal lines
    markers: [],      // Chart markers for labels
};

// Render Python indicator on chart
function renderPythonIndicator(data) {
    if (!data || !data.drawings) {
        console.warn('No drawing data in Python indicator response');
        return;
    }

    console.log(`Rendering Python indicator: ${data.name}`);
    console.log(`Lines: ${data.drawings.lines?.length || 0}, Boxes: ${data.drawings.boxes?.length || 0}, Labels: ${data.drawings.labels?.length || 0}`);

    const chart = state.chart;
    const candleSeries = state.candleSerie;

    if (!chart || !candleSeries) {
        console.error('Chart not initialized');
        return;
    }

    // Clear previous Python indicator drawings
    clearPythonIndicatorDrawings();

    // Draw all lines (including horizontal) as line series with specific time bounds
    const lines = data.drawings.lines || [];

    lines.forEach(line => {
        // Skip lines with null/undefined values
        if (line.x1 == null || line.y1 == null || line.x2 == null || line.y2 == null) {
            console.warn('Skipping line with null values:', line);
            return;
        }

        try {
            const lineColor = line.color || '#808080';
            const lineWidth = line.width || 1;
            const lineStyle = line.style || 'solid';

            // Create a line series for each line segment
            const lineSeries = chart.addLineSeries({
                color: lineColor,
                lineWidth: lineWidth,
                lineStyle: getLineStyle(lineStyle),
                priceLineVisible: false,
                lastValueVisible: false,
                crosshairMarkerVisible: false,
                // Don't show price scale for indicator lines
                priceScaleId: '',
            });

            // Set data with two points
            lineSeries.setData([
                { time: line.x1, value: line.y1 },
                { time: line.x2, value: line.y2 }
            ]);

            pythonIndicatorState.lineSeries.push(lineSeries);
        } catch (e) {
            console.error('Error drawing line:', e, line);
        }
    });

    // Draw boxes as 4 line series (top, bottom, left, right) + area fill
    const boxes = data.drawings.boxes || [];
    boxes.forEach(box => {
        // Skip boxes with null/undefined values
        if (box.x1 == null || box.y1 == null || box.x2 == null || box.y2 == null) {
            console.warn('Skipping box with null values:', box);
            return;
        }

        try {
        const boxColor = box.border_color || '#808080';
        const boxWidth = box.border_width || 1;
        const bgColor = box.background_color || 'rgba(128, 128, 128, 0.2)';

        // Create area series for box fill
        const areaSeries = chart.addAreaSeries({
            topColor: bgColor,
            bottomColor: bgColor,
            lineColor: 'transparent',
            lineWidth: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            priceScaleId: '',
        });

        // Fill the box area - need multiple points for the rectangle
        const boxData = [
            { time: box.x1, value: box.y1 },
            { time: box.x2, value: box.y1 },
        ];
        // Area series fills down to lineBase, so we set it to box bottom
        areaSeries.applyOptions({
            baseValue: { type: 'price', price: box.y2 }
        });
        areaSeries.setData(boxData);
        pythonIndicatorState.lineSeries.push(areaSeries);

        // Top line
        const topLine = chart.addLineSeries({
            color: boxColor,
            lineWidth: boxWidth,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            priceScaleId: '',
        });
        topLine.setData([
            { time: box.x1, value: box.y1 },
            { time: box.x2, value: box.y1 }
        ]);
        pythonIndicatorState.lineSeries.push(topLine);

        // Bottom line
        const bottomLine = chart.addLineSeries({
            color: boxColor,
            lineWidth: boxWidth,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            priceScaleId: '',
        });
        bottomLine.setData([
            { time: box.x1, value: box.y2 },
            { time: box.x2, value: box.y2 }
        ]);
        pythonIndicatorState.lineSeries.push(bottomLine);

        // Left line
        const leftLine = chart.addLineSeries({
            color: boxColor,
            lineWidth: boxWidth,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            priceScaleId: '',
        });
        leftLine.setData([
            { time: box.x1, value: box.y1 },
            { time: box.x1, value: box.y2 }
        ]);
        pythonIndicatorState.lineSeries.push(leftLine);

        // Right line
        const rightLine = chart.addLineSeries({
            color: boxColor,
            lineWidth: boxWidth,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
            priceScaleId: '',
        });
        rightLine.setData([
            { time: box.x2, value: box.y1 },
            { time: box.x2, value: box.y2 }
        ]);
        pythonIndicatorState.lineSeries.push(rightLine);
        } catch (e) {
            console.error('Error drawing box:', e, box);
        }
    });

    // Draw hlines (full-width horizontal lines) - these use priceLine
    const hlines = data.drawings.hlines || [];
    hlines.forEach(hline => {
        // Skip hlines with null/undefined values
        if (hline.y == null) {
            console.warn('Skipping hline with null value:', hline);
            return;
        }

        try {
        const priceLine = candleSeries.createPriceLine({
            price: hline.y,
            color: hline.color || '#808080',
            lineWidth: hline.width || 1,
            lineStyle: getLineStyle(hline.style),
            axisLabelVisible: true,
            title: hline.label || '',
        });
        pythonIndicatorState.priceLines.push(priceLine);
        } catch (e) {
            console.error('Error drawing hline:', e, hline);
        }
    });

    // Draw labels as markers
    const labels = data.drawings.labels || [];
    if (labels.length > 0) {
        const markers = labels.map(label => ({
            time: label.x,
            position: label.position === 'below' ? 'belowBar' : 'aboveBar',
            color: label.color || '#808080',
            shape: 'text',
            text: label.text,
        }));
        candleSeries.setMarkers(markers);
        pythonIndicatorState.markers = markers;
    }

    console.log(`Python indicator rendered: ${pythonIndicatorState.lineSeries.length} line series, ${pythonIndicatorState.priceLines.length} price lines`);
}

// Clear Python indicator drawings
function clearPythonIndicatorDrawings() {
    const chart = state.chart;
    const candleSeries = state.candleSerie;

    // Remove price lines
    pythonIndicatorState.priceLines.forEach(priceLine => {
        try {
            candleSeries.removePriceLine(priceLine);
        } catch (e) {
            // Price line might already be removed
        }
    });
    pythonIndicatorState.priceLines = [];

    // Remove line series
    pythonIndicatorState.lineSeries.forEach(series => {
        try {
            chart.removeSeries(series);
        } catch (e) {
            // Series might already be removed
        }
    });
    pythonIndicatorState.lineSeries = [];

    // Clear markers
    if (pythonIndicatorState.markers.length > 0) {
        candleSeries.setMarkers([]);
        pythonIndicatorState.markers = [];
    }
}

// Convert style string to Lightweight Charts LineStyle
function getLineStyle(style) {
    switch (style) {
        case 'dashed':
            return LightweightCharts.LineStyle.Dashed;
        case 'dotted':
            return LightweightCharts.LineStyle.Dotted;
        case 'solid':
        default:
            return LightweightCharts.LineStyle.Solid;
    }
}

// Export to global scope
window.renderPythonIndicator = renderPythonIndicator;
window.clearPythonIndicatorDrawings = clearPythonIndicatorDrawings;
