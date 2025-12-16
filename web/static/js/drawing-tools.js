/**
 * Drawing Tools for Robo Trader Pro
 * Provides TradingView-style drawing capabilities on Lightweight Charts
 */

class DrawingTools {
    constructor(chartContainer, chart, candleSeries) {
        this.chartContainer = chartContainer;
        this.chart = chart;
        this.candleSeries = candleSeries;

        // State
        this.currentTool = 'cursor';
        this.isDrawing = false;
        this.magnetMode = false;
        this.drawings = [];
        this.selectedDrawing = null;
        this.drawingId = 0;

        // Current drawing state
        this.startPoint = null;
        this.endPoint = null;
        this.tempDrawing = null;

        // Canvas for custom drawings
        this.canvas = null;
        this.ctx = null;

        // Price data for magnet mode
        this.priceData = [];

        // Colors
        this.colors = {
            trendline: '#2962ff',
            ray: '#2962ff',
            horizontal: '#ff6d00',
            vertical: '#ff6d00',
            extended: '#2962ff',
            fibonacci: '#9c27b0',
            rectangle: 'rgba(33, 150, 243, 0.2)',
            rectangleBorder: '#2196f3',
            ellipse: 'rgba(156, 39, 176, 0.2)',
            ellipseBorder: '#9c27b0',
            priceRange: 'rgba(76, 175, 80, 0.2)',
            priceRangeBorder: '#4caf50',
            text: '#ffffff',
            arrow: '#f44336',
            selected: '#00e676'
        };

        // Fibonacci levels
        this.fibLevels = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1];
        this.fibExtLevels = [0, 0.618, 1, 1.618, 2.618, 4.236];
        this.fibColors = [
            '#787b86', '#f44336', '#4caf50', '#2196f3',
            '#ff9800', '#9c27b0', '#787b86'
        ];

