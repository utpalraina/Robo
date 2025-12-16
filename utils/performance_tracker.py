"""
Performance Tracker - Track and analyze paper/live trading performance.

Saves all trades and generates reports for analysis before going live.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import sqlite3
from loguru import logger


@dataclass
class TradeRecord:
    """Individual trade record."""
    id: str
    timestamp: str
    symbol: str
    side: str  # 'buy' or 'sell'
    entry_price: float
    exit_price: Optional[float]
    size: float
    pnl: Optional[float]
    pnl_pct: Optional[float]
    exit_reason: Optional[str]
    duration_seconds: Optional[float]
    is_paper: bool
    strategy: str
    confluence_score: Optional[int]
    notes: Optional[str]


@dataclass
class DailyStats:
    """Daily trading statistics."""
    date: str
    trades: int
    wins: int
    losses: int
    total_pnl: float
    win_rate: float
    avg_pnl: float
    max_win: float
    max_loss: float
    is_paper: bool


class PerformanceTracker:
    """Track and analyze trading performance."""

    def __init__(self, db_path: str = "data/performance.db"):
        """Initialize performance tracker with SQLite database."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Trades table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT,
                    symbol TEXT,
                    side TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    size REAL,
                    pnl REAL,
                    pnl_pct REAL,
                    exit_reason TEXT,
                    duration_seconds REAL,
                    is_paper INTEGER,
                    strategy TEXT,
                    confluence_score INTEGER,
                    notes TEXT
                )
            """)

            # Daily stats table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    date TEXT,
                    trades INTEGER,
                    wins INTEGER,
                    losses INTEGER,
                    total_pnl REAL,
                    win_rate REAL,
                    avg_pnl REAL,
                    max_win REAL,
                    max_loss REAL,
                    is_paper INTEGER,
                    PRIMARY KEY (date, is_paper)
                )
            """)

            # Account snapshots
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS account_snapshots (
                    timestamp TEXT PRIMARY KEY,
                    equity REAL,
                    cash REAL,
                    positions_value REAL,
                    total_pnl REAL,
                    is_paper INTEGER
                )
            """)

            conn.commit()

    def record_trade(self, trade: Dict[str, Any], is_paper: bool = True):
        """Record a completed trade."""
        trade_id = trade.get('id', f"trade_{datetime.now().timestamp()}")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO trades
                (id, timestamp, symbol, side, entry_price, exit_price, size,
                 pnl, pnl_pct, exit_reason, duration_seconds, is_paper,
                 strategy, confluence_score, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                trade.get('timestamp', datetime.now().isoformat()),
                trade.get('symbol'),
                trade.get('side'),
                trade.get('entry_price'),
                trade.get('exit_price'),
                trade.get('size'),
                trade.get('pnl'),
                trade.get('pnl_pct'),
                trade.get('exit_reason'),
                trade.get('duration_seconds'),
                1 if is_paper else 0,
                trade.get('strategy', 'default'),
                trade.get('confluence_score'),
                trade.get('notes')
            ))
            conn.commit()

        logger.debug(f"Recorded trade: {trade_id}")

    def record_account_snapshot(
        self,
        equity: float,
        cash: float,
        positions_value: float,
        total_pnl: float,
        is_paper: bool = True
    ):
        """Record account equity snapshot for tracking over time."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO account_snapshots
                (timestamp, equity, cash, positions_value, total_pnl, is_paper)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                datetime.now().isoformat(),
                equity,
                cash,
                positions_value,
                total_pnl,
                1 if is_paper else 0
            ))
            conn.commit()

    def get_trades(
        self,
        is_paper: Optional[bool] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict]:
        """Get trades with optional filtering."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = "SELECT * FROM trades WHERE 1=1"
            params = []

            if is_paper is not None:
                query += " AND is_paper = ?"
                params.append(1 if is_paper else 0)

            if start_date:
                query += " AND timestamp >= ?"
                params.append(start_date)

            if end_date:
                query += " AND timestamp <= ?"
                params.append(end_date)

            if symbol:
                query += " AND symbol = ?"
                params.append(symbol)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_daily_summary(
        self,
        days: int = 30,
        is_paper: Optional[bool] = None
    ) -> List[Dict]:
        """Get daily trading summary."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            query = """
                SELECT
                    DATE(timestamp) as date,
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losses,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as max_win,
                    MIN(pnl) as max_loss,
                    is_paper
                FROM trades
                WHERE timestamp >= ? AND exit_price IS NOT NULL
            """
            params = [cutoff]

            if is_paper is not None:
                query += " AND is_paper = ?"
                params.append(1 if is_paper else 0)

            query += " GROUP BY DATE(timestamp), is_paper ORDER BY date DESC"

            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d['win_rate'] = (d['wins'] / d['trades'] * 100) if d['trades'] > 0 else 0
                results.append(d)

            return results

    def get_overall_stats(self, is_paper: Optional[bool] = None) -> Dict:
        """Get overall trading statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            query = """
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN pnl <= 0 THEN 1 ELSE 0 END) as losing_trades,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl,
                    MAX(pnl) as largest_win,
                    MIN(pnl) as largest_loss,
                    AVG(duration_seconds) as avg_duration,
                    AVG(CASE WHEN pnl > 0 THEN pnl END) as avg_win,
                    AVG(CASE WHEN pnl < 0 THEN pnl END) as avg_loss
                FROM trades
                WHERE exit_price IS NOT NULL
            """
            params = []

            if is_paper is not None:
                query += " AND is_paper = ?"
                params.append(1 if is_paper else 0)

            cursor.execute(query, params)
            row = cursor.fetchone()

            if not row or row[0] == 0:
                return {
                    "total_trades": 0,
                    "winning_trades": 0,
                    "losing_trades": 0,
                    "win_rate": 0,
                    "total_pnl": 0,
                    "avg_pnl": 0,
                    "largest_win": 0,
                    "largest_loss": 0,
                    "profit_factor": 0,
                    "avg_duration": 0
                }

            total_trades, wins, losses, total_pnl, avg_pnl, max_win, max_loss, avg_dur, avg_win, avg_loss = row

            # Calculate profit factor
            total_wins = avg_win * wins if avg_win and wins else 0
            total_losses = abs(avg_loss * losses) if avg_loss and losses else 0
            profit_factor = total_wins / total_losses if total_losses > 0 else 0

            return {
                "total_trades": total_trades or 0,
                "winning_trades": wins or 0,
                "losing_trades": losses or 0,
                "win_rate": (wins / total_trades * 100) if total_trades else 0,
                "total_pnl": total_pnl or 0,
                "avg_pnl": avg_pnl or 0,
                "largest_win": max_win or 0,
                "largest_loss": max_loss or 0,
                "profit_factor": profit_factor,
                "avg_duration_seconds": avg_dur or 0
            }

    def get_equity_curve(
        self,
        is_paper: Optional[bool] = None,
        days: int = 30
    ) -> List[Dict]:
        """Get equity curve data for charting."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()

            query = """
                SELECT timestamp, equity, total_pnl, is_paper
                FROM account_snapshots
                WHERE timestamp >= ?
            """
            params = [cutoff]

            if is_paper is not None:
                query += " AND is_paper = ?"
                params.append(1 if is_paper else 0)

            query += " ORDER BY timestamp"

            cursor.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_symbol_performance(self, is_paper: Optional[bool] = None) -> List[Dict]:
        """Get performance breakdown by symbol."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT
                    symbol,
                    COUNT(*) as trades,
                    SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                    SUM(pnl) as total_pnl,
                    AVG(pnl) as avg_pnl
                FROM trades
                WHERE exit_price IS NOT NULL
            """
            params = []

            if is_paper is not None:
                query += " AND is_paper = ?"
                params.append(1 if is_paper else 0)

            query += " GROUP BY symbol ORDER BY total_pnl DESC"

            cursor.execute(query, params)
            results = []
            for row in cursor.fetchall():
                d = dict(row)
                d['win_rate'] = (d['wins'] / d['trades'] * 100) if d['trades'] > 0 else 0
                results.append(d)

            return results

    def generate_report(self, is_paper: bool = True) -> str:
        """Generate a text report of trading performance."""
        stats = self.get_overall_stats(is_paper)
        daily = self.get_daily_summary(7, is_paper)
        symbols = self.get_symbol_performance(is_paper)

        mode = "PAPER" if is_paper else "LIVE"

        report = f"""
{'='*60}
{mode} TRADING PERFORMANCE REPORT
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
{'='*60}

