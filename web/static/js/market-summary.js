/**
 * Market Summary - Display performance stats, global data, and AI-powered analysis
 */

const MarketSummary = {
    isVisible: false,
    currentSymbol: 'BTC/USD',

    // Store data for analysis
    analysisData: {
        periods: {},
        globalStats: null,
        currentPrice: 0
    },

    // CoinGecko ID mapping for popular coins
    coinGeckoIds: {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'XRP': 'ripple',
        'SOL': 'solana',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'DOT': 'polkadot',
        'MATIC': 'matic-network',
        'LINK': 'chainlink',
        'AVAX': 'avalanche-2',
        'LTC': 'litecoin',
        'SHIB': 'shiba-inu',
        'TRX': 'tron',
        'ATOM': 'cosmos',
        'UNI': 'uniswap',
        'XLM': 'stellar',
        'BCH': 'bitcoin-cash',
        'NEAR': 'near',
        'APT': 'aptos',
        'FIL': 'filecoin',
        'ARB': 'arbitrum',
        'OP': 'optimism',
        'PEPE': 'pepe',
        'AAVE': 'aave',
        'MKR': 'maker',
        'CRV': 'curve-dao-token',
        'SAND': 'the-sandbox',
        'MANA': 'decentraland',
        'AXS': 'axie-infinity',
        'GRT': 'the-graph',
        'IMX': 'immutable-x',
        'INJ': 'injective-protocol',
        'SUI': 'sui',
        'SEI': 'sei-network',
        'TIA': 'celestia',
        'WLD': 'worldcoin-wld',
        'BONK': 'bonk',
        'WIF': 'dogwifcoin',
        'FLOKI': 'floki',
        'XMR': 'monero',
        'ZEC': 'zcash'
    },

    /**
     * Initialize market summary
     */
    init() {
        this.bindEvents();
    },

    /**
     * Bind event listeners
     */
    bindEvents() {
        const summaryBtn = document.getElementById('marketSummaryBtn');
        const closeBtn = document.getElementById('closeSummaryBtn');

        if (summaryBtn) {
            summaryBtn.addEventListener('click', () => this.toggle());
        }

        if (closeBtn) {
            closeBtn.addEventListener('click', () => this.hide());
        }
    },

    /**
     * Toggle market summary visibility
     */
    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    },

    /**
     * Show market summary panel
     */
    show() {
        const panel = document.getElementById('marketSummaryPanel');
        const chartWrapper = document.getElementById('multiChartWrapper');
        const btn = document.getElementById('marketSummaryBtn');

        if (panel && chartWrapper) {
            panel.style.display = 'block';
            chartWrapper.style.display = 'none';
            this.isVisible = true;
            btn?.classList.add('active');

            // Get current symbol from state
            if (window.state && window.state.symbol) {
                this.currentSymbol = window.state.symbol;
            }

            // Reset analysis data
            this.analysisData = { periods: {}, globalStats: null, currentPrice: 0 };

            // Load data
            this.loadAllData();
        }
    },

    /**
     * Hide market summary panel
     */
    hide() {
        const panel = document.getElementById('marketSummaryPanel');
        const chartWrapper = document.getElementById('multiChartWrapper');
        const btn = document.getElementById('marketSummaryBtn');

        if (panel && chartWrapper) {
            panel.style.display = 'none';
            chartWrapper.style.display = '';
            this.isVisible = false;
            btn?.classList.remove('active');
        }
    },

    /**
     * Load all market data
     */
    async loadAllData() {
        await Promise.all([
            this.loadPerformanceData(),
            this.loadGlobalStats(),
            this.loadAggressorRatio(),
            this.loadTechnicalAnalysis()
        ]);

        // Run analysis after data is loaded
        this.runAnalysis();
    },

    /**
     * Load technical analysis data
     */
    async loadTechnicalAnalysis() {
        try {
            const response = await fetch(`/api/technical-analysis/${encodeURIComponent(this.currentSymbol)}?timeframe=1h`);
            if (!response.ok) throw new Error('Failed to fetch technical analysis');

            const data = await response.json();
            if (data.error) {
                console.warn('Technical analysis error:', data.error);
                return;
            }

            // Store for AI analysis
            this.analysisData.technicalAnalysis = data;

            // Update UI
            this.updateTechnicalAnalysisUI(data);

        } catch (e) {
            console.error('Error loading technical analysis:', e);
        }
    },

    /**
     * Update technical analysis UI
     */
    updateTechnicalAnalysisUI(data) {
        // Update overall signal
        const signalEl = document.getElementById('taOverallSignal');
        if (signalEl) {
            signalEl.textContent = data.overall_signal;
            signalEl.className = 'ta-strength-signal ' + data.overall_signal.toLowerCase().replace(' ', '-');
        }

        // Update strength bar
        const total = data.summary.overall.buy + data.summary.overall.sell + data.summary.overall.neutral;
        if (total > 0) {
            const sellPct = (data.summary.overall.sell / total) * 100;
            const neutralPct = (data.summary.overall.neutral / total) * 100;
            const buyPct = (data.summary.overall.buy / total) * 100;

            document.getElementById('taSellBar').style.width = `${sellPct}%`;
            document.getElementById('taNeutralBar').style.width = `${neutralPct}%`;
            document.getElementById('taBuyBar').style.width = `${buyPct}%`;
        }

        // Update counts
        document.getElementById('taSellCount').textContent = `${data.summary.overall.sell} Sell`;
        document.getElementById('taNeutralCount').textContent = `${data.summary.overall.neutral} Neutral`;
        document.getElementById('taBuyCount').textContent = `${data.summary.overall.buy} Buy`;

        // Update oscillators summary
        const oscSummary = document.getElementById('taOscSummary');
        if (oscSummary) {
            const osc = data.summary.oscillators;
            oscSummary.textContent = `${osc.buy} Buy / ${osc.neutral} Neutral / ${osc.sell} Sell`;
        }

        // Update MA summary
        const maSummary = document.getElementById('taMASummary');
        if (maSummary) {
            const ma = data.summary.moving_averages;
            maSummary.textContent = `${ma.buy} Buy / ${ma.neutral} Neutral / ${ma.sell} Sell`;
        }

        // Populate oscillators table
        const oscBody = document.getElementById('taOscillators');
        if (oscBody && data.oscillators) {
            oscBody.innerHTML = data.oscillators.map(osc => `
                <tr>
                    <td>${osc.name}</td>
                    <td>${osc.value !== null ? osc.value.toLocaleString() : '--'}</td>
                    <td>
                        ${osc.signal}
                        <span class="ta-signal-dot ${osc.signal.toLowerCase()}"></span>
                    </td>
                </tr>
            `).join('');
        }

        // Populate moving averages table
        const maBody = document.getElementById('taMovingAverages');
        if (maBody && data.moving_averages) {
            maBody.innerHTML = data.moving_averages.map(ma => `
                <tr>
                    <td>${ma.name}</td>
                    <td>${ma.value !== null ? ma.value.toLocaleString() : '--'}</td>
                    <td>
                        ${ma.signal}
                        <span class="ta-signal-dot ${ma.signal.toLowerCase()}"></span>
                    </td>
                </tr>
            `).join('');
        }

        // Update key levels
        if (data.key_levels) {
            this.setElementText('taResistance2', `$${data.key_levels.resistance_2.toLocaleString()}`);
            this.setElementText('taResistance1', `$${data.key_levels.resistance_1.toLocaleString()}`);
            this.setElementText('taCurrentPrice', `$${data.key_levels.current_price.toLocaleString()}`);
            this.setElementText('taSupport1', `$${data.key_levels.support_1.toLocaleString()}`);
            this.setElementText('taSupport2', `$${data.key_levels.support_2.toLocaleString()}`);

            this.setElementText('taSMA20', data.key_levels.sma_20 ? `$${data.key_levels.sma_20.toLocaleString()}` : '--');
            this.setElementText('taSMA50', data.key_levels.sma_50 ? `$${data.key_levels.sma_50.toLocaleString()}` : '--');
            this.setElementText('taSMA200', data.key_levels.sma_200 ? `$${data.key_levels.sma_200.toLocaleString()}` : '--');
            this.setElementText('taATR', data.key_levels.atr ? `$${data.key_levels.atr.toLocaleString()}` : '--');
        }
    },

    /**
     * Toggle technical analysis accordion section
     */
    toggleTASection(section) {
        const item = section === 'oscillators'
            ? document.getElementById('taOscContent').parentElement
            : document.getElementById('taMAContent').parentElement;

        if (item) {
            item.classList.toggle('open');
        }
    },

    /**
     * Load aggressor ratio data
     */
    async loadAggressorRatio() {
        try {
            const response = await fetch(`/api/aggressor-ratio/${encodeURIComponent(this.currentSymbol)}?limit=500`);
            if (!response.ok) throw new Error('Failed to fetch aggressor ratio');

            const data = await response.json();
            if (data.error) {
                console.warn('Aggressor ratio error:', data.error);
                return;
            }

            // Store for analysis
            this.analysisData.aggressorRatio = data;

            // Update UI
            this.updateAggressorRatioUI(data);

        } catch (e) {
            console.error('Error loading aggressor ratio:', e);
        }
    },

    /**
     * Update aggressor ratio UI
     */
    updateAggressorRatioUI(data) {
        // Update sentiment badge
        const sentimentBadge = document.querySelector('.sentiment-badge');
        const sentimentText = document.getElementById('aggressorSentimentText');
        const sentimentStrength = document.getElementById('aggressorStrength');

        if (sentimentBadge && sentimentText) {
            sentimentBadge.className = 'sentiment-badge ' + data.sentiment.toLowerCase();
            sentimentText.textContent = data.sentiment;

            // Update sentiment icon
            const icon = sentimentBadge.querySelector('.sentiment-icon');
            if (icon) {
                if (data.sentiment === 'BULLISH') icon.textContent = '📈';
                else if (data.sentiment === 'BEARISH') icon.textContent = '📉';
                else icon.textContent = '⚖️';
            }
        }

        if (sentimentStrength) {
            sentimentStrength.textContent = `Strength: ${data.sentiment_strength}%`;
        }

        // Update ratio bar
        const buyBar = document.getElementById('aggressorBuyBar');
        const sellBar = document.getElementById('aggressorSellBar');
        const buyPct = document.getElementById('aggressorBuyPct');
        const sellPct = document.getElementById('aggressorSellPct');

        if (buyBar && sellBar) {
            buyBar.style.width = `${data.buy_vol_pct}%`;
            sellBar.style.width = `${data.sell_vol_pct}%`;
        }

        if (buyPct) buyPct.textContent = `${data.buy_vol_pct}%`;
        if (sellPct) sellPct.textContent = `${data.sell_vol_pct}%`;

        // Update metrics
        this.setElementText('aggressorVolumeRatio', data.volume_ratio ? data.volume_ratio.toFixed(3) : '--');
        this.setElementText('aggressorBuyVolume', this.formatVolume(data.buy_volume));
        this.setElementText('aggressorSellVolume', this.formatVolume(data.sell_volume));
        this.setElementText('aggressorTotalTrades', data.total_trades.toLocaleString());
        this.setElementText('aggressorTimeSpan', `${data.time_span_minutes} min`);
        this.setElementText('aggressorAvgBuySize', this.formatVolume(data.avg_buy_size));
        this.setElementText('aggressorAvgSellSize', this.formatVolume(data.avg_sell_size));

        // Generate insights
        this.generateAggressorInsights(data);

        // Generate correlations
        this.generateAggressorCorrelations(data);
    },

    /**
     * Generate dynamic insights based on aggressor data
     */
    generateAggressorInsights(data) {
        const insightsList = document.getElementById('aggressorInsights');
        if (!insightsList) return;

        const insights = [];

        // Volume ratio insight
        if (data.volume_ratio > 1.5) {
            insights.push({
                text: `Strong buying pressure detected. Buy volume is ${data.volume_ratio.toFixed(2)}x higher than sell volume.`,
                class: 'bullish'
            });
        } else if (data.volume_ratio < 0.67) {
            insights.push({
                text: `Strong selling pressure detected. Sell volume is ${(1/data.volume_ratio).toFixed(2)}x higher than buy volume.`,
                class: 'bearish'
            });
        } else {
            insights.push({
                text: `Market is relatively balanced with a ${data.volume_ratio.toFixed(2)} buy/sell ratio.`,
                class: ''
            });
        }

        // Trade size insight
        if (data.avg_buy_size > data.avg_sell_size * 1.3) {
            insights.push({
                text: `Larger buy orders detected (avg ${this.formatVolume(data.avg_buy_size)} vs ${this.formatVolume(data.avg_sell_size)} sells). May indicate institutional buying.`,
                class: 'bullish'
            });
        } else if (data.avg_sell_size > data.avg_buy_size * 1.3) {
            insights.push({
                text: `Larger sell orders detected (avg ${this.formatVolume(data.avg_sell_size)} vs ${this.formatVolume(data.avg_buy_size)} buys). May indicate institutional selling.`,
                class: 'bearish'
            });
        }

        // Trade count vs volume divergence
        const countRatio = data.buy_count / data.sell_count;
        if (data.volume_ratio > 1.2 && countRatio < 0.9) {
            insights.push({
                text: `Divergence: Fewer but larger buy orders. Suggests whale accumulation.`,
                class: 'bullish'
            });
        } else if (data.volume_ratio < 0.8 && countRatio > 1.1) {
            insights.push({
                text: `Divergence: More but smaller buy orders vs fewer larger sells. Smart money may be distributing.`,
                class: 'bearish'
            });
        }

        // Activity insight
        const tradesPerMinute = data.total_trades / Math.max(data.time_span_minutes, 1);
        if (tradesPerMinute > 10) {
            insights.push({
                text: `High trading activity: ${tradesPerMinute.toFixed(1)} trades/minute. Increased volatility likely.`,
                class: ''
            });
        } else if (tradesPerMinute < 2) {
            insights.push({
                text: `Low trading activity: ${tradesPerMinute.toFixed(1)} trades/minute. Market may be consolidating.`,
                class: ''
            });
        }

        // Render insights
        insightsList.innerHTML = insights.map(i =>
            `<li class="${i.class}">${i.text}</li>`
        ).join('');
    },

    /**
     * Generate intelligent correlation and divergence analysis
     */
    generateAggressorCorrelations(data) {
        const correlationPanel = document.getElementById('aggressorCorrelations');
        if (!correlationPanel) return;

        let html = '';
        const aggressorSignal = data.sentiment; // BULLISH, BEARISH, NEUTRAL
        const marketSignal = this.analysisData.overallAnalysis?.signal; // BULLISH, BEARISH, NEUTRAL
        const marketConfidence = this.analysisData.overallAnalysis?.confidence || 0;

        // Determine if there's a divergence
        const isDivergence = (aggressorSignal === 'BULLISH' && marketSignal === 'BEARISH') ||
                            (aggressorSignal === 'BEARISH' && marketSignal === 'BULLISH');
        const isAligned = (aggressorSignal === 'BULLISH' && marketSignal === 'BULLISH') ||
                         (aggressorSignal === 'BEARISH' && marketSignal === 'BEARISH');

        // Build analysis HTML
        if (isDivergence && marketSignal) {
            // DIVERGENCE DETECTED - Provide detailed analysis
            html += `<div class="correlation-alert divergence">`;
            html += `<div class="alert-header">⚠️ <strong>SIGNAL DIVERGENCE DETECTED</strong></div>`;
            html += `<div class="alert-summary">`;
            html += `<span class="signal-badge ${aggressorSignal.toLowerCase()}">Aggressor: ${aggressorSignal}</span>`;
            html += `<span class="vs">vs</span>`;
            html += `<span class="signal-badge ${marketSignal.toLowerCase()}">Market: ${marketSignal}</span>`;
            html += `</div>`;

            if (aggressorSignal === 'BULLISH' && marketSignal === 'BEARISH') {
                // Bullish buying into bearish trend
                html += `<div class="divergence-analysis">`;
                html += `<h5>🔍 What This Means:</h5>`;
                html += `<p>Strong buying pressure (${data.buy_vol_pct.toFixed(1)}% buy volume) is occurring despite a bearish market structure. This is a significant signal.</p>`;

                html += `<h5>📊 Possible Interpretations:</h5>`;
                html += `<ul>`;
                html += `<li><strong>Potential Reversal:</strong> Smart money may be accumulating at lower prices, anticipating a trend change.</li>`;
                html += `<li><strong>Short Covering:</strong> Bears closing positions, creating temporary buying pressure that may exhaust.</li>`;
                html += `<li><strong>Bull Trap:</strong> Bear market rally that could fail - watch for resistance levels.</li>`;
                html += `<li><strong>Accumulation Phase:</strong> Institutions buying while retail remains fearful.</li>`;
                html += `</ul>`;

                html += `<h5>🎯 Actionable Insights:</h5>`;
                html += `<ul class="action-list">`;
                if (data.volume_ratio > 5) {
                    html += `<li class="bullish">Extreme buying (${data.volume_ratio.toFixed(1)}x ratio) - High probability of at least a short-term bounce</li>`;
                }
                if (data.avg_buy_size > data.avg_sell_size * 1.5) {
                    html += `<li class="bullish">Large buy orders suggest institutional interest, not just retail</li>`;
                }
                html += `<li>Watch for price to break above recent resistance to confirm reversal</li>`;
                html += `<li>If price fails to rise despite buying, distribution may be occurring</li>`;
                html += `</ul>`;
                html += `</div>`;

            } else if (aggressorSignal === 'BEARISH' && marketSignal === 'BULLISH') {
                // Bearish selling into bullish trend
                html += `<div class="divergence-analysis">`;
                html += `<h5>🔍 What This Means:</h5>`;
                html += `<p>Heavy selling pressure (${data.sell_vol_pct.toFixed(1)}% sell volume) despite a bullish market structure. This warrants caution.</p>`;

                html += `<h5>📊 Possible Interpretations:</h5>`;
                html += `<ul>`;
                html += `<li><strong>Distribution Phase:</strong> Smart money may be selling into strength, taking profits.</li>`;
                html += `<li><strong>Potential Top:</strong> Heavy selling at highs often precedes reversals.</li>`;
                html += `<li><strong>Healthy Correction:</strong> Profit-taking in a bull trend - may be a buying opportunity.</li>`;
                html += `<li><strong>Bear Trap:</strong> Could be stop-hunting before continuation higher.</li>`;
                html += `</ul>`;

                html += `<h5>🎯 Actionable Insights:</h5>`;
                html += `<ul class="action-list">`;
                if (data.volume_ratio < 0.3) {
                    html += `<li class="bearish">Extreme selling (${(1/data.volume_ratio).toFixed(1)}x sell ratio) - Consider reducing exposure</li>`;
                }
                if (data.avg_sell_size > data.avg_buy_size * 1.5) {
                    html += `<li class="bearish">Large sell orders suggest institutional distribution</li>`;
                }
                html += `<li>Watch for support levels - breakdown confirms bearish divergence</li>`;
                html += `<li>If price holds support despite selling, trend may continue</li>`;
                html += `</ul>`;
                html += `</div>`;
            }
            html += `</div>`;

        } else if (isAligned && marketSignal) {
            // ALIGNED - Confirm the trend
            html += `<div class="correlation-alert aligned">`;
            html += `<div class="alert-header">✅ <strong>SIGNALS ALIGNED</strong></div>`;
            html += `<div class="alert-summary">`;
            html += `<span class="signal-badge ${aggressorSignal.toLowerCase()}">${aggressorSignal}</span>`;
            html += `<span class="match">matches</span>`;
            html += `<span class="signal-badge ${marketSignal.toLowerCase()}">${marketSignal}</span>`;
            html += `</div>`;

            html += `<div class="aligned-analysis">`;
            if (aggressorSignal === 'BULLISH') {
                html += `<p><strong>Strong Bullish Confluence:</strong> Both real-time order flow and technical analysis agree. `;
                html += `Buy volume at ${data.buy_vol_pct.toFixed(1)}% confirms the uptrend. Higher probability setup for long positions.</p>`;
                html += `<ul class="action-list">`;
                html += `<li class="bullish">Trend + Flow aligned - Consider buying on pullbacks</li>`;
                html += `<li>Use market analysis confidence (${marketConfidence.toFixed(0)}%) to size positions</li>`;
                html += `</ul>`;
            } else {
                html += `<p><strong>Strong Bearish Confluence:</strong> Both real-time order flow and technical analysis agree. `;
                html += `Sell volume at ${data.sell_vol_pct.toFixed(1)}% confirms the downtrend. Avoid long positions or consider shorts.</p>`;
                html += `<ul class="action-list">`;
                html += `<li class="bearish">Trend + Flow aligned - Avoid buying, consider shorts or cash</li>`;
                html += `<li>Use market analysis confidence (${marketConfidence.toFixed(0)}%) to size positions</li>`;
                html += `</ul>`;
            }
            html += `</div>`;
            html += `</div>`;

        } else {
            // No clear comparison available
            html += `<div class="correlation-info">`;

            // Show price trend correlation
            if (this.analysisData.periods['24h']) {
                const priceChange = this.analysisData.periods['24h'].change;
                if (data.sentiment === 'BULLISH' && priceChange < 0) {
                    html += `<p><strong>Divergence:</strong> Bullish aggression despite ${priceChange.toFixed(2)}% price drop. Watch for reversal.</p>`;
                } else if (data.sentiment === 'BEARISH' && priceChange > 0) {
                    html += `<p><strong>Divergence:</strong> Bearish aggression despite ${priceChange.toFixed(2)}% price rise. Potential top.</p>`;
                } else if (priceChange !== 0) {
                    html += `<p>Price ${priceChange > 0 ? 'up' : 'down'} ${Math.abs(priceChange).toFixed(2)}% aligns with ${data.sentiment.toLowerCase()} aggression.</p>`;
                }
            }

            // Volume conviction
            if (data.volume_ratio > 1.2 && data.total_trades > 200) {
                html += `<p>High conviction buying with ${data.total_trades} trades analyzed.</p>`;
            } else if (data.volume_ratio < 0.8 && data.total_trades > 200) {
                html += `<p>High conviction selling with ${data.total_trades} trades analyzed.</p>`;
            } else if (data.total_trades < 100) {
                html += `<p><strong>Note:</strong> Only ${data.total_trades} trades analyzed. Sample size is small.</p>`;
            }
            html += `</div>`;
        }

        correlationPanel.innerHTML = html || '<p>Waiting for market analysis data...</p>';
    },

    /**
     * Format volume for display
     */
    formatVolume(vol) {
        if (vol >= 1) return vol.toFixed(4);
        if (vol >= 0.01) return vol.toFixed(6);
        return vol.toFixed(8);
    },

    /**
     * Helper to set element text
     */
    setElementText(id, text) {
        const el = document.getElementById(id);
        if (el) el.textContent = text;
    },

    /**
     * Load performance data for all periods
     */
    async loadPerformanceData() {
        const periods = [
            { id: '24h', timeframe: '1h', limit: 24 },
            { id: '1w', timeframe: '4h', limit: 42 },
            { id: '1m', timeframe: '1d', limit: 30 },
            { id: '1y', timeframe: '1d', limit: 365 }
        ];

        for (const period of periods) {
            try {
                const data = await this.fetchCandleData(period.timeframe, period.limit);
                if (data && data.length > 0) {
                    this.updatePerformanceCard(period.id, data);
                    // Store for analysis
                    this.analysisData.periods[period.id] = {
                        candles: data,
                        change: this.calculateChange(data),
                        volatility: this.calculateVolatility(data),
                        trend: this.detectTrend(data)
                    };
                }
            } catch (e) {
                console.error(`Error loading ${period.id} data:`, e);
            }
        }
    },

    /**
     * Fetch candle data from the server
     */
    async fetchCandleData(timeframe, limit) {
        try {
            const response = await fetch(`/api/candles/${encodeURIComponent(this.currentSymbol)}?timeframe=${timeframe}&limit=${limit}`);
            if (!response.ok) throw new Error('Failed to fetch candles');
            const data = await response.json();
            return data.candles || [];
        } catch (e) {
            console.error('Error fetching candle data:', e);
            return [];
        }
    },

    /**
     * Calculate percentage change
     */
    calculateChange(candles) {
        if (!candles || candles.length < 2) return 0;
        const first = candles[0].close;
        const last = candles[candles.length - 1].close;
        return ((last - first) / first) * 100;
    },

    /**
     * Calculate volatility (standard deviation of returns)
     */
    calculateVolatility(candles) {
        if (!candles || candles.length < 2) return 0;

        const returns = [];
        for (let i = 1; i < candles.length; i++) {
            const ret = (candles[i].close - candles[i-1].close) / candles[i-1].close;
            returns.push(ret);
        }

        const mean = returns.reduce((a, b) => a + b, 0) / returns.length;
        const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length;
        return Math.sqrt(variance) * 100;
    },

    /**
     * Detect trend direction
     */
    detectTrend(candles) {
        if (!candles || candles.length < 10) return 'neutral';

        // Use simple linear regression
        const n = candles.length;
        const closes = candles.map(c => c.close);

        let sumX = 0, sumY = 0, sumXY = 0, sumX2 = 0;
        for (let i = 0; i < n; i++) {
            sumX += i;
            sumY += closes[i];
            sumXY += i * closes[i];
            sumX2 += i * i;
        }

        const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
        const avgPrice = sumY / n;
        const normalizedSlope = (slope / avgPrice) * 100;

        if (normalizedSlope > 0.1) return 'bullish';
        if (normalizedSlope < -0.1) return 'bearish';
        return 'neutral';
    },

    /**
     * Update performance card with data
     */
    updatePerformanceCard(periodId, candles) {
        if (!candles || candles.length < 2) return;

        const firstClose = candles[0].close;
        const lastClose = candles[candles.length - 1].close;
        const change = ((lastClose - firstClose) / firstClose) * 100;

        // Store current price
        this.analysisData.currentPrice = lastClose;

        const low = Math.min(...candles.map(c => c.low));
        const high = Math.max(...candles.map(c => c.high));

        // Update change
        const changeEl = document.getElementById(`perf${periodId}Change`);
        if (changeEl) {
            changeEl.textContent = `${change >= 0 ? '+' : ''}${change.toFixed(3)}%`;
            changeEl.className = `perf-change ${change >= 0 ? 'positive' : 'negative'}`;
        }

        // Update range
        const lowEl = document.getElementById(`perf${periodId}Low`);
        const highEl = document.getElementById(`perf${periodId}High`);
        if (lowEl) lowEl.textContent = this.formatPrice(low);
        if (highEl) highEl.textContent = this.formatPrice(high);

        // Draw sparkline
        this.drawSparkline(`sparkline${periodId}`, candles, change >= 0);
    },

    /**
     * Draw sparkline chart
     */
    drawSparkline(canvasId, candles, isPositive) {
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const width = canvas.width;
        const height = canvas.height;

        ctx.clearRect(0, 0, width, height);

        if (candles.length < 2) return;

        const closes = candles.map(c => c.close);
        const min = Math.min(...closes);
        const max = Math.max(...closes);
        const range = max - min || 1;

        const gradient = ctx.createLinearGradient(0, 0, 0, height);
        if (isPositive) {
            gradient.addColorStop(0, 'rgba(38, 166, 154, 0.3)');
            gradient.addColorStop(1, 'rgba(38, 166, 154, 0)');
        } else {
            gradient.addColorStop(0, 'rgba(239, 83, 80, 0.3)');
            gradient.addColorStop(1, 'rgba(239, 83, 80, 0)');
        }

        const stepX = width / (closes.length - 1);

        ctx.beginPath();
        ctx.moveTo(0, height);

        closes.forEach((close, i) => {
            const x = i * stepX;
            const y = height - ((close - min) / range) * (height - 10) - 5;
            ctx.lineTo(x, y);
        });

        ctx.lineTo(width, height);
        ctx.closePath();
        ctx.fillStyle = gradient;
        ctx.fill();

        ctx.beginPath();
        closes.forEach((close, i) => {
            const x = i * stepX;
            const y = height - ((close - min) / range) * (height - 10) - 5;
            if (i === 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });

        ctx.strokeStyle = isPositive ? '#26a69a' : '#ef5350';
        ctx.lineWidth = 1.5;
        ctx.stroke();
    },

    /**
     * Load global stats from CoinGecko
     */
    async loadGlobalStats() {
        const baseSymbol = this.currentSymbol.split('/')[0];
        const coinId = this.coinGeckoIds[baseSymbol];

        if (!coinId) {
            console.log('No CoinGecko ID for', baseSymbol);
            this.setPlaceholderStats();
            return;
        }

        try {
            const response = await fetch(
                `https://api.coingecko.com/api/v3/coins/${coinId}?localization=false&tickers=false&community_data=false&developer_data=false`
            );

            if (!response.ok) throw new Error('CoinGecko API error');

            const data = await response.json();
            this.analysisData.globalStats = data;
            this.updateGlobalStats(data);
        } catch (e) {
            console.error('Error fetching global stats:', e);
            this.setPlaceholderStats();
        }
    },

    /**
     * Update global stats display
     */
    updateGlobalStats(data) {
        const marketData = data.market_data;

        const vol24h = document.getElementById('globalVolume24h');
        if (vol24h && marketData.total_volume?.usd) {
            vol24h.textContent = this.formatLargeNumber(marketData.total_volume.usd) + ' USD';
        }

        const rank = document.getElementById('marketRank');
        if (rank && data.market_cap_rank) {
            rank.textContent = `#${data.market_cap_rank}`;
        }

        const cap = document.getElementById('marketCap');
        if (cap && marketData.market_cap?.usd) {
            cap.textContent = this.formatLargeNumber(marketData.market_cap.usd) + ' USD';
        }

        const globalVol = document.getElementById('globalVolumeTotal');
        if (globalVol && marketData.total_volume?.usd) {
            globalVol.textContent = this.formatLargeNumber(marketData.total_volume.usd) + ' USD';
        }

        const circSupply = document.getElementById('circulatingSupply');
        if (circSupply && marketData.circulating_supply) {
            const symbol = this.currentSymbol.split('/')[0];
            circSupply.textContent = this.formatLargeNumber(marketData.circulating_supply) + ' ' + symbol;
        }

        const maxSupply = document.getElementById('maxSupply');
        if (maxSupply) {
            if (marketData.max_supply) {
                const symbol = this.currentSymbol.split('/')[0];
                maxSupply.textContent = this.formatLargeNumber(marketData.max_supply) + ' ' + symbol;
            } else {
                maxSupply.textContent = 'Unlimited';
            }
        }

        const ath = document.getElementById('allTimeHigh');
        if (ath && marketData.ath?.usd) {
            ath.textContent = this.formatPrice(marketData.ath.usd) + ' USD';
        }

        const atl = document.getElementById('allTimeLow');
        if (atl && marketData.atl?.usd) {
            atl.textContent = this.formatPrice(marketData.atl.usd) + ' USD';
        }
    },

    /**
     * Set placeholder stats when data unavailable
     */
    setPlaceholderStats() {
        const elements = [
            'globalVolume24h', 'marketRank', 'marketCap',
            'globalVolumeTotal', 'circulatingSupply', 'maxSupply',
            'allTimeHigh', 'allTimeLow'
        ];

        elements.forEach(id => {
            const el = document.getElementById(id);
            if (el) el.textContent = '--';
        });
    },

    /**
     * Run comprehensive market analysis
     */
    runAnalysis() {
        const analysis = {
            trend: this.analyzeTrend(),
            momentum: this.analyzeMomentum(),
            volatility: this.analyzeVolatility(),
            volume: this.analyzeVolume(),
            position: this.analyzePosition(),
            mtf: this.analyzeMultiTimeframe()
        };

        // Calculate overall score and recommendation
        const overall = this.calculateOverallScore(analysis);

        // Store overall analysis for cross-referencing with aggressor ratio
        this.analysisData.overallAnalysis = overall;
        this.analysisData.factorAnalysis = analysis;

        // Update UI
        this.updateAnalysisUI(analysis, overall);
        this.updateInsights(analysis, overall);
        this.updateRiskAssessment(analysis);
        this.updateActionItems(analysis, overall);

        // Re-run aggressor correlations now that we have market analysis
        if (this.analysisData.aggressorRatio) {
            this.generateAggressorCorrelations(this.analysisData.aggressorRatio);
        }

        // Update timestamp
        const timestamp = document.getElementById('analysisTimestamp');
        if (timestamp) {
            timestamp.textContent = 'Updated just now';
        }
    },

    /**
     * Analyze trend across timeframes
     */
    analyzeTrend() {
        const periods = this.analysisData.periods;
        let score = 0;
        let description = '';

        const shortTerm = periods['24h']?.trend || 'neutral';
        const mediumTerm = periods['1w']?.trend || 'neutral';
        const longTerm = periods['1m']?.trend || 'neutral';

        // Weight: short-term 30%, medium 40%, long 30%
        const trendScores = { bullish: 1, neutral: 0, bearish: -1 };
        score = (trendScores[shortTerm] * 0.3 + trendScores[mediumTerm] * 0.4 + trendScores[longTerm] * 0.3);

        if (score > 0.3) {
            description = `Strong uptrend confirmed across timeframes. ${shortTerm === 'bullish' ? 'Short-term momentum supports' : 'Short-term may consolidate but'} overall direction is up.`;
            return { signal: 'BULLISH', score, description, class: 'bullish' };
        } else if (score < -0.3) {
            description = `Downtrend in progress. ${shortTerm === 'bearish' ? 'Selling pressure continues' : 'Short-term bounce possible but'} overall bias remains bearish.`;
            return { signal: 'BEARISH', score, description, class: 'bearish' };
        } else {
            description = 'Mixed signals across timeframes indicate consolidation. Wait for clearer directional bias before taking positions.';
            return { signal: 'NEUTRAL', score, description, class: 'neutral' };
        }
    },

    /**
     * Analyze momentum
     */
    analyzeMomentum() {
        const p24h = this.analysisData.periods['24h'];
        const p1w = this.analysisData.periods['1w'];

        if (!p24h || !p1w) {
            return { signal: '--', score: 0, description: 'Insufficient data', class: 'neutral' };
        }

        const change24h = p24h.change;
        const change1w = p1w.change;

        // Momentum is about rate of change
        const momentum = change24h - (change1w / 7);

        if (momentum > 2) {
            return {
                signal: 'ACCELERATING',
                score: 1,
                description: `Momentum is accelerating. 24h change (${change24h.toFixed(2)}%) exceeds weekly average, suggesting increasing buying pressure.`,
                class: 'bullish'
            };
        } else if (momentum < -2) {
            return {
                signal: 'DECELERATING',
                score: -1,
                description: `Momentum is weakening. 24h change (${change24h.toFixed(2)}%) lags weekly trend, indicating potential selling exhaustion or reversal.`,
                class: 'bearish'
            };
        } else {
            return {
                signal: 'STEADY',
                score: 0,
                description: `Momentum is stable. Price movement is consistent with recent trends, no significant acceleration or deceleration.`,
                class: 'neutral'
            };
        }
    },

    /**
     * Analyze volatility
     */
    analyzeVolatility() {
        const p24h = this.analysisData.periods['24h'];
        const p1m = this.analysisData.periods['1m'];

        if (!p24h) {
            return { signal: '--', score: 0, description: 'Insufficient data', class: 'neutral' };
        }

        const vol24h = p24h.volatility;
        const vol1m = p1m?.volatility || vol24h;

        // Compare current volatility to monthly average
        const volRatio = vol24h / (vol1m || 1);

        if (volRatio > 1.5) {
            return {
                signal: 'HIGH',
                score: -0.5,
                description: `Volatility is ${(volRatio * 100 - 100).toFixed(0)}% above average. High risk environment - use wider stops and smaller position sizes.`,
                class: 'bearish'
            };
        } else if (volRatio < 0.7) {
            return {
                signal: 'LOW',
                score: 0.3,
                description: `Volatility is compressed ${(100 - volRatio * 100).toFixed(0)}% below average. Often precedes significant moves - watch for breakouts.`,
                class: 'bullish'
            };
        } else {
            return {
                signal: 'NORMAL',
                score: 0,
                description: 'Volatility is within normal range. Standard risk management applies.',
                class: 'neutral'
            };
        }
    },

    /**
     * Analyze volume profile
     */
    analyzeVolume() {
        const p24h = this.analysisData.periods['24h'];

        if (!p24h || !p24h.candles || p24h.candles.length < 2) {
            return { signal: '--', score: 0, description: 'Insufficient data', class: 'neutral' };
        }

        const candles = p24h.candles;
        const recentVolume = candles.slice(-6).reduce((sum, c) => sum + (c.volume || 0), 0) / 6;
        const avgVolume = candles.reduce((sum, c) => sum + (c.volume || 0), 0) / candles.length;

        const volRatio = recentVolume / (avgVolume || 1);
        const priceUp = candles[candles.length - 1].close > candles[candles.length - 6].close;

        if (volRatio > 1.3 && priceUp) {
            return {
                signal: 'BULLISH VOLUME',
                score: 0.7,
                description: `Volume is ${((volRatio - 1) * 100).toFixed(0)}% above average on rising prices. Strong buying interest confirms upward momentum.`,
                class: 'bullish'
            };
        } else if (volRatio > 1.3 && !priceUp) {
            return {
                signal: 'BEARISH VOLUME',
                score: -0.7,
                description: `High volume on declining prices indicates distribution. Smart money may be exiting positions.`,
                class: 'bearish'
            };
        } else if (volRatio < 0.7) {
            return {
                signal: 'LOW VOLUME',
                score: -0.2,
                description: `Volume is ${((1 - volRatio) * 100).toFixed(0)}% below average. Low conviction move - be cautious of false breakouts.`,
                class: 'neutral'
            };
        } else {
            return {
                signal: 'AVERAGE',
                score: 0,
                description: 'Volume is in line with recent averages. Normal market participation.',
                class: 'neutral'
            };
        }
    },

    /**
     * Analyze price position relative to ATH/ATL
     */
    analyzePosition() {
        const stats = this.analysisData.globalStats;
        const currentPrice = this.analysisData.currentPrice;

        if (!stats || !stats.market_data || !currentPrice) {
            return { signal: '--', score: 0, description: 'Insufficient data', class: 'neutral' };
        }

        const ath = stats.market_data.ath?.usd || currentPrice;
        const atl = stats.market_data.atl?.usd || currentPrice;
        const range = ath - atl;
        const position = ((currentPrice - atl) / range) * 100;
        const fromAth = ((ath - currentPrice) / ath) * 100;

        if (position > 90) {
            return {
                signal: 'NEAR ATH',
                score: 0.3,
                description: `Price is ${fromAth.toFixed(1)}% below all-time high. In discovery mode but watch for resistance. Strong momentum needed to break higher.`,
                class: 'bullish'
            };
        } else if (position > 70) {
            return {
                signal: 'UPPER RANGE',
                score: 0.2,
                description: `Trading in upper ${(100-position).toFixed(0)}% of historical range. Healthy position with room to grow but approaching resistance zones.`,
                class: 'bullish'
            };
        } else if (position < 20) {
            return {
                signal: 'NEAR ATL',
                score: -0.3,
                description: `Price is near historical lows (${position.toFixed(1)}% of range). Could be value opportunity or falling knife - wait for reversal confirmation.`,
                class: 'bearish'
            };
        } else if (position < 40) {
            return {
                signal: 'LOWER RANGE',
                score: 0.1,
                description: `Trading in lower ${position.toFixed(0)}% of historical range. Potential accumulation zone if fundamentals remain strong.`,
                class: 'neutral'
            };
        } else {
            return {
                signal: 'MID RANGE',
                score: 0,
                description: `Price is in the middle of its historical range. No extreme over/undervaluation signals.`,
                class: 'neutral'
            };
        }
    },

    /**
     * Analyze multi-timeframe alignment
     */
    analyzeMultiTimeframe() {
        const periods = this.analysisData.periods;
        const trends = ['24h', '1w', '1m'].map(p => periods[p]?.trend || 'neutral');

        const allBullish = trends.every(t => t === 'bullish');
        const allBearish = trends.every(t => t === 'bearish');
        const bullishCount = trends.filter(t => t === 'bullish').length;
        const bearishCount = trends.filter(t => t === 'bearish').length;

        if (allBullish) {
            return {
                signal: 'ALIGNED UP',
                score: 1,
                description: 'All timeframes aligned bullish. Strong trend confirmation - high probability setup for long positions.',
                class: 'bullish'
            };
        } else if (allBearish) {
            return {
                signal: 'ALIGNED DOWN',
                score: -1,
                description: 'All timeframes aligned bearish. Strong downtrend - avoid longs, consider shorts or wait for reversal.',
                class: 'bearish'
            };
        } else if (bullishCount > bearishCount) {
            return {
                signal: 'MOSTLY BULLISH',
                score: 0.5,
                description: `${bullishCount}/3 timeframes bullish. Generally positive but not fully confirmed. Use tighter stops.`,
                class: 'bullish'
            };
        } else if (bearishCount > bullishCount) {
            return {
                signal: 'MOSTLY BEARISH',
                score: -0.5,
                description: `${bearishCount}/3 timeframes bearish. Negative bias but mixed signals. Caution advised.`,
                class: 'bearish'
            };
        } else {
            return {
                signal: 'MIXED',
                score: 0,
                description: 'Timeframes show conflicting signals. Market is indecisive - wait for clearer alignment.',
                class: 'neutral'
            };
        }
    },

    /**
     * Calculate overall score and recommendation
     */
    calculateOverallScore(analysis) {
        // Weight each factor
        const weights = {
            trend: 0.25,
            momentum: 0.20,
            volatility: 0.10,
            volume: 0.15,
            position: 0.10,
            mtf: 0.20
        };

        let totalScore = 0;
        let totalWeight = 0;

        for (const [key, weight] of Object.entries(weights)) {
            if (analysis[key] && typeof analysis[key].score === 'number') {
                totalScore += analysis[key].score * weight;
                totalWeight += weight;
            }
        }

        const normalizedScore = totalWeight > 0 ? totalScore / totalWeight : 0;
        const confidence = Math.min(Math.abs(normalizedScore) * 100, 95);

        let signal, summary, className;

        if (normalizedScore > 0.3) {
            signal = 'BULLISH';
            className = 'bullish';
            summary = `Market conditions favor buying. ${analysis.mtf.signal === 'ALIGNED UP' ? 'Strong multi-timeframe confirmation present.' : 'Consider entries on pullbacks to support.'} Key factors: ${this.getTopFactors(analysis, 'positive')}`;
        } else if (normalizedScore < -0.3) {
            signal = 'BEARISH';
            className = 'bearish';
            summary = `Market conditions favor selling or staying out. ${analysis.mtf.signal === 'ALIGNED DOWN' ? 'Downtrend is confirmed.' : 'Consider reducing exposure.'} Key concerns: ${this.getTopFactors(analysis, 'negative')}`;
        } else {
            signal = 'NEUTRAL';
            className = 'neutral';
            summary = `Market is in consolidation with no clear direction. Wait for better setup before committing capital. Mixed signals from: ${this.getMixedFactors(analysis)}`;
        }

        return { score: normalizedScore, signal, confidence, summary, className };
    },

    /**
     * Get top contributing factors
     */
    getTopFactors(analysis, type) {
        const factors = [];
        for (const [key, value] of Object.entries(analysis)) {
            if (type === 'positive' && value.score > 0.3) {
                factors.push(key);
            } else if (type === 'negative' && value.score < -0.3) {
                factors.push(key);
            }
        }
        return factors.length > 0 ? factors.join(', ') : 'overall weight of evidence';
    },

    /**
     * Get mixed/neutral factors
     */
    getMixedFactors(analysis) {
        const factors = [];
        for (const [key, value] of Object.entries(analysis)) {
            if (Math.abs(value.score) < 0.3) {
                factors.push(key);
            }
        }
        return factors.slice(0, 3).join(', ') || 'multiple indicators';
    },

    /**
     * Update analysis UI elements
     */
    updateAnalysisUI(analysis, overall) {
        // Update overall signal
        const signalEl = document.getElementById('overallSignal');
        if (signalEl) {
            signalEl.className = `rec-signal-large ${overall.className}`;
            signalEl.querySelector('.signal-text').textContent = overall.signal;
        }

        // Update confidence
        const confFill = document.getElementById('confidenceFillBar');
        const confValue = document.getElementById('confidencePercent');
        if (confFill) confFill.style.width = `${overall.confidence}%`;
        if (confValue) confValue.textContent = `${overall.confidence.toFixed(0)}%`;

        // Update summary
        const summaryEl = document.getElementById('recSummary');
        if (summaryEl) summaryEl.textContent = overall.summary;

        // Update individual factors
        const factorMap = {
            trend: 'trend',
            momentum: 'momentum',
            volatility: 'volatility',
            volume: 'volume',
            position: 'position',
            mtf: 'mtf'
        };

        for (const [key, elId] of Object.entries(factorMap)) {
            const factor = analysis[key];
            const signalEl = document.getElementById(`${elId}Signal`);
            const descEl = document.getElementById(`${elId}Desc`);

            if (signalEl) {
                signalEl.textContent = factor.signal;
                signalEl.className = `factor-signal ${factor.class}`;
            }
            if (descEl) {
                descEl.textContent = factor.description;
            }
        }
    },

    /**
     * Update insights list
     */
    updateInsights(analysis, overall) {
        const insightsList = document.getElementById('insightsList');
        if (!insightsList) return;

        const insights = [];
        const symbol = this.currentSymbol.split('/')[0];

        // Generate insights based on analysis
        if (analysis.mtf.signal.includes('ALIGNED')) {
            insights.push({
                text: `${symbol} shows strong trend alignment across all timeframes - high conviction ${analysis.mtf.class === 'bullish' ? 'bullish' : 'bearish'} setup`,
                class: analysis.mtf.class
            });
        }

        if (analysis.volatility.signal === 'HIGH') {
            insights.push({
                text: 'Elevated volatility detected - reduce position sizes and widen stop losses to avoid getting stopped out',
                class: 'warning'
            });
        } else if (analysis.volatility.signal === 'LOW') {
            insights.push({
                text: 'Volatility compression often precedes large moves - prepare for potential breakout',
                class: 'info'
            });
        }

        if (analysis.volume.class === 'bullish') {
            insights.push({
                text: 'Above-average volume on price increase confirms institutional interest and trend strength',
                class: 'bullish'
            });
        } else if (analysis.volume.class === 'bearish') {
            insights.push({
                text: 'Heavy selling volume indicates distribution - larger players may be exiting positions',
                class: 'bearish'
            });
        }

        if (analysis.position.signal === 'NEAR ATH') {
            insights.push({
                text: `${symbol} approaching all-time highs - uncharted territory requires careful risk management`,
                class: 'warning'
            });
        } else if (analysis.position.signal === 'NEAR ATL') {
            insights.push({
                text: `${symbol} near historical lows - potential value but confirm reversal before buying`,
                class: 'info'
            });
        }

        if (analysis.momentum.signal === 'ACCELERATING') {
            insights.push({
                text: 'Momentum accelerating - trend is gaining strength, consider adding to winning positions',
                class: 'bullish'
            });
        } else if (analysis.momentum.signal === 'DECELERATING') {
            insights.push({
                text: 'Momentum weakening - consider taking partial profits or tightening stops',
                class: 'bearish'
            });
        }

        // Add general insight
        insights.push({
            text: `Overall market bias: ${overall.signal} with ${overall.confidence.toFixed(0)}% confidence`,
            class: overall.className
        });

        // Render insights
        insightsList.innerHTML = insights.map(i =>
            `<li class="insight-item ${i.class}">${i.text}</li>`
        ).join('');
    },

    /**
     * Update risk assessment
     */
    updateRiskAssessment(analysis) {
        // Calculate risk level (0-100)
        let riskScore = 50; // Start neutral

        // High volatility increases risk
        if (analysis.volatility.signal === 'HIGH') riskScore += 25;
        else if (analysis.volatility.signal === 'LOW') riskScore -= 10;

        // Mixed signals increase risk
        if (analysis.mtf.signal === 'MIXED') riskScore += 15;

        // Near ATH/ATL increases risk
        if (analysis.position.signal.includes('NEAR')) riskScore += 10;

        // Low volume increases risk
        if (analysis.volume.signal === 'LOW VOLUME') riskScore += 10;

        riskScore = Math.max(10, Math.min(90, riskScore));

        // Update UI
        const riskMarker = document.getElementById('riskMarker');
        const riskExplanation = document.getElementById('riskExplanation');

        if (riskMarker) {
            riskMarker.style.left = `${riskScore}%`;
        }

        if (riskExplanation) {
            if (riskScore < 35) {
                riskExplanation.textContent = 'Low risk environment. Market conditions are stable with clear trends and normal volatility. Standard position sizing appropriate.';
            } else if (riskScore < 65) {
                riskExplanation.textContent = 'Moderate risk level. Some uncertainty in market conditions. Consider slightly smaller positions and defined stop losses.';
            } else {
                riskExplanation.textContent = 'Elevated risk conditions. High volatility, mixed signals, or extreme price levels present. Reduce position sizes significantly or wait for better setup.';
            }
        }
    },

    /**
     * Update action items
     */
    updateActionItems(analysis, overall) {
        const actionsGrid = document.getElementById('actionsGrid');
        if (!actionsGrid) return;

        const actions = [];

        if (overall.signal === 'BULLISH') {
            actions.push({ icon: '📈', text: 'Consider long positions on pullbacks to support', class: 'buy' });
            if (analysis.momentum.signal === 'ACCELERATING') {
                actions.push({ icon: '➕', text: 'Add to winning positions if trend continues', class: 'buy' });
            }
            actions.push({ icon: '🎯', text: 'Set stops below recent swing lows', class: 'wait' });
        } else if (overall.signal === 'BEARISH') {
            actions.push({ icon: '📉', text: 'Avoid new long positions', class: 'sell' });
            actions.push({ icon: '💰', text: 'Consider taking profits on existing longs', class: 'sell' });
            actions.push({ icon: '⏸️', text: 'Wait for reversal confirmation before buying', class: 'wait' });
        } else {
            actions.push({ icon: '⏳', text: 'Wait for clearer market direction', class: 'wait' });
            actions.push({ icon: '📊', text: 'Monitor for breakout/breakdown from range', class: 'wait' });
            actions.push({ icon: '📝', text: 'Prepare buy/sell levels for breakout', class: 'wait' });
        }

        // Add risk-based action
        if (analysis.volatility.signal === 'HIGH') {
            actions.push({ icon: '⚠️', text: 'Reduce position sizes due to high volatility', class: 'wait' });
        }

        actionsGrid.innerHTML = actions.map(a =>
            `<div class="action-card ${a.class}">
                <span class="action-icon">${a.icon}</span>
                <span class="action-text">${a.text}</span>
            </div>`
        ).join('');
    },

    /**
     * Format price with appropriate decimals
     */
    formatPrice(price) {
        if (price >= 1000) {
            return price.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
        } else if (price >= 1) {
            return price.toFixed(4);
        } else {
            return price.toFixed(6);
        }
    },

    /**
     * Format large numbers
     */
    formatLargeNumber(num) {
        if (num >= 1e12) {
            return (num / 1e12).toFixed(2) + 'T';
        } else if (num >= 1e9) {
            return (num / 1e9).toFixed(2) + 'B';
        } else if (num >= 1e6) {
            return (num / 1e6).toFixed(2) + 'M';
        } else if (num >= 1e3) {
            return (num / 1e3).toFixed(2) + 'K';
        }
        return num.toLocaleString('en-US', { maximumFractionDigits: 2 });
    },

    /**
     * Refresh data when symbol changes
     */
    onSymbolChange(newSymbol) {
        this.currentSymbol = newSymbol;
        if (this.isVisible) {
            this.analysisData = { periods: {}, globalStats: null, currentPrice: 0 };
            this.loadAllData();
        }
    },

    /**
     * Request AI analysis from Claude
     */
    async requestAIAnalysis() {
        const btn = document.getElementById('aiAnalyzeBtn');
        const statusEl = document.getElementById('aiStatus');
        const responseEl = document.getElementById('aiResponse');
        const responseContent = document.getElementById('aiResponseContent');
        const responseTime = document.getElementById('aiResponseTime');

        if (!btn) return;

        // Update button to loading state
        btn.disabled = true;
        btn.innerHTML = '<span class="btn-icon">⏳</span><span class="btn-text">Analyzing...</span>';

        // Update status
        statusEl.innerHTML = '<p class="ai-loading">Claude is analyzing market data...</p>';

        try {
            // Collect all available data for AI analysis (async - fetches orderbook & ticker)
            const marketData = await this.collectMarketDataForAI();

            const response = await fetch(`/api/ai-analysis/${encodeURIComponent(this.currentSymbol)}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(marketData)
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Failed to get AI analysis');
            }

            const data = await response.json();

            // Check for error in response
            if (data.error) {
                throw new Error(data.error);
            }

            if (!data.analysis) {
                throw new Error('No analysis returned from AI');
            }

            // Hide status, show response
            statusEl.style.display = 'none';
            responseEl.style.display = 'block';

            // Format and display the response
            responseContent.innerHTML = this.formatAIResponse(data.analysis);
            const modelName = data.model || 'AI';
            responseTime.textContent = `${modelName} | ${new Date().toLocaleTimeString()}`;

            // Update AI badge to show model name
            const aiBadge = document.querySelector('.ai-name');
            if (aiBadge) {
                aiBadge.textContent = modelName.includes('gemini') ? 'Gemini AI' : 'Claude AI';
            }

            // Update button
            btn.innerHTML = '<span class="btn-icon">🔄</span><span class="btn-text">Refresh Analysis</span>';

        } catch (e) {
            console.error('AI analysis error:', e);
            statusEl.innerHTML = `<p class="ai-error">Error: ${e.message}. Make sure ANTHROPIC_API_KEY is configured in .env file.</p>`;
            statusEl.style.display = 'block';
            responseEl.style.display = 'none';
            btn.innerHTML = '<span class="btn-icon">✨</span><span class="btn-text">Retry Analysis</span>';
        } finally {
            btn.disabled = false;
        }
    },

    /**
     * Collect all market data for AI analysis - comprehensive data gathering
     */
    async collectMarketDataForAI() {
        const data = {
            symbol: this.currentSymbol,
            timestamp: new Date().toISOString()
        };

        // Add current price
        if (this.analysisData.currentPrice) {
            data.current_price = this.analysisData.currentPrice;
        }

        // Fetch 24h ticker stats
        try {
            const tickerResponse = await fetch(`/api/ticker/${encodeURIComponent(this.currentSymbol)}`);
            if (tickerResponse.ok) {
                const ticker = await tickerResponse.json();
                if (!ticker.error) {
                    data.ticker_24h = {
                        high: ticker.high,
                        low: ticker.low,
                        change_percent: ticker.change,
                        volume: ticker.volume,
                        last_price: ticker.last,
                        vwap: ticker.vwap,
                        bid: ticker.bid,
                        ask: ticker.ask,
                        spread: ticker.ask && ticker.bid ? ((ticker.ask - ticker.bid) / ticker.bid * 100).toFixed(4) : null
                    };
                }
            }
        } catch (e) {
            console.warn('Could not fetch ticker for AI:', e);
        }

        // Fetch orderbook depth data
        try {
            const orderbookResponse = await fetch(`/api/orderbook/${encodeURIComponent(this.currentSymbol)}?limit=50`);
            if (orderbookResponse.ok) {
                const orderbook = await orderbookResponse.json();
                if (!orderbook.error && orderbook.bids && orderbook.asks) {
                    // Calculate orderbook metrics
                    let totalBidVolume = 0;
                    let totalAskVolume = 0;
                    let bidWalls = [];
                    let askWalls = [];
                    const avgBidSize = orderbook.bids.reduce((sum, [p, s]) => sum + s, 0) / orderbook.bids.length;
                    const avgAskSize = orderbook.asks.reduce((sum, [p, s]) => sum + s, 0) / orderbook.asks.length;

                    orderbook.bids.forEach(([price, size]) => {
                        totalBidVolume += size * price;
                        if (size > avgBidSize * 3) bidWalls.push({ price, size });
                    });

                    orderbook.asks.forEach(([price, size]) => {
                        totalAskVolume += size * price;
                        if (size > avgAskSize * 3) askWalls.push({ price, size });
                    });

                    const imbalance = ((totalBidVolume - totalAskVolume) / (totalBidVolume + totalAskVolume) * 100);

                    data.orderbook_depth = {
                        total_bid_volume_usd: totalBidVolume,
                        total_ask_volume_usd: totalAskVolume,
                        imbalance_percent: imbalance.toFixed(2),
                        imbalance_signal: imbalance > 10 ? 'BULLISH' : imbalance < -10 ? 'BEARISH' : 'NEUTRAL',
                        bid_walls: bidWalls.slice(0, 3),
                        ask_walls: askWalls.slice(0, 3),
                        best_bid: orderbook.bids[0]?.[0],
                        best_ask: orderbook.asks[0]?.[0],
                        spread_percent: orderbook.bids[0] && orderbook.asks[0] ?
                            ((orderbook.asks[0][0] - orderbook.bids[0][0]) / orderbook.bids[0][0] * 100).toFixed(4) : null
                    };
                }
            }
        } catch (e) {
            console.warn('Could not fetch orderbook for AI:', e);
        }

        // Add performance data
        if (this.analysisData.periods) {
            data.performance = {};
            for (const [period, periodData] of Object.entries(this.analysisData.periods)) {
                data.performance[period] = {
                    change: periodData.change,
                    volatility: periodData.volatility,
                    trend: periodData.trend
                };
            }
        }

        // Add aggressor ratio data
        if (this.analysisData.aggressorRatio) {
            data.aggressor_ratio = this.analysisData.aggressorRatio;
        }

        // Add overall analysis
        if (this.analysisData.overallAnalysis) {
            data.market_analysis = {
                signal: this.analysisData.overallAnalysis.signal,
                confidence: this.analysisData.overallAnalysis.confidence,
                summary: this.analysisData.overallAnalysis.summary
            };
        }

        // Add factor analysis
        if (this.analysisData.factorAnalysis) {
            data.factors = {};
            for (const [factor, factorData] of Object.entries(this.analysisData.factorAnalysis)) {
                data.factors[factor] = {
                    signal: factorData.signal,
                    score: factorData.score,
                    description: factorData.description
                };
            }
        }

        // Add global stats if available
        if (this.analysisData.globalStats) {
            const md = this.analysisData.globalStats.market_data;
            data.global_stats = {
                market_cap: md?.market_cap?.usd,
                volume_24h: md?.total_volume?.usd,
                circulating_supply: md?.circulating_supply,
                ath: md?.ath?.usd,
                atl: md?.atl?.usd,
                ath_change_percentage: md?.ath_change_percentage?.usd
            };
        }

        // Add technical analysis data
        if (this.analysisData.technicalAnalysis) {
            const ta = this.analysisData.technicalAnalysis;
            data.technical_analysis = {
                overall_signal: ta.overall_signal,
                summary: ta.summary,
                key_levels: ta.key_levels,
                moving_averages: ta.moving_averages,
                oscillators: ta.oscillators
            };
        }

        // Detect signal divergences/conflicts
        data.signal_analysis = this.detectSignalDivergences(data);

        return data;
    },

    /**
     * Detect divergences and conflicts between different signals
     */
    detectSignalDivergences(data) {
        const signals = [];
        const conflicts = [];

        // Collect all signals
        if (data.technical_analysis?.overall_signal) {
            signals.push({ source: 'Technical Analysis', signal: data.technical_analysis.overall_signal });
        }
        if (data.market_analysis?.signal) {
            signals.push({ source: 'Market Analysis', signal: data.market_analysis.signal });
        }
        if (data.aggressor_ratio?.signal) {
            signals.push({ source: 'Aggressor Ratio', signal: data.aggressor_ratio.signal });
        }
        if (data.orderbook_depth?.imbalance_signal) {
            signals.push({ source: 'Orderbook Depth', signal: data.orderbook_depth.imbalance_signal });
        }

        // Map signals to numeric values for comparison
        const signalValue = (sig) => {
            if (!sig) return 0;
            const s = sig.toUpperCase();
            if (s.includes('STRONG BUY') || s.includes('STRONGLY BULLISH')) return 2;
            if (s.includes('BUY') || s.includes('BULLISH')) return 1;
            if (s.includes('STRONG SELL') || s.includes('STRONGLY BEARISH')) return -2;
            if (s.includes('SELL') || s.includes('BEARISH')) return -1;
            return 0;
        };

        // Detect conflicts
        for (let i = 0; i < signals.length; i++) {
            for (let j = i + 1; j < signals.length; j++) {
                const val1 = signalValue(signals[i].signal);
                const val2 = signalValue(signals[j].signal);
                // Conflict if one is bullish and other is bearish
                if ((val1 > 0 && val2 < 0) || (val1 < 0 && val2 > 0)) {
                    conflicts.push({
                        signal1: `${signals[i].source}: ${signals[i].signal}`,
                        signal2: `${signals[j].source}: ${signals[j].signal}`,
                        severity: Math.abs(val1 - val2) >= 3 ? 'HIGH' : 'MEDIUM'
                    });
                }
            }
        }

        // Calculate consensus
        const totalValue = signals.reduce((sum, s) => sum + signalValue(s.signal), 0);
        const avgValue = signals.length > 0 ? totalValue / signals.length : 0;
        let consensus = 'NEUTRAL';
        if (avgValue >= 1.5) consensus = 'STRONG BULLISH';
        else if (avgValue >= 0.5) consensus = 'BULLISH';
        else if (avgValue <= -1.5) consensus = 'STRONG BEARISH';
        else if (avgValue <= -0.5) consensus = 'BEARISH';

        return {
            signals_summary: signals,
            conflicts: conflicts,
            has_conflicts: conflicts.length > 0,
            conflict_count: conflicts.length,
            consensus: consensus,
            consensus_strength: Math.abs(avgValue).toFixed(2)
        };
    },

    /**
     * Format AI response for display
     */
    formatAIResponse(text) {
        if (!text) return '<p>No analysis available.</p>';

        // First, convert markdown tables to HTML tables
        text = this.convertMarkdownTables(text);

        // Convert markdown-style formatting to HTML
        let html = text
            // Convert headers
            .replace(/^### (.*$)/gm, '<h4>$1</h4>')
            .replace(/^## (.*$)/gm, '<h3>$1</h3>')
            // Convert bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Convert bullet points (but not if inside a table)
            .replace(/^- (?!.*<\/td>)(.*$)/gm, '<li>$1</li>')
            .replace(/^• (.*$)/gm, '<li>$1</li>')
            // Convert numbered lists
            .replace(/^\d+\. (.*$)/gm, '<li>$1</li>')
            // Wrap consecutive li elements in ul
            .replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>')
            // Convert newlines to paragraphs (skip tables)
            .split('\n\n')
            .map(para => {
                para = para.trim();
                if (!para) return '';
                if (para.startsWith('<h') || para.startsWith('<ul') || para.startsWith('<table') || para.includes('</table>')) return para;
                return `<p>${para}</p>`;
            })
            .join('\n');

        // Add signal highlighting
        html = html
            .replace(/BULLISH/g, '<span class="ai-signal bullish">BULLISH</span>')
            .replace(/BEARISH/g, '<span class="ai-signal bearish">BEARISH</span>')
            .replace(/NEUTRAL/g, '<span class="ai-signal neutral">NEUTRAL</span>')
            .replace(/\bLONG\b/g, '<span class="ai-action buy">LONG</span>')
            .replace(/\bSHORT\b/g, '<span class="ai-action sell">SHORT</span>')
            .replace(/\bBUY\b/g, '<span class="ai-action buy">BUY</span>')
            .replace(/\bSELL\b/g, '<span class="ai-action sell">SELL</span>')
            .replace(/\bHOLD\b/g, '<span class="ai-action hold">HOLD</span>')
            .replace(/\bWAIT\b/g, '<span class="ai-action hold">WAIT</span>')
            .replace(/NO TRADE/g, '<span class="ai-action hold">NO TRADE</span>');

        return html;
    },

    /**
     * Convert markdown tables to HTML tables
     */
    convertMarkdownTables(text) {
        const lines = text.split('\n');
        let result = [];
        let inTable = false;
        let tableRows = [];

        for (let i = 0; i < lines.length; i++) {
            const line = lines[i].trim();

            // Check if this line is a table row (starts and ends with |)
            if (line.startsWith('|') && line.endsWith('|')) {
                // Check if this is the separator row (contains only |, -, and spaces)
                if (/^\|[\s\-:|]+\|$/.test(line)) {
                    // Skip separator row but mark we're in a table
                    inTable = true;
                    continue;
                }

                // Parse table row
                const cells = line.slice(1, -1).split('|').map(cell => cell.trim());

                if (!inTable) {
                    // This is the header row
                    inTable = true;
                    tableRows.push({ type: 'header', cells });
                } else {
                    // This is a data row
                    tableRows.push({ type: 'data', cells });
                }
            } else {
                // Not a table row - if we were in a table, close it
                if (inTable && tableRows.length > 0) {
                    result.push(this.buildHtmlTable(tableRows));
                    tableRows = [];
                    inTable = false;
                }
                result.push(line);
            }
        }

        // Close any remaining table
        if (tableRows.length > 0) {
            result.push(this.buildHtmlTable(tableRows));
        }

        return result.join('\n');
    },

    /**
     * Build HTML table from parsed rows
     */
    buildHtmlTable(rows) {
        let html = '<table class="ai-trade-table">';

        rows.forEach((row, index) => {
            if (row.type === 'header') {
                html += '<thead><tr>';
                row.cells.forEach(cell => {
                    html += `<th>${cell}</th>`;
                });
                html += '</tr></thead><tbody>';
            } else {
                html += '<tr>';
                row.cells.forEach((cell, cellIndex) => {
                    // Add special styling for first column (parameter names)
                    const className = cellIndex === 0 ? ' class="param-name"' : '';
                    html += `<td${className}>${cell}</td>`;
                });
                html += '</tr>';
            }
        });

        html += '</tbody></table>';
        return html;
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    MarketSummary.init();
});

// Expose globally
window.MarketSummary = MarketSummary;
