"""Backtesting engine for strategy evaluation."""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger
import matplotlib.pyplot as plt
from datetime import datetime

from strategy.ml_strategy import MLStrategy, Signal
from features.indicators import FeatureEngineer
from models.base import BaseModel


@dataclass
class Trade:
    """Represents a single trade."""
    entry_time: datetime
    entry_price: float
    size: float
    side: str  # 'buy' or 'sell'
    exit_time: Optional[datetime] = None
    exit_price: Optional[float] = None
    pnl: float = 0.0
    pnl_pct: float = 0.0
    exit_reason: str = ""


@dataclass
class BacktestResult:
    """Results from backtesting."""
    trades: List[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    total_return: float = 0.0
    annual_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    avg_win: float = 0.0
    avg_loss: float = 0.0


class Backtester:
    """Backtesting engine for trading strategies."""

    def __init__(self, config: dict):
        """
        Initialize Backtester.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.backtest_config = config.get("backtest", {})
        self.initial_capital = self.backtest_config.get("initial_capital", 10000)
        self.commission = self.backtest_config.get("commission", 0.001)

    def run(
        self,
        strategy: MLStrategy,
        data: pd.DataFrame,
        symbol: str
    ) -> BacktestResult:
        """
        Run backtest on historical data.

        Args:
            strategy: Trading strategy to test
            data: Historical OHLCV data with features
            symbol: Trading symbol

        Returns:
            BacktestResult with performance metrics
        """
        logger.info(f"Starting backtest for {symbol} with {len(data)} candles")

        # Initialize tracking variables
        capital = self.initial_capital
        position = 0  # Current position size
        entry_price = 0
        entry_time = None
        trades = []
        equity_history = []

        # Ensure data has features
        if "rsi_14" not in data.columns:
            logger.warning("Data may not have features - generating them")

        # Iterate through data
        for i in range(100, len(data) - 1):  # Start after warmup period
            current_time = data.index[i]
            current_price = data["close"].iloc[i]

            # Get historical window for signal generation
            window = data.iloc[max(0, i-200):i+1].copy()

            # Generate signal
            signal, confidence = strategy.generate_signal(window)

            # Check for exit conditions if in position
            if position > 0:
                # Check stop loss / take profit
                should_close, reason = strategy.should_close_position(current_price, signal)

                if should_close:
                    # Close position
                    exit_value = position * current_price * (1 - self.commission)
                    pnl = exit_value - (position * entry_price)
                    pnl_pct = (current_price - entry_price) / entry_price

                    trades.append(Trade(
                        entry_time=entry_time,
                        entry_price=entry_price,
                        size=position,
                        side="buy",
                        exit_time=current_time,
                        exit_price=current_price,
                        pnl=pnl,
                        pnl_pct=pnl_pct,
                        exit_reason=reason
                    ))

                    capital += exit_value
                    position = 0
                    entry_price = 0
                    strategy.update_position(0)

            # Check for entry conditions if flat
            elif position == 0 and signal == Signal.BUY and confidence >= 0.6:
                # Calculate position size
                position_size = strategy.calculate_position_size(capital, current_price)
                cost = position_size * current_price * (1 + self.commission)

                if cost <= capital:
                    position = position_size
                    entry_price = current_price
                    entry_time = current_time
                    capital -= cost
                    strategy.update_position(1, entry_price)

            # Record equity
            current_equity = capital + (position * current_price if position > 0 else 0)
            equity_history.append({
                "timestamp": current_time,
                "equity": current_equity
            })

        # Close any open position at end
        if position > 0:
            final_price = data["close"].iloc[-1]
            exit_value = position * final_price * (1 - self.commission)
            pnl = exit_value - (position * entry_price)

            trades.append(Trade(
                entry_time=entry_time,
                entry_price=entry_price,
                size=position,
                side="buy",
                exit_time=data.index[-1],
                exit_price=final_price,
                pnl=pnl,
                pnl_pct=(final_price - entry_price) / entry_price,
                exit_reason="end_of_backtest"
            ))
            capital += exit_value

        # Calculate metrics
        result = self._calculate_metrics(trades, equity_history)
        logger.info(f"Backtest completed: {result.total_trades} trades, "
                   f"Return: {result.total_return:.2%}, Sharpe: {result.sharpe_ratio:.2f}")

        return result

    def _calculate_metrics(
        self,
        trades: List[Trade],
        equity_history: List[dict]
    ) -> BacktestResult:
        """Calculate backtest performance metrics."""

        result = BacktestResult()
        result.trades = trades
        result.total_trades = len(trades)

        if not trades:
            return result

        # Create equity curve
        equity_df = pd.DataFrame(equity_history)
        if not equity_df.empty:
            equity_df.set_index("timestamp", inplace=True)
            result.equity_curve = equity_df["equity"]

        # Win/Loss statistics
        winning = [t for t in trades if t.pnl > 0]
        losing = [t for t in trades if t.pnl <= 0]

        result.winning_trades = len(winning)
        result.losing_trades = len(losing)
        result.win_rate = len(winning) / len(trades) if trades else 0

        # Average win/loss
        result.avg_win = np.mean([t.pnl for t in winning]) if winning else 0
        result.avg_loss = np.mean([t.pnl for t in losing]) if losing else 0

        # Profit factor
        gross_profit = sum(t.pnl for t in winning) if winning else 0
        gross_loss = abs(sum(t.pnl for t in losing)) if losing else 1
        result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0

        # Total return
        final_equity = result.equity_curve.iloc[-1] if not result.equity_curve.empty else self.initial_capital
        result.total_return = (final_equity - self.initial_capital) / self.initial_capital

        # Sharpe ratio (assuming daily returns)
        if not result.equity_curve.empty and len(result.equity_curve) > 1:
            returns = result.equity_curve.pct_change().dropna()
            if len(returns) > 0 and returns.std() > 0:
                result.sharpe_ratio = np.sqrt(252) * returns.mean() / returns.std()

        # Maximum drawdown
        if not result.equity_curve.empty:
            rolling_max = result.equity_curve.expanding().max()
            drawdown = (result.equity_curve - rolling_max) / rolling_max
            result.max_drawdown = drawdown.min()

        return result

    def plot_results(self, result: BacktestResult, save_path: Optional[str] = None):
        """
        Plot backtest results.

        Args:
            result: BacktestResult to visualize
            save_path: Optional path to save the plot
        """
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))

        # Equity curve
        if not result.equity_curve.empty:
            axes[0, 0].plot(result.equity_curve)
            axes[0, 0].set_title("Equity Curve")
            axes[0, 0].set_xlabel("Date")
            axes[0, 0].set_ylabel("Equity ($)")
            axes[0, 0].grid(True)

        # Drawdown
        if not result.equity_curve.empty:
            rolling_max = result.equity_curve.expanding().max()
            drawdown = (result.equity_curve - rolling_max) / rolling_max * 100
            axes[0, 1].fill_between(drawdown.index, drawdown, 0, alpha=0.3, color="red")
            axes[0, 1].set_title("Drawdown (%)")
            axes[0, 1].set_xlabel("Date")
            axes[0, 1].grid(True)

        # Trade PnL distribution
        pnls = [t.pnl for t in result.trades]
        if pnls:
            axes[1, 0].hist(pnls, bins=30, edgecolor="black", alpha=0.7)
            axes[1, 0].axvline(x=0, color="red", linestyle="--")
            axes[1, 0].set_title("Trade PnL Distribution")
            axes[1, 0].set_xlabel("PnL ($)")
            axes[1, 0].set_ylabel("Frequency")

        # Summary statistics
        stats_text = f"""
        Total Return: {result.total_return:.2%}
        Sharpe Ratio: {result.sharpe_ratio:.2f}
        Max Drawdown: {result.max_drawdown:.2%}
        Win Rate: {result.win_rate:.2%}
        Profit Factor: {result.profit_factor:.2f}
        Total Trades: {result.total_trades}
        Avg Win: ${result.avg_win:.2f}
        Avg Loss: ${result.avg_loss:.2f}
        """
        axes[1, 1].text(0.1, 0.5, stats_text, fontsize=12, family="monospace",
                       transform=axes[1, 1].transAxes, verticalalignment="center")
        axes[1, 1].axis("off")
        axes[1, 1].set_title("Performance Summary")

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150)
            logger.info(f"Plot saved to {save_path}")

        plt.show()

    def generate_report(self, result: BacktestResult) -> str:
        """Generate a text report of backtest results."""
        report = f"""
================================================================================
                           BACKTEST REPORT
================================================================================

PERFORMANCE METRICS
-------------------
Total Return:        {result.total_return:>10.2%}
Sharpe Ratio:        {result.sharpe_ratio:>10.2f}
Max Drawdown:        {result.max_drawdown:>10.2%}
Profit Factor:       {result.profit_factor:>10.2f}

TRADE STATISTICS
----------------
Total Trades:        {result.total_trades:>10}
Winning Trades:      {result.winning_trades:>10}
Losing Trades:       {result.losing_trades:>10}
Win Rate:            {result.win_rate:>10.2%}
Average Win:         ${result.avg_win:>9.2f}
Average Loss:        ${result.avg_loss:>9.2f}

RECENT TRADES
-------------
"""
        # Add last 10 trades
        for trade in result.trades[-10:]:
            report += f"{trade.entry_time.strftime('%Y-%m-%d')} | "
            report += f"{trade.side:>4} | "
            report += f"Entry: ${trade.entry_price:.2f} | "
            report += f"Exit: ${trade.exit_price:.2f} | " if trade.exit_price else ""
            report += f"PnL: ${trade.pnl:>8.2f} | "
            report += f"{trade.exit_reason}\n"

        report += "=" * 80

        return report
