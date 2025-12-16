/**
 * Depth Chart for Robo Trader Pro
 * Visualizes order book depth as a mountain chart
 */

class DepthChart {
    constructor(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) {
            console.error('[DepthChart] Canvas element not found:', canvasId);
            return;
        }

        this.ctx = this.canvas.getContext('2d');
        this.tooltip = document.getElementById('depthChartTooltip');

        // Data
        this.bids = [];
        this.asks = [];
        this.midPrice = 0;

        // Chart dimensions
        this.padding = { top: 20, right: 60, bottom: 30, left: 10 };

        // Colors
        this.colors = {
            bidFill: 'rgba(14, 203, 129, 0.3)',
            bidLine: '#0ecb81',
            bidGradientStart: 'rgba(14, 203, 129, 0.4)',
            bidGradientEnd: 'rgba(14, 203, 129, 0.05)',
            askFill: 'rgba(246, 70, 93, 0.3)',
            askLine: '#f6465d',
            askGradientStart: 'rgba(246, 70, 93, 0.4)',
            askGradientEnd: 'rgba(246, 70, 93, 0.05)',
            midLine: '#fcd535',
            grid: 'rgba(255, 255, 255, 0.05)',
            text: '#848e9c',
            crosshair: 'rgba(255, 255, 255, 0.3)'
        };

        // Mouse state
        this.mouseX = null;
        this.mouseY = null;

