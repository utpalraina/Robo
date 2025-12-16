// Backtest Simulation Page JavaScript

class BacktestSimulator {
    constructor() {
        this.isRunning = false;
        this.results = [];
        this.init();
    }

    init() {
        this.bindEvents();
        this.updateSummary();
    }

    bindEvents() {
        // Input change events
        document.getElementById('capital').addEventListener('input', () => this.updateSummary());
        document.getElementById('risk-percent').addEventListener('input', () => this.updateSummary());
        document.getElementById('num-days').addEventListener('input', () => this.updateSummary());
        document.getElementById('trades-per-day').addEventListener('input', () => this.updateSummary());

        // Run backtest button
        document.getElementById('run-backtest').addEventListener('click', () => this.runBacktest());
    }

    updateSummary() {
        const capital = parseFloat(document.getElementById('capital').value) || 0;
        const riskPercent = parseFloat(document.getElementById('risk-percent').value) || 0;
        const numDays = parseInt(document.getElementById('num-days').value) || 0;
        const tradesPerDay = parseInt(document.getElementById('trades-per-day').value) || 0;

        const totalTrades = numDays * tradesPerDay;
        const riskPerTrade = capital * (riskPercent / 100);

        document.getElementById('total-trades').textContent = totalTrades;
        document.getElementById('risk-per-trade').textContent = `$${riskPerTrade.toFixed(2)}`;
        document.getElementById('max-risk').textContent = `${riskPercent}%`;
    }

    async runBacktest() {
        if (this.isRunning) return;

        const config = {
            capital: parseFloat(document.getElementById('capital').value),
            riskPercent: parseFloat(document.getElementById('risk-percent').value),
            startDate: document.getElementById('start-date').value,
            numDays: parseInt(document.getElementById('num-days').value),
            tradesPerDay: parseInt(document.getElementById('trades-per-day').value),
            symbol: document.getElementById('symbol').value
        };

        // Validate inputs
        if (!config.capital || config.capital < 100) {
            alert('Please enter a valid capital amount (minimum $100)');
            return;
        }

        this.isRunning = true;
        this.showProgress(config.numDays * config.tradesPerDay);

        try {
            const response = await fetch('/api/ai-backtest', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config)
            });

            if (!response.ok) {
                throw new Error(`Backtest failed: ${response.statusText}`);
            }