OVERALL STATISTICS
------------------
Total Trades:    {stats['total_trades']}
Winning Trades:  {stats['winning_trades']}
Losing Trades:   {stats['losing_trades']}
Win Rate:        {stats['win_rate']:.1f}%

Total PnL:       ${stats['total_pnl']:.2f}
Average PnL:     ${stats['avg_pnl']:.2f}
Largest Win:     ${stats['largest_win']:.2f}
Largest Loss:    ${stats['largest_loss']:.2f}
Profit Factor:   {stats['profit_factor']:.2f}

Avg Duration:    {stats['avg_duration_seconds']:.1f} seconds

LAST 7 DAYS
-----------
"""
        for day in daily[:7]:
            report += f"{day['date']}: {day['trades']} trades, ${day['total_pnl']:.2f} PnL, {day['win_rate']:.0f}% win rate\n"

        report += "\nPERFORMANCE BY SYMBOL\n---------------------\n"
        for sym in symbols:
            report += f"{sym['symbol']}: {sym['trades']} trades, ${sym['total_pnl']:.2f} PnL, {sym['win_rate']:.0f}% win rate\n"

        report += f"\n{'='*60}\n"

        return report

    def is_ready_for_live(self, min_trades: int = 50, min_win_rate: float = 50.0) -> Dict:
        """
        Check if paper trading results suggest readiness for live trading.

        Returns a dict with recommendation and reasoning.
        """
        stats = self.get_overall_stats(is_paper=True)

        checks = {
            "sufficient_trades": stats['total_trades'] >= min_trades,
            "positive_pnl": stats['total_pnl'] > 0,
            "good_win_rate": stats['win_rate'] >= min_win_rate,
            "positive_profit_factor": stats['profit_factor'] > 1.0,
        }

        all_passed = all(checks.values())

        reasons = []
        if not checks['sufficient_trades']:
            reasons.append(f"Need more trades ({stats['total_trades']}/{min_trades})")
        if not checks['positive_pnl']:
            reasons.append(f"PnL is negative (${stats['total_pnl']:.2f})")
        if not checks['good_win_rate']:
            reasons.append(f"Win rate too low ({stats['win_rate']:.1f}%/{min_win_rate}%)")
        if not checks['positive_profit_factor']:
            reasons.append(f"Profit factor < 1 ({stats['profit_factor']:.2f})")

        return {
            "ready": all_passed,
            "checks": checks,
            "stats": stats,
            "reasons": reasons if reasons else ["All criteria met!"],
            "recommendation": "Ready for live trading with small position sizes" if all_passed else "Continue paper trading"
        }


# Singleton instance
_tracker: Optional[PerformanceTracker] = None


def get_tracker() -> PerformanceTracker:
    """Get or create performance tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = PerformanceTracker()
    return _tracker


if __name__ == "__main__":
    # Test the tracker
    tracker = PerformanceTracker()

    # Add a sample trade
    tracker.record_trade({
        "id": "test_trade_1",
        "symbol": "BTC/USD",
        "side": "buy",
        "entry_price": 87000,
        "exit_price": 87500,
        "size": 0.01,
        "pnl": 5.0,
        "pnl_pct": 0.57,
        "exit_reason": "take_profit",
        "duration_seconds": 120,
        "strategy": "scalping"
    }, is_paper=True)

    print(tracker.generate_report(is_paper=True))
    print("\nReadiness check:")
    print(tracker.is_ready_for_live())
