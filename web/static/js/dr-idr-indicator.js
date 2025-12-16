/**
 * DR/IDR (Defining Range / Initial Defining Range) Indicator
 *
 * Sessions (New York Time):
 * - NY: 9:30-10:30 AM (extends to 4:00 PM)
 * - London: 3:00-4:00 AM NY (8:00-9:00 AM London)
 * - Asia: 7:00-8:00 PM NY (8:00-9:00 AM Tokyo)
 */

class DRIDRIndicator {
    constructor() {
        this.enabled = true;
        this.sessions = [];
        this.drLines = [];
        this.idrBox = null;

        // Settings
        this.settings = {
            showDR: true,           // DR High/Low lines (gray solid)
            showIDR: true,          // IDR High/Low lines (red dashed)
            showMiddleDR: false,    // DR Midpoint
            showMiddleIDR: true,    // IDR Midpoint (red dotted)
            showOpen: true,         // Opening price (green dotted)
            showSTD: true,          // Standard deviation levels
            stdLevels: 5,           // Number of STD levels each side
            showNY: true,           // New York session
            showLondon: false,      // London session
            showAsia: false,        // Asia session
            showBox: true,          // IDR shaded box
        };

        // Colors
        this.colors = {
            drHigh: '#4a4a4a',      // Dark gray for DR High
            drLow: '#4a4a4a',       // Dark gray for DR Low
            drMid: '#808080',       // Gray for DR Mid
            idrHigh: '#ef4444',     // Red for IDR High
            idrLow: '#ef4444',      // Red for IDR Low
            idrMid: '#ef4444',      // Red for IDR Mid
            open: '#22c55e',        // Green for Open
            std: '#808080',         // Gray for STD levels
            boxBg: 'rgba(128, 128, 128, 0.1)',  // Light gray box
        };
    }

    async fetchDRIDR(symbol = 'BTC/USD') {
        try {
            const response = await fetch(`/api/dr-idr/${encodeURIComponent(symbol)}?timeframe=5m`);
            const data = await response.json();

            if (data.error) {
                console.warn('DR/IDR fetch error:', data.error);
                return null;
            }

            this.sessions = data.sessions || [];
            return data;
        } catch (error) {
            console.error('Failed to fetch DR/IDR:', error);
            return null;
        }
    }