            const results = await response.json();
            this.displayResults(results, config);
        } catch (error) {
            console.error('Backtest error:', error);
            alert(`Backtest failed: ${error.message}`);
            this.hideProgress();
        } finally {
            this.isRunning = false;
        }
    }

    showProgress(totalTrades) {
        document.getElementById('progress-panel').style.display = 'block';
        document.getElementById('results-panel').style.display = 'none';
        document.getElementById('progress-total').textContent = totalTrades;
        document.getElementById('progress-current').textContent = '0';
        document.getElementById('progress-bar').style.width = '0%';
        document.getElementById('progress-status').textContent = 'Starting backtest...';

        // Disable run button
        const btn = document.getElementById('run-backtest');
        btn.disabled = true;
        btn.querySelector('.btn-text').style.display = 'none';
        btn.querySelector('.btn-loading').style.display = 'inline';
    }

    hideProgress() {
        document.getElementById('progress-panel').style.display = 'none';

        // Re-enable run button
        const btn = document.getElementById('run-backtest');
        btn.disabled = false;
        btn.querySelector('.btn-text').style.display = 'inline';
        btn.querySelector('.btn-loading').style.display = 'none';
    }

    displayResults(data, config) {
        this.hideProgress();
        document.getElementById('results-panel').style.display = 'block';

        const { results, summary } = data;
        const riskPerTrade = config.capital * (config.riskPercent / 100);

        // Summary cards
        const totalPnL = summary.totalR * riskPerTrade;
        const finalCapital = config.capital + totalPnL;
        const roi = (totalPnL / config.capital) * 100;

        document.getElementById('result-pnl').textContent = `${totalPnL >= 0 ? '+' : ''}$${totalPnL.toFixed(2)}`;
        document.getElementById('result-final-capital').textContent = `$${finalCapital.toFixed(2)}`;
        document.getElementById('result-roi').textContent = `${roi >= 0 ? '+' : ''}${roi.toFixed(1)}%`;
        document.getElementById('result-winrate').textContent = `${summary.winRate.toFixed(1)}%`;

        // Update card colors
        const pnlCard = document.getElementById('result-pnl').closest('.result-card');
        pnlCard.classList.remove('positive', 'negative');
        pnlCard.classList.add(totalPnL >= 0 ? 'positive' : 'negative');

        // Detailed stats
        document.getElementById('stat-total-trades').textContent = summary.totalTrades;
        document.getElementById('stat-wins').textContent = summary.wins;
        document.getElementById('stat-losses').textContent = summary.losses;
        document.getElementById('stat-skipped').textContent = summary.skipped;
        document.getElementById('stat-total-r').textContent = `${summary.totalR >= 0 ? '+' : ''}${summary.totalR.toFixed(2)}R`;
        document.getElementById('stat-avg-r').textContent = summary.totalTrades > 0
            ? `${(summary.totalR / summary.totalTrades).toFixed(2)}R`
            : '0R';
        document.getElementById('stat-max-dd').textContent = `$${(summary.maxDrawdown * riskPerTrade).toFixed(2)} (${summary.maxDrawdown.toFixed(1)}R)`;

        // By direction
        document.getElementById('stat-long-trades').textContent = summary.longTrades;
        document.getElementById('stat-long-winrate').textContent = summary.longTrades > 0
            ? `${(summary.longWins / summary.longTrades * 100).toFixed(0)}%`
            : 'N/A';
        document.getElementById('stat-short-trades').textContent = summary.shortTrades;
        document.getElementById('stat-short-winrate').textContent = summary.shortTrades > 0
            ? `${(summary.shortWins / summary.shortTrades * 100).toFixed(0)}%`
            : 'N/A';

        // Trade log
        this.renderTradeLog(results, riskPerTrade);
    }

    renderTradeLog(results, riskPerTrade) {
        const tbody = document.getElementById('trade-log-body');
        tbody.innerHTML = '';

        let cumR = 0;
        results.forEach((trade, index) => {
            if (trade.outcome !== 'N/A') {
                cumR += trade.rMultiple || 0;
            }

            const row = document.createElement('tr');

            const directionClass = trade.direction === 'LONG' ? 'long' :
                                   trade.direction === 'SHORT' ? 'short' : 'skip';

            const outcomeClass = trade.outcome === 'TP_HIT' ? 'win' :
                                 trade.outcome === 'SL_HIT' ? 'loss' : 'skip';

            const rDisplay = trade.direction === 'NO_TRADE' ? '---' :
                             trade.rMultiple !== undefined ? `${trade.rMultiple >= 0 ? '+' : ''}${trade.rMultiple.toFixed(1)}R` : '---';

            row.innerHTML = `
                <td>${index + 1}</td>
                <td>${this.formatDate(trade.date)}</td>
                <td>$${trade.price?.toLocaleString() || '---'}</td>
                <td>${trade.signal || '---'}</td>
                <td class="${directionClass}">${trade.direction}</td>
                <td class="${outcomeClass}">${this.formatOutcome(trade.outcome)}</td>
                <td class="${outcomeClass}">${rDisplay}</td>
                <td>${cumR >= 0 ? '+' : ''}${cumR.toFixed(1)}R</td>
            `;

            tbody.appendChild(row);
        });

        document.getElementById('log-count').textContent = `(${results.length} trades)`;
    }

    formatDate(dateStr) {
        if (!dateStr) return '---';
        const date = new Date(dateStr);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    formatOutcome(outcome) {
        switch (outcome) {
            case 'TP_HIT': return 'WIN';
            case 'SL_HIT': return 'LOSS';
            case 'OPEN': return 'OPEN';
            case 'N/A': return '---';
            default: return outcome || '---';
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.simulator = new BacktestSimulator();
});