        this.init();
    }

    init() {
        this.resize();
        this.bindEvents();

        // Handle window resize
        window.addEventListener('resize', () => this.resize());

        // Observe container resize
        const resizeObserver = new ResizeObserver(() => this.resize());
        resizeObserver.observe(this.canvas.parentElement);
    }

    resize() {
        const container = this.canvas.parentElement;
        const rect = container.getBoundingClientRect();

        // Set canvas size with device pixel ratio for sharp rendering
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = (rect.height - 80) * dpr; // Leave room for stats
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = (rect.height - 80) + 'px';

        this.ctx.scale(dpr, dpr);

        this.width = rect.width;
        this.height = rect.height - 80;

        this.render();
    }

    bindEvents() {
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseleave', () => this.onMouseLeave());
    }

    onMouseMove(e) {
        const rect = this.canvas.getBoundingClientRect();
        this.mouseX = e.clientX - rect.left;
        this.mouseY = e.clientY - rect.top;

        this.render();
        this.showTooltip(e);
    }

    onMouseLeave() {
        this.mouseX = null;
        this.mouseY = null;
        this.hideTooltip();
        this.render();
    }

    setData(bids, asks, midPrice) {
        // Sort and calculate cumulative volumes
        // Bids: highest price first, cumulative from highest to lowest
        this.bids = this.calculateCumulative(
            [...bids].sort((a, b) => b.price - a.price)
        );

        // Asks: lowest price first, cumulative from lowest to highest
        this.asks = this.calculateCumulative(
            [...asks].sort((a, b) => a.price - b.price)
        );

        this.midPrice = midPrice;

        // Update stats
        this.updateStats();

        this.render();
    }

    calculateCumulative(orders) {
        let cumulative = 0;
        return orders.map(order => {
            cumulative += order.size;
            return {
                price: order.price,
                size: order.size,
                cumulative: cumulative
            };
        });
    }

    updateStats() {
        const totalBidVolume = this.bids.length > 0 ?
            this.bids[this.bids.length - 1].cumulative : 0;
        const totalAskVolume = this.asks.length > 0 ?
            this.asks[this.asks.length - 1].cumulative : 0;

        document.getElementById('totalBidVolume').textContent =
            totalBidVolume.toFixed(4);
        document.getElementById('totalAskVolume').textContent =
            totalAskVolume.toFixed(4);

        const ratio = totalAskVolume > 0 ?
            (totalBidVolume / totalAskVolume).toFixed(2) : '∞';
        const ratioEl = document.getElementById('bidAskRatio');
        ratioEl.textContent = ratio;

        // Color the ratio based on value
        if (parseFloat(ratio) > 1.1) {
            ratioEl.style.color = this.colors.bidLine;
        } else if (parseFloat(ratio) < 0.9) {
            ratioEl.style.color = this.colors.askLine;
        } else {
            ratioEl.style.color = '';
        }

        // Generate recommendation
        this.updateRecommendation(totalBidVolume, totalAskVolume, parseFloat(ratio));

        // Also update analysis view if it's visible
        const analysisView = document.getElementById('orderbookAnalysisView');
        if (analysisView && analysisView.classList.contains('active')) {
            this.updateAnalysisView();
        }
    }

    updateRecommendation(bidVol, askVol, ratio) {
        const recEl = document.getElementById('depthRecommendation');
        if (!recEl) return;

        const iconEl = recEl.querySelector('.rec-icon');
        const textEl = recEl.querySelector('.rec-text');

        // Remove existing classes
        recEl.classList.remove('bullish', 'bearish', 'neutral', 'strong');

        // ============================================
        // MULTI-FACTOR ANALYSIS
        // ============================================

        // 1. DEPTH RATIO SCORE (-100 to +100)
        // Negative = bearish, Positive = bullish
        let depthScore = 0;
        if (ratio > 1) {
            depthScore = Math.min(((ratio - 1) * 100), 100);
        } else {
            depthScore = Math.max(((ratio - 1) * 100), -100);
        }

        // 2. TOP-OF-BOOK PRESSURE (immediate market pressure)
        // Analyze top 5 levels for immediate sentiment
        const topBookScore = this.analyzeTopOfBook();

        // 3. SPREAD ANALYSIS (liquidity indicator)
        const spreadAnalysis = this.analyzeSpread();

        // 4. WALL DETECTION (support/resistance)
        const bidWall = this.detectWall(this.bids, 'bid');
        const askWall = this.detectWall(this.asks, 'ask');
        let wallScore = 0;
        if (bidWall && !askWall) wallScore = 20;
        else if (askWall && !bidWall) wallScore = -20;

        // 5. VOLUME CONCENTRATION (where is the liquidity?)
        const concentrationScore = this.analyzeVolumeConcentration();

        // ============================================
        // WEIGHTED COMPOSITE SCORE
        // ============================================
        const weights = {
            depth: 0.35,      // Full depth ratio
            topBook: 0.30,    // Immediate pressure
            spread: 0.10,     // Liquidity
            walls: 0.15,      // Support/resistance
            concentration: 0.10 // Volume distribution
        };

        const compositeScore =
            (depthScore * weights.depth) +
            (topBookScore * weights.topBook) +
            (spreadAnalysis.score * weights.spread) +
            (wallScore * weights.walls) +
            (concentrationScore * weights.concentration);

        // ============================================
        // GENERATE RECOMMENDATION
        // ============================================
        let sentiment = 'neutral';
        let icon = '◆';
        let message = '';
        let strength = Math.abs(compositeScore);

        // Determine sentiment and strength
        if (compositeScore > 25) {
            sentiment = 'bullish';
            icon = '▲';
            if (strength > 50) {
                recEl.classList.add('strong');
                if (bidWall) {
                    message = `STRONG BUY signal • Wall at $${bidWall.toLocaleString()} • Score: +${compositeScore.toFixed(0)}`;
                } else {
                    message = `STRONG BUY signal • Heavy accumulation • Score: +${compositeScore.toFixed(0)}`;
                }
            } else {
                message = `BUY signal • Buyers in control • Score: +${compositeScore.toFixed(0)}`;
            }
        } else if (compositeScore < -25) {
            sentiment = 'bearish';
            icon = '▼';
            if (strength > 50) {
                recEl.classList.add('strong');
                if (askWall) {
                    message = `STRONG SELL signal • Wall at $${askWall.toLocaleString()} • Score: ${compositeScore.toFixed(0)}`;
                } else {
                    message = `STRONG SELL signal • Distribution detected • Score: ${compositeScore.toFixed(0)}`;
                }
            } else {
                message = `SELL signal • Sellers in control • Score: ${compositeScore.toFixed(0)}`;
            }
        } else {
            sentiment = 'neutral';
            icon = '◆';
            if (bidWall && askWall) {
                message = `HOLD • Range $${bidWall.toLocaleString()} - $${askWall.toLocaleString()} • Score: ${compositeScore.toFixed(0)}`;
            } else if (spreadAnalysis.isWide) {
                message = `CAUTION • Wide spread, low liquidity • Score: ${compositeScore.toFixed(0)}`;
            } else {
                message = `HOLD • Market balanced • Score: ${compositeScore.toFixed(0)}`;
            }
        }

        recEl.classList.add(sentiment);
        iconEl.textContent = icon;
        textEl.textContent = message;
    }

    // Analyze top 5 levels of order book for immediate pressure
    analyzeTopOfBook() {
        const topN = 5;
        const topBids = this.bids.slice(0, Math.min(topN, this.bids.length));
        const topAsks = this.asks.slice(0, Math.min(topN, this.asks.length));

        const topBidVol = topBids.reduce((sum, o) => sum + o.size, 0);
        const topAskVol = topAsks.reduce((sum, o) => sum + o.size, 0);

        if (topAskVol === 0) return 50;
        if (topBidVol === 0) return -50;

        const topRatio = topBidVol / topAskVol;

        // Convert to score (-100 to +100)
        if (topRatio > 1) {
            return Math.min((topRatio - 1) * 100, 100);
        } else {
            return Math.max((topRatio - 1) * 100, -100);
        }
    }

    // Analyze spread for liquidity
    analyzeSpread() {
        if (this.bids.length === 0 || this.asks.length === 0) {
            return { spread: 0, spreadPct: 0, isWide: false, score: 0 };
        }

        const bestBid = this.bids[0].price;
        const bestAsk = this.asks[0].price;
        const spread = bestAsk - bestBid;
        const midPrice = (bestAsk + bestBid) / 2;
        const spreadPct = (spread / midPrice) * 100;

        // Wide spread = less liquid = more risk
        // Tight spread = liquid = safer
        const isWide = spreadPct > 0.1; // >0.1% is considered wide for BTC

        // Score: tight spread = positive, wide spread = negative
        let score = 0;
        if (spreadPct < 0.02) score = 20;      // Very tight
        else if (spreadPct < 0.05) score = 10; // Tight
        else if (spreadPct < 0.1) score = 0;   // Normal
        else if (spreadPct < 0.2) score = -10; // Wide
        else score = -20;                       // Very wide

        return { spread, spreadPct, isWide, score };
    }

    // Analyze where volume is concentrated
    analyzeVolumeConcentration() {
        if (this.bids.length < 5 || this.asks.length < 5) return 0;

        // Calculate volume in first 25% vs last 25% of price range
        const bidQuarter = Math.floor(this.bids.length / 4);
        const askQuarter = Math.floor(this.asks.length / 4);

        const nearBidVol = this.bids.slice(0, bidQuarter).reduce((s, o) => s + o.size, 0);
        const farBidVol = this.bids.slice(-bidQuarter).reduce((s, o) => s + o.size, 0);
        const nearAskVol = this.asks.slice(0, askQuarter).reduce((s, o) => s + o.size, 0);
        const farAskVol = this.asks.slice(-askQuarter).reduce((s, o) => s + o.size, 0);

        // If bids concentrated near price = strong support
        // If asks concentrated near price = strong resistance
        let score = 0;

        if (nearBidVol > farBidVol * 1.5) score += 15; // Buyers defending price
        if (nearAskVol > farAskVol * 1.5) score -= 15; // Sellers attacking price

        return score;
    }

    // Update the Analysis tab UI with all factor scores
    updateAnalysisView() {
        if (this.bids.length === 0 || this.asks.length === 0) return;

        // Calculate all scores
        const totalBidVol = this.bids[this.bids.length - 1]?.cumulative || 0;
        const totalAskVol = this.asks[this.asks.length - 1]?.cumulative || 0;
        const ratio = totalAskVol > 0 ? totalBidVol / totalAskVol : 1;

        // 1. Depth Ratio Score
        let depthScore = 0;
        if (ratio > 1) {
            depthScore = Math.min(((ratio - 1) * 100), 100);
        } else {
            depthScore = Math.max(((ratio - 1) * 100), -100);
        }

        // 2. Top-of-Book Score
        const topBookScore = this.analyzeTopOfBook();

        // 3. Spread Analysis
        const spreadAnalysis = this.analyzeSpread();

        // 4. Wall Detection
        const bidWall = this.detectWall(this.bids, 'bid');
        const askWall = this.detectWall(this.asks, 'ask');
        let wallScore = 0;
        if (bidWall && !askWall) wallScore = 20;
        else if (askWall && !bidWall) wallScore = -20;

        // 5. Volume Concentration
        const concentrationScore = this.analyzeVolumeConcentration();

        // Calculate composite score
        const weights = { depth: 0.35, topBook: 0.30, spread: 0.10, walls: 0.15, concentration: 0.10 };
        const compositeScore =
            (depthScore * weights.depth) +
            (topBookScore * weights.topBook) +
            (spreadAnalysis.score * weights.spread) +
            (wallScore * weights.walls) +
            (concentrationScore * weights.concentration);

        // Update UI elements
        this.updateFactorUI('depthRatio', depthScore);
        this.updateFactorUI('topBook', topBookScore);
        this.updateFactorUI('wall', wallScore);
        this.updateFactorUI('spread', spreadAnalysis.score);
        this.updateFactorUI('concentration', concentrationScore);

        // Update wall details
        const wallDetails = document.getElementById('wallDetails');
        if (wallDetails) {
            if (bidWall && askWall) {
                wallDetails.textContent = `Support: $${bidWall.toLocaleString()} | Resistance: $${askWall.toLocaleString()}`;
            } else if (bidWall) {
                wallDetails.textContent = `Support wall at $${bidWall.toLocaleString()}`;
            } else if (askWall) {
                wallDetails.textContent = `Resistance wall at $${askWall.toLocaleString()}`;
            } else {
                wallDetails.textContent = 'No significant walls detected';
            }
        }

        // Update spread details
        const spreadDetails = document.getElementById('spreadDetails');
        if (spreadDetails) {
            spreadDetails.textContent = `Spread: ${spreadAnalysis.spreadPct.toFixed(4)}% ${spreadAnalysis.isWide ? '(Wide - Low liquidity)' : '(Normal)'}`;
        }

        // Update composite score display
        this.updateCompositeScore(compositeScore);

        // Update final recommendation
        this.updateAnalysisRecommendation(compositeScore, bidWall, askWall, spreadAnalysis);
    }

    updateFactorUI(factorId, score) {
        const barEl = document.getElementById(`${factorId}Bar`);
        const scoreEl = document.getElementById(`${factorId}Score`);

        if (barEl) {
            barEl.classList.remove('positive', 'negative');
            if (score > 0) {
                barEl.classList.add('positive');
                barEl.style.width = `${Math.min(Math.abs(score), 100) / 2}%`;
            } else if (score < 0) {
                barEl.classList.add('negative');
                barEl.style.width = `${Math.min(Math.abs(score), 100) / 2}%`;
            } else {
                barEl.style.width = '0%';
            }
        }

        if (scoreEl) {
            scoreEl.classList.remove('positive', 'negative');
            if (score > 0) {
                scoreEl.classList.add('positive');
                scoreEl.textContent = `+${score.toFixed(0)}`;
            } else if (score < 0) {
                scoreEl.classList.add('negative');
                scoreEl.textContent = score.toFixed(0);
            } else {
                scoreEl.textContent = '0';
            }
        }
    }

    updateCompositeScore(score) {
        const valueEl = document.getElementById('compositeScoreValue');
        const markerEl = document.getElementById('compositeGaugeMarker');

        if (valueEl) {
            valueEl.classList.remove('positive', 'negative', 'neutral');
            if (score > 25) {
                valueEl.classList.add('positive');
                valueEl.textContent = `+${score.toFixed(0)}`;
            } else if (score < -25) {
                valueEl.classList.add('negative');
                valueEl.textContent = score.toFixed(0);
            } else {
                valueEl.classList.add('neutral');
                valueEl.textContent = score.toFixed(0);
            }
        }

        if (markerEl) {
            // Convert score (-100 to +100) to percentage (0% to 100%)
            const position = ((score + 100) / 200) * 100;
            markerEl.style.left = `${Math.max(0, Math.min(100, position))}%`;
        }
    }

    updateAnalysisRecommendation(score, bidWall, askWall, spreadAnalysis) {
        const recEl = document.getElementById('analysisRecommendation');
        const signalEl = document.getElementById('analysisSignal');
        const messageEl = document.getElementById('analysisMessage');

        if (!recEl || !signalEl || !messageEl) return;

        recEl.classList.remove('bullish', 'bearish', 'neutral', 'strong');

        let signal = 'HOLD';
        let message = '';
        const strength = Math.abs(score);

        if (score > 25) {
            recEl.classList.add('bullish');
            if (strength > 50) {
                recEl.classList.add('strong');
                signal = 'STRONG BUY';
                message = bidWall
                    ? `Heavy accumulation detected with support at $${bidWall.toLocaleString()}`
                    : 'Significant buying pressure across all factors';
            } else {
                signal = 'BUY';
                message = 'Buyers showing control, consider long positions';
            }
        } else if (score < -25) {
            recEl.classList.add('bearish');
            if (strength > 50) {
                recEl.classList.add('strong');
                signal = 'STRONG SELL';
                message = askWall
                    ? `Distribution detected with resistance at $${askWall.toLocaleString()}`
                    : 'Significant selling pressure across all factors';
            } else {
                signal = 'SELL';
                message = 'Sellers showing control, consider short positions or exit longs';
            }
        } else {
            recEl.classList.add('neutral');
            signal = 'HOLD';
            if (bidWall && askWall) {
                message = `Range-bound between $${bidWall.toLocaleString()} and $${askWall.toLocaleString()}`;
            } else if (spreadAnalysis.isWide) {
                message = 'Low liquidity detected, avoid large orders';
            } else {
                message = 'No clear directional bias, wait for better setup';
            }
        }

        signalEl.textContent = signal;
        messageEl.textContent = message;
    }

    detectWall(orders, side) {
        if (orders.length < 3) return null;

        // Calculate average order size
        const sizes = orders.map(o => o.size);
        const avgSize = sizes.reduce((a, b) => a + b, 0) / sizes.length;
        const threshold = avgSize * 3; // 3x average = wall

        // Find significant walls
        for (const order of orders) {
            if (order.size > threshold) {
                return order.price;
            }
        }

        return null;
    }

    render() {
        if (!this.ctx || this.bids.length === 0 || this.asks.length === 0) {
            this.renderEmpty();
            return;
        }

        // Clear canvas
        this.ctx.clearRect(0, 0, this.width, this.height);

        // Calculate scales
        const scales = this.calculateScales();

        // Draw grid
        this.drawGrid(scales);

        // Draw depth areas
        this.drawBids(scales);
        this.drawAsks(scales);

        // Draw mid price line
        this.drawMidLine(scales);

        // Draw price axis
        this.drawPriceAxis(scales);

        // Draw volume axis
        this.drawVolumeAxis(scales);

        // Draw crosshair if mouse is over
        if (this.mouseX !== null) {
            this.drawCrosshair(scales);
        }
    }

    renderEmpty() {
        this.ctx.clearRect(0, 0, this.width, this.height);
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = '14px Inter, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText('Loading depth data...', this.width / 2, this.height / 2);
    }

    calculateScales() {
        const chartWidth = this.width - this.padding.left - this.padding.right;
        const chartHeight = this.height - this.padding.top - this.padding.bottom;

        // Price range - extend slightly beyond bid/ask range
        const minBidPrice = this.bids.length > 0 ?
            this.bids[this.bids.length - 1].price : this.midPrice * 0.95;
        const maxAskPrice = this.asks.length > 0 ?
            this.asks[this.asks.length - 1].price : this.midPrice * 1.05;

        const priceRange = maxAskPrice - minBidPrice;
        const minPrice = minBidPrice - priceRange * 0.05;
        const maxPrice = maxAskPrice + priceRange * 0.05;

        // Volume range
        const maxBidVol = this.bids.length > 0 ?
            this.bids[this.bids.length - 1].cumulative : 1;
        const maxAskVol = this.asks.length > 0 ?
            this.asks[this.asks.length - 1].cumulative : 1;
        const maxVolume = Math.max(maxBidVol, maxAskVol) * 1.1;

        return {
            chartWidth,
            chartHeight,
            minPrice,
            maxPrice,
            maxVolume,
            priceToX: (price) => {
                return this.padding.left +
                    ((price - minPrice) / (maxPrice - minPrice)) * chartWidth;
            },
            volumeToY: (volume) => {
                return this.padding.top + chartHeight -
                    (volume / maxVolume) * chartHeight;
            },
            xToPrice: (x) => {
                return minPrice +
                    ((x - this.padding.left) / chartWidth) * (maxPrice - minPrice);
            }
        };
    }

    drawGrid(scales) {
        this.ctx.strokeStyle = this.colors.grid;
        this.ctx.lineWidth = 1;

        // Horizontal grid lines (volume levels)
        const volumeSteps = 5;
        for (let i = 0; i <= volumeSteps; i++) {
            const volume = (i / volumeSteps) * scales.maxVolume;
            const y = scales.volumeToY(volume);

            this.ctx.beginPath();
            this.ctx.moveTo(this.padding.left, y);
            this.ctx.lineTo(this.width - this.padding.right, y);
            this.ctx.stroke();
        }

        // Vertical grid lines (price levels)
        const priceSteps = 5;
        const priceRange = scales.maxPrice - scales.minPrice;
        for (let i = 0; i <= priceSteps; i++) {
            const price = scales.minPrice + (i / priceSteps) * priceRange;
            const x = scales.priceToX(price);

            this.ctx.beginPath();
            this.ctx.moveTo(x, this.padding.top);
            this.ctx.lineTo(x, this.height - this.padding.bottom);
            this.ctx.stroke();
        }
    }

    drawBids(scales) {
        if (this.bids.length === 0) return;

        // Create gradient
        const gradient = this.ctx.createLinearGradient(
            0, this.padding.top,
            0, this.height - this.padding.bottom
        );
        gradient.addColorStop(0, this.colors.bidGradientStart);
        gradient.addColorStop(1, this.colors.bidGradientEnd);

        // Draw filled area (step chart style)
        this.ctx.beginPath();
        this.ctx.moveTo(scales.priceToX(this.midPrice), this.height - this.padding.bottom);

        // Start from mid price with 0 volume
        let prevX = scales.priceToX(this.midPrice);
        let prevY = this.height - this.padding.bottom;

        this.bids.forEach((bid, i) => {
            const x = scales.priceToX(bid.price);
            const y = scales.volumeToY(bid.cumulative);

            // Draw horizontal then vertical (step style)
            this.ctx.lineTo(x, prevY);
            this.ctx.lineTo(x, y);

            prevX = x;
            prevY = y;
        });

        // Close the path
        this.ctx.lineTo(this.padding.left, prevY);
        this.ctx.lineTo(this.padding.left, this.height - this.padding.bottom);
        this.ctx.closePath();

        // Fill
        this.ctx.fillStyle = gradient;
        this.ctx.fill();

        // Draw line on top
        this.ctx.beginPath();
        this.ctx.moveTo(scales.priceToX(this.midPrice), this.height - this.padding.bottom);

        this.bids.forEach((bid, i) => {
            const x = scales.priceToX(bid.price);
            const y = scales.volumeToY(bid.cumulative);

            if (i === 0) {
                this.ctx.lineTo(x, this.height - this.padding.bottom);
            }
            this.ctx.lineTo(x, y);
        });

        this.ctx.strokeStyle = this.colors.bidLine;
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
    }

    drawAsks(scales) {
        if (this.asks.length === 0) return;

        // Create gradient
        const gradient = this.ctx.createLinearGradient(
            0, this.padding.top,
            0, this.height - this.padding.bottom
        );
        gradient.addColorStop(0, this.colors.askGradientStart);
        gradient.addColorStop(1, this.colors.askGradientEnd);

        // Draw filled area (step chart style)
        this.ctx.beginPath();
        this.ctx.moveTo(scales.priceToX(this.midPrice), this.height - this.padding.bottom);

        let prevX = scales.priceToX(this.midPrice);
        let prevY = this.height - this.padding.bottom;

        this.asks.forEach((ask, i) => {
            const x = scales.priceToX(ask.price);
            const y = scales.volumeToY(ask.cumulative);

            // Draw horizontal then vertical (step style)
            this.ctx.lineTo(x, prevY);
            this.ctx.lineTo(x, y);

            prevX = x;
            prevY = y;
        });

        // Close the path
        this.ctx.lineTo(this.width - this.padding.right, prevY);
        this.ctx.lineTo(this.width - this.padding.right, this.height - this.padding.bottom);
        this.ctx.closePath();

        // Fill
        this.ctx.fillStyle = gradient;
        this.ctx.fill();

        // Draw line on top
        this.ctx.beginPath();
        this.ctx.moveTo(scales.priceToX(this.midPrice), this.height - this.padding.bottom);

        this.asks.forEach((ask, i) => {
            const x = scales.priceToX(ask.price);
            const y = scales.volumeToY(ask.cumulative);

            if (i === 0) {
                this.ctx.lineTo(x, this.height - this.padding.bottom);
            }
            this.ctx.lineTo(x, y);
        });

        this.ctx.strokeStyle = this.colors.askLine;
        this.ctx.lineWidth = 2;
        this.ctx.stroke();
    }

    drawMidLine(scales) {
        const x = scales.priceToX(this.midPrice);

        this.ctx.beginPath();
        this.ctx.moveTo(x, this.padding.top);
        this.ctx.lineTo(x, this.height - this.padding.bottom);
        this.ctx.strokeStyle = this.colors.midLine;
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([4, 4]);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Draw mid price label
        this.ctx.fillStyle = this.colors.midLine;
        this.ctx.font = 'bold 11px Inter, sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText(
            '$' + this.midPrice.toLocaleString(undefined, { maximumFractionDigits: 0 }),
            x,
            this.padding.top - 5
        );
    }

    drawPriceAxis(scales) {
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = '10px Inter, sans-serif';
        this.ctx.textAlign = 'center';

        const priceSteps = 5;
        const priceRange = scales.maxPrice - scales.minPrice;

        for (let i = 0; i <= priceSteps; i++) {
            const price = scales.minPrice + (i / priceSteps) * priceRange;
            const x = scales.priceToX(price);
            const label = price >= 1000 ?
                '$' + (price / 1000).toFixed(1) + 'k' :
                '$' + price.toFixed(0);

            this.ctx.fillText(label, x, this.height - 8);
        }
    }

    drawVolumeAxis(scales) {
        this.ctx.fillStyle = this.colors.text;
        this.ctx.font = '10px Inter, sans-serif';
        this.ctx.textAlign = 'right';

        const volumeSteps = 5;
        for (let i = 0; i <= volumeSteps; i++) {
            const volume = (i / volumeSteps) * scales.maxVolume;
            const y = scales.volumeToY(volume);

            const label = volume >= 1 ?
                volume.toFixed(1) :
                volume.toFixed(3);

            this.ctx.fillText(label, this.width - 5, y + 4);
        }
    }

    drawCrosshair(scales) {
        if (this.mouseX < this.padding.left ||
            this.mouseX > this.width - this.padding.right ||
            this.mouseY < this.padding.top ||
            this.mouseY > this.height - this.padding.bottom) {
            return;
        }

        // Vertical line
        this.ctx.beginPath();
        this.ctx.moveTo(this.mouseX, this.padding.top);
        this.ctx.lineTo(this.mouseX, this.height - this.padding.bottom);
        this.ctx.strokeStyle = this.colors.crosshair;
        this.ctx.lineWidth = 1;
        this.ctx.setLineDash([2, 2]);
        this.ctx.stroke();
        this.ctx.setLineDash([]);

        // Horizontal line
        this.ctx.beginPath();
        this.ctx.moveTo(this.padding.left, this.mouseY);
        this.ctx.lineTo(this.width - this.padding.right, this.mouseY);
        this.ctx.stroke();
    }

    showTooltip(e) {
        if (!this.tooltip) return;

        const scales = this.calculateScales();
        const price = scales.xToPrice(this.mouseX);

        // Find the order at this price
        let order = null;
        let side = '';

        if (price <= this.midPrice) {
            // Look in bids
            order = this.bids.find(b => b.price <= price);
            if (!order && this.bids.length > 0) {
                order = this.bids[0];
            }
            side = 'bid';
        } else {
            // Look in asks
            order = this.asks.find(a => a.price >= price);
            if (!order && this.asks.length > 0) {
                order = this.asks[this.asks.length - 1];
            }
            side = 'ask';
        }

        if (order) {
            const priceEl = this.tooltip.querySelector('.tooltip-price');
            const volumeEl = this.tooltip.querySelector('.tooltip-volume');
            const totalEl = this.tooltip.querySelector('.tooltip-total');

            priceEl.textContent = `Price: $${order.price.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
            volumeEl.textContent = `Size: ${order.size.toFixed(6)}`;
            totalEl.textContent = `Cumulative: ${order.cumulative.toFixed(4)}`;

            priceEl.className = 'tooltip-price ' + side;

            // Position tooltip
            const rect = this.canvas.getBoundingClientRect();
            let left = e.clientX - rect.left + 15;
            let top = e.clientY - rect.top - 30;

            // Keep tooltip in bounds
            if (left + 150 > this.width) {
                left = e.clientX - rect.left - 165;
            }

            this.tooltip.style.left = left + 'px';
            this.tooltip.style.top = top + 'px';
            this.tooltip.style.display = 'block';
        }
    }

    hideTooltip() {
        if (this.tooltip) {
            this.tooltip.style.display = 'none';
        }
    }
}

// Global instance
let depthChart = null;

// Initialize depth chart
function initDepthChart() {
    depthChart = new DepthChart('depthChartCanvas');
    window.depthChart = depthChart;
    console.log('[DepthChart] Initialized');
    return depthChart;
}

// Update depth chart with order book data
function updateDepthChart(bids, asks, midPrice) {
    if (depthChart) {
        depthChart.setData(bids, asks, midPrice);
    }
}

// Export for use in other modules
window.initDepthChart = initDepthChart;
window.updateDepthChart = updateDepthChart;
window.DepthChart = DepthChart;