    drawOnChart(chart, candleSeries) {
        if (!chart || !candleSeries || !this.enabled) return;

        // Clear existing lines
        this.clearLines();

        // Get the latest NY session
        const nySession = this.sessions.find(s => s.session === 'NY');
        if (!nySession) {
            console.log('No NY session found');
            return;
        }

        const dr = nySession.dr;
        const idr = nySession.idr;

        console.log('Drawing DR/IDR:', { dr, idr });

        // Draw DR lines (solid black)
        if (this.settings.showDR) {
            // DR High
            this.drLines.push(candleSeries.createPriceLine({
                price: dr.high,
                color: this.colors.drHigh,
                lineWidth: 1,
                lineStyle: 0, // Solid
                axisLabelVisible: true,
                title: 'DR High',
            }));

            // DR Low
            this.drLines.push(candleSeries.createPriceLine({
                price: dr.low,
                color: this.colors.drLow,
                lineWidth: 1,
                lineStyle: 0, // Solid
                axisLabelVisible: true,
                title: 'DR Low',
            }));
        }

        // Draw IDR lines (dashed red)
        if (this.settings.showIDR) {
            // IDR High
            this.drLines.push(candleSeries.createPriceLine({
                price: idr.high,
                color: this.colors.idrHigh,
                lineWidth: 1,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: 'IDR High',
            }));

            // IDR Low
            this.drLines.push(candleSeries.createPriceLine({
                price: idr.low,
                color: this.colors.idrLow,
                lineWidth: 1,
                lineStyle: 2, // Dashed
                axisLabelVisible: true,
                title: 'IDR Low',
            }));
        }

        // Draw IDR Middle (dotted red)
        if (this.settings.showMiddleIDR) {
            this.drLines.push(candleSeries.createPriceLine({
                price: idr.middle,
                color: this.colors.idrMid,
                lineWidth: 1,
                lineStyle: 1, // Dotted
                axisLabelVisible: false,
                title: 'IDR Mid',
            }));
        }

        // Draw DR Middle (dotted gray)
        if (this.settings.showMiddleDR) {
            this.drLines.push(candleSeries.createPriceLine({
                price: dr.middle,
                color: this.colors.drMid,
                lineWidth: 1,
                lineStyle: 1, // Dotted
                axisLabelVisible: false,
                title: 'DR Mid',
            }));
        }

        // Draw Opening price (dotted green)
        if (this.settings.showOpen && nySession.session_open) {
            this.drLines.push(candleSeries.createPriceLine({
                price: nySession.session_open,
                color: this.colors.open,
                lineWidth: 1,
                lineStyle: 1, // Dotted
                axisLabelVisible: false,
                title: 'Open',
            }));
        }

        // Draw STD levels (dotted gray)
        if (this.settings.showSTD && nySession.std_levels) {
            const stdLevels = nySession.std_levels.slice(0, this.settings.stdLevels * 2);
            stdLevels.forEach((std, i) => {
                this.drLines.push(candleSeries.createPriceLine({
                    price: std.level,
                    color: this.colors.std,
                    lineWidth: 1,
                    lineStyle: 1, // Dotted
                    axisLabelVisible: i < 4, // Only show label for first few
                    title: std.label,
                }));
            });
        }

        console.log(`Drew ${this.drLines.length} DR/IDR lines`);
    }

    clearLines() {
        // Note: LightweightCharts doesn't have a direct way to remove price lines
        // They persist until the series is removed or chart is recreated
        // This is a limitation - we just track them for reference
        this.drLines = [];
    }

    toggle() {
        this.enabled = !this.enabled;
        return this.enabled;
    }

    updateSettings(newSettings) {
        this.settings = { ...this.settings, ...newSettings };
    }

    getSummary() {
        const nySession = this.sessions.find(s => s.session === 'NY');
        if (!nySession) return null;

        return {
            session: 'New York',
            date: nySession.date,
            dr: nySession.dr,
            idr: nySession.idr,
            open: nySession.session_open,
            range: nySession.dr.range,
            idrRange: nySession.idr.range,
        };
    }
}

// Initialize and expose globally
window.drIdrIndicator = new DRIDRIndicator();

// Auto-load when chart is ready
document.addEventListener('DOMContentLoaded', async () => {
    // Wait for chart to be initialized
    setTimeout(async () => {
        if (window.state && window.state.charts && window.state.charts[0] && window.state.candleSeries && window.state.candleSeries[0]) {
            console.log('Initializing DR/IDR indicator...');

            // Fetch and draw DR/IDR
            const data = await window.drIdrIndicator.fetchDRIDR('BTC/USD');
            if (data) {
                window.drIdrIndicator.drawOnChart(
                    window.state.charts[0],
                    window.state.candleSeries[0]
                );

                // Log summary
                const summary = window.drIdrIndicator.getSummary();
                if (summary) {
                    console.log('DR/IDR Summary:', summary);
                }
            }
        }
    }, 3000); // Wait 3 seconds for chart to load
});

// Expose refresh function
window.refreshDRIDR = async function() {
    if (window.state && window.state.charts && window.state.charts[0] && window.state.candleSeries && window.state.candleSeries[0]) {
        const data = await window.drIdrIndicator.fetchDRIDR('BTC/USD');
        if (data) {
            window.drIdrIndicator.drawOnChart(
                window.state.charts[0],
                window.state.candleSeries[0]
            );
        }
    }
};

console.log('DR/IDR Indicator loaded. Use window.refreshDRIDR() to refresh levels.');