        this.init();
    }

    init() {
        console.log('[DrawingTools] Initializing...');
        console.log('[DrawingTools] Chart container:', this.chartContainer);
        console.log('[DrawingTools] Chart:', this.chart);
        console.log('[DrawingTools] CandleSeries:', this.candleSeries);

        this.createCanvas();
        this.bindEvents();
        this.loadDrawings();
        this.initToolbarEvents();
        this.initKeyboardShortcuts();

        console.log('[DrawingTools] Initialization complete');
    }

    createCanvas() {
        // Create overlay canvas for drawings
        this.canvas = document.createElement('canvas');
        this.canvas.className = 'drawing-canvas';
        this.canvas.id = 'drawingCanvas';
        this.canvas.style.cssText = `
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            pointer-events: none;
            z-index: 50;
        `;

        // Append canvas directly to the chart container
        this.chartContainer.style.position = 'relative';
        this.chartContainer.appendChild(this.canvas);

        console.log('[DrawingTools] Canvas created and appended to:', this.chartContainer);
        console.log('[DrawingTools] Canvas element:', this.canvas);

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();

        // Handle resize
        const resizeObserver = new ResizeObserver(() => this.resizeCanvas());
        resizeObserver.observe(this.chartContainer);
    }

    resizeCanvas() {
        const rect = this.chartContainer.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
        this.redrawAll();
    }

    bindEvents() {
        // Mouse events on canvas (for drawing mode)
        this.canvas.addEventListener('mousedown', (e) => this.onMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.onMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.onMouseUp(e));
        this.canvas.addEventListener('dblclick', (e) => this.onDoubleClick(e));
        this.canvas.addEventListener('contextmenu', (e) => this.onContextMenu(e));

        // Also bind to chart container for cursor mode selection
        this.chartContainer.addEventListener('mousedown', (e) => {
            // Ignore clicks on the selection toolbar
            if (e.target.closest('.drawing-selection-toolbar')) {
                console.log('[DrawingTools] Click on selection toolbar, ignoring');
                return;
            }

            if (this.currentTool === 'cursor' || this.currentTool === 'crosshair') {
                this.onMouseDown(e);
            }
        });

        // Subscribe to chart visible range changes to redraw
        this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
            this.redrawAll();
        });

        // Subscribe to crosshair move for coordinates
        this.chart.subscribeCrosshairMove((param) => {
            if (this.isDrawing && param.point) {
                this.updateDrawingPreview(param);
            }
        });
    }

    initToolbarEvents() {
        const toolbar = document.getElementById('drawingToolbar');
        if (!toolbar) return;

        toolbar.querySelectorAll('.drawing-tool-btn-h').forEach(btn => {
            btn.addEventListener('click', () => {
                const tool = btn.dataset.tool;

                if (tool === 'magnet') {
                    this.toggleMagnetMode();
                    btn.classList.toggle('active', this.magnetMode);
                } else if (tool === 'delete') {
                    // If a drawing is selected, delete only that drawing
                    // Otherwise, delete all drawings with confirmation
                    if (this.selectedDrawing) {
                        this.deleteDrawing(this.selectedDrawing);
                    } else {
                        this.deleteAllDrawings();
                    }
                } else {
                    this.selectTool(tool);
                }
            });
        });
    }

    initKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Don't trigger if typing in an input
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;

            switch(e.key.toLowerCase()) {
                case 'escape':
                    this.selectTool('cursor');
                    this.cancelDrawing();
                    break;
                case 't':
                    this.selectTool('trendline');
                    break;
                case 'r':
                    this.selectTool('ray');
                    break;
                case 'h':
                    this.selectTool('horizontal');
                    break;
                case 'v':
                    this.selectTool('vertical');
                    break;
                case 'f':
                    this.selectTool('fibonacci');
                    break;
                case 'g':
                    this.selectTool('rectangle');
                    break;
                case 'x':
                    this.selectTool('text');
                    break;
                case 'm':
                    this.toggleMagnetMode();
                    break;
                case 'delete':
                case 'backspace':
                    if (this.selectedDrawing) {
                        this.deleteDrawing(this.selectedDrawing);
                    }
                    break;
            }
        });
    }

    selectTool(tool) {
        this.currentTool = tool;
        this.cancelDrawing();

        // Update toolbar UI
        document.querySelectorAll('.drawing-tool-btn-h').forEach(btn => {
            if (btn.dataset.tool !== 'magnet' && btn.dataset.tool !== 'delete') {
                btn.classList.toggle('active', btn.dataset.tool === tool);
            }
        });

        // Update cursor and pointer events
        if (tool === 'cursor' || tool === 'crosshair') {
            this.chartContainer.style.cursor = tool === 'crosshair' ? 'crosshair' : 'default';
            this.canvas.style.pointerEvents = 'none';
            this.canvas.style.cursor = 'default';
        } else {
            this.chartContainer.style.cursor = 'crosshair';
            this.canvas.style.pointerEvents = 'auto';
            this.canvas.style.cursor = 'crosshair';
        }

        console.log(`[DrawingTools] Selected tool: ${tool}, pointer-events: ${this.canvas.style.pointerEvents}`);
    }

    toggleMagnetMode() {
        this.magnetMode = !this.magnetMode;
        document.querySelector('.magnet-btn')?.classList.toggle('active', this.magnetMode);
        this.showNotification(`Magnet mode ${this.magnetMode ? 'enabled' : 'disabled'}`);
    }

    // Convert pixel coordinates to price/time
    pixelToCoordinates(x, y) {
        const timeCoord = this.chart.timeScale().coordinateToTime(x);
        const priceCoord = this.candleSeries.coordinateToPrice(y);

        // If coordinateToTime returns null, estimate time based on visible range
        let time = timeCoord;
        if (time === null) {
            const timeRange = this.chart.timeScale().getVisibleLogicalRange();
            if (timeRange) {
                // Estimate time based on x position
                const chartWidth = this.canvas.width;
                const ratio = x / chartWidth;
                time = Math.floor(timeRange.from + (timeRange.to - timeRange.from) * ratio);
            }
        }

        return { time: time, price: priceCoord };
    }

    // Convert price/time to pixel coordinates
    coordinatesToPixel(time, price) {
        const x = this.chart.timeScale().timeToCoordinate(time);
        const y = this.candleSeries.priceToCoordinate(price);

        // Return null coordinates if conversion fails
        if (x === null || y === null) {
            return { x: null, y: null };
        }

        return { x, y };
    }

    // Apply magnet mode - snap to OHLC
    applyMagnet(coords, x, y) {
        if (!this.magnetMode || !coords.time) return coords;

        // Find the candle at this time
        const candleData = this.priceData.find(c => c.time === coords.time);
        if (!candleData) return coords;

        // Find closest OHLC value
        const prices = [candleData.open, candleData.high, candleData.low, candleData.close];
        let closestPrice = coords.price;
        let minDist = Infinity;

        prices.forEach(price => {
            const pY = this.candleSeries.priceToCoordinate(price);
            const dist = Math.abs(pY - y);
            if (dist < minDist && dist < 20) { // 20px threshold
                minDist = dist;
                closestPrice = price;
            }
        });

        return { time: coords.time, price: closestPrice };
    }

    // Set price data for magnet mode
    setPriceData(data) {
        this.priceData = data;
    }

    onMouseDown(e) {
        // Get coordinates relative to the chart container
        const rect = this.chartContainer.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        console.log(`[DrawingTools] MouseDown at (${x}, ${y}), tool: ${this.currentTool}, isDrawing: ${this.isDrawing}`);

        if (this.currentTool === 'cursor' || this.currentTool === 'crosshair') {
            // Check if clicking on existing drawing
            const drawing = this.findDrawingAtPoint(x, y);
            if (drawing) {
                this.selectDrawing(drawing);
                return;
            }
            this.deselectDrawing();
            return;
        }

        let coords = this.pixelToCoordinates(x, y);
        console.log(`[DrawingTools] Coordinates: time=${coords.time}, price=${coords.price}`);

        coords = this.applyMagnet(coords, x, y);

        if (!this.isDrawing) {
            // Start drawing
            this.isDrawing = true;
            this.startPoint = { ...coords, x, y };
            console.log(`[DrawingTools] Started drawing at:`, this.startPoint);

            // For single-click tools
            if (this.currentTool === 'horizontal' || this.currentTool === 'vertical') {
                this.endPoint = { ...coords, x, y };
                this.finishDrawing();
            }
        } else {
            // Second click - finish drawing
            this.endPoint = { ...coords, x, y };
            console.log(`[DrawingTools] Finishing drawing at:`, this.endPoint);
            this.finishDrawing();
        }
    }

    onMouseMove(e) {
        if (!this.isDrawing) return;

        const rect = this.chartContainer.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;

        let coords = this.pixelToCoordinates(x, y);
        coords = this.applyMagnet(coords, x, y);

        this.endPoint = { ...coords, x, y };
        this.redrawAll();
        this.drawPreview();
    }

    onMouseUp(e) {
        // For drag-based tools, finish on mouse up
        if (this.isDrawing && (this.currentTool === 'rectangle' ||
            this.currentTool === 'ellipse' || this.currentTool === 'price-range')) {
            const rect = this.chartContainer.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            let coords = this.pixelToCoordinates(x, y);
            this.endPoint = { ...coords, x, y };
            this.finishDrawing();
        }
    }

    onDoubleClick(e) {
        if (this.currentTool === 'text') {
            const rect = this.chartContainer.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;

            const coords = this.pixelToCoordinates(x, y);
            this.promptForText(coords);
        }
    }

    onContextMenu(e) {
        e.preventDefault();
        const drawing = this.findDrawingAtPoint(e.offsetX, e.offsetY);
        if (drawing) {
            this.showContextMenu(e, drawing);
        }
    }

    updateDrawingPreview(param) {
        if (!this.isDrawing || !param.point) return;

        let coords = {
            time: param.time,
            price: param.seriesData.get(this.candleSeries)?.close || 0
        };

        if (param.point) {
            coords = this.pixelToCoordinates(param.point.x, param.point.y);
            coords = this.applyMagnet(coords, param.point.x, param.point.y);
        }

        this.endPoint = { ...coords, x: param.point?.x, y: param.point?.y };
        this.redrawAll();
        this.drawPreview();
    }

    cancelDrawing() {
        this.isDrawing = false;
        this.startPoint = null;
        this.endPoint = null;
        this.tempDrawing = null;
        this.redrawAll();
    }

    finishDrawing() {
        if (!this.startPoint) return;

        const drawing = {
            id: ++this.drawingId,
            type: this.currentTool,
            startTime: this.startPoint.time,
            startPrice: this.startPoint.price,
            endTime: this.endPoint?.time || this.startPoint.time,
            endPrice: this.endPoint?.price || this.startPoint.price,
            color: this.colors[this.currentTool.replace('-', '')] || this.colors.trendline,
            text: '',
            visible: true
        };

        this.drawings.push(drawing);
        this.saveDrawings();

        this.isDrawing = false;
        this.startPoint = null;
        this.endPoint = null;

        this.redrawAll();

        // Return to cursor after drawing
        if (this.currentTool !== 'trendline' && this.currentTool !== 'ray') {
            this.selectTool('cursor');
        }
    }

    promptForText(coords) {
        const text = prompt('Enter text:');
        if (text) {
            const drawing = {
                id: ++this.drawingId,
                type: 'text',
                startTime: coords.time,
                startPrice: coords.price,
                endTime: coords.time,
                endPrice: coords.price,
                color: this.colors.text,
                text: text,
                visible: true
            };
            this.drawings.push(drawing);
            this.saveDrawings();
            this.redrawAll();
        }
        this.selectTool('cursor');
    }

    // Drawing methods
    drawPreview() {
        if (!this.startPoint || !this.endPoint) return;

        this.ctx.save();
        this.ctx.setLineDash([5, 5]);
        this.ctx.globalAlpha = 0.7;

        this.drawShape(this.currentTool, this.startPoint, this.endPoint, this.colors[this.currentTool.replace('-', '')] || '#2962ff');

        this.ctx.restore();
    }

    drawShape(type, start, end, color, drawing = null) {
        const startPixel = this.coordinatesToPixel(start.time || start.startTime, start.price || start.startPrice);
        const endPixel = this.coordinatesToPixel(end.time || end.endTime, end.price || end.endPrice);

        if (!startPixel.x || !startPixel.y || !endPixel.x || !endPixel.y) return;

        this.ctx.strokeStyle = color;
        this.ctx.fillStyle = color;
        this.ctx.lineWidth = 1.5;

        switch(type) {
            case 'trendline':
                this.drawLine(startPixel, endPixel);
                break;
            case 'ray':
                this.drawRay(startPixel, endPixel);
                break;
            case 'horizontal':
                this.drawHorizontalLine(startPixel.y);
                this.drawPriceLabel(start.price || start.startPrice, color);
                break;
            case 'vertical':
                this.drawVerticalLine(startPixel.x);
                break;
            case 'extended':
                this.drawExtendedLine(startPixel, endPixel);
                break;
            case 'fibonacci':
                this.drawFibonacciRetracement(startPixel, endPixel, start, end);
                break;
            case 'fib-extension':
                this.drawFibonacciExtension(startPixel, endPixel, start, end);
                break;
            case 'rectangle':
                this.drawRectangle(startPixel, endPixel);
                break;
            case 'ellipse':
                this.drawEllipse(startPixel, endPixel);
                break;
            case 'price-range':
                this.drawPriceRange(startPixel, endPixel, start, end);
                break;
            case 'arrow':
                this.drawArrow(startPixel, endPixel);
                break;
            case 'text':
                if (drawing && drawing.text) {
                    this.drawText(startPixel, drawing.text);
                }
                break;
        }
    }

    drawLine(start, end) {
        this.ctx.beginPath();
        this.ctx.moveTo(start.x, start.y);
        this.ctx.lineTo(end.x, end.y);
        this.ctx.stroke();

        // Draw anchor points
        this.drawAnchor(start.x, start.y);
        this.drawAnchor(end.x, end.y);
    }

    drawRay(start, end) {
        // Extend the line from start through end
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const length = Math.sqrt(dx * dx + dy * dy);
        const extendedEnd = {
            x: end.x + (dx / length) * 5000,
            y: end.y + (dy / length) * 5000
        };

        this.ctx.beginPath();
        this.ctx.moveTo(start.x, start.y);
        this.ctx.lineTo(extendedEnd.x, extendedEnd.y);
        this.ctx.stroke();

        this.drawAnchor(start.x, start.y);
    }

    drawHorizontalLine(y) {
        this.ctx.beginPath();
        this.ctx.moveTo(0, y);
        this.ctx.lineTo(this.canvas.width, y);
        this.ctx.stroke();
    }

    drawVerticalLine(x) {
        this.ctx.beginPath();
        this.ctx.moveTo(x, 0);
        this.ctx.lineTo(x, this.canvas.height);
        this.ctx.stroke();
    }

    drawExtendedLine(start, end) {
        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const length = Math.sqrt(dx * dx + dy * dy);

        const extStart = {
            x: start.x - (dx / length) * 5000,
            y: start.y - (dy / length) * 5000
        };
        const extEnd = {
            x: end.x + (dx / length) * 5000,
            y: end.y + (dy / length) * 5000
        };

        this.ctx.beginPath();
        this.ctx.moveTo(extStart.x, extStart.y);
        this.ctx.lineTo(extEnd.x, extEnd.y);
        this.ctx.stroke();

        this.drawAnchor(start.x, start.y);
        this.drawAnchor(end.x, end.y);
    }

    drawFibonacciRetracement(startPixel, endPixel, start, end) {
        const startPrice = start.price || start.startPrice;
        const endPrice = end.price || end.endPrice;
        const priceRange = endPrice - startPrice;

        this.fibLevels.forEach((level, i) => {
            const price = startPrice + priceRange * (1 - level);
            const y = this.candleSeries.priceToCoordinate(price);

            if (y === null) return;

            this.ctx.strokeStyle = this.fibColors[i] || '#787b86';
            this.ctx.fillStyle = this.fibColors[i] || '#787b86';
            this.ctx.lineWidth = 1;

            // Draw horizontal line
            this.ctx.beginPath();
            this.ctx.moveTo(Math.min(startPixel.x, endPixel.x), y);
            this.ctx.lineTo(Math.max(startPixel.x, endPixel.x), y);
            this.ctx.stroke();

            // Draw label
            this.ctx.font = '11px Inter, sans-serif';
            const label = `${(level * 100).toFixed(1)}% (${price.toFixed(2)})`;
            this.ctx.fillText(label, Math.max(startPixel.x, endPixel.x) + 5, y + 4);
        });

        // Draw connecting line
        this.ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        this.ctx.setLineDash([2, 2]);
        this.ctx.beginPath();
        this.ctx.moveTo(startPixel.x, startPixel.y);
        this.ctx.lineTo(endPixel.x, endPixel.y);
        this.ctx.stroke();
        this.ctx.setLineDash([]);
    }

    drawFibonacciExtension(startPixel, endPixel, start, end) {
        const startPrice = start.price || start.startPrice;
        const endPrice = end.price || end.endPrice;
        const priceRange = endPrice - startPrice;

        this.fibExtLevels.forEach((level, i) => {
            const price = startPrice + priceRange * level;
            const y = this.candleSeries.priceToCoordinate(price);

            if (y === null) return;

            this.ctx.strokeStyle = this.fibColors[i] || '#787b86';
            this.ctx.fillStyle = this.fibColors[i] || '#787b86';
            this.ctx.lineWidth = level > 1 ? 1 : 1.5;
            if (level > 1) this.ctx.setLineDash([3, 3]);

            // Draw horizontal line
            this.ctx.beginPath();
            this.ctx.moveTo(Math.min(startPixel.x, endPixel.x), y);
            this.ctx.lineTo(this.canvas.width, y);
            this.ctx.stroke();
            this.ctx.setLineDash([]);

            // Draw label
            this.ctx.font = '11px Inter, sans-serif';
            const label = `${(level * 100).toFixed(1)}% (${price.toFixed(2)})`;
            this.ctx.fillText(label, this.canvas.width - 120, y + 4);
        });
    }

    drawRectangle(start, end) {
        const x = Math.min(start.x, end.x);
        const y = Math.min(start.y, end.y);
        const width = Math.abs(end.x - start.x);
        const height = Math.abs(end.y - start.y);

        // Fill
        this.ctx.fillStyle = this.colors.rectangle;
        this.ctx.fillRect(x, y, width, height);

        // Border
        this.ctx.strokeStyle = this.colors.rectangleBorder;
        this.ctx.strokeRect(x, y, width, height);

        // Anchors
        this.drawAnchor(start.x, start.y);
        this.drawAnchor(end.x, end.y);
        this.drawAnchor(start.x, end.y);
        this.drawAnchor(end.x, start.y);
    }

    drawEllipse(start, end) {
        const cx = (start.x + end.x) / 2;
        const cy = (start.y + end.y) / 2;
        const rx = Math.abs(end.x - start.x) / 2;
        const ry = Math.abs(end.y - start.y) / 2;

        this.ctx.beginPath();
        this.ctx.ellipse(cx, cy, rx, ry, 0, 0, 2 * Math.PI);

        // Fill
        this.ctx.fillStyle = this.colors.ellipse;
        this.ctx.fill();

        // Border
        this.ctx.strokeStyle = this.colors.ellipseBorder;
        this.ctx.stroke();
    }

    drawPriceRange(startPixel, endPixel, start, end) {
        const x = Math.min(startPixel.x, endPixel.x);
        const y = Math.min(startPixel.y, endPixel.y);
        const width = Math.abs(endPixel.x - startPixel.x);
        const height = Math.abs(endPixel.y - startPixel.y);

        // Fill
        this.ctx.fillStyle = this.colors.priceRange;
        this.ctx.fillRect(x, y, width, height);

        // Top and bottom lines
        this.ctx.strokeStyle = this.colors.priceRangeBorder;
        this.ctx.beginPath();
        this.ctx.moveTo(x, startPixel.y);
        this.ctx.lineTo(x + width, startPixel.y);
        this.ctx.moveTo(x, endPixel.y);
        this.ctx.lineTo(x + width, endPixel.y);
        this.ctx.stroke();

        // Price difference label
        const startPrice = start.price || start.startPrice;
        const endPrice = end.price || end.endPrice;
        const diff = endPrice - startPrice;
        const pct = ((diff / startPrice) * 100).toFixed(2);

        this.ctx.fillStyle = this.colors.priceRangeBorder;
        this.ctx.font = 'bold 12px Inter, sans-serif';
        const label = `${diff >= 0 ? '+' : ''}${diff.toFixed(2)} (${pct}%)`;
        this.ctx.fillText(label, x + width / 2 - 40, y + height / 2 + 4);
    }

    drawArrow(start, end) {
        const headLength = 15;
        const angle = Math.atan2(end.y - start.y, end.x - start.x);

        // Line
        this.ctx.strokeStyle = this.colors.arrow;
        this.ctx.lineWidth = 2;
        this.ctx.beginPath();
        this.ctx.moveTo(start.x, start.y);
        this.ctx.lineTo(end.x, end.y);
        this.ctx.stroke();

        // Arrowhead
        this.ctx.fillStyle = this.colors.arrow;
        this.ctx.beginPath();
        this.ctx.moveTo(end.x, end.y);
        this.ctx.lineTo(
            end.x - headLength * Math.cos(angle - Math.PI / 6),
            end.y - headLength * Math.sin(angle - Math.PI / 6)
        );
        this.ctx.lineTo(
            end.x - headLength * Math.cos(angle + Math.PI / 6),
            end.y - headLength * Math.sin(angle + Math.PI / 6)
        );
        this.ctx.closePath();
        this.ctx.fill();
    }

    drawText(pos, text) {
        this.ctx.font = '14px Inter, sans-serif';
        this.ctx.fillStyle = this.colors.text;
        this.ctx.fillText(text, pos.x, pos.y);
    }

    drawAnchor(x, y) {
        this.ctx.fillStyle = '#ffffff';
        this.ctx.strokeStyle = '#2962ff';
        this.ctx.lineWidth = 1;
        this.ctx.beginPath();
        this.ctx.arc(x, y, 4, 0, 2 * Math.PI);
        this.ctx.fill();
        this.ctx.stroke();
    }

    drawPriceLabel(price, color) {
        const y = this.candleSeries.priceToCoordinate(price);
        if (y === null) return;

        const text = price.toFixed(2);
        this.ctx.font = '11px Inter, sans-serif';
        const textWidth = this.ctx.measureText(text).width;

        // Background
        this.ctx.fillStyle = color;
        this.ctx.fillRect(this.canvas.width - textWidth - 10, y - 8, textWidth + 10, 16);

        // Text
        this.ctx.fillStyle = '#ffffff';
        this.ctx.fillText(text, this.canvas.width - textWidth - 5, y + 4);
    }

    redrawAll() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        this.drawings.forEach(drawing => {
            if (!drawing.visible) return;

            const color = this.selectedDrawing?.id === drawing.id ? this.colors.selected : drawing.color;

            this.drawShape(drawing.type, {
                time: drawing.startTime,
                price: drawing.startPrice
            }, {
                time: drawing.endTime,
                price: drawing.endPrice
            }, color, drawing);
        });
    }

    // Selection and editing
    findDrawingAtPoint(x, y) {
        const threshold = 15; // Increased for easier selection

        for (let i = this.drawings.length - 1; i >= 0; i--) {
            const drawing = this.drawings[i];
            if (!drawing.visible) continue;

            const startPixel = this.coordinatesToPixel(drawing.startTime, drawing.startPrice);
            const endPixel = this.coordinatesToPixel(drawing.endTime, drawing.endPrice);

            if (startPixel.x === null || endPixel.x === null) continue;

            // Check based on drawing type
            switch(drawing.type) {
                case 'horizontal':
                    if (Math.abs(y - startPixel.y) < threshold) return drawing;
                    break;
                case 'vertical':
                    if (Math.abs(x - startPixel.x) < threshold) return drawing;
                    break;
                case 'rectangle':
                case 'price-range':
                case 'ellipse':
                    if (x >= Math.min(startPixel.x, endPixel.x) - threshold &&
                        x <= Math.max(startPixel.x, endPixel.x) + threshold &&
                        y >= Math.min(startPixel.y, endPixel.y) - threshold &&
                        y <= Math.max(startPixel.y, endPixel.y) + threshold) {
                        return drawing;
                    }
                    break;
                case 'fibonacci':
                case 'fib-extension':
                    // Check if near any of the fib levels
                    const levels = drawing.type === 'fibonacci' ? this.fibLevels : this.fibExtLevels;
                    const startPrice = drawing.startPrice;
                    const endPrice = drawing.endPrice;
                    const priceRange = endPrice - startPrice;

                    for (const level of levels) {
                        const price = drawing.type === 'fibonacci'
                            ? startPrice + priceRange * (1 - level)
                            : startPrice + priceRange * level;
                        const levelY = this.candleSeries.priceToCoordinate(price);
                        if (levelY !== null && Math.abs(y - levelY) < threshold) return drawing;
                    }
                    break;
                case 'text':
                    // Check if near the text position
                    if (Math.abs(x - startPixel.x) < 50 && Math.abs(y - startPixel.y) < 20) {
                        return drawing;
                    }
                    break;
                default:
                    // Line-based drawings - distance from point to line
                    const dist = this.pointToLineDistance(x, y, startPixel, endPixel);
                    if (dist < threshold) return drawing;
            }
        }

        return null;
    }

    pointToLineDistance(px, py, start, end) {
        if (start.x === null || start.y === null || end.x === null || end.y === null) {
            return Infinity;
        }

        const dx = end.x - start.x;
        const dy = end.y - start.y;
        const lengthSquared = dx * dx + dy * dy;

        if (lengthSquared === 0) {
            return Math.sqrt((px - start.x) ** 2 + (py - start.y) ** 2);
        }

        let t = ((px - start.x) * dx + (py - start.y) * dy) / lengthSquared;
        t = Math.max(0, Math.min(1, t));

        const nearestX = start.x + t * dx;
        const nearestY = start.y + t * dy;

        return Math.sqrt((px - nearestX) ** 2 + (py - nearestY) ** 2);
    }

    selectDrawing(drawing) {
        this.selectedDrawing = drawing;
        this.redrawAll();
        this.showSelectionToolbar(drawing);
        console.log('[DrawingTools] Selected drawing:', drawing);
    }

    deselectDrawing() {
        this.selectedDrawing = null;
        this.hideSelectionToolbar();
        this.redrawAll();
    }

    showSelectionToolbar(drawing) {
        // Remove existing toolbar
        this.hideSelectionToolbar();

        // Get drawing position for toolbar placement
        const startPixel = this.coordinatesToPixel(drawing.startTime, drawing.startPrice);
        const endPixel = this.coordinatesToPixel(drawing.endTime, drawing.endPrice);

        if (startPixel.x === null) return;

        // Calculate toolbar position (above the drawing)
        const toolbarX = Math.min(startPixel.x, endPixel.x || startPixel.x);
        const toolbarY = Math.min(startPixel.y, endPixel.y || startPixel.y) - 45;

        // Create toolbar element
        const toolbar = document.createElement('div');
        toolbar.id = 'drawingSelectionToolbar';
        toolbar.className = 'drawing-selection-toolbar';
        toolbar.innerHTML = `
            <button type="button" class="selection-btn" data-action="delete" title="Delete (Del)">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3,6 5,6 21,6"/>
                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
            </button>
            <button type="button" class="selection-btn" data-action="duplicate" title="Duplicate">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2"/>
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
            </button>
            <button type="button" class="selection-btn" data-action="hide" title="${drawing.visible ? 'Hide' : 'Show'}">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    ${drawing.visible ?
                        '<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94"/><line x1="1" y1="1" x2="23" y2="23"/>' :
                        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>'}
                </svg>
            </button>
        `;

        // Position the toolbar - use higher z-index to be above canvas
        const containerRect = this.chartContainer.getBoundingClientRect();
        toolbar.style.cssText = `
            position: absolute;
            left: ${Math.max(10, toolbarX)}px;
            top: ${Math.max(10, toolbarY)}px;
            z-index: 1000;
            pointer-events: auto;
        `;

        this.chartContainer.appendChild(toolbar);

        // Store reference to current drawing for the handlers
        const currentDrawing = drawing;
        const self = this;

        // Bind toolbar button events
        toolbar.querySelectorAll('.selection-btn').forEach(btn => {
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                const action = this.dataset.action;
                console.log('[DrawingTools] Toolbar action clicked:', action, currentDrawing);

                self.handleToolbarAction(action, currentDrawing);
            });

            // Also handle mousedown to prevent chart interaction
            btn.addEventListener('mousedown', function(e) {
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();
            });
        });

        console.log('[DrawingTools] Selection toolbar shown for drawing:', drawing.id);
    }

    hideSelectionToolbar() {
        const toolbar = document.getElementById('drawingSelectionToolbar');
        if (toolbar) {
            toolbar.remove();
        }
    }

    handleToolbarAction(action, drawing) {
        console.log('[DrawingTools] handleToolbarAction:', action, drawing);

        if (!drawing) {
            console.error('[DrawingTools] No drawing provided to handleToolbarAction');
            return;
        }

        switch(action) {
            case 'delete':
                console.log('[DrawingTools] Deleting drawing:', drawing.id);
                this.deleteDrawing(drawing);
                break;
            case 'duplicate':
                console.log('[DrawingTools] Duplicating drawing:', drawing.id);
                this.duplicateDrawing(drawing);
                break;
            case 'hide':
                console.log('[DrawingTools] Toggling visibility for drawing:', drawing.id);
                drawing.visible = !drawing.visible;
                this.saveDrawings();
                this.deselectDrawing();
                this.redrawAll();
                this.showNotification(drawing.visible ? 'Drawing shown' : 'Drawing hidden');
                break;
            default:
                console.warn('[DrawingTools] Unknown action:', action);
        }
    }

    duplicateDrawing(drawing) {
        const duplicate = {
            ...drawing,
            id: ++this.drawingId,
            // Offset the duplicate slightly
            startPrice: drawing.startPrice * 1.005,
            endPrice: drawing.endPrice * 1.005
        };
        this.drawings.push(duplicate);
        this.saveDrawings();
        this.selectDrawing(duplicate);
        this.showNotification('Drawing duplicated');
    }

    deleteDrawing(drawing) {
        const index = this.drawings.findIndex(d => d.id === drawing.id);
        if (index !== -1) {
            this.drawings.splice(index, 1);
            this.selectedDrawing = null;
            this.hideSelectionToolbar();
            this.saveDrawings();
            this.redrawAll();
            this.showNotification('Drawing deleted');
        }
    }

    deleteAllDrawings() {
        if (this.drawings.length === 0) {
            this.showNotification('No drawings to delete');
            return;
        }

        if (confirm('Delete all drawings?')) {
            this.drawings = [];
            this.selectedDrawing = null;
            this.saveDrawings();
            this.redrawAll();
            this.showNotification('All drawings deleted');
        }
    }

    showContextMenu(e, drawing) {
        // Remove existing context menu
        const existing = document.querySelector('.drawing-context-menu');
        if (existing) existing.remove();

        const menu = document.createElement('div');
        menu.className = 'drawing-context-menu';
        menu.innerHTML = `
            <div class="context-item" data-action="delete">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="3,6 5,6 21,6"/>
                    <path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a2 2 0 012-2h4a2 2 0 012 2v2"/>
                </svg>
                Delete
            </div>
            <div class="context-item" data-action="duplicate">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                    <path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>
                </svg>
                Duplicate
            </div>
            <div class="context-item" data-action="hide">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/>
                    <line x1="1" y1="1" x2="23" y2="23"/>
                </svg>
                ${drawing.visible ? 'Hide' : 'Show'}
            </div>
        `;
        menu.style.cssText = `
            position: fixed;
            left: ${e.clientX}px;
            top: ${e.clientY}px;
            z-index: 1000;
        `;

        document.body.appendChild(menu);

        // Handle actions
        menu.querySelectorAll('.context-item').forEach(item => {
            item.addEventListener('click', () => {
                const action = item.dataset.action;
                switch(action) {
                    case 'delete':
                        this.deleteDrawing(drawing);
                        break;
                    case 'duplicate':
                        const duplicate = { ...drawing, id: ++this.drawingId };
                        duplicate.startPrice += (duplicate.endPrice - duplicate.startPrice) * 0.1;
                        duplicate.endPrice += (duplicate.endPrice - duplicate.startPrice) * 0.1;
                        this.drawings.push(duplicate);
                        this.saveDrawings();
                        this.redrawAll();
                        break;
                    case 'hide':
                        drawing.visible = !drawing.visible;
                        this.saveDrawings();
                        this.redrawAll();
                        break;
                }
                menu.remove();
            });
        });

        // Close on click outside
        setTimeout(() => {
            document.addEventListener('click', function closeMenu(e) {
                if (!menu.contains(e.target)) {
                    menu.remove();
                    document.removeEventListener('click', closeMenu);
                }
            });
        }, 0);
    }

    // Persistence
    saveDrawings() {
        try {
            const key = `drawings_${window.state?.symbol || 'BTC/USD'}`;
            localStorage.setItem(key, JSON.stringify(this.drawings));
        } catch (e) {
            console.error('Failed to save drawings:', e);
        }
    }

    loadDrawings() {
        try {
            const key = `drawings_${window.state?.symbol || 'BTC/USD'}`;
            const saved = localStorage.getItem(key);
            if (saved) {
                this.drawings = JSON.parse(saved);
                this.drawingId = Math.max(...this.drawings.map(d => d.id), 0);
                this.redrawAll();
            }
        } catch (e) {
            console.error('Failed to load drawings:', e);
        }
    }

    showNotification(message) {
        // Use existing notification system or create simple one
        if (window.showNotification) {
            window.showNotification(message);
        } else {
            console.log(message);

            // Create temporary notification
            const notification = document.createElement('div');
            notification.className = 'drawing-notification';
            notification.textContent = message;
            notification.style.cssText = `
                position: fixed;
                bottom: 20px;
                left: 50%;
                transform: translateX(-50%);
                background: rgba(0, 0, 0, 0.8);
                color: white;
                padding: 10px 20px;
                border-radius: 8px;
                z-index: 10000;
                font-size: 13px;
                animation: fadeInOut 2s ease-in-out;
            `;
            document.body.appendChild(notification);
            setTimeout(() => notification.remove(), 2000);
        }
    }
}

// Global instance
let drawingTools = null;

// Initialize drawing tools when chart is ready
function initDrawingTools(chartContainer, chart, candleSeries) {
    console.log('[DrawingTools] initDrawingTools called with:', {
        chartContainer,
        chart,
        candleSeries
    });

    if (!chartContainer || !chart || !candleSeries) {
        console.error('[DrawingTools] Missing required parameters!');
        return null;
    }

    drawingTools = new DrawingTools(chartContainer, chart, candleSeries);

    // Expose for debugging
    window.drawingTools = drawingTools;

    console.log('[DrawingTools] Drawing tools initialized successfully');
    return drawingTools;
}

// Export for use in other modules
window.initDrawingTools = initDrawingTools;
window.DrawingTools = DrawingTools;
